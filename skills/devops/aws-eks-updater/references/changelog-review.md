# Reviewing changelogs

Read the release notes between the current version (exclusive) and the target
(inclusive) for every package that moves. Judge them as a reader would; keyword hits
are a way to find the passages, not a verdict.

## Where the notes are

- GitHub releases of the upstream project (the GitHub MCP if it reaches public GitHub,
  otherwise the public API or `gh`), a `CHANGELOG.md`, or the project's upgrade or
  release-notes page.
- Chart and application versions differ: read both when the chart bumps the app.
- If no notes can be found, the package is **manual review**. Never auto-plan it.

## Signals

Strong — treat the release as breaking until shown otherwise:
`breaking`, `backwards incompatible`, `action required`, `migration required`,
`manual migration`, `must upgrade`, `no longer supported`, `requires kubernetes`,
`minimum kubernetes`, CRD schema or version changes, values keys removed or renamed.

Weak — read the passage, then decide:
`deprecated`, `removed`, `renamed`, `moved`, `default changed`, `behavior change`.
Most releases contain these for internal changes; they only matter when they touch
something this deployment uses (its values, its annotations, its CRDs, its flags).

## What to record per package

- Breaking: yes / no / unknown, with the one-line reason and the release link.
- What in **this** deployment it touches (a values key, an annotation prefix, a CRD).
- Pre-steps (apply CRDs first, set a value before the bump, migrate data).
- Whether the target supports each hop's Kubernetes minor.

## Many packages

With about eight or more packages, hand the reading to one subagent with the full list
(package, repo, from, to, what this deployment uses) and ask for a table back. It must
not edit files or run mutating commands. One agent for the whole list, not one per
package.
