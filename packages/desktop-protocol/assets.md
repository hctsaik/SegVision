# Data plane encoding (protocol 1.1)

- Asset tokens are unguessable, opaque, and MUST NOT embed filesystem paths.
- Tokens bind `session_id` or dataset identity, `revision` (0 for viewer assets), `kind`, and an expiry.
- `kind` is one of `source_image`, `thumbnail`, `mask`.
- Display and commit-preview masks SHALL be PNG with pixel values `{0,255}`.
- Source images remain PNG, JPEG, or WebP as stored.
- `Content-Type` on `assets.get` MUST be the concrete media type.
- Control JSON MUST NOT contain images, masks, embeddings, logits, or dense integer rasters.
- Shared memory is out of scope for 1.0.
