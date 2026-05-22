# Installation Guide

## Prerequisites

- **An AI coding agent** — Claude Code, Codex, Cursor, Kiro, or any MCP-compatible agent
- **Cloud CLIs** (only for skills that need them): `aws`, `az`, `kubectl`, `helm`, `terraform`

---

## Part 1: Installing Skills

Skills are instruction packages for your agent. Install them via plugin or manually.

### Option A: Plugin Install (Recommended)

One command gives your agent the bundled skills with no manual config.

**Claude Code**

```bash
/plugin marketplace add PaperBackPear3/awesome-agent-toolkits
/plugin install devops-core@awesome-agent-toolkits
```

Other plugins published in the same marketplace:

```bash
/plugin install github-actions-writer@awesome-agent-toolkits
/plugin install harness-addons@awesome-agent-toolkits
/plugin install post-work-checks@awesome-agent-toolkits
/plugin install plugin-factory@awesome-agent-toolkits
```

**Codex**

```bash
codex plugin marketplace add PaperBackPear3/awesome-agent-toolkits
# Then run /plugins in Codex to install devops-core
```

### Option B: Manual Skill Copy

Copy individual skills into your agent's skill directory.

```bash
git clone https://github.com/PaperBackPear3/awesome-agent-toolkits.git ~/skills
```

| Agent | Skills directory |
|-------|-----------------|
| Claude Code | `~/.claude/skills/` or `.claude/skills/` (project) |
| Codex | `~/.codex/skills/` or `.agents/skills/` (project) |
| GitHub Copilot | `~/.agents/skills/` |
| Cursor | `~/.cursor/skills/` or `.cursor/skills/` (project) |
| Kiro | `~/.kiro/skills/` or `.kiro/skills/` (project) |

```bash
# Example: install EKS updater for Claude Code
mkdir -p ~/.claude/skills
cp -r ~/skills/skills/devops/aws-eks-updater ~/.claude/skills/
```

### Option C: Symlinks (for development)

If you want to edit skills and have changes reflected immediately:

```bash
mkdir -p ~/.claude/skills
ln -s ~/skills/skills/devops/aws-eks-updater ~/.claude/skills/aws-eks-updater
ln -s ~/skills/skills/devops/azure-aks-updater ~/.claude/skills/azure-aks-updater
```

---

## Part 2: Installing the Agent Toolkit MCP (Optional, Separate)

The **Agent Toolkit MCP** is a separate package (`agent-toolkit-mcp-server`) that adds
capabilities not built into agents — persistent notes, todos, timers, and a cross-project
registry. It is independent of this skills repository and must be installed on its own.

See the [mcp-server README](../mcp-server/README.md) for the full tool index.

### Configure your agent

Add to your agent's MCP config (`~/.claude/settings.json`, project `.mcp.json`, etc.):

**Claude Code**

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

**VS Code (GitHub Copilot)** — `.vscode/mcp.json`

```json
{
  "servers": {
    "agent-toolkit": {
      "command": "uvx",
      "args": ["agent-toolkit-mcp-server@latest"]
    }
  }
}
```

**Claude Desktop** — `claude_desktop_config.json`

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

### Data location

All state is stored under `~/.agent-toolkit/` by default. Override with the
`AGENT_TOOLKIT_HOME` environment variable.

---

## Verifying Skills Installation

After installing skills, test by asking your agent:

- *"Help me update my EKS cluster"* → should trigger `aws-eks-updater`
- *"Update my AKS cluster"* → should trigger `azure-aks-updater`
- *"Create a GitHub Actions workflow for ..."* → should trigger `github-actions-writer`
- *"Save this as a note / add a todo"* → should trigger `agent-toolkit`
- *"Run post-work checks"* → should trigger `post-work-checks`

---

## Uninstalling

| What | How |
|------|-----|
| Plugin | `/plugin uninstall devops-core@awesome-agent-toolkits` |
| Manual skill copy | Delete the skill directory |
| Symlink | Remove the symlink |
| Agent Toolkit MCP | Remove the server entry from your MCP config |
