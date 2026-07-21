# MUSEUM-09B-MEDIA capability gap

## Direct reuse

- M03C remains the single source of truth for safe HTTP transport, DNS/peer validation, bounded retries, atomic promotion, MIME/signature/decode inspection, perceptual comparison and the JPEG/WebP image processor.
- The canonical responsive recipe remains `museum-03c-responsive-v1.1.0`: widths 320/640/960/1600 when available, JPEG quality 85, WebP quality 82, no crop, no upscale and metadata stripping after deterministic sRGB conversion.
- M04–M08 release manifests, attribution, notice, withdrawal and physical byte-closure conventions are reused as contracts only. Their public bytes and routes are immutable inputs in this phase.
- M08 ADR-0011 supplies the content-addressed identity model: shared SHA-256 bytes may be reused while each work retains its own rights, attribution and withdrawal reference.

## Batch 01 incremental extension

- One `museum_pipeline.art.media_bundle` writer locks the 65/423 partition, consumes the protected acquisition vault and writes the only canonical internal overlay.
- Cleveland object records gain an allowlisted, object-bound CC0 acquisition path. Originals remain ignored; only verified responsive derivatives enter the tracked internal package.
- AIC gains an external-only IIIF evidence path. Exact service and manifest identities, object binding, source rule, object public-domain record and transport result are retained; no AIC image bytes are downloaded.
- The validator adds exact allowlist, rights/final-state, source drift, original, derivative, IIIF, attribution/notice/withdrawal, physical package, public leakage and registry closure. Twenty-eight named invalid scenarios exercise required fail-closed paths.
- The predecessor M09B validator accepts only the ordered `formal_candidate_ready` and `media_bundle_ready` registry states, preserving its immutable candidate-package boundary after a legitimate phase advance.

## Protected shared and public logic

- No frontend, runtime loader, route, search, public release writer, dependency lock, workflow or Pages configuration changed.
- Existing M03C originals and derivatives were not overwritten, migrated or deleted.
- No second rights model, image processor, release manifest writer or public media namespace was introduced.

## Deferred to MUSEUM-09B-RELEASE

- Projecting approved derivatives into a new public release, choosing external-link/no-image presentation, updating route/search data and producing a Pages artifact remain future work.
- Rechecking all 65 live object records immediately before release, resolving any new drift and proving public byte closure remain mandatory.
- MUSEUM-09B-RELEASE, MUSEUM-09C and the Arms Museum were not entered.
