# Best Practices: MCP, Agents, Tools, and Skills

A practical guide for developers building in the AI-assisted development ecosystem.

---

## 1. Conceptual Model

### What is MCP (Model Context Protocol)

MCP is an open standard for exposing **tools**, **resources**, and **prompts** to AI models over a lightweight JSON-RPC transport. Think of it as a USB-C port for AI — a universal interface that lets any compliant client (agent, IDE, chat UI) discover and invoke capabilities from any compliant server.

```
┌─────────────┐       JSON-RPC        ┌─────────────┐
│  AI Client  │◄─────────────────────►│  MCP Server │
│  (Agent)    │  tools/resources/prompts│  (Provider) │
└─────────────┘                        └─────────────┘
```

Key properties:
- **Discoverable** — clients list available tools at runtime
- **Typed** — inputs/outputs have JSON Schema definitions
- **Stateless per call** — each tool invocation is independent
- **Transport-agnostic** — stdio, HTTP+SSE, WebSocket

### What are Agents

Agents are autonomous AI systems that pursue goals by reasoning about context, selecting actions, and iterating until a task is complete. They differ from simple chat by having:

- **Agency** — they decide what to do next without human prompting each step
- **Tool use** — they invoke external capabilities (via MCP or direct function calls)
- **Memory** — they maintain context across multiple steps within a session
- **Judgment** — they interpret results and adapt their approach

Examples: GitHub Copilot coding agent, Claude Code, custom task agents.

### What are Tools

Tools are individual, well-scoped capabilities an agent can invoke. A tool is a function with:

- A **name** (e.g., `terraform-list_workspaces`)
- An **input schema** (JSON Schema for parameters)
- An **output** (structured result or error)
- A **description** (natural language for the agent to understand when/how to use it)

Tools are the atoms of agent capability. They should do one thing well.

### What are Skills

Skills are **higher-level instruction packages** that guide agent behavior through multi-step workflows. Unlike tools (which execute a single operation), skills encode:

- **Phases** — ordered sequences of activities
- **Decision logic** — when to branch, retry, or escalate to the user
- **Safety constraints** — hard rules the agent must never violate
- **Domain knowledge** — compatibility matrices, naming conventions, known pitfalls
- **Sub-agent delegation** — which parts to fan out in parallel

A skill is not code the agent runs — it's a prompt the agent follows.

### How They Compose

```
┌─────────────────────────────────────────────────────────┐
│                        SKILL                             │
│  (Phase-based playbook loaded into agent context)        │
│                                                          │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐            │
│  │Sub-Agent │   │Sub-Agent │   │Sub-Agent │  (fan-out)  │
│  └────┬─────┘   └────┬─────┘   └────┬─────┘            │
│       │               │               │                  │
└───────┼───────────────┼───────────────┼──────────────────┘
        │               │               │
   ┌────▼────┐    ┌────▼────┐    ┌────▼────┐
   │MCP Tool │    │MCP Tool │    │  bash   │
   └─────────┘    └─────────┘    └─────────┘
```

**Skills** orchestrate **Agents** which call **Tools** (some exposed via **MCP**).

---

## 2. When to Use What

### MCP Tools

Use MCP tools when the capability is:

| Characteristic | Fit for MCP Tool |
|---|---|
| Stateless | ✅ No session state between calls |
| Well-defined I/O | ✅ Clear input schema, predictable output |
| Reusable across contexts | ✅ Useful to multiple agents/skills |
| Discoverable | ✅ Agents can find and use without special prompting |
| Fast | ✅ Completes in seconds, not minutes |

**Good for:** data retrieval, validation, transformation, API queries, file parsing.

```jsonc
// Example: A good MCP tool — focused, stateless, reusable
{
  "name": "eks_get_addon_versions",
  "description": "Returns available versions for an EKS add-on, filtered by cluster Kubernetes version",
  "inputSchema": {
    "type": "object",
    "properties": {
      "addon_name": { "type": "string", "description": "e.g., vpc-cni, coredns" },
      "kubernetes_version": { "type": "string", "description": "e.g., 1.29" }
    },
    "required": ["addon_name", "kubernetes_version"]
  }
}
```

### Agent Skills

Use skills when the workflow:

| Characteristic | Fit for Skill |
|---|---|
| Multi-step | ✅ Multiple phases with dependencies |
| Requires judgment | ✅ Agent must interpret results and decide |
| Context-dependent | ✅ Decisions depend on accumulated state |
| Needs user interaction | ✅ Confirmation gates, preference elicitation |
| Has safety constraints | ✅ "Never apply without confirmation" |

**Good for:** cluster upgrades, migrations, debugging sessions, refactoring workflows.

### Sub-Agents

Use sub-agents when work is:

| Characteristic | Fit for Sub-Agent |
|---|---|
| Parallelizable | ✅ Multiple independent research threads |
| Needs isolation | ✅ Separate context window to avoid pollution |
| Well-scoped | ✅ Clear deliverable the sub-agent can produce |

**Good for:** changelog research across repos, multi-service scanning, parallel validation.

### Decision Matrix

```
Is it a single, stateless operation with clear I/O?
  → MCP Tool

Is it a multi-step workflow requiring judgment and user interaction?
  → Skill

Is it a parallelizable chunk of research/work within a skill?
  → Sub-Agent (delegated by the skill)

Is it a reusable prompt template for a common task?
  → MCP Prompt

Is it static reference data an agent might need?
  → MCP Resource
```

---

## 3. MCP Server Design Best Practices

### Tool Naming Conventions

Use `verb_noun` or `namespace-verb_noun` patterns:

```
✅ Good:
  list_workspaces
  get_addon_versions
  terraform-create_run
  eks-scan_cluster

❌ Bad:
  workspaces          (no verb — is this list? create? delete?)
  doTheThing          (camelCase, vague)
  get_all_the_data    (too broad)
```

**Rules:**
- Lowercase with underscores (snake_case)
- Namespace with hyphen prefix for multi-domain servers
- Verb first: `list_`, `get_`, `create_`, `update_`, `delete_`, `search_`, `validate_`
- Nouns should be domain-specific and unambiguous

### Input Schema Design

```jsonc
{
  "inputSchema": {
    "type": "object",
    "properties": {
      "cluster_name": {
        "type": "string",
        "description": "Name of the EKS cluster (not ARN)"  // ← Be specific
      },
      "region": {
        "type": "string",
        "description": "AWS region (e.g., us-east-1)",
        "default": "us-east-1"  // ← Sensible defaults
      },
      "include_deprecated": {
        "type": "boolean",
        "description": "Whether to include deprecated add-on versions",
        "default": false  // ← Safe default
      }
    },
    "required": ["cluster_name"]  // ← Only truly required params
  }
}
```

**Rules:**
- Every property gets a `description` — the agent reads these to decide how to call you
- Use `default` values so agents don't need to guess
- Mark only genuinely required fields as `required`
- Use enums for constrained values: `"enum": ["plan_only", "plan_and_apply"]`
- Prefer flat schemas over deeply nested objects

### Output Structure

Return JSON with a consistent envelope:

```jsonc
// Success
{
  "status": "success",
  "data": {
    "addons": [
      { "name": "vpc-cni", "version": "v1.18.1", "compatible": true }
    ]
  },
  "metadata": {
    "cluster": "my-cluster",
    "timestamp": "2024-01-15T10:30:00Z"
  }
}

// Error
{
  "status": "error",
  "error": {
    "code": "CLUSTER_NOT_FOUND",
    "message": "Cluster 'my-cluster' not found in region us-east-1",
    "suggestion": "Check cluster name with: aws eks list-clusters --region us-east-1"
  }
}
```

**Rules:**
- Always return valid JSON (not mixed text/JSON)
- Include enough context for the agent to act on the result
- Structured errors with codes, messages, and suggestions
- Never return raw stack traces — translate to actionable error info

### Error Handling

```python
# ❌ Bad — crashes with raw exception
def list_clusters(region):
    return boto3.client('eks', region_name=region).list_clusters()

# ✅ Good — structured error response
def list_clusters(region):
    try:
        client = boto3.client('eks', region_name=region)
        response = client.list_clusters()
        return {"status": "success", "data": {"clusters": response["clusters"]}}
    except client.exceptions.ClientError as e:
        return {
            "status": "error",
            "error": {
                "code": "AWS_API_ERROR",
                "message": str(e),
                "suggestion": "Verify AWS credentials and region"
            }
        }
```

### Resources vs Tools vs Prompts

| MCP Primitive | Use When | Example |
|---|---|---|
| **Tool** | Agent needs to perform an action or query | `list_workspaces`, `create_run` |
| **Resource** | Agent needs reference data (read-only, often large) | Compatibility matrix, config file |
| **Prompt** | Reusable prompt template for common tasks | "Upgrade EKS cluster" template |

**Resources** are like GET endpoints — static or slowly-changing data the agent reads.  
**Tools** are like POST endpoints — they do something or query with parameters.  
**Prompts** are like skill templates — they structure how the agent approaches a task.

### Security

1. **Never auto-apply** — destructive operations require explicit user confirmation
2. **Principle of least privilege** — request only the permissions you need
3. **Validate inputs** — don't trust agent-provided parameters blindly
4. **Audit trail** — log what was invoked and by whom
5. **Idempotency** — tools should be safe to retry
6. **Read before write** — always offer a plan/preview before mutations

```jsonc
// Tool that modifies infrastructure should have a dry_run option
{
  "name": "apply_terraform_plan",
  "inputSchema": {
    "properties": {
      "workspace": { "type": "string" },
      "dry_run": {
        "type": "boolean",
        "default": true,  // ← Safe by default
        "description": "If true, shows what would change without applying"
      }
    }
  }
}
```

### Versioning and Backwards Compatibility

- Add new optional fields — never remove or rename existing ones
- Use `deprecated: true` in schema for fields being phased out
- Version your server (`1.0.0`) and document breaking changes
- If you must break compatibility, use a new tool name (e.g., `list_workspaces_v2`)

---

## 4. Composing MCP + Skills + Agents

### Pattern: Skill as Orchestrator, MCP Tools as Data Layer

The skill defines *what* to do and *in what order*. MCP tools provide the data.

```markdown
<!-- In SKILL.md -->
## PHASE 2 — Inventory

1. Call `eks-list_addons` to get installed add-on versions
2. Call `terraform-scan_modules` to get declared versions
3. Compare installed vs declared → find drift
4. Present drift table to user for confirmation before proceeding
```

The skill never reimplements data retrieval — it delegates to MCP tools and focuses on orchestration logic, safety gates, and user interaction.

### Pattern: MCP Prompts as Skill Discovery

MCP prompts can serve as lightweight skill entry points:

```jsonc
{
  "name": "upgrade_eks_cluster",
  "description": "Interactive workflow to upgrade an EKS cluster safely",
  "arguments": [
    { "name": "cluster_name", "description": "Target cluster", "required": true }
  ]
}
```

When the agent receives this prompt, it loads the full skill (SKILL.md) which contains the detailed phase-based playbook.

### Pattern: Agent Fan-Out with MCP Tools

Sub-agents run in parallel, each calling MCP tools independently:

```markdown
<!-- In agents/changelog-researcher.md -->
For each add-on in the upgrade list:
1. Call `github-get_file_contents` to fetch CHANGELOG.md
2. Parse entries between current and target version
3. Flag any line containing "BREAKING", "removed", or "deprecated"
4. Return structured findings
```

The orchestrating skill launches N sub-agents in parallel, each researching one add-on's changelog via MCP tools.

### Anti-Patterns

#### ❌ Orchestration logic inside MCP tools

```python
# BAD — this tool is doing workflow orchestration
def upgrade_cluster(cluster_name):
    addons = list_addons(cluster_name)
    for addon in addons:
        changelog = fetch_changelog(addon)
        if has_breaking_changes(changelog):
            # Now what? Can't ask user for confirmation from inside a tool
            pass
        apply_upgrade(addon)
```

Tools should be stateless atoms. Orchestration belongs in the skill/agent layer.

#### ❌ Tools that are too coarse-grained

```jsonc
// BAD — does too many things, can't be reused in other contexts
{
  "name": "analyze_and_upgrade_everything",
  "description": "Scans cluster, checks changelogs, and applies all upgrades"
}
```

Break it into composable pieces: `scan_cluster`, `check_changelog`, `plan_upgrade`, `apply_upgrade`.

#### ❌ Skills that reimplement what MCP tools already provide

```markdown
<!-- BAD — the skill tells the agent to write custom boto3 code -->
## PHASE 2
Run this Python script to call AWS APIs directly...
```

If an MCP tool exists for the data retrieval, use it. Skills should focus on orchestration.

---

## 5. This Repository's Architecture

### How Skills Currently Work

Skills are installed by symlinking a skill directory into the agent's skills folder:

```bash
ln -s /path/to/skills/<category>/<skill-name> ~/.agents/skills/<skill-name>
```

The agent discovers skills via YAML frontmatter in `SKILL.md`:

```yaml
---
name: my-skill-name
description: >
  What it does. Use when [trigger conditions].
  Do NOT use for [exclusions].
---
```

Each skill follows a consistent structure:

```
<category>/<skill-name>/
├── SKILL.md              # Phase-based playbook
├── agents/               # Sub-agent prompts for fan-out
├── assets/               # Report templates
├── references/           # Static reference data
└── tools/                # Helper scripts (stdlib only)
```

### How MCP Complements Skills

Adding MCP exposes the data-gathering tools (currently Python scripts in `tools/`) to **any MCP client** — not just the agent running the skill:

| Current (Skill-only) | With MCP |
|---|---|
| `tools/my_script.py` runs as subprocess | `category__my_tool` callable by any MCP client |
| Only usable within this skill's context | Reusable by other skills, IDEs, CI pipelines |
| Output format is ad-hoc text/JSON | Standardized JSON Schema input/output |

### Coexistence: MCP for Tooling, Skills for Workflows

Both approaches serve different purposes and coexist naturally:

```
┌─────────────────────────────────────────────┐
│              SKILL LAYER                     │
│  (Orchestration, safety, user interaction)   │
│                                              │
│  SKILL.md → Phases → Sub-agents             │
└──────────────────┬──────────────────────────┘
                   │ invokes
┌──────────────────▼──────────────────────────┐
│              MCP TOOL LAYER                  │
│  (Data retrieval, validation, queries)       │
│                                              │
│  devops__list_addons, security__audit_policy,              │
│  data__validate_schema, github-get_file_contents           │
└─────────────────────────────────────────────┘
```

**The skill layer** handles:
- Multi-step orchestration
- User confirmation gates
- Safety constraints and hard rules
- Report generation
- Decision-making about upgrade order

**The MCP tool layer** handles:
- Fetching current system state
- Querying available versions or configurations
- Reading changelogs or documentation
- Validating compatibility or schemas
- Executing atomic operations

This separation means:
1. Tools are testable and reusable independently
2. Skills remain focused on workflow logic
3. New MCP clients get access to the same capabilities without needing the full skill
4. The skill can swap underlying tools without changing its orchestration logic

---

## Summary

| Layer | Responsibility | Lifecycle | Example |
|---|---|---|---|
| **MCP Tool** | Single atomic operation | Stateless per call | `list_addons(cluster)` |
| **MCP Resource** | Static reference data | Read-only | Compatibility matrix |
| **MCP Prompt** | Task template | Triggers workflow | "Audit IAM policies" |
| **Sub-Agent** | Parallel research unit | Scoped to one task | Changelog researcher |
| **Skill** | End-to-end workflow | Session-long | Multi-step guided task |

**The golden rule:** Push data operations down into MCP tools. Keep orchestration, judgment, and safety in skills. Let agents be the glue that connects them.

---

## 6. The AWS Agent Toolkit Pattern (Reference Architecture)

AWS's Agent Toolkit for AWS establishes the gold-standard pattern for packaging agent capabilities. This repo follows the same structure.

### Key Principles

1. **Skills are discoverable at install time** — agents load skills from their skills directory via YAML frontmatter. The Agent Toolkit MCP is installed separately.
2. **Plugins bundle skills** — a plugin = skills + metadata. One install gives the agent the skills it needs. The Agent Toolkit MCP is a separate, optional installation.
3. **Rules files set guardrails** — project-level markdown that tells agents _how_ to work (e.g., "use MCP first", "never apply without confirmation").
4. **Marketplace manifests enable distribution** — `.claude-plugin/marketplace.json` and `.agents/plugins/marketplace.json` make skills installable via `/plugin install`.
5. **Skills are the unit of knowledge** — `SKILL.md` with YAML frontmatter (`name`, `description`, `version`) is the universal format.

### Repository Layout Pattern

```
.claude-plugin/marketplace.json     # Agent marketplace discovery
.agents/plugins/marketplace.json    # Generic agent marketplace
plugins/<name>/                     # Installable bundles
  .claude-plugin/plugin.json        #   Claude Code metadata
  .codex-plugin/plugin.json         #   Codex metadata (includes skills/mcpServers pointers)
  .mcp.json                         #   MCP server config (empty {} — no bundled MCP)
  skills/                           #   Bundled skills (symlinks or copies)
skills/<category>/<skill>/          # Canonical skill content
  SKILL.md                          #   Entry point (YAML frontmatter + instructions)
  references/                       #   Deep-dive reference materials
  tools/                            #   Helper scripts
rules/                              # Agent behavior rules
mcp-server/                         # Agent Toolkit MCP (separate package: agent-toolkit-mcp-server)
```

> **Note:** the Agent Toolkit MCP (`mcp-server/`) is a separate, independently versioned
> package. It is not bundled with plugins. Users who want notes, todos, timers, and
> cross-project registry must install it independently — see [INSTALL.md](INSTALL.md).

### Skill Discovery Flow

```
Agent receives user request
  → Finds matching skill in its skills directory by description (SKILL.md frontmatter)
  → Loads the full SKILL.md content
  → Follows the skill's phased instructions
  → Calls MCP tools (inventory, scan, etc.) as directed by skill
```

### SKILL.md Frontmatter Best Practices

```yaml
---
name: kebab-case-name          # Machine-readable identifier
description: >                 # 2-3 sentences. Start with what it does.
  Verb phrase describing the skill. Use when [trigger conditions].
  Do NOT use for [exclusions].
version: 1                     # Integer, bump on breaking changes
---
```

The `description` field is critical — agents use it for routing. Write it as trigger documentation:
- Start with an action verb ("Creates...", "Diagnoses...", "Updates...")
- Include "Use when..." with concrete trigger phrases
- Include "Do NOT use for..." to prevent false matches

### Rules File Best Practices

Rules are simple markdown bullets — not code, not YAML. Keep them:
- Actionable ("prefer X over Y", "always do Z before W")
- Scoped (one rules file per domain/concern)
- Short (6-10 bullets max — agents have finite context)

```markdown
# Domain Guidance

- Prefer [tool/approach A] for [situation]. Fall back to [B] otherwise.
- Before starting [task type], check for available skills via list_skills.
- Never [dangerous action] without explicit user confirmation.
- When uncertain about [X], verify via [Y] rather than guessing.
```
