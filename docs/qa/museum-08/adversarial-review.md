---
phase_id: MUSEUM-08
review_kind: adversarial_A-G
review_status: local_pass_online_pending
reviewed_at: 2026-07-19
p0_count: 0
p1_count: 0
p2_count: 0
p3_count: 5
---

# MUSEUM-08 adversarial review A–G

## A — CI classification, hash-only history, and execution: pass

- Twenty-four synthetic changed-path cases cover docs-only, phase-local, shared schema/loader/rights, dependencies, workflow, public bytes, route suites, multi-commit, delete, rename, empty before SHA, mixed changes, and manual targeted/full modes.
- Docs-only produces zero full Python, frontend install/build, release rebuild, browser, Pages artifact, and deployment work. Phase-local work rebuilds only its affected release; historical releases default to ledger hash closure.
- Validation uses `museum-validate-${{ github.ref }}` with cancellation; deployment uses independent `pages` concurrency without cancellation. The same-commit build marker is required before online closure.
- Local full gate count is zero. The one GitHub final full gate and one runtime deployment remain the explicit online acceptance step, not an open code finding.

## B — Candidate overlay, ledger, withdrawal, and rollback: pass

- `release:art-v1-candidate-1.4.0` is a 317-file / 42,018,091-byte immutable overlay of `release:art-time-place-1.3.0`; inherited records remain byte-identical.
- Manifest SHA, content hash, and physical tree hash close independently. The integrity ledger covers five releases and defaults the four historical releases to hash-only verification.
- Four synthetic withdrawal cases remove media, relationship, place episode, and artwork metadata from a derived release while preserving reference closure, notices, natural URL fallbacks, and predecessor immutability.
- Candidate-to-predecessor rollback validates loader, routes, media, path, map, hashes, private-data absence, RTO 15 minutes, and zero-published-mutation RPO.

## C — Search and privacy: pass

- OD-008 closes on deterministic Unicode normalization plus exact, alias, prefix, optional Segmenter token, and substring matching. Ranking is an explainable tuple and never uses popularity, importance, artistic value, embeddings, remote search, or query logs.
- Search has 367 public records in eight hash-bound shards. It is media-free, lazy on first query, has zero external requests, and retains full behavior when `Intl.Segmenter` is unavailable.
- Controlled p95 is 32.7065 ms for the current index and 66.2855 ms for 1,000 fixed synthetic records. The route is 87,834 gzip bytes and the index is 45,663 gzip bytes.
- OD-009 closes on no analytics, account, profile, telemetry, cookies, fingerprinting, geolocation, remote logging, or query/visit/selection/path/map/tour/print/share history. Runtime storage is limited to locale and low-bandwidth preference keys.

## D — Mobile, low bandwidth, and route resilience: pass

- Sixteen route templates / 87 concrete routes are inventoried with lazy chunk, data, media, WebGL, print, keyboard, no-script, rights/source, and withdrawal behavior.
- Seven required viewports pass no-overflow and 44px controls. Compare stacks; filters and long content reflow; orientation and on-screen keyboard layouts remain usable.
- Low bandwidth initializes neither Sigma nor MapLibre, creates no image request, and preserves equivalent constellation, map, path, tour, compare, and search tasks through text/metadata.
- Missing chunk, stale search manifest, failed image, unknown/withdrawn stable ID, no-script, reload, Fast 4G, and Slow 4G cases fail naturally without a blank site.

## E — Accessibility: pass; real AT/device unavailable

- Automated route assertions cover landmarks/headings, names, focus/skip, live status, controls, tables, image alternatives, graph/map text equivalents, forced colors, reduced motion, print, keyboard, 200% reflow, and mobile reflow.
- Serious violations are zero and critical violations are zero on every core route template.
- Real NVDA/JAWS/VoiceOver/TalkBack sessions and physical touch devices are `not_available`; this review does not convert controlled Chromium into a real-AT or physical-device certification.

## F — Performance, scale, and storage architecture: pass

- Home is 101,947 gzip bytes (+1.887% from M07); largest non-map route 87,834; map route 533,891; low-bandwidth initial transfer p95 151,277. Desktop/mobile first-interactive p95 are 625.7817/455.3261 ms, interaction p95 17.8 ms, CLS 0, external request/media preload/geolocation counts 0.
- Fixed-seed synthetic scale validates 500 artists, 5,000 artworks, 20,000 search records, 10,000 relationships, and 50,000 path/index records with byte-identical repeat, 46,736,112-byte peak memory, and zero public leakage.
- Search and stable-ID data can shard by entity type, language, and hash prefix; one changed ID rebuilds one shard while 193 unrelated shards remain hash-only.
- The graph uses a focused 120-node / 1,000-edge visual neighborhood; complete text lists use stable 50/100-item pagination, keyboard navigation, and 200% reflow.
- ADR-0011 binds future shared media by SHA-256 with per-reference rights and withdrawal. M08 validates a synthetic two-release/one-byte prototype and intentionally does not migrate or delete immutable historical media.

## G — Scope, decisions, rights/source, and publication: local pass; online gate pending

- Only OD-011 remains open. No arms work, MUSEUM-09 research, real-content acquisition, new artist/artwork/media/relationship/place/tour, analytics, query history, or geolocation was introduced.
- Current content counts remain exact candidate manifest invariants but are blocked as shared runtime/schema/test-tool limits by the hard-coded-count scanner.
- Claim → Evidence → Source, source/rights closure, Pages base path, secrets/absolute-path scans, and candidate physical closure pass locally.
- GitHub Actions full validation, Pages deployment, online build identity, 317-file byte closure, and synchronized clean `main` remain the planned single online closure. This document will be updated after that run.

## Resolved findings

| Severity | Finding | Resolution |
|---|---|---|
| P1 | The previous workflow rebuilt M04–M07 and ran every heavy gate on each push. | Added four-level impact classification, release ledger, conditional reusable workflows, separate validation/deploy concurrency, and 24 self-test fixtures. |
| P1 | Candidate search and shared loaders could inherit monolithic/full-catalog assumptions. | Added manifest-bound shards, stable-ID lazy loaders, bounded graph/list strategies, deterministic partial rebuild, and synthetic scale gates. |
| P1 | First M08 browser pass exposed hidden-details name false positives, short navigation targets, a stale text assertion, and an incorrect media interception path. | Corrected the gate visibility model, made short navigation/footer targets 44px, updated the natural-language assertion, and intercepted actual local asset paths; final 17/17 passes. |
| P2 | Impacted frontend tests still named older current releases, and the media allowlist blocked predecessor rollback. | Updated expectations to the candidate profile and retained same-origin versioned release media for rollback compatibility. |
| P2 | Minified vendored capability tokens could be misread as analytics/geolocation use. | Source and browser gates prove zero call/storage behavior; the dist scanner permits only documented vendored capability tokens when those independent zero-use gates pass. |
| P2 | A search benchmark run shared CPU with the 203 MB ledger hash closure and exceeded p95. | Kept the threshold unchanged and reran the benchmark in isolation; current/1k p95 closed at 32.7065/66.2855 ms. |

## Open P3 register

| Finding | Owner | Mitigation | Latest review point |
|---|---|---|---|
| Getty TGN still has no usable coordinate for Allegheny City and a malformed upstream coordinate for Mexico City. | Place-data owner | Keep both identities/episodes list-only and `unknown`; never invent coordinates. | A future authorized data release with corrected authority records. |
| No explicit stable source closes creation place for the current 44 artworks. | Art-data owner | Preserve all as `not_asserted`; do not infer from artist, title, subject, or holding. | A later authorized content release with explicit formal evidence. |
| Real assistive technology and physical devices are unavailable. | Accessibility QA owner | Preserve automated semantics, keyboard, forced-colors, reduced-motion, mobile, print, and fallback evidence. | Before a phase explicitly requiring real-device certification. |
| Public cold latency varies by CDN/TLS/geography while the privacy decision forbids RUM. | Web-performance owner | Use controlled budgets as release gates and bounded cold probes only; do not add tracking. | Before changing the privacy or public-network performance contract. |
| Content-addressed media reuse is a validated synthetic prototype, not a migration of real release bytes. | Release engineering owner | Preserve all old URLs and physical hashes; require Pages cache/404/rollback and per-reference rights/withdrawal staging before migration. | Before the first real MUSEUM-09 expansion batch. |

No P0, P1, or P2 remains open. These P3 items do not authorize MUSEUM-09.
