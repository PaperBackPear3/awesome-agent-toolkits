# EKS upgrade ledger — <clusters> <from> → <target>

Started <YYYY-MM-DD> · Policy <N-1 of latest = target> · Deadline <end of standard support of current minor>

## Environments

| Env | Account / profile | Region | Cluster | TF root | Now | Target |
|---|---|---|---|---|---|---|

Promotion: <dev → test → prod → dr>, soak <N working days> between environments.

## Status

Current round: <round id> · Next checkpoint: <what the user must decide or verify>

## Plan

One row per change. Rounds run in order; a round starts only when its requirements hold.

| # | Round | Env | Change | Method | Requires | Status | Done (date, how, evidence) |
|---|---|---|---|---|---|---|---|
| 1 | pre-0 | all | <chart> 1.2.3 → 1.4.0 | PR to `<file>` | changelog read | todo | |

Status: `todo` · `in progress` · `waiting` (on whom) · `done` · `skipped` (why) · `blocked` (why)

## Pull requests

Merge top to bottom. Full URLs only.

| Order | PR | Rows | Merge when | State |
|---|---|---|---|---|
| 1 | <https://…/pull/N> | 0.4 | <condition, e.g. after the dev apply soaked 2 days> | <open / approved / merged> |

## Findings and decisions

- <YYYY-MM-DD> <what was found or decided, and why>

## Follow-ups (outside this upgrade)

- <item, owner if known>
