# Issue Tracker: Local Markdown

Issues and specs live in `.scratch/`, relative to the repository root. Tracker operations are local file operations; they do not require a hosted issue tracker or a Git remote.

## Conventions

- Use one directory per feature: `.scratch/<feature-slug>/`.
- Store its spec at `.scratch/<feature-slug>/spec.md`.
- Store each implementation ticket separately at `.scratch/<feature-slug>/issues/<NN>-<slug>.md`, numbering from `01` within that feature. Choose an unused number and preserve existing files.
- Link each ticket to its spec and record its acceptance criteria, dependencies, and verification evidence in the ticket.
- Put a `Status:` line near the top. Triage values come from [triage-labels.md](triage-labels.md); execution additionally uses `claimed` and `resolved`.
- Record dependencies as `Blocked by: 01, 02`, referring to tickets in the same feature. Omit the line when there are none; use full repository-relative paths for cross-feature dependencies.
- Append discussion and progress under `## Comments`, preserving earlier entries.
- Keep specs and tickets eligible for Git tracking so their history can be reviewed alongside the implementation. Create directories when the first spec or ticket is needed.

## Publish and Fetch

When a skill says "publish to the issue tracker", create or update the appropriate spec or individual ticket file using the conventions above. An update retains the existing ticket path and history.

When a skill says "fetch the relevant ticket", read the referenced file, its linked spec, and relevant dependency tickets. A bare number is scoped to its feature; if it matches multiple features, resolve the feature before using it. Commit references should use the repository-relative ticket path.

## Execution and Completion

An implementation ticket is eligible for automatic work when its status is `ready-for-agent` and every dependency is `resolved`. Set `Status: claimed` before starting. On resumption, inspect the recorded progress and current code before continuing a claimed ticket.

Set `Status: resolved` after the acceptance criteria and required verification are satisfied. Record the result and verification evidence under `## Answer`. If blocked or interrupted, record the remaining work under `## Comments`; retain the unresolved state. A `wontfix` dependency is not equivalent to a completed prerequisite.

## Wayfinding Operations

When `/wayfinder` is used, its map is `.scratch/<feature-slug>/map.md`, with `Notes`, `Decisions-so-far`, and `Fog` sections. Its child tickets use the same `issues/` directory and numbering convention.

- A `Type:` line records `research`, `prototype`, `grilling`, or `task`.
- `Status: open` identifies an unclaimed wayfinding question; claim and resolve it using the execution states above.
- The frontier contains `open` tickets whose dependencies are all `resolved`, ordered by ticket number.
- On resolution, append the answer under `## Answer`, then add a concise finding and ticket link to the map's `Decisions-so-far` section.

`open` is specific to wayfinding questions. Implementation-ticket readiness uses the triage mapping.
