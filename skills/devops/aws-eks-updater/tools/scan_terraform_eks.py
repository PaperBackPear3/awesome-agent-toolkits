#!/usr/bin/env python3
"""scan_terraform_eks.py — extract declared EKS and in-cluster versions from a Terraform root.

Handles these declaration styles:
  1. Raw `aws_eks_cluster` / `aws_eks_node_group` / `aws_eks_addon` resources.
  2. Module calls whose source references EKS (e.g. `terraform-aws-modules/eks/aws`,
     a private registry module, or a local `./modules/eks` path). Extracts:
       - cluster_version / kubernetes_version
       - cluster_addons as a map (`{ coredns = {...} }`) or a list of objects
         (`[{ name = "coredns", version = "..." }]`)
       - node groups as maps or lists (`eks_managed_node_groups`, `node_groups`, ...)
       - fargate_profiles
  3. Helm charts: `helm_release` resources and module calls that wrap a chart
     (`helm_chart` / `helm_version` / `chart_version` inputs). Unpinned charts are flagged;
     for a wrapped chart with no version input, the module's variable default is reported.
  4. AMI SSM lookups pinned to a Kubernetes minor
     (`/aws/service/bottlerocket/aws-k8s-1.34/...`, `/aws/service/eks/optimized-ami/1.34/...`),
     which must be bumped on every control-plane hop.

It also checks whether the module that owns the node groups actually wires a Kubernetes
version into `aws_eks_node_group` (`version` / `release_version`). When it does not,
Terraform never moves node groups to a new minor and the plan needs out-of-band steps.

Blocks are found with a brace matcher that skips strings, comments and heredocs, so
nesting depth does not matter. Every finding carries the file and line it came from.

Output is JSON for further enrichment by the skill via the Terraform MCP.

Usage:
    ./scan_terraform_eks.py <terraform-root-dir>
    ./scan_terraform_eks.py --root-dir <terraform-root-dir>
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


# Public/private registry source patterns that indicate an EKS module.
EKS_HINT_RE = re.compile(r"(?i)(^|[/.-])eks([/.-]|$)")

# Module inputs that hold node group definitions, across common EKS modules.
NODE_GROUP_INPUTS = ("eks_managed_node_groups", "node_groups", "managed_node_groups")
SELF_MANAGED_INPUTS = ("self_managed_node_groups",)

# Module inputs that identify a wrapped Helm chart. Version inputs may carry a
# prefix when one module wraps several charts (`falconsensor_helmversion`).
HELM_CHART_INPUTS = ("helm_chart", "chart_name")
HELM_VERSION_INPUTS = ("helm_version", "chart_version")
HELM_VERSION_KEY_RE = re.compile(r"^(?:(.+?)_)?(?:helm_?version|chart_?version)$")
HELM_REPO_INPUTS = ("helm_repository", "chart_repository")

SSM_K8S_RE = re.compile(r"aws-k8s-(\d+\.\d+)|/eks/optimized-ami/(\d+\.\d+)/")


# ── HCL scanning helpers ──────────────────────────────────────────────────────

def _skip_string(text: str, i: int) -> int:
    """i points at an opening quote; return the index after the closing quote."""
    i += 1
    depth = 0  # depth of ${ ... } / %{ ... } template sequences inside the string
    while i < len(text):
        c = text[i]
        if c == "\\":
            i += 2
            continue
        if depth == 0 and c == '"':
            return i + 1
        if text.startswith("${", i) or text.startswith("%{", i):
            depth += 1
            i += 2
            continue
        if depth and c == "}":
            depth -= 1
        elif depth and c == '"':
            i = _skip_string(text, i)
            continue
        i += 1
    return i


def _skip_heredoc(text: str, i: int) -> int | None:
    """i points at '<<'; return the index after the heredoc, or None if it is not one."""
    m = re.match(r"<<-?([A-Za-z_][A-Za-z0-9_]*)[ \t]*\n", text[i:])
    if not m:
        return None
    end = re.compile(rf"^[ \t]*{re.escape(m.group(1))}[ \t]*$", re.MULTILINE)
    e = end.search(text, i + m.end())
    return e.end() if e else len(text)


def skip_noise(text: str, i: int) -> int | None:
    """If a string, comment or heredoc starts at i, return the index after it."""
    c = text[i]
    if c == '"':
        return _skip_string(text, i)
    if c == "#" or text.startswith("//", i):
        nl = text.find("\n", i)
        return len(text) if nl == -1 else nl
    if text.startswith("/*", i):
        e = text.find("*/", i + 2)
        return len(text) if e == -1 else e + 2
    if text.startswith("<<", i):
        return _skip_heredoc(text, i)
    return None


def match_close(text: str, open_idx: int) -> int:
    """open_idx points at '{' or '['; return the index of the matching closer."""
    pairs = {"{": "}", "[": "]"}
    stack = [pairs[text[open_idx]]]
    i = open_idx + 1
    while i < len(text) and stack:
        nxt = skip_noise(text, i)
        if nxt is not None:
            i = nxt
            continue
        c = text[i]
        if c in pairs:
            stack.append(pairs[c])
        elif c == stack[-1]:
            stack.pop()
            if not stack:
                return i
        i += 1
    return len(text) - 1


def line_of(text: str, idx: int) -> int:
    return text.count("\n", 0, idx) + 1


def strip_comments(text: str) -> str:
    """Blank out comments (keeping offsets and newlines) so commented-out code is ignored."""
    out = list(text)
    i = 0
    while i < len(text):
        c = text[i]
        if c == '"':
            i = _skip_string(text, i)
            continue
        if text.startswith("<<", i):
            j = _skip_heredoc(text, i)
            if j is not None:
                i = j
                continue
        if c == "#" or text.startswith("//", i) or text.startswith("/*", i):
            j = skip_noise(text, i) or i + 1
            for k in range(i, j):
                if out[k] != "\n":
                    out[k] = " "
            i = j
            continue
        i += 1
    return "".join(out)


def find_blocks(text: str, head_re: str) -> list[tuple[tuple[str, ...], str, int]]:
    """Find blocks `<head> {` where head_re matches the header.

    Returns (regex groups, body, start offset) for every match, at any depth."""
    out = []
    for m in re.finditer(head_re + r"\s*\{", text):
        open_idx = m.end() - 1
        close = match_close(text, open_idx)
        out.append((m.groups(), text[open_idx + 1:close], m.start()))
    return out


def top_level_attrs(body: str) -> dict[str, str]:
    """Attributes assigned directly in this body (not inside nested blocks).

    String values are unquoted; maps/lists are returned with their brackets;
    other expressions are returned raw (rest of the line)."""
    attrs: dict[str, str] = {}
    i, depth, at_line_start = 0, 0, True
    while i < len(body):
        nxt = skip_noise(body, i)
        if nxt is not None:
            at_line_start = at_line_start and body[i] != '"'
            i = nxt
            continue
        c = body[i]
        if c == "\n":
            at_line_start = True
            i += 1
            continue
        if depth == 0 and at_line_start and not c.isspace():
            m = re.match(r'"?([A-Za-z_][A-Za-z0-9_-]*)"?\s*=(?!=)[ \t]*', body[i:])
            if m:
                key = m.group(1)
                vstart = i + m.end()
                if vstart < len(body) and body[vstart] == '"':
                    vend = _skip_string(body, vstart)
                    attrs[key] = body[vstart + 1:vend - 1]
                    i = vend
                elif vstart < len(body) and body[vstart] in "{[":
                    vend = match_close(body, vstart)
                    attrs[key] = body[vstart:vend + 1]
                    i = vend + 1
                else:
                    nl = body.find("\n", vstart)
                    nl = len(body) if nl == -1 else nl
                    attrs[key] = body[vstart:nl].strip()
                    i = nl
                at_line_start = False
                continue
        if c in "{[(":
            depth += 1
        elif c in "}])":
            depth -= 1
        if not c.isspace():
            at_line_start = False
        i += 1
    return attrs


def collection_items(value: str) -> list[tuple[str | None, str]]:
    """Split a map `{ label = {..} }` or a list `[ {..}, {..} ]` into (label, body) items."""
    value = (value or "").strip()
    items: list[tuple[str | None, str]] = []
    if not value or value[0] not in "{[":
        return items
    inner = value[1:-1]
    if value[0] == "[":
        i = 0
        while i < len(inner):
            nxt = skip_noise(inner, i)
            if nxt is not None:
                i = nxt
                continue
            if inner[i] == "{":
                close = match_close(inner, i)
                items.append((None, inner[i + 1:close]))
                i = close + 1
                continue
            i += 1
        return items
    for key, val in top_level_attrs(inner).items():
        if val.startswith("{"):
            items.append((key, val[1:-1]))
    return items


def nested_labelled(body: str, kind: str) -> list[tuple[str, str]]:
    """Blocks written as  kind "label" { ... }  inside body."""
    return [(g[0], b) for g, b, _ in find_blocks(body, rf'(?m)^[ \t]*{re.escape(kind)}\s+"([^"]+)"')]


def unquote(v: str | None) -> str | None:
    if v is None:
        return None
    v = v.strip()
    return None if v in ("", "null") else v


# ── Module source handling ────────────────────────────────────────────────────

def _classify_source(source: str) -> str:
    """Best-effort classification of a module source string."""
    s = source.strip()
    if s.startswith((".", "/")):
        return "local"
    if s.startswith(("git::", "git@", "https://github.com", "github.com")):
        return "git"
    if s.count("/") == 2:  # public Terraform Registry: namespace/name/provider
        return "public_registry"
    if "/" in s and "." in s.split("/", 1)[0]:  # host/org/name/provider — private registry
        return "private_registry"
    return "unknown"


def _investigation_hint(source: str, root: Path) -> dict:
    """How the skill should look up the module's schema/versions."""
    kind = _classify_source(source)
    base = {"source": source, "kind": kind}

    if kind == "local":
        local_path = (root / source).resolve() if not Path(source).is_absolute() else Path(source)
        base["local_path"] = str(local_path)
        base["next_step"] = (
            f"Re-run scan_terraform_eks.py on {local_path} to inspect the local module's resources."
        )
    elif kind == "public_registry":
        base["next_step"] = (
            f"Use Terraform MCP: get_latest_module_version + get_module_details for '{source}' "
            "to confirm the latest version and locate variables that control K8s/addon versions."
        )
    elif kind == "private_registry":
        base["next_step"] = (
            f"Use Terraform MCP: get_private_module_details for '{source}' (requires HCP "
            "Terraform/TFE token). Falls back to search_private_modules if details fail."
        )
    elif kind == "git":
        base["next_step"] = (
            "Module is sourced from Git. Resolve the ref/tag in the source URL and inspect the "
            "repo on GitHub via the GitHub MCP if needed."
        )
    else:
        base["next_step"] = "Unknown source kind — ask the user how to inspect this module."

    return base


def resolve_module_dir(root: Path, mod_name: str, source: str) -> Path | None:
    """Local path for a module's code: the source itself, or the copy `terraform init` cached."""
    if _classify_source(source) == "local":
        p = (root / source).resolve()
        return p if p.is_dir() else None
    manifest = root / ".terraform" / "modules" / "modules.json"
    try:
        for m in json.loads(manifest.read_text()).get("Modules", []):
            if m.get("Key") == mod_name and m.get("Dir"):
                p = (root / m["Dir"]).resolve()
                return p if p.is_dir() else None
    except (OSError, ValueError):
        pass
    p = root / ".terraform" / "modules" / mod_name
    return p if p.is_dir() else None


def read_module(mod_dir: Path) -> str:
    text = ""
    for f in sorted(mod_dir.glob("*.tf")):
        try:
            text += "\n" + strip_comments(f.read_text())
        except OSError:
            continue
    return text


def module_variable_default(mod_text: str, name: str) -> str | None:
    for g, b, _ in find_blocks(mod_text, r'variable\s+"([^"]+)"'):
        if g[0] == name:
            return unquote(top_level_attrs(b).get("default"))
    return None


def module_node_group_wiring(mod_text: str, mod_dir: Path) -> dict:
    """Does the module pass a Kubernetes version to its aws_eks_node_group resources?"""
    groups = find_blocks(mod_text, r'resource\s+"aws_eks_node_group"\s+"([^"]+)"')
    if not groups:
        return {"module_dir": str(mod_dir), "node_group_resources": 0}
    accepted: list[str] = []
    for g, b, _ in find_blocks(mod_text, r'variable\s+"([^"]+)"'):
        if g[0] in NODE_GROUP_INPUTS:
            accepted = [k for k in ("version", "release_version")
                        if re.search(rf"(?m)^\s*{k}\s*=", top_level_attrs(b).get("type", ""))]
    return {
        "module_dir": str(mod_dir),
        "node_group_resources": len(groups),
        "sets_version": all("version" in top_level_attrs(b) for _, b, _ in groups),
        "sets_release_version": all("release_version" in top_level_attrs(b) for _, b, _ in groups),
        "node_group_input_accepts": accepted,
    }


# ── Scan ──────────────────────────────────────────────────────────────────────

def scan(root: Path) -> dict:
    files: list[tuple[str, str]] = []
    for tf_file in sorted(root.rglob("*.tf")):
        if ".terraform" in tf_file.parts:
            continue
        try:
            files.append((str(tf_file.relative_to(root)), strip_comments(tf_file.read_text())))
        except OSError:
            continue

    result: dict = {
        "scanned_root": str(root),
        "tf_files_scanned": len(files),
        "clusters": [],
        "node_groups": [],
        "addons": [],
        "eks_module_calls": [],
        "helm_releases": [],
        "ami_ssm_parameters": [],
        "investigation_hints": [],
        "warnings": [],
    }
    warnings = result["warnings"]

    for rel, text in files:
        def loc(off: int) -> str:
            return f"{rel}:{line_of(text, off)}"

        # ── Raw aws_eks_* resources ───────────────────────────────────────────
        for g, body, off in find_blocks(text, r'resource\s+"aws_eks_cluster"\s+"([^"]+)"'):
            a = top_level_attrs(body)
            result["clusters"].append({
                "name": g[0], "cluster_name": a.get("name"), "version": a.get("version"),
                "location": loc(off),
            })

        for g, body, off in find_blocks(text, r'resource\s+"aws_eks_node_group"\s+"([^"]+)"'):
            a = top_level_attrs(body)
            ng = {
                "name": g[0], "version": a.get("version"), "ami_type": a.get("ami_type"),
                "release_version": a.get("release_version"), "location": loc(off),
            }
            result["node_groups"].append(ng)
            if not ng["version"]:
                warnings.append({
                    "type": "node_group_version_not_managed",
                    "where": f"aws_eks_node_group.{g[0]} ({loc(off)})",
                    "message": "No `version` set: Terraform will not move this node group to a "
                               "new Kubernetes minor. Plan an explicit node group version step.",
                })

        for g, body, off in find_blocks(text, r'resource\s+"aws_eks_addon"\s+"([^"]+)"'):
            a = top_level_attrs(body)
            result["addons"].append({
                "name": g[0], "addon_name": a.get("addon_name"),
                "addon_version": a.get("addon_version"), "location": loc(off),
            })

        # ── Helm releases ─────────────────────────────────────────────────────
        for g, body, off in find_blocks(text, r'resource\s+"helm_release"\s+"([^"]+)"'):
            a = top_level_attrs(body)
            version = unquote(a.get("version"))
            result["helm_releases"].append({
                "name": g[0], "kind": "helm_release", "chart": a.get("chart"),
                "repository": a.get("repository"), "version": version,
                "namespace": a.get("namespace"), "pinned": bool(version), "location": loc(off),
            })

        # ── AMI SSM parameters pinned to a K8s minor ──────────────────────────
        for g, body, off in find_blocks(text, r'data\s+"aws_ssm_parameter"\s+"([^"]+)"'):
            name = top_level_attrs(body).get("name") or ""
            m = SSM_K8S_RE.search(name)
            if m:
                result["ami_ssm_parameters"].append({
                    "name": g[0], "parameter": name, "k8s_version": m.group(1) or m.group(2),
                    "location": loc(off),
                })

        # ── Module calls ──────────────────────────────────────────────────────
        for g, body, off in find_blocks(text, r'module\s+"([^"]+)"'):
            mod_name = g[0]
            a = top_level_attrs(body)
            source = a.get("source") or ""
            mod_dir = resolve_module_dir(root, mod_name, source) if source else None
            mod_text = read_module(mod_dir) if mod_dir else ""

            # Module-wrapped Helm chart: explicit chart inputs, or a module whose
            # code is a helm_release driven by a chart version variable.
            chart = next((a[k] for k in HELM_CHART_INPUTS if k in a), None)
            ver_key = next((k for k in HELM_VERSION_INPUTS if k in a), None)
            mod_chart_var = None
            if mod_text and re.search(r'resource\s+"helm_release"', mod_text):
                mod_chart_var = next((k for k in HELM_VERSION_INPUTS
                                      if re.search(rf'variable\s+"{k}"', mod_text)), None)
            prefixed = [(m.group(1), k) for k in a
                        if (m := HELM_VERSION_KEY_RE.match(k)) and m.group(1)]
            for prefix, k in prefixed:
                version = unquote(a.get(k))
                result["helm_releases"].append({
                    "name": f"{mod_name}.{prefix}", "kind": "module", "module_source": source,
                    "module_version": a.get("version"), "chart": f"{prefix} (via {k})",
                    "repository": None, "version": version,
                    "version_from": "input" if version else None,
                    "pinned": bool(version), "location": loc(off),
                })
            if not prefixed and (chart or ver_key or mod_chart_var):
                version = unquote(a.get(ver_key)) if ver_key else None
                version_from = "input" if version else None
                if not version and mod_chart_var:
                    version = module_variable_default(mod_text, ver_key or mod_chart_var)
                    version_from = "module default" if version else None
                if not chart and mod_text:
                    hr = find_blocks(mod_text, r'resource\s+"helm_release"\s+"[^"]+"')
                    chart = top_level_attrs(hr[0][1]).get("chart") if hr else None
                result["helm_releases"].append({
                    "name": mod_name, "kind": "module", "module_source": source,
                    "module_version": a.get("version"), "chart": chart,
                    "repository": next((a[k] for k in HELM_REPO_INPUTS if k in a), None),
                    "version": version, "version_from": version_from,
                    "pinned": version_from == "input", "location": loc(off),
                })

            if not source or not EKS_HINT_RE.search(source):
                continue

            call: dict = {
                "name": mod_name,
                "source": source,
                "version": a.get("version"),
                "cluster_version": a.get("cluster_version") or a.get("kubernetes_version"),
                "cluster_addons": [],
                "managed_node_groups": [],
                "self_managed_node_groups": [],
                "fargate_profiles": [],
                "kind": _classify_source(source),
                "location": loc(off),
            }

            addons_val = a.get("cluster_addons") or a.get("addons") or ""
            for label, inner in collection_items(addons_val) + nested_labelled(body, "cluster_addons"):
                ia = top_level_attrs(inner)
                call["cluster_addons"].append({
                    "name": label or ia.get("name"),
                    "addon_version": ia.get("addon_version") or ia.get("version"),
                    "most_recent": ia.get("most_recent"),
                })

            for key in NODE_GROUP_INPUTS:
                for label, inner in collection_items(a.get(key, "")):
                    ia = top_level_attrs(inner)
                    call["managed_node_groups"].append({
                        "name": label or ia.get("name"),
                        "input": key,
                        "ami_type": ia.get("ami_type"),
                        "version": ia.get("version") or ia.get("cluster_version"),
                        "release_version": ia.get("release_version"),
                    })
            for key in SELF_MANAGED_INPUTS:
                for label, inner in collection_items(a.get(key, "")):
                    ia = top_level_attrs(inner)
                    call["self_managed_node_groups"].append({
                        "name": label or ia.get("name"), "ami_id": ia.get("ami_id"),
                        "version": ia.get("version"),
                    })
            for label, inner in collection_items(a.get("fargate_profiles", "")):
                call["fargate_profiles"].append({"name": label or top_level_attrs(inner).get("name")})

            call["investigation"] = _investigation_hint(source, root)
            result["investigation_hints"].append(call["investigation"])

            if mod_dir:
                wiring = module_node_group_wiring(mod_text, mod_dir)
                call["node_group_wiring"] = wiring
                if wiring.get("node_group_resources") and call["managed_node_groups"]:
                    if not wiring.get("sets_version"):
                        warnings.append({
                            "type": "node_group_version_not_managed",
                            "where": f"module.{mod_name} ({call['location']})",
                            "message": "The module's aws_eks_node_group does not set `version`: "
                                       "node groups stay on their current minor after a "
                                       "control-plane bump. Plan `aws eks update-nodegroup-version` "
                                       "steps, or extend the module.",
                        })
                    accepted = set(wiring.get("node_group_input_accepts", []))
                    for ng in call["managed_node_groups"]:
                        for k in ("version", "release_version"):
                            if ng.get(k) and k not in accepted:
                                warnings.append({
                                    "type": "node_group_input_dropped",
                                    "where": f"module.{mod_name} node group '{ng['name']}'",
                                    "message": f"`{k}` is set, but the module's node group input "
                                               "type has no such field, so Terraform silently "
                                               "drops it.",
                                })
            else:
                call["node_group_wiring"] = None
                result["investigation_hints"].append({
                    "source": source,
                    "next_step": f"Module code for '{mod_name}' is not available locally (run "
                                 "`terraform init`, or read it via the Terraform MCP) — cannot "
                                 "check whether node group versions are managed.",
                })

            result["eks_module_calls"].append(call)

    # ── Unpinned charts ───────────────────────────────────────────────────────
    for hr in result["helm_releases"]:
        if hr["pinned"]:
            continue
        if hr.get("version_from") == "module default":
            msg = (f"Chart '{hr.get('chart')}' follows the module default ({hr['version']}): "
                   "it changes whenever the module version changes. Pin it explicitly.")
        else:
            msg = (f"Chart '{hr.get('chart')}' has no pinned version: every plan/apply may "
                   "install whatever is latest. Pin it before upgrading the cluster.")
        warnings.append({"type": "helm_chart_unpinned",
                         "where": f"{hr['name']} ({hr['location']})", "message": msg})

    # ── Addons declared in two places (standalone + module-managed) ───────────
    standalone = {a.get("addon_name"): f"aws_eks_addon.{a['name']}"
                  for a in result["addons"] if a.get("addon_name")}
    module_addons: dict[str, list[str]] = {}
    for call in result["eks_module_calls"]:
        for ca in call.get("cluster_addons", []):
            if ca.get("name"):
                module_addons.setdefault(ca["name"], []).append(
                    f"module.{call['name']}.cluster_addons"
                )
    for addon_name, src in standalone.items():
        if addon_name in module_addons:
            warnings.append({
                "type": "addon_double_management",
                "addon": addon_name,
                "declared_in": [src, *module_addons[addon_name]],
                "message": (
                    f"'{addon_name}' is declared both as a standalone aws_eks_addon "
                    "and inside a module's cluster_addons. Terraform will flip it on "
                    "every apply. Remove one declaration."
                ),
            })

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("root", nargs="?", help="Terraform root directory")
    parser.add_argument("--root-dir", dest="root_flag", help="Terraform root directory")
    args = parser.parse_args()
    root_arg = args.root_flag or args.root
    if not root_arg:
        parser.error("a Terraform root directory is required")
    root = Path(root_arg)
    if not root.is_dir():
        print(f"Directory not found: {root}", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(scan(root), indent=2))


if __name__ == "__main__":
    main()
