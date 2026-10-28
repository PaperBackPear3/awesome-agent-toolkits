# Skill Writing Guide

## Frontmatter Fields

Every `SKILL.md` starts with YAML frontmatter between `---` fences:

| Field | Required | Type | Notes |
|-------|----------|------|-------|
| `name` | yes | string | Kebab-case, unique across all skills |
| `description` | yes | string | Verb phrase + triggers + exclusions (see below) |
| `version` | yes | integer | Increment on breaking changes |
| `requires_tools` | no | array | MCP tool names this skill depends on |
| `requires_mcp` | no | array | MCP servers that must be available |
| `tags` | no | array | Discovery keywords |

Example:

```yaml
---
name: aws-eks-updater
description: >
  Interactive, safety-first skill for updating an AWS EKS cluster...
  Use when the user mentions updating or upgrading an EKS cluster...
  Do NOT use for initial cluster provisioning or non-EKS Kubernetes.
version: 1
requires_tools:
  - devops__eks_inventory_addons
requires_mcp:
  - terraform
  - github
tags: [aws, eks, kubernetes]
---
```

---

## Body Structure

After frontmatter, organize the body in this order:

### 1. Overview

2–3 sentences expanding on what the skill does and why. Set expectations for what the agent will deliver.

### 2. Hard Rules

Non-negotiable safety constraints. Keep this short — only rules that must never be violated:

```markdown
## Hard Rules
- Never apply changes without explicit user confirmation
- Never commit or push to remote branches
- Always verify prerequisites before starting work
```

### 3. Phases

The main content. Each phase is one agent turn:

```markdown
## Phase 1 — Gather Context
1. Ask the user for cluster name and region
2. Run prerequisite checks
3. Report findings and confirm before advancing

## Phase 2 — Inventory
...
```

### 4. Additional Resources

Links to references, templates, or related skills.

---

## Progressive Disclosure

Layer information to avoid overwhelming the agent's context window:

| Layer | Size Target | Purpose |
|-------|-------------|---------|
| Frontmatter `description` | ~100 words | Routing/triggering |
| SKILL.md body | <500 lines | Playbook the agent follows |
| `references/` files | Unlimited | Deep-dive data loaded on demand |

The agent reads the description first (for routing), then the full SKILL.md (for execution), and only loads references when a phase explicitly calls for them.

---

## Writing Style

- **Imperative form** — "Run the inventory tool" not "You should run the inventory tool"
- **Explain the why** — "Check compatibility first (upgrades can break workloads)" not just "Check compatibility"
- **Avoid heavy-handed MUSTs** — Reserve uppercase MUST/NEVER for genuine safety constraints in Hard Rules
- **Use tables** for structured data (version matrices, field descriptions, option lists)
- **Be specific** — "Run `devops__eks_inventory_addons`" not "check the add-ons"

---

## Phase Design

Each phase follows a consistent pattern:

1. **Gather input** — what does the agent need from the user or tools?
2. **Work** — execute the logic (tool calls, analysis, generation)
3. **Report** — present findings clearly (tables, summaries)
4. **Confirm** — ask the user before advancing to the next phase
5. **Advance** — move to the next phase only after confirmation

One phase = one agent turn. Don't try to pack multiple concerns into a single phase.

---

## Hard Rules Section

Reserve for safety-critical constraints only:

- Things that could cause data loss or service disruption
- Actions that are irreversible
- Security boundaries (never expose secrets, never run untrusted code)

Bad hard rule: "Always use tables for output" (style preference, not safety)
Good hard rule: "Never apply Terraform changes without user confirmation"

---

## Description Quality

The `description` field is the **primary trigger mechanism**. Agents route to skills based on matching the description against user intent. Write it like trigger documentation:

1. Start with a verb phrase describing what the skill does
2. Add "Use when..." with specific trigger phrases and contexts
3. Add "Do NOT use for..." with clear exclusions
4. Include adjacent triggers (related terms users might say)
5. Include contextual signals ("even without the word X when Y is clear")

See `description-patterns.md` for detailed patterns and anti-patterns.

---

## Tool Scripts

Python scripts in `tools/` exposed via `mcp_tools.json`:

- **stdlib only** — no pip dependencies
- **argparse** for input — clear `--flag` interface
- **JSON to stdout** — structured output the agent can parse
- **Exit codes** — `0` for success, `1` for failure
- **Stateless** — no side effects, no file writes unless explicitly requested

---

## References

Files in `references/` are auto-exposed as MCP resources:

- One file per topic (don't combine unrelated data)
- Add a table of contents for files over 300 lines
- Use markdown for prose, JSON for structured data
- Name files descriptively: `version-compatibility-matrix.md`, not `data.md`

---

## Examples

Reference these existing skills for patterns:

- `skills/devops/github-actions-writer/` — multi-phase devops skill with references
- `skills/meta/plugin-factory/` — meta skill that creates other skills/plugins
