---
status: accepted
---

# Media Identity And Role Boundaries

Source media keeps an explicit role and identity: SKU images are associated by source SKU ID first and complete specification combination second, while videos are configured only when their main/detail role is explicitly known. Display order, filename, page position, or a single shared video are never used to infer an association or destination. This prevents a plausible-looking draft from silently attaching the wrong media to a SKU or seller area.

Missing optional media remains a warning; target-store or publishing-template requirements decide whether a missing or failed upload blocks draft saving.
