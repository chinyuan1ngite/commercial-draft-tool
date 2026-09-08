# Commercial Draft Media

This context defines the product media carried from a source 1688 offer into a seller draft. It distinguishes media identity, placement, and validation so collection never invents an association.

## Language

**Source Media**:
An image or video that can be demonstrably attributed to the current source offer.
_Avoid_: Page media, scraped media

**Media Role**:
The source-declared destination purpose of media: main image, detail image, SKU image, main video, or detail video. An unknown role remains unclassified rather than being inferred.
_Avoid_: Media type, position

**SKU Image**:
The single source image associated with one SKU identity for use in the corresponding seller SKU row. Missing SKU images remain missing unless the seller page requires them.
_Avoid_: Variant gallery, color image

**SKU Identity**:
The stable association key for an SKU image: source platform SKU ID first, with the complete specification combination as a fallback. Display order is not an identity.
_Avoid_: Row number, merchant code

**Main Video**:
A source video explicitly identified for the product's main media area.
_Avoid_: Product video

**Detail Video**:
A source video explicitly identified for the product description area.
_Avoid_: Product video

**Unclassified Video**:
A source-attributed video whose media role cannot be established. It is retained for review but is not automatically configured in a seller draft.
_Avoid_: Main video, detail video

**Media Manifest**:
The collected inventory of source media, including role, origin, local asset, content identity, SKU identity when applicable, and validation status.
_Avoid_: Asset list

**Media Requirement**:
A target-store or publishing-template rule that decides whether absence or configuration failure of a media role blocks draft saving. Video roles are optional by default.
_Avoid_: Required upload

**Media Reference**:
A stable reference from an SKU row to its entry in the media manifest. It identifies the media without copying its URL, local path, or validation data into the SKU row.
_Avoid_: Image path, copied asset

**Media Identity**:
The content-based SHA-256 identity used to deduplicate local media and make retries idempotent. It is distinct from a platform media ID, which is assigned after upload.
_Avoid_: Filename, source URL

**Media Probe**:
The bounded metadata check performed before downloading a video, including URL policy, response type, size, and direct-download support.
_Avoid_: Video scan, network scrape

**Media Configuration Status**:
The result of applying one manifest entry to the seller draft, including pending, uploaded, confirmed, failed, and not-selected states.
_Avoid_: Upload result

**Media Execution Policy**:
The runtime switches that decide whether a media role is collected, downloaded, or configured. It is separate from the quality requirement that decides whether failure blocks saving.
_Avoid_: Media requirement

**Store Media Ledger**:
The store-scoped record keyed by store identity and media identity, used to reuse confirmed platform uploads without changing the source product record.
_Avoid_: Product media history

**Indeterminate Upload**:
A media operation whose final platform state cannot be confirmed, such as a processing timeout. It must pause automatic retry and draft saving until a human checks the seller page.
_Avoid_: Upload timeout, failed upload

**Media Capability Probe**:
A read-only inspection of the current seller page that identifies media controls, accepted inputs, processing states, and reopen evidence before an upload adapter is enabled.
_Avoid_: Selector test

**Image-Bearing Property**:
The target sales property whose values own images, such as color rather than each complete SKU row. It must be identified from seller-page evidence.
_Avoid_: First SKU property, color property

**Unsupported Media Mapping**:
A source-to-target association that cannot be represented without discarding distinctions, such as different size images collapsing into one color image. It remains unconfigured rather than selecting an arbitrary media item.
_Avoid_: Best-effort mapping

**Source Evidence**:
The structured field path, SKU identity, or explicit page region that establishes both current-offer ownership and media role. A URL or display position alone is not source evidence.
_Avoid_: Source URL

**Role Conflict**:
A disagreement between trustworthy sources about a media role. Conflicted media remains available for review but is not automatically configured.
_Avoid_: Unknown role

**Remote-Only Media**:
Source media whose metadata and evidence were collected but whose content was not downloaded during collection. The publisher does not download it later across the collection boundary.
_Avoid_: Pending download

**Manifest Version**:
The schema version of a media manifest. A publisher must reject a version newer than it supports rather than partially interpreting it.
_Avoid_: Product version
