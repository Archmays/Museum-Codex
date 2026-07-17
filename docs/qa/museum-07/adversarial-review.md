---
phase_id: MUSEUM-07
review_status: local_candidate_pass
reviewed_at: 2026-07-17
p0_count: 0
p1_count: 0
p2_count: 0
p3_count: 4
---

# MUSEUM-07 adversarial review A–F

## A — Historical geography and names: pass

- All 23 formal places bind a stable project ID to Getty TGN or another formal authority, historical/current labels, alternate names, hierarchy, coordinates and source precision. Modern jurisdiction is secondary context only.
- Place precision is 20 city centroids, 1 regional centroid, and 2 unknown. Episode precision is 31 city centroids, 2 regional centroids, and 3 unknown; centroids are never labeled as buildings, regional records receive uncertainty halos, and unknown records are list/timeline only.
- Historical labels include distinctions such as Edo/Tokyo, Königsberg/Kaliningrad, Ceylon/Sri Lanka, Calcutta/Kolkata, and Travancore/Kilimanoor. Episode-date labels lead; current/common names remain secondary.
- The Natural Earth layer contains only land, coastline, and lakes. It has no country names, administrative properties, political borders, roads, POIs, or country ranking fills. The public method text states that modern outlines are not historical political borders.

## B — Art history and time: pass

- Exactly 12 artists have 36 verified artist episodes, three per artist. Types are 12 birth, 12 death, 7 documented activity, 2 publication/print activity, 2 residence, and 1 studio.
- Time precision is explicit. Twelve source-closed but undated/low-spatial-resolution records remain `verified_list_only`; none is promoted by inferred chronology.
- No movement line or inferred travel route exists. Public copy and selected Evidence panels state that chronology does not prove a travel route, continuous presence, influence, or exclusive cultural identity.
- All 44 artwork creation places remain `not_asserted` because no retained formal record explicitly closes a creation-place claim. Zero is an intentional fail-closed result, not a missing-data error.
- Two current holding-institution records form a separate layer and explicitly do not prove creation place or historic activity.

## C — Sources, licenses, and autonomy: pass

- The production `getty_tgn` adapter accepts current Getty JSON/RDF identities, preserves stable IDs/names/hierarchy/reference coordinates, binds ODC Attribution 1.0, and forbids the discontinued XML service.
- Each unique TGN ID is cached once by ID/hash. ULAN assertions become public episodes only after TGN identity and Claim → Evidence → Source closure; Wikidata is not the sole public episode source.
- Natural Earth official 1:110m ZIP bytes, theme versions, SHA-256 values, download date, public-domain decision, transform recipe, output hashes, and `Made with Natural Earth` attribution close in the physical release.
- Automated dispositions contain only terminal states; no `waiting_for_human_review`, pending user approval, guessed coordinate, private lead, or item-by-item human dependency exists.

## D — Map, accessibility, and product: pass; real AT/device unavailable

- Map, timeline, and place table consume the same filters, selection, layers, and allowlisted URL state. The table exposes all 36 episodes, including list-only records; the map has a synchronized 24-item DOM marker navigator.
- Native filters, numeric/range year controls, keyboard selection, focus movement, live status, 44 px targets, forced colors, reduced motion, 360/390 containment, and print wrapping pass automated checks.
- Low bandwidth, forced colors, unavailable WebGL, context loss, and renderer error resolve to the equivalent list/timeline experience without losing URL/filter/selection state or displaying internal errors.
- Real assistive-technology sessions and physical touch devices are `not_available`; no certification claim is made.

## E — Engineering and performance: pass

- MapLibre GL JS `5.24.0` is exact-pinned and lazy. The style/runtime contract forbids remote style, tile URLs, glyphs, sprite, image URL, geocoder, telemetry, geolocation, rotation, 3D, and route lines.
- Home gzip is 100,059 B (+0.673% over the 99,390 B M06 baseline); map route total is 532,296 B; renderer closure 292,330 B; basemap 174,103 B; place/timeline/filter data 20,876 B. All formal budgets pass.
- Controlled measurements: desktop first-interactive 585.931 ms, mobile 121.596 ms, low-bandwidth list 994.197 ms, filter p95 78.9 ms, marker p95 28.7 ms, heap increment 1,378,028 B, CLS 0, and external request count 0.
- The deterministic rebuild is byte-identical and validates at `sha256:aa969f48fd152301a66ee4f4841392b36f271bbca8537897484bc70c6ece718f`. M04 scale and M06 synthetic benchmarks were not rerun; their evidence hashes remain the regression input.
- Final local gates pass: Python 448/448, Vitest 89/89, lint, strict typecheck, production build, build/resource scan, all release/source/rights/leakage/security validators, and complete Playwright 26/26. Controlled performance scenarios run in separate fresh browser processes so their samples are not contaminated by functional-flow load.

## F — Scope, privacy, and publication: local pass; online closeout pending

- Work remains on linear `main`; no branch, worktree, PR, media regeneration, M08 artifact, analytics, geolocation, visit/map history, online geocoder, external tile/token, or runtime API was introduced.
- The published M06 predecessor directory remains byte-identical. The M07 overlay refreshes only the two inherited governance bindings needed for Getty TGN and records every new physical file/hash.
- OD-006 is closed. Open decisions are exactly OD-008, OD-009, and OD-011 (`open_decisions_count=3`).
- Local old/new routes, physical release, build scan, browser requests, leakage, rights, and performance gates pass. Actions, Pages, live routes, live assets, screenshots, and local/origin/remote equality remain the final closeout steps.

## Resolved findings

| Severity | Finding | Resolution |
|---|---|---|
| P1 | Three Kollwitz Museum Evidence entries had official locators but null snapshot hashes. | Captured the official biography once in the ignored source vault, verified required text, bound the exact SHA-256, and rebuilt the uncommitted release. |
| P1 | Unknown URL parameters and invalid unpublished IDs survived in the address bar. | Added deterministic ten-key allowlist normalization and invalid-ID/facet/year rejection or clamping; refresh and tracking-key browser tests pass. |
| P2 | `Number(null)` collapsed an absent end year to the release minimum. | Treat null/blank as absent before parsing; 36 rows and 24 mappable points now load by default. |
| P2 | Minimal loading content produced CLS 0.9. | Added a stable geometry-preserving map loading shell; controlled CLS is 0. |
| P2 | The first mobile print capture clipped three table columns. | Added fixed print column widths and wrapping; all columns are visible in the regenerated print screenshot. |
| P2 | Initial route-budget traversal charged every app lazy route through the Vite entry record. | Restricted accounting to the page static closure plus explicit MapCanvas/MapLibre dynamic seeds; no threshold was changed. |
| P2 | Generic build scan treated MapLibre's built-in attribution anchor as a remote runtime dependency. | Allow only the exact literal in the manifest-identified 5.24.0 vendor chunk, continue scanning the remainder, and retain zero-request browser interception. |
| P2 | Adding Getty TGN changed the current global source-registry hashes and initially invalidated immutable M04/M05B/M06 release checks. | Bind the three predecessor release IDs to their sealed source-matrix snapshot and keep M04 build inputs on their sealed license snapshot; old release bytes remain unchanged while arbitrary historical hashes still fail. |
| P2 | Legacy M04/M05A performance validators treated M07 source additions as a demand to rerun old labs. | CI now verifies the exact committed evidence hashes, matching the M07 rule to reuse—not regenerate—old performance evidence. |
| P2 | Parallel/long-lived Playwright runs contaminated strict M05B/M06/M07 controlled timing samples. | Run the three performance scenarios first in separate one-worker browser processes, measure browser-side interaction boundaries, and then run the 23 functional scenarios; final complete E2E is 26/26 without relaxed budgets. |

## Open P3 register

| Finding | Owner | Mitigation | Latest resolution point |
|---|---|---|---|
| Getty TGN returns no usable coordinate for Allegheny City and a malformed upstream coordinate for Mexico City. | Place-data owner | Keep both identities/episodes list-only with `unknown`; never invent coordinates. | A future release with corrected official authority records. |
| No explicit, stable formal source closes artwork creation place for the current 44 works. | Art-data owner | Preserve all 44 as `not_asserted`; do not infer from residence, subject, title, or holding. | A later authorized data release with explicit official records. |
| Real AT and physical touch-device sessions are unavailable. | Accessibility QA owner | Retain automated semantics, keyboard, forced-colors, reduced-motion, touch-size, mobile, print, and fallback evidence. | Before a future phase explicitly requiring real-device certification. |
| Public cold-route latency varies with CDN/TLS/geography and the project intentionally has no RUM/analytics stream. | Web-performance owner | Keep controlled budgets as the release gate and record bounded live smoke timing without tracking. | Before a future phase changes the privacy or public-network performance contract. |

No P0, P1, or P2 remains open.
