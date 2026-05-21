# github-actions-writer

Interactive, safety-first skill for creating, updating, and migrating GitHub Actions workflows.

## What it does

- Inventories existing workflows and detects CI configs from other systems
- Designs multi-environment pipelines with OIDC, matrices, and approval gates
- Generates workflow YAML one file at a time with mandatory review steps
- Validates workflows for structural correctness and security best practices
- Migrates from Jenkins, GitLab CI, CircleCI, and Azure Pipelines

## Safety guarantees

- Never commits, pushes, or merges without explicit user instruction
- Edits one workflow file at a time and hands off for review after each
- Always pins third-party actions to full SHA
- Never stores secrets inline — always uses GitHub Secrets or OIDC

## Installation

### Claude Code

```bash
claude plugin add github:PaperBackPear3/awesome-agent-toolkits/plugins/github-actions-writer
```

### Codex

Add to your `.codex/plugins.json`:

```json
{
  "plugins": ["github:PaperBackPear3/awesome-agent-toolkits/plugins/github-actions-writer"]
}
```

### Manual

1. Clone this repository
2. Symlink or copy `plugins/github-actions-writer/` into your agent's plugin directory

## Included Skills

- **github-actions-writer** — End-to-end GitHub Actions workflow authoring and migration

## Required MCP Servers

The skill requires the **GitHub MCP server** to be configured separately. It uses GitHub
API tools for reading workflow files, secrets, and environments.

```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": { "GITHUB_PERSONAL_ACCESS_TOKEN": "<your-token>" }
    }
  }
}
```

## MCP Tools (bundled)

| Tool | Description |
|------|-------------|
| `devops__gha_list_workflows` | List and summarise workflow files in `.github/workflows/` |
| `devops__gha_validate` | Validate a workflow YAML for correctness and security |
| `devops__ci_detect_configs` | Detect and parse Jenkins/GitLab CI/CircleCI/Azure Pipelines configs |
