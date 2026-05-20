---
name: plugin-factory
description: >
  Create new plugins and skills for this repository. Scaffolds complete plugin structures
  (directory layout, .claude-plugin, .codex-plugin, .mcp.json, marketplace registration),
  writes SKILL.md files with proper frontmatter and phased workflows, generates MCP tool
  scripts, validates everything, and registers in manifests.
  Use when the user wants to create a new plugin, add a new skill to the repository,
  scaffold a plugin or skill from scratch, generate MCP tool boilerplate, validate an
  existing skill or plugin structure, or register something in the marketplace.
  Do NOT use for modifying the MCP server code itself, managing infrastructure, or
  deploying plugins to external registries.
version: 1
requires_tools:
  - meta__scaffold_plugin
  - meta__scaffold_skill
  - meta__validate_plugin
  - meta__validate_skill
tags: [meta, scaffolding, plugin, skill, creation]
---

# Plugin Factory

You are a plugin and skill creation assistant for this repository. Work through phases
sequentially. At each phase: gather input, perform work, report results, get confirmation,
then advance.

**Hard rules — never violate:**

- Never overwrite existing files without explicit user confirmation.
- Never bundle an MCP server inside a plugin — tools are declared via `mcp_tools.json`.
- Always validate before declaring done — run `validate_plugin` and `validate_skill`.
- Skills must include "Use when..." and "Do NOT use for..." in their description.
- Tool scripts use stdlib only — no pip dependencies.
- Use kebab-case for skill names, plugin names, and directory names.

---

## Phase 1: Discover Intent

Understand what the user wants to build:

1. **Domain** — What area does this cover? (devops, security, data, meta, business, etc.)
2. **Plugin scope** — What skills will this plugin bundle? (1 plugin can have multiple skills)
3. **Each skill's purpose** — For each skill:
   - What task does it accomplish?
   - What triggers should activate it?
   - What tools/CLIs does it need?
   - What phases will it follow?
4. **MCP tools needed** — Will the skills need Python tool scripts exposed via MCP?

Output a summary table before proceeding:

| Component | Name | Description |
|-----------|------|-------------|
| Plugin | `<name>` | ... |
| Skill 1 | `<name>` | ... |
| Skill 2 | `<name>` | ... |
| Tool 1 | `<category>__<name>` | ... |

---

## Phase 2: Scaffold Plugin

Run `meta__scaffold_plugin` with the plugin name and metadata to generate:

```
plugins/<plugin-name>/
├── .claude-plugin/plugin.json
├── .codex-plugin/plugin.json
├── .mcp.json
├── README.md
└── skills/
    └── <skill-name> -> ../../../skills/<category>/<skill-name>
```

Verify the output and show the user what was created.

---

## Phase 3: Create Skills

For each skill in the plugin, repeat this sub-workflow:

### 3a. Scaffold the skill

Run `meta__scaffold_skill` with category, name, and description to create:

```
skills/<category>/<skill-name>/
├── SKILL.md          (template with frontmatter filled in)
├── tools/            (empty, ready for scripts)
├── references/       (empty, ready for docs)
└── agents/           (empty, ready for sub-agent prompts)
```

### 3b. Write the SKILL.md body

Help the user write the skill body. Follow these principles:

- **Progressive disclosure** — keep SKILL.md under 500 lines; use references/ for deep dives
- **Phases are linear** — the agent works through them one at a time
- **Imperative form** — "Run X", "Check Y", not "You should run X"
- **Explain the why** — don't just say ALWAYS/NEVER, explain reasoning
- **Hard rules section** — list absolute constraints at the top
- **Tables for structured data** — compatibility matrices, parameter lists
- **Examples** — include input/output examples where helpful

Reference `references/skill-writing-guide.md` for the full guide.

### 3c. Add MCP tools (if needed)

For each tool script:

1. Write the Python script in `tools/` — uses argparse, prints JSON to stdout, stdlib only
2. Add the tool declaration to `tools/mcp_tools.json`
3. Tools are namespaced as `<category>__<tool_name>` (double underscore)

### 3d. Add references (if needed)

Put detailed docs in `references/`. These are auto-exposed as MCP resources.
Keep them focused — one file per topic, include a table of contents for files > 300 lines.

### 3e. Add sub-agent prompts (if needed)

Write agent prompts in `agents/`. Each agent prompt should define:
- Role
- Inputs
- Process (numbered steps)
- Output format

---

## Phase 4: Validate & Register

### 4a. Validate structure

Run `meta__validate_plugin` on the plugin directory. It checks:
- All required files exist (.claude-plugin/plugin.json, .mcp.json, etc.)
- JSON files are valid
- Skills symlinks resolve
- .mcp.json does not bundle a standalone MCP server (must be `{"mcpServers": {}}`)

Run `meta__validate_skill` on each skill directory. It checks:
- SKILL.md exists and has valid frontmatter
- name is kebab-case
- description includes trigger phrases and exclusions
- tools/mcp_tools.json is valid (if present)
- Referenced scripts exist

### 4b. Register in manifest

Add each skill to `skills/manifest.json`:

```json
{
  "name": "<skill-name>",
  "category": "<category>",
  "version": 1,
  "path": "<category>/<skill-name>",
  "description": "Same as SKILL.md description.",
  "requires_tools": [],
  "requires_mcp": [],
  "tags": ["tag1", "tag2"]
}
```

### 4c. Register in marketplace

Add the plugin to both marketplace files:
- `.claude-plugin/marketplace.json`
- `.agents/plugins/marketplace.json`

### 4d. Final verification

```bash
python3 -c "import json; json.load(open('skills/manifest.json'))"
```

Confirm the skill loads correctly when placed in the agent's skills directory.

---

## Phase 5: Review & Optimize

After everything is created and validated:

1. **Review skill descriptions** — Are they specific enough to trigger correctly?
   Use patterns from `references/description-patterns.md`.
2. **Review hard rules** — Are safety constraints clear and complete?
3. **Review tool scripts** — Do they handle errors gracefully? Print useful JSON on failure?
4. **Suggest improvements** — Based on patterns from existing skills in this repo.

Present a final summary to the user showing everything that was created.

---

## Reference Files

- `references/plugin-structure.md` — Complete plugin anatomy and file requirements
- `references/skill-writing-guide.md` — How to write effective skills
- `references/description-patterns.md` — Trigger description best practices and anti-patterns
- `agents/skill-reviewer.md` — Sub-agent for reviewing skill quality
- `agents/description-optimizer.md` — Sub-agent for improving descriptions
