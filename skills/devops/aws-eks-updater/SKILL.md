---
disable-model-invocation: true
name: aws-eks-updater
description: >
  Use when an EKS cluster version, Kubernetes version, or any cluster component needs to be bumped — including managed add-ons (vpc-cni, coredns, kube-proxy, ebs-csi, efs-csi, pod-identity-agent, adot, cloudwatch-observability), node groups and Helm releases, for one cluster or several environments (dev/test/prod/DR). Trigger even on vague upgrade intent: "update my cluster", "bump k8s version", "upgrade coredns", "new EKS release is out", "we must stay one version behind", or any time the user pastes Terraform with aws_eks_*, an eksctl config, or a helmfile/Chart.yaml and asks what needs changing. The skill inventories Terraform and live state, picks a target under the version policy, reads changelogs, and plans the upgrade in rounds with a ledger of what is done and what comes next; it edits files locally one component at a time, without committing, pushing, or applying. Do NOT use for AKS (use azure-aks-updater), for application image or manifest rollouts, or for building a new cluster from scratch.

version: 3
recommends_mcp:
  - aws-mcp      # AWS API reads (fallback: aws CLI)
  - terraform    # private/public module details, HCP Terraform workspace runs
  - github       # release notes (fallback: public API, gh, project docs)
optional_mcp:
  - devops-core  # interactive inventory/plan/summary views
tags: [aws, eks, kubernetes, terraform, helm]
---

# EKS Cluster Updater

You plan and carry out EKS upgrades in **rounds**. Each round ends with a short report
to the user and an updated ledger, so the work can stop and resume across days,
sessions and harnesses.

**Hard rules and the reasoning behind them:**

- Don't run `git commit`, `git push`, `kubectl apply`, `helm upgrade`, `terraform apply`,
  `aws eks update-*` or any other mutating command without explicit user instruction —
  the user owns the change-control boundary and partial cluster upgrades are painful to
  roll back.
- Change **one component in one environment at a time**, then hand off for review and
  test — keeps blast radius small and rollback granular.
- Prefer the previous stable version over the absolute latest (unless they're equal) —
  fresh releases often regress.
- Never assume the environment or account — wrong-account changes are the most common
  high-impact incident in this work. Confirm identity per profile before reading, and
  ask when ambiguous.

## Way of working

These are habits, not ceremony. Use what the harness already gives you.

- **Checkpoints.** Stop and report at the end of each phase, before and after every
  control-plane bump, before promoting to the next environment, and whenever something
  unexpected changes the plan (a blocker, drift, a deadline). A report is a few lines:
  what was done, what was found, what is next and what it requires, and the decision
  you need from the user. Do not run through checkpoints on your own.
- **Ledger.** Keep the plan and its progress in one Markdown file, started from
  `assets/ledger-template.md`: one row per change with its round, environment, method,
  requirements, status, and — once done — the date, how it was done and the evidence
  (PR, run id, command output). Update it at every checkpoint. It is the record that
  survives the session; an in-session todo or task tool, if the harness has one, is for
  the steps of the current round only — don't duplicate the ledger into it.
- **Where the ledger lives.** Ask the user once. Default: `eks-upgrade-<target>.md` next
  to the Terraform roots, left uncommitted. If the user keeps a knowledge base with its
  own skill or conventions, follow those instead (for example, record decisions and
  verified procedures there and link the ledger), rather than inventing a parallel
  format.
- **Resuming.** If a ledger exists, read it first, re-check the live state of the rows
  marked `in progress` or `done` since the last checkpoint, then continue from the
  current round. The ledger records intent; the cluster is the truth.
- **Commands the user runs.** When a step needs the user to run something (an
  out-of-band `aws eks` command, a login, a `terraform` or `kubectl` check), print each
  command on its own in a fenced block, ready to copy, with the profile, region and
  cluster written out (no placeholders left to fill), and one line above it saying what
  it does and whether it changes anything. Number them when order matters, and say what
  output to expect or send back.
- **Pull requests.** Whenever a change goes through PRs, list every PR with its full
  URL and the **merge order** (with the reason when it is not obvious, e.g. "after the
  test apply has soaked"), in the checkpoint report and in the ledger. Never refer to
  a PR only by number or branch name.
- **Use what you know.** You know the AWS CLI/API, kubectl, helm and Terraform. The only
  bundled tool is the Terraform scanner, because it reads many files deterministically
  and catches module wiring problems; everything else is ordinary commands.

## Defaults

Confirm these once in Phase 0 and record them in the ledger header.

| Setting | Default |
|---|---|
| Version policy | One minor below the newest standard-support version (N-1) |
| Hops | One minor at a time; a full round per hop |
| Promotion order | dev → test → prod → dr (only those that exist) |
| Soak between environments | 2 working days |
| Add-on target | Default build for each hop's minor |
| Chart target | Newest patch of the previous minor line, if it supports the target minor |

---

## PHASE 0 — Context

1. **Environments.** Build the environment table: name, account and profile, region,
   cluster, Terraform root, how Terraform runs (local, HCP Terraform workspace, CI).
   Several roots are normal (one per environment, a DR region). Ask for anything you
   cannot find in the repo.
2. **Access.** Prefer the AWS MCP (API calls with an explicit profile); otherwise the
   `aws` CLI. Check the caller identity for every profile and stop if a profile points
   at an unexpected account. kubectl and helm are only needed for live Helm and PDB
   checks and for execution.
3. **Terraform runs.** For HCP Terraform / TFE roots, read each workspace's latest runs
   (Terraform MCP). Errored or stuck runs are pre-work: an upgrade PR cannot land behind
   them.
4. **Ledger.** Create it (or resume it), with the environment table and the defaults.

Checkpoint: echo the environment table and defaults; get confirmation.

## PHASE 1 — Inventory and drift (per environment)

- **Terraform.** `python3 tools/scan_terraform_eks.py <tf-root>` per root. It returns the
  cluster version, add-ons, node groups, Helm charts (resources and module-wrapped),
  AMI SSM parameters pinned to a minor, and warnings: node group versions the module
  never sets, inputs the module silently drops, unpinned charts, add-ons declared twice.
  Module code is read from local paths or the `terraform init` cache; when it is not
  there, follow `investigation_hints` (Terraform MCP `get_private_module_details` /
  `get_module_details`, or the Git source).
- **Live.** `DescribeCluster` (version, `upgradePolicy`, Auto Mode `computeConfig`),
  `ListAddons` / `DescribeAddon`, `ListNodegroups` / `DescribeNodegroup` (`version`,
  `releaseVersion`, launch template), Helm releases (`helm list -A`) when you have a
  kube context.
- **Drift.** One row per add-on, chart and node group:
  `in-sync` · `declared-ahead` · `installed-ahead` · `unmanaged` (installed, not
  declared) · `missing` (declared, not installed). For each `unmanaged` item, ask:
  adopt it into Terraform, or keep moving it by CLI (and record which).
- **Readiness.** `ListInsights` / `DescribeInsight`. Record every non-passing insight
  with its Kubernetes version, the deprecated APIs and the client user agents.

Checkpoint: one consolidated table per environment, drift and warnings first.

## PHASE 2 — Target and research

- **Target.** `DescribeClusterVersions` → newest standard-support version, the policy
  target, the hops from the current minor, and the end-of-standard-support date of the
  current minor (a deadline, and a cost if `upgradePolicy` is `EXTENDED`).
- **Add-ons.** `describe-addon-versions --kubernetes-version <minor>` for **each** hop.
- **Charts.** For each chart: latest stable, recommended, whether it supports each
  hop's minor, and the breaking changes between current and recommended — see
  `references/changelog-review.md`. A chart that does not support the next minor is a
  pre-requisite of that hop.
- **Platform changes.** Kubernetes notes for each hop's minor and, on Auto Mode, the
  Auto Mode change log (some changes are dated, not versioned) — see
  `references/eks-compatibility.md`.

Decision per package: `auto-plan` (no breaking signals, compatible, notes read) ·
`manual-review` (breaking signals, a major jump, multi-hop, or notes not found) ·
`blocked` (no compatible version). Record the reason in one line.

## PHASE 3 — Plan in rounds

Write the plan into the ledger:

- **Round 0 — pre-work, all environments:** errored Terraform runs, drift decisions,
  pins for unpinned charts, node groups out of skew, chart bumps the first hop needs,
  and any dated deadline that lands before the upgrade.
- **One round per hop**, environments in promotion order, each environment:
  control plane → node groups (including AMI SSM parameters; out-of-band
  `update-nodegroup-version` when the scanner says Terraform does not drive them) →
  `kube-proxy`, `coredns`, `vpc-cni` → other add-ons → verification (nodes Ready on the
  new minor, add-ons `ACTIVE`, insights re-read, workloads healthy) → soak.
  Chart bumps the **next** hop needs go at the end of the round.
- **Follow-ups:** findings outside the upgrade (e.g. an API removed in a later minor).

Each row names the file (or command, if out of band), the target version, the
rationale, and what it requires to start.

If the devops-core MCP is available, `eks_inventory`, `eks_plan` (approve/skip
checklist) and `eks_summary` render the same data interactively; use only the items the
user approves.

Checkpoint: present the rounds and get explicit approval before any edit.

## PHASE 4 — Execute one change at a time

For each approved row, in order:

1. Show the exact diff for the local file (or the exact command, for out-of-band
   steps — the user runs it, or you run it only on explicit instruction).
2. Edit the file and show the resulting `git diff`.
3. Hand off: "Updated `<file>`: `<package>` `<old>` → `<new>` in `<env>`. Please review,
   plan, test and commit. Reply when it is applied and I'll verify it and move on."
4. When the user confirms, verify the live state, mark the row done in the ledger with
   date, method and evidence, then continue.

If a plan, apply or test fails, stop and help debug; don't move on. At the end of each
environment and each round, report at a checkpoint before promoting.

## PHASE 5 — Close

Summarise in the ledger and to the user: what changed per environment (old → new),
what was skipped or deferred and why, and the follow-ups with what they need. If the
user keeps a knowledge base, record the reusable findings there under its rules.

---

## Files in this skill

- `tools/scan_terraform_eks.py` — Terraform inventory with file:line locations and
  wiring warnings (also exposed through `tools/mcp_tools.json`)
- `tools/mcp_prompts.json` — prompt templates for drift analysis, changelog research,
  upgrade plans
- `references/eks-compatibility.md` — version policy, hop order, insights, skew, node
  groups Terraform does not move, Auto Mode, add-on and chart compatibility
- `references/changelog-review.md` — how to read release notes and what to record
- `assets/ledger-template.md` — the plan and progress ledger
