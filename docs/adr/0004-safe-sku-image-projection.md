---
status: accepted
---

# Safe SKU Image Projection

The source model associates images with complete SKU identities, while a seller page may accept images only on one sales-property value. Projection is allowed only when the page identifies the image-bearing property and every source SKU collapsed into one target value references the same image. Any conflicting or ambiguous projection is reported as unsupported and is never resolved by row order, first match, or an arbitrary image.
