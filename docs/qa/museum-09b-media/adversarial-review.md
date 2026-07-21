# MUSEUM-09B-MEDIA adversarial review

## Result

Reviewers A–G pass. P0/P1/P2 are all zero. The sole P3 is recurring `source-record-drift`; it is controlled but cannot be permanently eliminated while official records remain live.

## Reviewer A — Allowlist and identity

Pass. The package contains exactly 65 allowlisted works with the original 40 self-hosted / 25 external-IIIF split, and exactly 423 excluded metadata-only works. The sets are disjoint and cover all 488 Batch 01 works. Every media decision binds the stable work, artist, source object, source rule and candidate media identity. Downloads outside the allowlist fail closed.

## Reviewer B — Rights and provenance

Pass. All 65 objects have current object-level identity, metadata/media separation, source rule, rights evidence hash, attribution and withdrawal route. Cleveland self-hosting requires the current object record's CC0 media status. AIC availability and `is_public_domain` are not treated as permission to localize; those 25 objects remain external link-only. `RIGHTS_STATUS: PASS_BY_USER_AUTHORIZATION`, while the operative third-party media gate remains object-specific evidence and fail-closed classification rather than user authorization alone.

Canonical drift is 4 changed / 61 unchanged / 0 unavailable. Three AIC records changed only `source_updated_at`; one Cleveland record changed `creation_date`. Rights changed=0, endpoint changed=0, downgraded=0 and blocked=0.

## Reviewer C — Retrieval and security

Pass. Transport uses exact host/path allowlists, DNS and connected-peer checks, TLS verification, bounded retries/rate limits, 100 MiB and pixel limits, atomic partial promotion, MIME/signature/decode checks and HTML/error rejection. Forty Cleveland originals succeeded with zero failures. Partial files and failed response bodies remaining=0. Repository secret and absolute-path scans pass; no access control or source restriction was bypassed.

## Reviewer D — Image fidelity and quality

Pass. Forty originals decode and bind to official objects: 39 `display_high`, 1 `display_standard`, 0 corrupt/thumbnail-only/metadata-only/blocked. The 318 derivatives preserve full aspect ratio and use orientation plus deterministic sRGB/encoding conversion only. Crop, upscale, content alteration, watermark removal, restoration, generated substitute and AI modification counts are zero.

## Reviewer E — IIIF and external-only boundary

Pass. Twenty-five AIC candidates retain exact IIIF Image API 2 service identities and documented presentation-manifest identities, plus provider, object ID, source rule and object rights record. The service `info.json` probes returned HTTP 403 in this environment and a bounded object refresh encountered TLS EOF; transport failures are preserved rather than relabeled as source absence. Same-phase sealed object receipts close identity/rights, but no manifest or image response is claimed present. Final status is 25 external link-only, with zero IIIF image downloads and no current runtime image assumption.

## Reviewer F — Engineering and storage

Pass. One canonical writer produces one immutable overlay. Originals use the ignored protected vault; derivatives use SHA-256 paths. There are 40 unique original hashes, zero duplicate physical originals and zero cross-work dedup savings in this batch. Two clean builds reproduce the full package and all derivatives byte-for-byte. An unchanged canonical rebuild reused all 40 derivative groups and 61,418,168 derivative bytes with zero re-encode. All tracked files are below 5 MiB; temporary phase directories remaining=0.

Post-CI evidence review found raw acquisition drift metrics (43/22) beside the normalized canonical drift (4/61). The bounded repair normalized `download-manifest` at the writer, added a cross-manifest validator assertion, changed no derivative byte, and passed a second phase-scoped run.

## Reviewer G — Public and phase boundary

Pass. `public/` and all five release trees have zero changed paths; current release content/manifest/tree remain `93365e…` / `1eb5cc…` / `5029d2…`. Public leakage=0, public growth=0, Pages artifact=0 and new deployment=0. Existing Pages deployment `5508931387` still serves runtime commit `b36ac365…`. Batch 02–10 remain `registered_not_started`; M09B-RELEASE, M09C and Arms remain unentered; OD-011 remains open.

## P3

| Priority | Risk | Owner | Mitigation | Latest review stage |
|---|---|---|---|---|
| P3 | Official object, rights or endpoint records can drift after this internal review. | MUSEUM-09B-RELEASE canonical writer | Recheck all 65 stable object IDs and exact media/service identities; retain old/new hashes and minimal field diffs; rerun only affected work/media/package closure; fail closed on identity or rights uncertainty. | Before any MUSEUM-09B-RELEASE public projection |
