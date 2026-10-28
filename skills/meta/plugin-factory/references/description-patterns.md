# Description Patterns

## Why Descriptions Matter

The `description` field in SKILL.md frontmatter is the **primary trigger mechanism**. When a user makes a request, the agent matches their intent against skill descriptions to decide which skill to load. A poorly written description means the skill never gets triggered — or triggers for the wrong requests.

---

## Good Patterns

### Start with a verb phrase

Tell the agent what this skill *does*, not what it *is*:

- ✅ "Interactive, safety-first skill for updating an AWS EKS cluster."
- ❌ "An EKS cluster management skill."

### Include all trigger keywords

Think about every way a user might phrase their request:

- ✅ "...updating or upgrading an EKS cluster, bumping Kubernetes/k8s versions, upgrading EKS add-ons (vpc-cni, coredns, kube-proxy, ebs-csi, efs-csi, pod-identity-agent, adot, cloudwatch-observability), upgrading Helm releases on EKS..."
- ❌ "...updating EKS..."

### Include context clues

Users don't always name the thing directly — reference the tools and patterns that imply intent:

- ✅ "...even without the word 'EKS' when context (eksctl, aws-auth configmap, terraform `aws_eks_*`) is clear."
- ❌ (no contextual signals)

### Be slightly "pushy"

Err on the side of triggering. Include adjacent triggers that are close enough:

- ✅ "...checking EKS/add-on compatibility, or planning a control-plane minor bump..."
- ❌ (only exact-match triggers)

### Include contextual override phrases

Tell the agent when to trigger even without explicit keywords:

- ✅ "...even without the word 'EKS' when context (eksctl, aws-auth configmap, terraform `aws_eks_*`) is clear."

---

## Anti-Patterns

### Too vague

```
# Bad
description: "Helps with DevOps tasks"
```

Problem: Matches everything, routes nothing accurately.

### Too narrow

```
# Bad
description: "Updates the vpc-cni addon version in EKS"
```

Problem: Misses coredns, kube-proxy, ebs-csi, Helm releases, control plane bumps, and every other update scenario.

### Missing exclusions

```
# Bad — no "Do NOT use for..." section
description: "Updates Kubernetes clusters on AWS"
```

Problem: Will trigger for initial provisioning, troubleshooting, cost optimization — things this skill doesn't handle.

### Keyword-only

```
# Bad
description: "EKS, Kubernetes, upgrade, update, addon, Helm"
```

Problem: No context for the agent to understand *when* to trigger or what the skill actually does.

### Too long (over 200 words)

Problem: Dilutes the signal. The agent's matching becomes fuzzy when there's too much text. Keep descriptions between 80–150 words for optimal routing.

---

## Template

```
<Verb phrase describing what the skill does>. <Method/approach in 1 sentence>.
Use when the user mentions <trigger1>, <trigger2>, <trigger3>, <context clues>,
or <adjacent triggers> — even without <explicit keyword> when <contextual signals> are clear.
Do NOT use for <exclusion1>, <exclusion2>, or <exclusion3>.
```

---

## Example: an EKS upgrade skill

```yaml
description: >
  Interactive, safety-first skill for updating an AWS EKS cluster. Verifies prerequisites,
  inventories the cluster from three sources (Terraform definitions, AWS-managed add-ons,
  Helm releases), reconciles declared vs. installed versions, fetches GitHub changelogs and
  scans them for breaking changes, then walks the user through updates one package at a time.
  Auto-plans patch/minor bumps; proposes major bumps only when no breaking-change markers are
  found and always with a written report. Never commits, pushes, or applies changes.
  Use when the user mentions updating or upgrading an EKS cluster, bumping Kubernetes/k8s
  versions, upgrading EKS add-ons (vpc-cni, coredns, kube-proxy, ebs-csi, efs-csi,
  pod-identity-agent, adot, cloudwatch-observability), upgrading Helm releases on EKS,
  checking EKS/add-on compatibility, or planning a control-plane minor bump — even without
  the word "EKS" when context (eksctl, aws-auth configmap, terraform `aws_eks_*`) is clear.
```

### Why this works:

1. **Opens with verb phrase** — "Interactive, safety-first skill for updating..."
2. **Explains the method** — three-source inventory, changelog scanning, one-at-a-time upgrades
3. **States safety posture** — "Never commits, pushes, or applies changes"
4. **Exhaustive trigger list** — every addon name, every user phrasing
5. **Contextual override** — triggers on `eksctl` or `aws_eks_*` terraform resources even without "EKS"
6. **Implicit exclusion** — "updating" scopes it away from provisioning (though an explicit "Do NOT use for..." would strengthen it further)

---

## Checklist

Before finalizing a description, verify:

- [ ] Starts with a verb phrase (not "A skill that..." or "This skill...")
- [ ] Under 200 words
- [ ] Lists 5+ specific trigger phrases
- [ ] Includes at least one contextual override ("even without X when Y")
- [ ] Has "Do NOT use for..." with 2+ exclusions
- [ ] Mentions the key tools/files/patterns involved
- [ ] A colleague reading just the description could predict when it should trigger
