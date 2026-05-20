# Agent Skills Toolkit

A framework for packaging business logic as discoverable, composable agent skills — served via MCP to Claude Code, Codex, GitHub Copilot, and other AI coding agents.

Skills can encode expertise from **any domain**: DevOps, security, data engineering, finance, compliance, and more. Each skill is a self-contained instruction package that an agent loads at runtime to perform complex, multi-step tasks safely.

## Quick Start

### Claude Code / GitHub Copilot

Add the Marketplace

```bash
/plugin marketplace add PaperBackPear3/awesome-agent-toolkits
```

Install a plugin (e.g. the DevOps plugin — one of the available plugins):

```bash
plugin add github:PaperBackPear3/awesome-agent-toolkits/plugins/devops-core
```

or browse the Marketplace

```bash
/plugin marketplace browse awesome-agent-toolkit
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
cp -r skills/devops/aws-eks-updater ~/.agents/skills/
```

Or point your agent at the MCP server to augment its harness with persistent notes, todos, timers, and a cross-project registry:

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

| Plugin        | Category                 | Description                                                 | Status       |
| ------------- | ------------------------ | ----------------------------------------------------------- | ------------ |
| `devops-core` | DevOps                   | Kubernetes cluster update skills (EKS + AKS) with MCP tools | ✅ Available |
| _more coming_ | Security, Data, Finance… | Community and first-party plugins                           | 🚧 Planned   |

### Skills (via `devops-core`)

| Skill                                                           | Description                                    |
| --------------------------------------------------------------- | ---------------------------------------------- |
| [`aws-eks-updater`](skills/devops/aws-eks-updater/SKILL.md)     | Interactive, safety-first EKS cluster upgrades |
| [`azure-aks-updater`](skills/devops/azure-aks-updater/SKILL.md) | Interactive, safety-first AKS cluster upgrades |

### MCP Server

The MCP server (published as `agent-toolkit-mcp-server` via uvx) augments an agent's harness with capabilities Claude Code does not provide natively:

| Area         | What it adds                                                                    | Tools |
| ------------ | ------------------------------------------------------------------------------- | ----- |
| **Notes**    | Persistent, named markdown notes (plans, designs, scratch) with tags & revisions | 15    |
| **Todos**    | Cross-session todo lists, optionally project-scoped, with blockers              | 11    |
| **Timers**   | Durable scheduled/recurring wake-ups; agents poll fired events                  | 7     |
| **Projects** | Cross-project registry — register repos/folders by name and reference them anywhere | 6     |

All state lives under `~/.agent-toolkit/` (overridable via `AGENT_TOOLKIT_HOME`). See [`mcp-server/README.md`](mcp-server/README.md) for the full tool index and storage layout, and [`docs/CLAUDE_CODE_CAPABILITIES.md`](docs/CLAUDE_CODE_CAPABILITIES.md) for what's already built into Claude Code (so you know what this MCP intentionally does not duplicate).

## Repository Structure

> This layout is **extensible** — add new domains by creating a directory under `skills/` and a corresponding plugin under `plugins/`.

```
.claude-plugin/         # Claude Code marketplace index
.agents/plugins/        # Kiro/generic agent marketplace index
plugins/                # Installable plugin packages
  devops-core/          #   └─ DevOps plugin (skills + MCP config)
skills/                 # Canonical skill definitions
  devops/               #   └─ DevOps skills (EKS, AKS)
    aws-eks-updater/
    azure-aks-updater/
rules/                  # Agent behavior rules
mcp-server/             # MCP server implementation
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
| [Claude Code Capabilities](docs/CLAUDE_CODE_CAPABILITIES.md) | Reference of built-in harness tools (and gaps the MCP fills) |
| [Agent Rules](rules/devops-agent-rules.md)          | Behavioral guardrails                              |

## License

MIT
