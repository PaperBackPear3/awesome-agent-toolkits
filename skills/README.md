# Skills

Agent skills are self-contained instruction packages that AI coding agents load at runtime to perform complex DevOps tasks.

## Available Skills

| Category | Skill | Description |
|----------|-------|-------------|
| DevOps | `aws-eks-updater` | Interactive, safety-first EKS cluster upgrades |
| DevOps | `azure-aks-updater` | Interactive, safety-first AKS cluster upgrades |

## How to Use

### Method 1: Plugin Install (Claude Code)

```bash
claude plugin add github:PaperBackPear3/awesome-agent-toolkits/plugins/devops-core
```

### Method 2: Local Copy

Copy a skill directory into your agent's skill folder:

| Agent | Path |
|-------|------|
| GitHub Copilot | `~/.agents/skills/<skill-name>/` |
| Claude Code | `~/.claude/skills/<skill-name>/` |

## Skill Structure

Each skill follows this layout:

```
<skill-name>/
  SKILL.md        # Entry point — YAML frontmatter + phase-based playbook
  agents/         # Sub-agent prompts for parallel fan-out
  assets/         # HTML report templates
  references/     # Static reference data (compatibility matrices)
  tools/          # Python helper scripts (CLI, stdout JSON)
```

The agent discovers a skill via the YAML frontmatter (`name`, `description`) in `SKILL.md` and follows the phased playbook linearly.
