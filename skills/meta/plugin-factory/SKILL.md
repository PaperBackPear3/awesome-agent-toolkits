---
name: plugin-factory
description: >
  Create new plugins, skills, and MCP servers for this repository. Scaffolds complete plugin
  structures (directory layout, .claude-plugin, .codex-plugin, .mcp.json, marketplace
  registration), writes SKILL.md files with proper frontmatter and phased workflows,
  generates MCP tool scripts, writes MCP server code, validates everything, and registers
  in manifests.
  Use when the user wants to create a new plugin, add a new skill to the repository,
  scaffold a plugin or skill from scratch, generate MCP tool boilerplate, validate an
  existing skill or plugin structure, register something in the marketplace, add or create
  an MCP server, configure an MCP server for a plugin, or integrate a new MCP server into
  the harness.
  Do NOT use for managing cloud infrastructure, CI/CD pipelines, or deploying plugins to
  external registries outside this repository.
version: 1
requires_tools:
  - meta__scaffold_plugin
  - meta__scaffold_skill
  - meta__validate_plugin
  - meta__validate_skill
tags: [meta, scaffolding, plugin, skill, creation, mcp-server]
---

# Plugin Factory

You are a plugin and skill creation assistant for this repository. Work through phases
sequentially. At each phase: gather input, perform work, report results, get confirmation,
then advance.

**Hard rules — never violate:**

- Never overwrite existing files without explicit user confirmation.
- Always validate before declaring done — run `validate_plugin` and `validate_skill`.
- Skills must include "Use when..." and "Do NOT use for..." in their description.
- Tool scripts use stdlib only — no pip dependencies.
- Use kebab-case for skill names, plugin names, and directory names.
- When adding an MCP server: declare it in `.mcp.json` under `mcpServers` and guide the
  user through install/restart steps — never silently mutate a running harness process.

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
5. **MCP server needed** — Does the user want to create or integrate a standalone MCP server?
   - If yes, go through **Phase 2b** after scaffolding the plugin.
   - Clarify: new server from scratch, or wrapping an existing CLI/API?
   - Clarify: transport preference (`stdio` default, `sse`, or `streamable-http`)?

Output a summary table before proceeding:

| Component | Name | Description |
|-----------|------|-------------|
| Plugin | `<name>` | ... |
| MCP Server | `<name>` (if any) | ... |
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

## Phase 2b: Create MCP Server (if requested)

Skip this phase if the user does not need a standalone MCP server.

### 2b-1. Choose server approach

| Approach | Transport | When to use |
|----------|-----------|-------------|
| **FastMCP (Python)** | `stdio` | New server from scratch; rich tool/resource/prompt support |
| **Wrapper script** | `stdio` | Thin shell around an existing CLI or REST API |
| **Local package** (`uvx`/`npx`) | `stdio` | User has a published package to run locally |
| **Remote HTTP server** | `sse` / `streamable-http` | Server already deployed at a URL; no local process |
| **Inline definition** | n/a | Single-file tool with no separate server process needed |

### 2b-2. Write the server code (local only)

Skip this step for remote or inline approaches.

For a **FastMCP** server, create `plugins/<plugin-name>/server/server.py`:

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("<plugin-name>")

@mcp.tool()
def my_tool(arg: str) -> str:
    """Tool description shown to the model."""
    return arg

if __name__ == "__main__":
    mcp.run()  # defaults to stdio transport
```

- Keep each tool focused on one action.
- Use Python type annotations — FastMCP reflects them into the tool schema.
- Return plain values (str, dict, list); FastMCP serializes them.
- Add a `requirements.txt` in `server/` listing `mcp` and any other deps.

### 2b-3. Register in `.mcp.json`

Update the plugin's `.mcp.json` to declare the server under `mcpServers`.
Pick the block that matches the chosen approach:

**Local script (stdio):**
```json
{
  "mcpServers": {
    "<server-name>": {
      "command": "python3",
      "args": ["plugins/<plugin-name>/server/server.py"],
      "env": {}
    }
  }
}
```

**Local package via `uvx` or `npx` (stdio):**
```json
{
  "mcpServers": {
    "<server-name>": {
      "command": "uvx",
      "args": ["<package-name>"],
      "env": { "API_KEY": "${API_KEY}" }
    }
  }
}
```

**Remote server (SSE or streamable-http):**
```json
{
  "mcpServers": {
    "<server-name>": {
      "url": "https://<host>/mcp",
      "headers": { "Authorization": "Bearer ${API_KEY}" }
    }
  }
}
```
No local process is spawned; the harness connects over HTTP. Ask the user for
the URL and any required auth headers/env vars.

**Inline tool (no separate process):**
Some harnesses support declaring lightweight tools directly in `.mcp.json`
without spawning a server. Use this for trivial single-tool cases:
```json
{
  "mcpServers": {
    "<server-name>": {
      "command": "python3",
      "args": ["-c", "import sys,json; print(json.dumps({'result': sys.argv[1]}))"],
      "env": {}
    }
  }
}
```
Keep inline definitions to a single, short expression — anything complex
belongs in a real script file.

### 2b-4. Guide the user through activation

After writing the files, tell the user exactly what to do based on approach:

**For local scripts/packages:**
1. Install deps if needed: `pip install -r plugins/<plugin-name>/server/requirements.txt`
   (or `uv pip install ...` if they use uv)
2. Restart Claude Code / the harness so it picks up the new `mcpServers` entry.
3. Verify the server appears: run `/mcp` in Claude Code and confirm the server name is listed.

**For remote servers:**
1. Confirm the URL is reachable: `curl -I <url>`
2. Set any required env vars (API keys, tokens) in the shell or `.env`.
3. Restart Claude Code / the harness.
4. Verify with `/mcp` — the remote server should appear as connected.

> **Why restart is required**: The harness reads `.mcp.json` at startup. A running instance
> won't see changes until restarted. Guide the user explicitly — never assume they know.

### 2b-5. Expose server tools in skill declarations

If the plugin's skills will call tools from this MCP server, add them to `requires_mcp`
in each relevant SKILL.md frontmatter:

```yaml
requires_mcp:
  - <server-name>__<tool-name>
```

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
- If `.mcp.json` declares `mcpServers`, confirm the referenced command/script exists

If the plugin includes an MCP server (Phase 2b), also verify manually:
- The server script is executable and runs without import errors:
  `python3 plugins/<plugin-name>/server/server.py --help` (or equivalent)
- The `mcpServers` entry in `.mcp.json` uses the correct command and args

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
