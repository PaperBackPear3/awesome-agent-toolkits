# Post-Work Todo Status Guide

## Choosing a status

| Status | Use when... |
|--------|-------------|
| `always` | The task should run unconditionally at the end of every work session. Examples: update CHANGELOG, run the formatter, ping a Slack channel. |
| `conditional` | The task is only relevant when something specific happened. Examples: update README only if docs changed, run migrations only if schema files changed. |
| `disabled` | You want to keep the todo definition but temporarily skip it. Use this instead of deleting when the task will be re-enabled later. |

## Writing good conditions

A condition is a short natural-language description that the agent evaluates
against observable state. Make it unambiguous:

**Good conditions:**
- `"if any file in docs/ was modified"`
- `"if TypeScript (.ts, .tsx) files changed"`
- `"if src/schema.sql changed"`
- `"if the version in package.json changed"`
- `"if new migrations were added to db/migrations/"`

**Avoid:**
- `"if something changed"` — too vague, always true
- `"when relevant"` — agent cannot evaluate this
- `"if needed"` — subjective, will be interpreted differently each run

## Writing good descriptions

The description tells the agent *what to do*, not just *what to check*:

**Good description:**
```
Read all files changed in this session (git diff --name-only HEAD),
then update README.md to reflect any new features, removed features,
or changed configuration options.
```

**Avoid:**
```
Update the README.
```

## Example todos

```json
[
  {
    "id": "a1b2c3d4",
    "title": "Update README",
    "description": "Review git diff and update README.md to reflect any changes to features, config, or usage.",
    "status": "always",
    "condition": ""
  },
  {
    "id": "e5f6g7h8",
    "title": "Check for stale type errors",
    "description": "Run tsc --noEmit and report any type errors introduced in this session.",
    "status": "conditional",
    "condition": "if any TypeScript files were modified"
  },
  {
    "id": "i9j0k1l2",
    "title": "Deploy to staging",
    "description": "Run make deploy-staging and confirm the deployment succeeds.",
    "status": "disabled",
    "condition": ""
  }
]
```
