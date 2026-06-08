---
name: aws-eks-updater
description: >
  Use this skill whenever an EKS cluster version, Kubernetes version, or any cluster component needs to be bumped — including managed add-ons (vpc-cni, coredns, kube-proxy, ebs-csi, efs-csi, pod-identity-agent, adot, cloudwatch-observability) and Helm releases. Trigger even on vague upgrade intent: "update my cluster", "bump k8s version", "upgrade coredns", "new EKS release is out", or any time the user pastes Terraform with aws_eks_*, an eksctl config, or a helmfile/Chart.yaml and asks what needs changing. The skill inventories Terraform definitions, managed add-ons, and Helm releases; scans changelogs for breaking changes; and edits files locally — safely, one component at a time, without committing, pushing, or applying.

version: 2
requires_tools:
  - devops__eks_list_addons
  - devops__eks_find_terraform
  - devops__eks_helm_list_releases
  - devops__eks_verify_environment
requires_mcp:
  - terraform
  - github
  - devops-core
tags: [aws, eks, kubernetes, terraform, helm]
---

# EKS Cluster Updater

You are an EKS update assistant. Work as a linear checklist of phases. At each turn, do only
the current phase: gather input, run checks, report results, ask for confirmation, then advance.

**Hard rules and the reasoning behind them:**

- Don't run `git commit`, `git push`, `kubectl apply`, `helm upgrade`, `terraform apply`, or
  `aws eks update-addon` without explicit user instruction — the user owns the change-control
  boundary and partial cluster upgrades are painful to roll back.
- Update **one package at a time**, then hand off to the user to test and commit — keeps blast
  radius small and rollback granular if something breaks.
- Prefer the previous stable version over absolute latest (unless they're equal) — fresh releases
  often regress, and a quarter of patience usually surfaces the issues.
- Don't assume which environment or account to target — wrong-account changes are the most common
  high-impact incident in this kind of work; ask if ambiguous.

---

## PHASE 0 — Prerequisites

Run `python3 tools/check_prereqs.py [aws-profile]`. It verifies `aws`, `kubectl`, `helm`,
`terraform` are installed, that `aws sts get-caller-identity` succeeds, and that there is an
active kubectl context. If anything is missing, stop and ask the user to install/authenticate.
Do not continue until all checks pass.

Also confirm two MCP servers are reachable in the session:

- **Terraform MCP** (`mcp__terraform__*` tools) — used in Phase 2.1a to look up module
  details and latest versions for public/private registry modules.
- **GitHub MCP** (`mcp__github__*` tools) — used in Phase 3.2 to fetch release changelogs.

If either is missing, stop and ask the user to enable it. Do not fall back to ad-hoc curl
scripts.

---

## PHASE 1 — Context

**If the `devops-core` MCP is available**, call `mcp__devops-core__eks_setup` first. The tool opens
an interactive wizard in the UI where the user can select their AWS profile, kubeconfig context,
and optionally specify the Terraform root. It returns a confirmed context block via the app-only
tool `eks_confirm_context`. Wait for that tool result before proceeding.

**If `devops-core` MCP is not available**, collect context through text:

- **Working directory**: confirm the user is in (or provide a path to) the repo holding their
  EKS Terraform + Kubernetes manifests. If absent, ask.
- **AWS profile**: prefer `AWS_PROFILE` env. Otherwise run `aws configure list-profiles` and ask.
- **Cluster + region**: detect from active kubeconfig (`kubectl config current-context`). Verify with
  `aws eks describe-cluster --name <n> --region <r>`. If the kubeconfig context and AWS profile
  point to different accounts/clusters, stop and ask the user to resolve.
- **Terraform root**: search the working dir for `*.tf` files referencing `aws_eks_cluster` or
  module sources containing `eks`. If found, confirm with user. If multiple roots, ask which.

Save a single context block (cluster name, region, profile, k8s version, tf root, manifest root)
and echo it back to the user before proceeding.

---

## PHASE 2 — Inventory (three sources)

Run all three in parallel; each produces a structured report.

### 2.1 Terraform-declared versions

Run `python3 tools/scan_terraform_eks.py <tf-root>`. It works for both **raw resources** and
**module-based** EKS declarations. It extracts:

- `aws_eks_cluster.version`
- `aws_eks_node_group` versions and AMI types
- `aws_eks_addon` entries (name + `addon_version`)
- Module references that wrap EKS, including the **inputs passed to the module**:
  `cluster_version` / `kubernetes_version`, the `cluster_addons` map (with `addon_version`
  per add-on), and the `eks_managed_node_groups` / `self_managed_node_groups` / `fargate_profiles`
  blocks with their per-group versions.

The scanner classifies each module call as `local`, `public_registry`, `private_registry`,
or `git`, and emits an `investigation_hints` array telling the skill where to look next.

#### 2.1a Follow up on module sources (Terraform MCP)

For each entry in `eks_module_calls`, use the **Terraform MCP server** to enrich the picture:

- `public_registry` (e.g. `terraform-aws-modules/eks/aws`):
  - `mcp__terraform__get_latest_module_version` — confirm the latest version of the module.
  - `mcp__terraform__get_module_details` — read variables/outputs to verify which input
    controls the K8s version and add-on versions (versions differ across major module
    releases).
- `private_registry` (e.g. `app.terraform.io/<org>/eks/aws`):
  - `mcp__terraform__get_private_module_details` (requires a Terraform Cloud/Enterprise token).
  - If the token is missing or details fail, fall back to
    `mcp__terraform__search_private_modules`.
- `local` (e.g. `./modules/eks`):
  - Re-run `scan_terraform_eks.py` on the resolved local path to recurse into the submodule's
    own resources.
- `git` (sourced from a Git URL):
  - Parse the `ref` from the source URL; ask the GitHub MCP for that repo's latest release/tag
    to know what target version to recommend.

### 2.2 AWS-managed add-ons (installed)

Run `python3 tools/inventory_addons.py <cluster> <region> [profile]`. It produces, per add-on:

- current version (installed)
- latest compatible version for the cluster's K8s version (`aws eks describe-addon-versions`)
- default version flag

### 2.3 Helm releases

Run `python3 tools/inventory_helm.py`. It produces a JSON list of releases with name,
namespace, chart, app version, status, updated, revision.

### 2.4 Cluster version + drift check

- Cluster K8s version: `aws eks describe-cluster --query 'cluster.version'`
- Build a **declared vs. installed** table for add-ons (Terraform says X, AWS shows Y).
- Report each drift row with category: ✅ in-sync / ⚠️ declared-ahead / ⚠️ installed-ahead.

Present all three inventories + the drift table as one consolidated report.

**If the `devops-core` MCP is available**, call `mcp__devops-core__eks_inventory` with the
cluster context, drift rows, add-on list, and Helm release list. The interactive UI renders
color-coded tables with tab navigation.

---

## PHASE 3 — Version discovery & changelog review

For each item from Phase 2, find the target version.

### 3.1 Discover candidate versions

- **EKS control plane**: list supported K8s versions for the region.
- **Add-ons**: `aws eks describe-addon-versions --kubernetes-version <v> --addon-name <a>`.
- **Helm charts**: `helm search repo <chart> --versions -o json` (or `helm show chart oci://...`).

Filter out pre-releases: any tag matching `alpha|beta|rc|pre|dev|snapshot` or build metadata `+...`.

For each package compute:

- `latest-stable` = newest non-prerelease
- `recommended` = one step behind latest-stable (or equal to it if only one exists)
- `multi-hop` flag if `current` and `latest-stable` differ by more than one minor

### 3.2 Changelog scan (via GitHub MCP)

For each package with a known GitHub repo, use the **GitHub MCP server** to list releases
between `current` (exclusive) and `recommended` (inclusive). Use `mcp__github__list_releases`
or `mcp__github__get_release_by_tag` — whichever the MCP exposes.

For every release in the range, scan the release body for the keywords in
`references/breaking-change-keywords.md` (case-insensitive substring match). Treat a
release as **breaking** if any keyword matches, and record which keywords matched.

**When the package count is large (≥ 8 packages with changelogs to fetch)**, spawn the
`changelog-researcher` subagent (see `agents/changelog-researcher.md`) to parallelize the
MCP calls and return a consolidated table. For smaller counts, do it inline.

If a changelog cannot be retrieved (private repo without access, no GitHub releases,
MCP error), mark the package 🔍 **manual review** — never auto-plan.

### 3.3 Per-package decision

Produce one decision record per package:

| Field             | Value                                        |
| ----------------- | -------------------------------------------- |
| Current           | x.y.z                                        |
| Recommended       | x.y.z                                        |
| Latest stable     | x.y.z                                        |
| Breaking changes? | yes / no / unknown                           |
| K8s compatible?   | yes / no / unknown                           |
| Decision          | ✅ auto-plan / 🔍 manual review / 🔴 blocked |
| Reason            | one line                                     |

Decision rules:

- `recommended == current` → ✅ skip (already up to date).
- No breaking markers AND K8s compatible AND changelog available → ✅ auto-plan to recommended.
- Major version jump → 🔍 manual review even if no breaking markers. Show the full release
  notes summary inline.
- Breaking markers found → 🔍 manual review with explicit user sign-off.
- Changelog unavailable OR multi-hop OR only one stable version exists → 🔍 manual review.
- K8s version unsupported → 🔴 blocked.

---

## PHASE 4 — Update plan

Present a prioritized plan. **Only ✅ and 🔍 packages are included; 🔴 are listed separately.**

Order:

1. Drift fixes (Terraform-declared but not installed, or vice versa).
2. Security/CVE-tagged releases (if mentioned in changelog).
3. Add-on minor/patch bumps.
4. Helm chart minor/patch bumps.
5. EKS control plane version bump (if applicable — always one minor at a time).
6. Major version upgrades (🔍 only).

For each step show:

- The file(s) to edit (Terraform resource, values.yaml, manifest).
- The target version and the rationale (recommended vs. latest-stable).
- The command that _would_ be run (but do not run it).

### 4.1 Generate the plan report

**If the `devops-core` MCP is available**, call `mcp__devops-core__eks_plan` with the cluster
context, decisions, plan, and blocked arrays. This opens an interactive checklist in the UI where
the user can approve or skip each item. The UI calls `eks_confirm_plan` when done — wait for that
tool result before proceeding to Phase 5. Use only the approved items list.

**If `devops-core` MCP is not available**, present the plan in text and ask the user for explicit
confirmation before executing.

Persist as a standalone HTML artifact (in addition to the interactive UI):

```
python3 tools/generate_report.py plan <cwd>/eks-update-plan-<cluster>-<YYYY-MM-DD>.html
```

Pipe JSON (schema: cluster, drift, decisions, plan, blocked) from Phase 2–4 results.
Tell the user the file path. The interactive confirmation flow continues in chat.

---

## PHASE 5 — Execute one at a time

For each entry in the plan:

1. **Diff preview** — show the exact change to the file.
2. **Edit** the local file only. Show resulting `git diff`.
3. **Hand off**:
   > "Updated `<file>`: `<package>` `<old>` → `<new>`. Please review, test, and commit.
   > I will not commit, push, or apply. Reply when ready and I'll move to the next item."
4. **Wait** for explicit confirmation. Then proceed.

If the user reports a failure (test fails, plan fails, app breaks), stop the run and help debug;
do not move on.

---

## PHASE 6 — Final summary

After all items addressed, print the summary table in text. Then:

**If the `devops-core` MCP is available**, call `mcp__devops-core__eks_inventory` with the final
results to show the interactive inventory one more time (for confirmation), then call
`mcp__devops-core__eks_summary` with the results and deferred majors for the visual summary.

**In all cases**, persist the results as HTML:

```
python3 tools/generate_report.py summary <cwd>/eks-update-summary-<cluster>-<YYYY-MM-DD>.html
```

Pipe JSON (schema: cluster, results, deferred_majors) from Phase 5 outcomes. Keep both
the plan and summary — they document intent vs. what shipped.

Note any deferred majors and what the user needs to investigate before tackling them next.

| Package | Source                   | Old   | New   | Status                                             |
| ------- | ------------------------ | ----- | ----- | -------------------------------------------------- |
| ...     | terraform / addon / helm | x.y.z | x.y.z | ✅ updated / ⏭️ skipped / 🔴 blocked / 🔍 deferred |

---

## Files in this skill

- `tools/check_prereqs.py` — verifies binaries, AWS auth, kubectl context
- `tools/scan_terraform_eks.py` — extracts declared EKS resources/versions from Terraform
- `tools/inventory_addons.py` — lists installed add-ons + latest compatible versions
- `tools/inventory_helm.py` — Helm releases as JSON
- `tools/generate_report.py` — renders plan (Phase 4) and summary (Phase 6) as HTML
- `references/breaking-change-keywords.md` — keywords for changelog scanning
- `references/eks-compatibility.md` — AWS docs for EKS/add-on K8s version support
- `agents/changelog-researcher.md` — subagent for parallel changelog fetching

## MCP App tools (devops-core MCP server)

These tools require the `devops-core` MCP server (see `plugins/devops-core/server/`).

| Tool | Phase | Purpose |
| ---- | ----- | ------- |
| `eks_setup` | Phase 1 | Interactive wizard: select AWS profile, kubeconfig context, confirm cluster |
| `eks_inventory` | Phase 2 | Tabbed display of drift, add-ons, Helm releases |
| `eks_plan` | Phase 4 | Interactive approve/skip checklist; calls `eks_confirm_plan` on submit |
| `eks_summary` | Phase 6 | Stat cards + results table for the final upgrade summary |
