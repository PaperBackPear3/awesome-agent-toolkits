# Agent Skills Toolkit

A framework for packaging business logic as discoverable, composable agent skills — served via MCP to Claude Code, Codex, GitHub Copilot, and other AI coding agents.

Skills can encode expertise from **any domain**: DevOps, security, data engineering, finance, compliance, and more. Each skill is a self-contained instruction package that an agent loads at runtime to perform complex, multi-step tasks safely.

## Quick Start

### Claude Code / GitHub Copilot

Add the marketplace, then install one or more plugins:

```bash
/plugin marketplace add PaperBackPear3/awesome-agent-toolkits
/plugin install devops-core@awesome-agent-toolkits
```

Browse everything available:

```bash
/plugin marketplace browse awesome-agent-toolkits
```

### Codex

```json
{
  "plugins": [
    "github:PaperBackPear3/awesome-agent-toolkits/plugins/devops-core"
  ]
}
```

### Manual (any agent)

Copy a skill into your agent's skill directory:

```bash
cp -r skills/devops/aws-eks-updater ~/.claude/skills/
```

Or point your agent at the Agent Toolkit MCP server to augment its harness with persistent notes, todos, timers, and a cross-project registry:

```json
{
  "mcpServers": {
    "agent-toolkit": {
      "command": "uvx",
      "args": ["agent-toolkit-mcp-server@latest"]
    }
  }
}
```

## What's Included

### Plugins

| Plugin                  | Category     | Description                                                                                    |
| ----------------------- | ------------ | ---------------------------------------------------------------------------------------------- |
| `devops-core`           | DevOps       | Kubernetes cluster update skills (EKS + AKS) with MCP tools                                    |
| `github-actions-writer` | DevOps       | Author, update, and migrate GitHub Actions workflows with multi-environment release pipelines  |
| `harness-addons`        | Productivity | Exposes the agent-toolkit MCP (notes, todos, timers, projects) as harness add-ons              |
| `post-work-checks`      | Productivity | Per-project post-work todo lists that run when the agent finishes a task                       |
| `plugin-factory`        | Meta         | Meta-plugin for scaffolding new plugins and skills inside this repository                      |

### Skills

| Skill                                                                   | Category | Description                                                                          |
| ----------------------------------------------------------------------- | -------- | ------------------------------------------------------------------------------------ |
| [`aws-eks-updater`](skills/devops/aws-eks-updater/SKILL.md)             | devops   | Interactive, safety-first EKS cluster upgrades                                       |
| [`azure-aks-updater`](skills/devops/azure-aks-updater/SKILL.md)         | devops   | Interactive, safety-first AKS cluster upgrades                                       |
| [`github-actions-writer`](skills/devops/github-actions-writer/SKILL.md) | devops   | Create, update, and migrate GitHub Actions workflows for complex release pipelines   |
| [`agent-toolkit`](skills/meta/agent-toolkit/SKILL.md)                   | meta     | Drive the agent-toolkit MCP (notes, todos, timers, projects)                         |
| [`plugin-factory`](skills/meta/plugin-factory/SKILL.md)                 | meta     | Scaffold and validate new plugins/skills in this repository                          |
| [`post-work-checks`](skills/meta/post-work-checks/SKILL.md)             | meta     | Run a project's post-work checklist after the agent finishes a task                  |

### MCP Server

The `agent-toolkit-mcp-server` (published on PyPI; run via `uvx`) augments an agent's harness with capabilities Claude Code does not provide natively:

| Area         | What it adds                                                                          | Tools |
| ------------ | ------------------------------------------------------------------------------------- | ----- |
| **Notes**    | Persistent, named markdown notes (plans, designs, scratch) with tags, revisions, FTS5 | 16    |
| **Todos**    | Cross-session todo lists, optionally project-scoped, with blockers and tags           | 11    |
| **Timers**   | Durable scheduled/recurring wake-ups; agents poll fired events                        | 7     |
| **Projects** | Cross-project registry — register repos/folders by name, attach markdown docs         | 10    |

All state lives under `~/.agent-toolkit/` (overridable via `AGENT_TOOLKIT_HOME`). See [`mcp-server/README.md`](mcp-server/README.md) for the full tool index and storage layout.

## Repository Structure

> This layout is **extensible** — add new domains by creating a directory under `skills/` and a corresponding plugin under `plugins/`.

```
.claude-plugin/         # Claude Code marketplace index
.agents/plugins/        # Kiro/generic agent marketplace index
plugins/                # Installable plugin packages
  devops-core/            #   ├─ EKS + AKS updater skills
  github-actions-writer/  #   ├─ GitHub Actions workflow authoring
  harness-addons/         #   ├─ Wires up the agent-toolkit MCP
  plugin-factory/         #   ├─ Meta-plugin: scaffold new plugins/skills
  post-work-checks/       #   └─ Per-project post-work checklist runner
skills/                 # Canonical skill definitions
  devops/                 #   ├─ DevOps skills
  meta/                   #   └─ Meta skills (toolkit, factory, post-work)
  manifest.json           #   skill registry — keep in sync when adding/removing
rules/                  # Agent behavior rules
mcp-server/             # agent-toolkit MCP server (Python, stdlib-friendly)
docs/                   # Documentation
```

## Documentation

| Doc                                                 | What it covers                                     |
| --------------------------------------------------- | -------------------------------------------------- |
| [Installation Guide](docs/INSTALL.md)               | All install methods (plugin, MCP, manual, symlink) |
| [Contributing: Add New Stuff](docs/CONTRIBUTING.md) | How to add skills, tools, plugins, rules           |
| [Quick Reference Guide](docs/GUIDE.md)              | Architecture, concepts, conventions                |
| [Best Practices](docs/BEST_PRACTICES.md)            | MCP vs Agents vs Tools vs Skills deep-dive         |
| [MCP Server](mcp-server/README.md)                  | Server setup, storage layout, and available tools  |
| [Agent Rules](rules/devops-agent-rules.md)          | Behavioral guardrails                              |

## License

MIT
