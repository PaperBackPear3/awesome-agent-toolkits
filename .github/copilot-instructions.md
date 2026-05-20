# Copilot Instructions

## What This Repository Is

A **framework for packaging business logic as discoverable agent skills**. Skills are self-contained instruction packages that AI agents load at runtime to perform complex, multi-step tasks. The MCP server makes skills discoverable and exposes their tools to any MCP-compatible client.

This is NOT an application. There is no build system, no runtime code, no tests. The deliverables are: Markdown playbooks, Python helper scripts, JSON manifests, and HTML templates.

## Repository Structure

```
skills/<category>/<skill-name>/     ← Canonical skill content
  SKILL.md                          ← Entry point (YAML frontmatter + phases)
  tools/                            ← Python scripts (optional, exposed via MCP)
    mcp_tools.json                  ← Tool declarations for auto-discovery
  references/                       ← Reference data (auto-exposed as MCP resources)
  agents/                           ← Sub-agent prompts for fan-out work
  assets/                           ← Report templates
plugins/<plugin-name>/              ← Installable bundles for agent marketplaces
  .claude-plugin/plugin.json
  .codex-plugin/plugin.json
  .mcp.json
  skills/                           ← Symlinks to canonical skills
rules/                              ← Agent behavior rules (per-domain)
mcp-server/                         ← Agent Toolkit MCP server (published separately as `agent-toolkit-mcp-server` via uvx)
skills/manifest.json                ← Machine-readable skill catalog
docs/                               ← Framework documentation
```

## How to Work in This Repo

### Adding a new skill

1. `mkdir -p skills/<category>/<name>/{tools,references}`
2. Write `SKILL.md` — must have YAML frontmatter with `name`, `description` (include "Use when..." and "Do NOT use for...")
3. Optionally add `tools/mcp_tools.json` to expose scripts as MCP tools
4. Register in `skills/manifest.json`
5. Validate: `python3 -c "import json; json.load(open('skills/manifest.json'))"`

### Adding a new MCP tool

1. Write a Python script in `skills/<category>/<skill>/tools/` — prints JSON to stdout, uses argparse, stdlib only
2. Add entry to that skill's `tools/mcp_tools.json`

### Adding a new plugin

1. Create `plugins/<name>/` with `.claude-plugin/plugin.json`, `.codex-plugin/plugin.json`, `.mcp.json`
2. Symlink skills into `plugins/<name>/skills/`
3. Register in `.claude-plugin/marketplace.json` and `.agents/plugins/marketplace.json`

## Conventions — Follow These

- **SKILL.md frontmatter is sacred** — `name` (kebab-case, unique), `description` (verb phrase + triggers + exclusions), `version` (integer)
- **Tools are namespaced** — `<category>__<tool_name>` (double underscore)
- **Resources auto-discovered** — anything in `references/` or `assets/` becomes an MCP resource
- **Safety-first** — skills never apply changes without user confirmation
- **Stdlib only** — Python scripts use no external dependencies
- **One concern per skill** — don't combine unrelated workflows in one SKILL.md
- **Phases are linear** — agents work through phases sequentially, one per turn
- **Description quality matters** — agents route to skills based on the description field; write it like trigger documentation

## What NOT to Do

- Don't add `requirements.txt` or external Python dependencies to tool scripts
- Don't put orchestration logic in MCP tools (keep them stateless)
- Don't create skills without registering in `manifest.json`
- Don't hardcode tool registrations — use `mcp_tools.json`
- Don't mix domains in one skill — create separate skills per concern
