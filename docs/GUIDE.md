# Guide: How This Toolkit Works

A quick, practical guide to understanding and extending this toolkit.

---

## The Big Picture

```
┌────────────────────────────────────────────────────────────┐
│                      YOUR AGENT                             │
│  (Claude Code, Copilot, Codex, Cursor, etc.)              │
└────────────┬──────────────────────┬────────────────────────┘
             │                      │
     loads skills via          calls tools via
     retrieve_skill()              MCP
             │                      │
┌────────────▼──────────────────────▼────────────────────────┐
│                    MCP SERVER                               │
│                                                            │
│  Core:     list_skills() · retrieve_skill(name)            │
│  Tools:    <category>__<tool_name> · ...                    │
│  Resources: compatibility matrices · templates             │
│  Prompts:  analyze_drift · changelog_research              │
└────────────────────────────────────────────────────────────┘
             │
     discovers from
             │
┌────────────▼───────────────────────────────────────────────┐
│                    YOUR SKILLS                              │
│                                                            │
│  skills/devops/aws-eks-updater/                            │
│  skills/devops/github-actions-writer/                      │
│  skills/meta/agent-toolkit/                                │
│    SKILL.md          ← Agent reads this, follows phases    │
│    tools/            ← Scripts exposed via MCP             │
│    references/       ← Exposed as MCP resources            │
│    agents/           ← Sub-agent prompts for fan-out       │
│    assets/           ← Report templates                    │
└────────────────────────────────────────────────────────────┘
```

---

## Key Concepts (30-second version)

| Concept | What it is | Analogy |
|---------|-----------|---------|
| **Skill** | A multi-step playbook an agent follows | A recipe |
| **MCP Tool** | A single function the agent can call | A kitchen utensil |
| **MCP Resource** | Read-only reference data | A cookbook page |
| **MCP Prompt** | A reusable task template | A recipe card |
| **Plugin** | A bundle (skills + MCP config) for one-click install | A meal kit |
| **Rules** | Guardrails that shape agent behavior | House rules |

---

## How Skill Discovery Works

1. Agent receives a user request
2. Agent calls `list_skills()` → gets names + descriptions
3. Agent picks the best match by description
4. Agent calls `retrieve_skill("my-skill-name")` → gets full SKILL.md
5. Agent follows the skill's phases, calling MCP tools as needed

**No local installation required** — skills are discoverable at runtime through the MCP server.

---

## How to Add a New Skill

```bash
# 1. Create the skill directory
mkdir -p skills/<category>/<skill-name>/{tools,references}

# 2. Write SKILL.md
cat > skills/<category>/<skill-name>/SKILL.md << 'EOF'
---
name: my-new-skill
description: >
  What it does. Use when [trigger conditions].
  Do NOT use for [exclusions].
version: 1
requires_tools:
  - <category>__my_tool
requires_mcp: []
tags: [relevant, keywords]
---

# My New Skill

## Overview
What this skill accomplishes.

## Common Tasks
Step-by-step procedures...
EOF

# 3. (Optional) Expose tools via MCP — create mcp_tools.json
cat > skills/<category>/<skill-name>/tools/mcp_tools.json << 'EOF'
{
  "tools": [
    {
      "name": "my_tool",
      "script": "my_script.py",
      "description": "What it does.",
      "params": [
        { "name": "input", "flag": "--input", "required": true, "description": "..." }
      ]
    }
  ]
}
EOF

# 4. Add to manifest
# Edit skills/manifest.json — add your skill entry

# 5. Done — MCP server auto-discovers everything on next start
```

---

## How to Add a New Plugin

Plugins bundle skills for one-click agent installation:

```
plugins/<plugin-name>/
  .claude-plugin/plugin.json    ← metadata for Claude Code
  .codex-plugin/plugin.json     ← metadata for Codex (includes skills/mcpServers pointers)
  .mcp.json                     ← MCP server connection config
  skills/                       ← symlinks to canonical skills
  README.md
```

Then add an entry to `.claude-plugin/marketplace.json` and `.agents/plugins/marketplace.json`.

---

## Tool Naming Convention

Tools are namespaced by category with double underscores:

```
<category>__<tool_name>
```

Examples:
- `devops__eks_list_addons`
- `devops__aks_find_terraform`
- `devops__gha_list_workflows`
- `meta__scaffold_skill`

---

## Resource URI Convention

```
skills://<category>/<skill-name>/references/<filename>
skills://<category>/<skill-name>/assets/<filename>
```

Examples:
- `skills://devops/aws-eks-updater/references/eks-compatibility.md`
- `skills://devops/azure-aks-updater/assets/plan_template.html`

---

## SKILL.md Frontmatter Reference

```yaml
---
name: kebab-case-name              # Required. Machine ID.
description: >                     # Required. 2-3 sentences.
  Starts with verb. Include "Use when..." triggers.
  Include "Do NOT use for..." exclusions.
version: 1                         # Required. Integer, bump on breaking changes.
requires_tools:                    # Optional. MCP tools this skill needs.
  - category__tool_name
requires_mcp:                      # Optional. External MCP servers needed.
  - terraform
  - github
tags: [keyword1, keyword2]         # Optional. For search/filtering.
---
```

---

## Rules Files

Simple markdown bullets — not code. Put in `rules/`:

```markdown
# Domain Guidance

- Prefer [X] for [situation]. Fall back to [Y] otherwise.
- Before [task type], check for skills via list_skills.
- Never [dangerous action] without user confirmation.
```

Agents load these as behavioral guardrails. Keep them short (6-10 bullets).

---

## Quick Reference: When to Put Logic Where

| You want to... | Put it in... |
|----------------|-------------|
| Query/fetch data (stateless) | MCP Tool (`mcp_tools.json`) |
| Reusable prompt templates | MCP Prompt (`mcp_prompts.json`) |
| Provide reference material | MCP Resource (`references/`) |
| Guide a multi-step workflow | Skill (`SKILL.md`) |
| Parallelize research work | Sub-agent (`agents/*.md`) |
| Set behavioral guardrails | Rules file (`rules/`) |
| Bundle for distribution | Plugin (`plugins/`) |
| Generate reports/output | Asset template (`assets/`) |
