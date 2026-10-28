# EKS compatibility and upgrade rules

Facts the plan depends on. Versions move: confirm with the live API or the linked docs
before relying on any of them.

## Supported versions and the target

- `eks:DescribeClusterVersions` lists every version the region supports, with
  `versionStatus`, `endOfStandardSupportDate`, `endOfExtendedSupportDate` and the
  `defaultVersion` flag. It is the source for "latest".
- Default version policy: **one minor below the newest standard-support version**
  (N-1). Ask the user if their policy differs.
- `cluster.upgradePolicy.supportType` = `EXTENDED` means the cluster keeps running past
  end of standard support, at extended-support pricing. Put the end-of-standard-support
  date in the plan as a deadline.
- Docs: https://docs.aws.amazon.com/eks/latest/userguide/kubernetes-versions.html and the
  per-version notes at
  https://docs.aws.amazon.com/eks/latest/userguide/kubernetes-versions-standard.html

## Order inside one hop (one minor)

The control plane moves one minor at a time. For each hop:

1. Pre-flight: Upgrade Insights pass (see below), node kubelets within skew, charts
   already on versions that support the **next** minor.
2. Control plane (`cluster_version` / `version` in Terraform).
3. Node groups to the new minor: managed node groups, the AMI SSM parameters that pin
   a minor (`/aws/service/bottlerocket/aws-k8s-X.Y/...`,
   `/aws/service/eks/optimized-ami/X.Y/...`), self-managed groups. Auto Mode nodes
   roll on their own.
4. Version-coupled add-ons: `kube-proxy` must match the new minor; move `coredns` and
   `vpc-cni` to the default build for the new minor.
5. Remaining add-ons and Helm charts that the next hop needs.

Then re-read the insights: they only judge the next minor, so a clean result for
1.35 says nothing about 1.36.

## Upgrade Insights

- `eks:ListInsights` + `eks:DescribeInsight` (category `UPGRADE_READINESS`). Checks
  include deprecated API usage (with client user agents and last request time), add-on
  compatibility, kubelet and kube-proxy skew, and cluster health.
- Treat `ERROR` as blocking and `WARNING` as needing a decision. A deprecated-API warning
  for a later minor than the target is a follow-up item, not a blocker.
- Insights refresh roughly daily; re-check after fixing something rather than assuming.

## Version skew

- Kubelet may be up to three minors older than the API server (Kubernetes ≥ 1.28), but
  EKS flags two behind as a warning. Before a hop, bring every node group to within one
  minor of the **target**.
- `kube-proxy` follows the same skew rule as kubelet; keep it on the cluster minor.
- Read node group versions live (`eks:DescribeNodegroup` → `version`, `releaseVersion`).
  Terraform may not drive them (see below).

## Node groups that Terraform does not move

- `aws_eks_node_group` without `version` (or without `release_version` for a pinned
  AMI) stays on whatever minor it has when the control plane moves. Some wrapper modules
  never set either, and silently drop a `release_version` passed in the node group
  object. `scan_terraform_eks.py` reports both cases.
- In that case the plan needs `aws eks update-nodegroup-version --cluster-name C
  --nodegroup-name N --kubernetes-version X.Y` per group (or a console upgrade), or a
  module change that wires the version through. Say which, and that it is out of band.
- Groups with a launch template that does not set an AMI still take a version update;
  groups whose launch template pins an AMI ID need a new template version instead.

## EKS Auto Mode

- After a control-plane upgrade, Auto Mode replaces its nodes to match, respecting PDBs.
  A PDB that allows zero disruptions (e.g. `minAvailable: 1` on one replica) stalls the
  rollout; list those before the hop
  (`kubectl get pdb -A` where `ALLOWED DISRUPTIONS` is 0).
- Auto Mode nodes bring their own networking, storage and load-balancing components.
  The `vpc-cni`, `kube-proxy`, `aws-ebs-csi-driver` add-ons (and often `coredns`) are
  only needed for managed or self-managed node groups. If a cluster has none, they are
  removal candidates, not upgrade work.
- Auto Mode shares the `nodepools.karpenter.sh` / `nodeclaims.karpenter.sh` CRDs. A
  separately installed `karpenter-crd` chart keeps them in `templates/`, so uninstalling
  or destroying that release deletes every NodePool and NodeClaim. Do not remove it
  without `helm.sh/resource-policy: keep` and a check of who owns the live CRDs.
- Auto Mode behaviour changes are listed at
  https://docs.aws.amazon.com/eks/latest/userguide/auto-change.html — read it each run;
  some changes are date-based rather than version-based.
- Docs: https://docs.aws.amazon.com/eks/latest/userguide/auto-upgrade.html

## Add-on versions

- The API is authoritative:
  `aws eks describe-addon-versions --addon-name <name> --kubernetes-version <x.y>`
  returns builds compatible with that minor, newest first, with `defaultVersion` per
  minor. Query it for **each** hop's minor.
- Default target: the default build for the minor. Use the newest compatible build only
  when the user wants it or a fix requires it.
- Docs: https://docs.aws.amazon.com/eks/latest/userguide/eks-add-ons.html

## Helm chart compatibility

- Look for `kubeVersion:` in `Chart.yaml`, a compatibility matrix in the project README
  or docs, or the release notes. Mark "unverified" when none of them says.
- A chart that does not support the next hop's minor is a pre-requisite of that hop,
  not a follow-up.
- Default target: the newest patch of the previous minor line (prefer previous stable
  over the newest release), unless that line does not support the target minor.
