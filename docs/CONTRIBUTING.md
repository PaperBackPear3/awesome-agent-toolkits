# Contributing: Adding New Skills, Tools, and Plugins

How to extend this toolkit with your own skills, MCP tools, and plugins.

---

## Adding a New Skill

### Step 1: Create the directory

```bash
mkdir -p skills/<category>/<skill-name>/{tools,references}
```

Categories are top-level domains: `devops`, `security`, `data`, `business`, etc.

### Step 2: Write SKILL.md

This is the only required file. It's what the agent reads and follows.

```yaml
---
name: my-skill-name
description: >
  One sentence saying what it does. Use when the user mentions X, Y, or Z.
  Do NOT use for A or B.
version: 1
requires_tools: []
requires_mcp: []
tags: [keyword1, keyword2]
---
```

Then write the body — use phases, tables, constraints:

```markdown
# My Skill

## Overview
What this skill accomplishes in 2-3 sentences.

## Common Tasks

### 1. First Task
Steps, commands, constraints...

### 2. Second Task
...

## Troubleshooting
Known issues and fixes.

## Additional Resources
- [references/details.md](references/details.md)
```

### Step 3: Add reference materials (optional)

Put deep-dive docs in `references/`:
```
references/
  setup-guide.md
  troubleshooting.md
  compatibility-matrix.md
```

These are auto-exposed as MCP resources.

### Step 4: Add to the manifest

Edit `skills/manifest.json`:

```json
{
  "name": "my-skill-name",
  "category": "my-category",
  "version": 1,
  "path": "my-category/my-skill-name",
  "description": "Same as SKILL.md description.",
  "requires_tools": [],
  "requires_mcp": [],
  "tags": ["keyword1", "keyword2"]
}
```

### Step 5: Done

The skill is ready. Agents discover it via the YAML frontmatter `description` field when the skill is in their skills directory.

---

## Adding MCP Tools to a Skill

If your skill uses Python scripts that should be callable via MCP:

### Step 1: Write the script

```python
#!/usr/bin/env python3
"""tools/my_script.py — Does something useful."""
import argparse
import json

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    args = parser.parse_args()

    result = {"status": "ok", "data": f"processed {args.input}"}
    print(json.dumps(result))

if __name__ == "__main__":
    main()
```

Rules for tool scripts:
- Print JSON to stdout
- Use argparse for parameters
- Exit 0 on success, non-zero on error
- Errors go to stderr
- No external dependencies (stdlib only)

### Step 2: Create `tools/mcp_tools.json`

```json
{
  "tools": [
    {
      "name": "my_tool",
      "script": "my_script.py",
      "description": "Clear one-line description of what this tool does.",
      "params": [
        {
          "name": "input",
          "flag": "--input",
          "required": true,
          "description": "What this parameter controls"
        },
        {
          "name": "optional_thing",
          "flag": "--optional-thing",
          "required": false,
          "description": "Optional param with sensible default"
        }
      ]
    }
  ]
}
```

### Step 3: (Optional) Create `tools/mcp_prompts.json`

If your skill benefits from reusable prompt templates (e.g., analysis, research, planning), declare them:

```json
{
  "prompts": [
    {
      "name": "my_prompt",
      "description": "Clear one-line description of what this prompt produces.",
      "params": [
        { "name": "input_data", "required": true, "description": "Data to include in the prompt" }
      ],
      "template": "Analyze the following data:\n\n{input_data}\n\nProduce a summary."
    }
  ]
}
```

Prompts are namespaced as `<category>__my_prompt` and auto-discovered on server restart.

### Step 4: Done

Your tool is declared and will be available when the skill is loaded by an agent that supports MCP tool discovery.

---

## Adding a New Plugin

Plugins bundle skills + MCP config for one-click agent installation.

### Step 1: Create the plugin directory

```
plugins/<plugin-name>/
  .claude-plugin/
    plugin.json
  .codex-plugin/
    plugin.json
  .mcp.json
  skills/           ← symlinks to canonical skills
  README.md
```

### Step 2: Create manifests

**`.claude-plugin/plugin.json`** (metadata only):
```json
{
  "name": "my-plugin",
  "version": "1.0.0",
  "description": "What this plugin provides.",
  "author": { "name": "Your Name" },
  "homepage": "https://github.com/you/repo",
  "repository": "https://github.com/you/repo",
  "license": "MIT",
  "keywords": ["relevant", "keywords"]
}
```

**`.codex-plugin/plugin.json`** (full manifest):
```json
{
  "name": "my-plugin",
  "version": "1.0.0",
  "description": "What this plugin provides.",
  "author": { "name": "Your Name" },
  "skills": "./skills/",
  "mcpServers": "./.mcp.json",
  "interface": {
    "displayName": "My Plugin",
    "shortDescription": "Brief description",
    "category": "Category",
    "capabilities": ["Read"]
  }
}
```

**`.mcp.json`**:
```json
{
  "mcpServers": {}
}
```

Plugins do not bundle an MCP server. If your skill needs MCP tools, declare them in
`tools/mcp_tools.json` within the skill. The Agent Toolkit MCP (`agent-toolkit-mcp-server`)
is a separate installation — see [INSTALL.md](INSTALL.md).

### Step 3: Symlink skills

```bash
cd plugins/my-plugin/skills
ln -s ../../../skills/category/skill-name skill-name
```

### Step 4: Register in marketplace

Add to `.claude-plugin/marketplace.json` and `.agents/plugins/marketplace.json`:

```json
{
  "name": "my-plugin",
  "description": "...",
  "source": "./plugins/my-plugin",
  "version": "1.0.0",
  "category": "category"
}
```

---

## Adding Rules Files

Rules shape agent behavior for a domain. Put them in `rules/`:

```markdown
# My Domain Guidance

- Before starting [task], check for skills via list_skills.
- Use [preferred tool/approach] for [situation].
- Never [dangerous action] without explicit user confirmation.
- When uncertain about [X], verify via [Y] rather than guessing.
- Prefer [safe approach] over [risky approach].
```

Keep rules:
- **Short** — 6-10 bullets max
- **Actionable** — "do X" not "X is important"
- **Specific** — name actual tools, commands, patterns

---

## Adding Sub-Agent Prompts

For skills that fan out work in parallel, put prompts in `agents/`:

```markdown
<!-- agents/research-agent.md -->
# Research Agent

You are researching [specific topic] for the parent skill.

## Your Task
1. Find [specific information]
2. Check [specific sources]
3. Return structured results as JSON

## Output Format
Return a JSON object with: ...
```

The parent skill references these via: *"Delegate to the research agent at `agents/research-agent.md`"*

---

## Checklist: New Skill

- [ ] `skills/<category>/<name>/SKILL.md` created with valid frontmatter
- [ ] Description includes "Use when..." triggers
- [ ] Description includes "Do NOT use for..." exclusions
- [ ] `skills/manifest.json` updated
- [ ] (If tools) `tools/mcp_tools.json` created
- [ ] (If prompts) `tools/mcp_prompts.json` created
- [ ] (If tools) Scripts output JSON, use argparse, stdlib only
- [ ] (If references) Files in `references/` for deep-dive content
- [ ] Tested: skill loads correctly when copied to agent's skills directory

## Checklist: New Plugin

- [ ] `.claude-plugin/plugin.json` with metadata
- [ ] `.codex-plugin/plugin.json` with skills/mcpServers pointers
- [ ] `.mcp.json` with server config
- [ ] Skills symlinked in `skills/`
- [ ] `README.md` with install instructions
- [ ] Root marketplace JSONs updated
