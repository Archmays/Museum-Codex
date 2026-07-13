# MUSEUM-03B media execution policy

## Decision

MUSEUM-03B uses the approved `Mixed` strategy with a metadata-first execution order. The stage records object-level media readiness but downloads, caches, transforms, self-hosts, or displays no third-party media.

## Per-object separation

Every artwork receives a separate media-eligibility assessment recording the metadata license and media license independently, together with source object URL, rights statement, rights holder, status, attribution, redistribution/modification/commercial/share-alike terms, platform/purpose/territory scope, permission state, verification and re-verification dates, revocation/withdrawal state, technical delivery, caching, risk, and evidence hash.

Metadata permission never flows into media permission. An image URL or IIIF endpoint proves technical availability only.

## Readiness classes

- `self_hosted_open_media_eligible`: object-level public-domain/CC0 evidence is present, but `cache_bytes=false`, no storage path exists, and no bytes are acquired in this phase.
- `external_iiif_candidate`: the official IIIF service and object-level permission are recorded; no manifest, image service, or tile is requested by the public runtime or cached by the batch.
- `metadata_only`: the object metadata and official link are complete while media delivery remains absent or blocked.

CC BY/CC BY-SA candidates additionally require the exact version, original URL, rights holder, attribution template, modification decision, and ShareAlike compatibility. MUSEUM-03B still creates no derivative.

## Hard blockers

Future public-media eligibility is blocked for unknown/restricted status, research-or-education-only use without written permission, `development_only`, revoked/expired permission, absent object-level evidence, inherited metadata status, or an unlicensed image/IIIF URL.

## Repository and Pages boundary

The reviewed package declares zero media bytes. It contains no image/audio/video/document payload, no self-hosted storage path, and no public media dependency. Pages continues to render the empty art antechamber and must not request any recorded media candidate.
