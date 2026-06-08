# DevOps Core Plugin

Interactive, safety-first skills for updating Kubernetes clusters (EKS and AKS).

## Installation

### Claude Code

```bash
claude plugin add github:PaperBackPear3/awesome-agent-toolkits/plugins/devops-core
```

### Codex

Add to your `.codex/plugins.json`:

```json
{
  "plugins": ["github:PaperBackPear3/awesome-agent-toolkits/plugins/devops-core"]
}
```

### Manual

1. Clone this repository
2. Symlink or copy `plugins/devops-core/` into your agent's plugin directory
3. The MCP server starts automatically via `.mcp.json`

## MCP Server — how it works

The server ships as a **pre-bundled single file** (`server/bundle.mjs`). No `npm install` or build step is required after plugin installation — the `.mcp.json` just runs:

```json
{ "command": "node", "args": ["server/bundle.mjs"] }
```

### Rebuilding after source changes

If you modify `server/server.ts` or the UI source (`server/src/`), rebuild with:

```bash
cd server

# Rebuild the React UI bundle (dist/mcp-app.html)
npm run build:ui

# Rebuild the server bundle (bundle.mjs)
npm run build:server
```

Then commit both `dist/mcp-app.html` and `server/bundle.mjs` so the plugin stays self-contained.

## Included Skills

- **aws-eks-updater** — Guided EKS cluster upgrades (control plane, add-ons, Helm)
- **azure-aks-updater** — Guided AKS cluster upgrades (control plane, add-ons, Helm)

## MCP Server

The plugin includes an MCP server providing tools for:
- Cluster add-on inventory (AWS/Azure APIs)
- Terraform scanning for declared versions
- Helm release inventory
- Prerequisite checks
- Skill discovery (`list_skills`, `retrieve_skill`)
