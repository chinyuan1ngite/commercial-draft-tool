# Triage Labels

The five canonical triage roles use their default strings in this repository.

| Canonical role | Local tracker value | Meaning |
| --- | --- | --- |
| `needs-triage` | `needs-triage` | Maintainer needs to evaluate the issue. |
| `needs-info` | `needs-info` | More information is required. |
| `ready-for-agent` | `ready-for-agent` | Fully specified and ready for agent implementation. |
| `ready-for-human` | `ready-for-human` | Requires human implementation. |
| `wontfix` | `wontfix` | Will not be actioned. |

When a skill applies a triage role, write the corresponding value to the ticket's `Status:` line. These roles describe triage, not completion; execution states and dependency rules are defined in [issue-tracker.md](issue-tracker.md).

To customize the vocabulary later, edit the local tracker value column here and update affected ticket statuses consistently.
