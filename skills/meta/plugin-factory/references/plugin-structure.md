# Plugin Structure Reference

## Directory Layout

```
plugins/<plugin-name>/
├── .claude-plugin/
│   └── plugin.json          ← Claude Code marketplace metadata
├── .codex-plugin/
│   └── plugin.json          ← Codex marketplace metadata
├── .mcp.json                ← MCP server configuration
├── skills/
│   ├── <skill-a>            ← Symlink → ../../../skills/<category>/<skill-a>
│   └── <skill-b>            ← Symlink → ../../../skills/<category>/<skill-b>
└── README.md                ← Human-readable description + install instructions
```

---

## `.claude-plugin/plugin.json`

Required fields:

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Plugin identifier (kebab-case) |
| `version` | string | Semver (e.g., `"1.0.0"`) |
| `description` | string | What the plugin provides (1–2 sentences) |
| `author` | object | `{ "name": "AuthorName" }` |
| `homepage` | string | URL to the repository or docs |
| `repository` | string | Git repository URL |
| `license` | string | SPDX license identifier |
| `keywords` | array | Trigger/discovery keywords |

Example:

```json
{
  "name": "devops-core",
  "version": "1.0.0",
  "description": "Interactive, safety-first skills for updating Kubernetes clusters (EKS and AKS).",
  "author": { "name": "PaperBackPear3" },
  "homepage": "https://github.com/PaperBackPear3/awesome-agent-toolkits",
  "repository": "https://github.com/PaperBackPear3/awesome-agent-toolkits",
  "license": "MIT",
  "keywords": ["devops", "kubernetes", "eks", "aks", "terraform"]
}
```

---

## `.codex-plugin/plugin.json`

Same core fields as the Claude variant, plus Codex-specific UI metadata:

| Additional Field | Type | Description |
|-----------------|------|-------------|
| `skills` | string | Relative path to skills directory (e.g., `"./skills/"`) |
| `mcpServers` | string | Relative path to `.mcp.json` |
| `interface` | object | Display metadata for the Codex marketplace |
| `interface.displayName` | string | Human-readable plugin name |
| `interface.shortDescription` | string | One-liner for listing views |
| `interface.longDescription` | string | Full description for detail pages |
| `interface.developerName` | string | Author display name |
| `interface.category` | string | Primary category |
| `interface.capabilities` | array | e.g., `["Read"]` |

Example:

```json
{
  "name": "devops-core",
  "version": "1.0.0",
  "description": "Interactive, safety-first skills for updating Kubernetes clusters (EKS and AKS).",
  "author": { "name": "PaperBackPear3" },
  "homepage": "https://github.com/PaperBackPear3/awesome-agent-toolkits",
  "repository": "https://github.com/PaperBackPear3/awesome-agent-toolkits",
  "license": "MIT",
  "skills": "./skills/",
  "mcpServers": "./.mcp.json",
  "interface": {
    "displayName": "DevOps Core",
    "shortDescription": "Kubernetes cluster update skills with MCP tools",
    "longDescription": "Safety-first skills for updating AWS EKS and Azure AKS clusters.",
    "developerName": "PaperBackPear3",
    "category": "DevOps",
    "capabilities": ["Read"]
  }
}
```

---

## `.mcp.json`

Plugins do not bundle an MCP server. This file must always be present but declares no servers:

```json
{
  "mcpServers": {}
}
```

If your skill uses MCP tools, declare them in the skill's `tools/mcp_tools.json`. The
**Agent Toolkit MCP** (`agent-toolkit-mcp-server`) — which provides notes, todos, timers,
and project registry — is a separate package installed independently by the user. Do not
reference it here.

---

## `skills/` Directory

Contains **relative symlinks** pointing back to the canonical skill location:

```bash
cd plugins/<plugin-name>/skills/
ln -s ../../../skills/<category>/<skill-name> <skill-name>
```

Example:

```
plugins/devops-core/skills/
├── aws-eks-updater  → ../../../skills/devops/aws-eks-updater
└── azure-aks-updater → ../../../skills/devops/azure-aks-updater
```

Always use relative paths so the repo works when cloned to any location.

---

## `README.md`

Include:

1. Plugin name and one-line description
2. List of included skills with brief descriptions
3. Installation command (e.g., `claude plugin add PaperBackPear3/awesome-agent-toolkits/plugins/<name>`)
4. Link to individual skill documentation

---

## Registration Files

Both files live at the **repository root** and list all available plugins:

### `.claude-plugin/marketplace.json`

```json
{
  "plugins": [
    {
      "name": "devops-core",
      "path": "plugins/devops-core",
      "description": "..."
    }
  ]
}
```

### `.agents/plugins/marketplace.json`

Same structure, used by Codex for plugin discovery. Keep both files in sync when adding or removing plugins.
