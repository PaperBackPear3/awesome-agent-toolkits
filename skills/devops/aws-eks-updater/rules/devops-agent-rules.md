# DevOps Agent Guidance

- Before starting a Kubernetes upgrade task, check whether a relevant skill is available.
  Load the skill and follow its phased approach rather than improvising.
- Use the DevOps MCP Server for cluster inventory, Terraform scanning, and prerequisite
  checks. It provides structured output and consistent error handling.
- Never run destructive commands (`kubectl apply`, `helm upgrade`, `terraform apply`,
  `git push`) without explicit user confirmation.
- Update one component at a time. After each change, stop and let the user verify
  before proceeding to the next.
- When uncertain about version compatibility, consult the compatibility matrix resources
  available through the MCP server.
- Prefer infrastructure-as-code (Terraform) over direct CLI commands for persistent changes.
