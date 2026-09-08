---
status: accepted
---

# Video Rollout And Retry Policy

Video collection and video configuration are independently switchable. Metadata probing may be enabled by default, but downloading and seller-page configuration remain opt-in until capability probes cover representative pages. A failed item may be retried once in isolation; a confirmed SHA-256/platform-media match is never uploaded again, and an indeterminate processing state pauses automatic retry and draft saving.

Protected source URLs may be downloaded only within the active buyer-browser session. Credentials and cookies never enter `product.json`, reports, manifests, or the store media ledger.
