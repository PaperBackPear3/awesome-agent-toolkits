# devops-core

Interactive, safety-first skills for upgrading Kubernetes clusters (EKS and AKS). Covers prerequisite checks, Terraform scanning, add-on inventory, Helm release management, changelog research, and guided upgrades with a React UI.

## Installation

```bash
claude plugin add github:PaperBackPear3/awesome-agent-toolkits/plugins/devops-core
```

On first use the plugin launcher (`bin/devops-core-mcp`) downloads the MCP server from npm via `npx`. Subsequent starts use the npm cache — no internet required.

**Requirements:** Node.js ≥ 18 (Homebrew, NVM, or Volta — the launcher finds it automatically).

## Included skills

| Skill | Description |
|---|---|
| `aws-eks-updater` | Guided EKS control-plane, add-on, and Helm upgrades |
| `azure-aks-updater` | Guided AKS control-plane, add-on, and Helm upgrades |

---

## Development

### Local dev (Docker — recommended)

Docker provides a hot-reload environment with your AWS and kubeconfig credentials mounted read-only.

```bash
cd server
docker-compose up
```

The container runs `tsx watch server.ts` and rebuilds automatically when you edit `server.ts` or `src/`.

### Local dev (without Docker)

```bash
cd server
npm install
npm run dev:local   # npx tsx server.ts
```

### Building for release

```bash
cd server
npm run build       # builds dist/mcp-app.html (React UI) + bundle.mjs (MCP server)
```

`bundle.mjs` and `dist/` are **build artifacts** — they are `.gitignore`d and only exist after a build. Run the build before publishing to npm.

### Publishing to npm

```bash
cd server
npm run build       # prepublishOnly also runs this automatically
npm publish
```

The published package contains only `bundle.mjs` and `dist/` (see `.npmignore`). After publishing, users who install the plugin will pick up the new version on the next `npx` cache expiry.

---

## Architecture

```
plugins/devops-core/
├── bin/
│   └── devops-core-mcp   # Plugin launcher (in PATH via Claude Code)
├── server/
│   ├── server.ts          # MCP server source
│   ├── src/               # React UI source
│   ├── Dockerfile         # Multi-stage: dev (tsx watch) + prod (node bundle)
│   ├── docker-compose.yml # Local dev workflow
│   ├── package.json       # npm package config (name: devops-core-mcp)
│   └── .gitignore         # Excludes bundle.mjs, dist/ (build artifacts)
└── skills/
    ├── aws-eks-updater/
    └── azure-aks-updater/
```

### How the launcher works

Claude Code adds `{plugin_dir}/bin/` to `PATH`, so `devops-core-mcp` is always found as an absolute path. The launcher:

1. **Dev mode** — if `server/bundle.mjs` exists locally (you built it), runs it directly with `node`.
2. **Prod mode** — otherwise runs `npx --yes devops-core-mcp` to fetch the published npm package.

This means end users get automatic updates from npm, while plugin developers test against their local build.

### MCP server tools

| Tool | Visible to | Description |
|---|---|---|
| `eks_setup` | agent + UI | Setup wizard: pick AWS profile and kubeconfig context |
| `eks_inventory` | agent + UI | Display add-on drift, installed add-ons, Helm releases |
| `eks_plan` | agent + UI | Interactive upgrade plan checklist |
| `eks_summary` | agent + UI | Final upgrade summary |
| `eks_list_profiles` | UI only | List AWS CLI profiles |
| `eks_list_contexts` | UI only | List kubeconfig contexts |
| `eks_get_identity` | UI only | Get AWS caller identity |
| `eks_confirm_context` | UI only | Record confirmed cluster context |
| `eks_confirm_plan` | UI only | Record user-approved plan items |
