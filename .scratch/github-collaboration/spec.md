# Private GitHub collaboration and release verification

Status: claimed

Baseline: `8b7c7b1`

## Goal

Prepare this repository for private GitHub collaboration with reviewable issue and pull-request workflows, Windows CI, and a repeatable package validation process. Keep real profiles, credentials, runtime data, reports, and collected products outside Git.

## Scope

- Add GitHub issue forms, a pull-request template, and least-privilege Windows workflows.
- Make version consistency and release archive validation reusable from a clean clone.
- Make install, test, and build scripts propagate native command failures.
- Prevent accidental replacement of a same-version local release archive.
- Document maintenance, triage, release, rollback, and the transition from local specs to GitHub Issues.
- Audit the Git history and refs that will be pushed before creating the private remote.
- Create the private GitHub repository, push `main`, and configure available branch rules after local verification.

## Acceptance criteria

- Non-browser CI installs the project, checks dependencies and versions, compiles source/tests/examples, and runs the default test suite on Windows.
- Browser regression and release packaging are explicit manual workflows and do not use real account profiles.
- A tracked verifier checks archive paths, required files, version, executable hash, smoke test, and CLI help; its structural checks have synthetic-archive tests.
- Build dependencies and packaged documentation are explicit, and the build refuses an existing same-version output unless the maintainer opts in.
- Issue and PR forms collect platform, environment, acceptance, compatibility, validation, and sanitization information.
- Collaboration and maintenance docs identify GitHub Issues as the task-status source after the remote is established, while repository specs and ADRs remain durable design records.
- Tests pass, documentation links resolve, and the existing 0.4.24 ZIP hash is unchanged.
- The remote repository remains private. Collaborator invitations and public licensing wait for concrete accounts and an owner decision.

## Verification

To be recorded after implementation.
