---
status: accepted
---

# Media Manifest Compatibility

The collector will retain the existing `assets` and `detail_assets` fields while adding a `media_manifest` and SKU-level media references. This preserves compatibility with existing quality gates and draft inputs while giving new image/video roles one extensible inventory; the publisher will prefer the manifest and fall back to legacy fields during the transition.
