# Domain Docs

This repository uses a single context: [CONTEXT.md](../../CONTEXT.md) at the root and accepted decisions under [docs/adr/](../adr/).

## Before Exploring

Read `CONTEXT.md` and the ADRs relevant to the area being explored or changed. The root context currently describes commercial draft media; use its definitions for media concepts without assuming it specifies unrelated business behavior.

If a domain document is absent, proceed with the available code and requirements. Domain documents are created through domain modeling when terminology or decisions are actually resolved; their absence alone does not block work.

## Vocabulary and Decisions

Use the glossary's defined terms in specs, tickets, hypotheses, tests, and review findings. Consult the context for definitions rather than duplicating them in agent configuration.

If a needed concept is missing, first check whether an existing term applies. Record a genuine terminology gap for domain modeling.

When a proposal or implementation conflicts with an ADR, identify the ADR and explain the conflict explicitly. An alternative proposal is not an implicit replacement for an accepted decision.
