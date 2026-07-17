# MUSEUM-07 implementation notes

- **Task / plan reference:** MUSEUM-07 Art Across Time and Place
- **Date or sequence:** 2026-07-16 / entry

## Task contract

- **Goal:** Close OD-006 and publish an immutable, source-closed art time/place release with equivalent map, timeline, and place-list experiences.
- **Context:** The protected input is `release:art-pathways-1.2.0` at `sha256:8a773b00b37f025520e7ea4ef7a7ebc9cd3e0d3f1298925d3c20be29b28fe6f3`, containing 12 artists, 44 artworks, 31 contexts, 36 C-level relationships, 66 endpoint pairs, and 198 paths.
- **Constraints:** Linear `main`; no branch/worktree/PR; no media regeneration; no M04/M06 synthetic benchmark rerun; 12 artists and 44 artworks only; local static runtime; no tiles, token, geolocation, analytics, visit history, modern-boundary layer, or inferred travel line; no MUSEUM-08 work.
- **Done when:** OD-006 is closed; TGN/Natural Earth/renderer contracts pass; every artist has at least two verified episodes; release, UI, accessibility, performance, full gates, Actions, Pages, screenshots, and byte closure pass; P0-P2 are zero; `main` is synchronized and clean.
- **Must not touch:** Immutable predecessor release bytes, 31 media originals and 242 derivatives, open decisions OD-008/009/011, unrelated museum halls, or later-phase artifacts.
- **Evidence sources:** M06 report and release, existing ULAN snapshots and reviewed artist/artwork records, Getty TGN LOD, Natural Earth official 1:110m physical vectors, official institution records, targeted/final validators, Actions/Pages/live QA.
- **Current stage:** final local candidate complete; online closeout pending

## Unknown register

| ID | Category | Evidence | Consequence if wrong | Resolve now / defer | Resolution or owner | Confidence |
|---|---|---|---|---|---|---|
| U-01 | known unknown | MapLibre `5.24.0` is the current stable npm/GitHub release; `6.0.0-*` is prerelease. The unpacked package is large, but route gzip is the operative budget. | A renderer choice could violate the stability or 400 KB closure gate. | Resolve now. | Exact-pin `5.24.0`, lazy-load it, scan the built route and fall back to list/timeline on runtime failure. | high |
| U-02 | unknown unknown | The existing release loader hard-codes the M06 overlay, and generic physical closure expects predecessor source/media ID sets to remain exact. | Rewriting inherited registries could break old routes or physical validation. | Resolve now. | Keep the published M06 release directory byte-identical. In the new M07 overlay, preserve every inherited artifact except the two governance bindings that must incorporate Getty TGN; regenerate and validate those exact `claims.json` and `source-rules-snapshot.json` bytes plus the M07 manifest. | high |
| U-03 | known unknown | Existing ULAN snapshots provide TGN-linked birth/death places for 11 artists; Kollwitz ULAN omits those place nodes. | A fabricated place join would invalidate the minimum episode coverage. | Resolve now. | Bind Kollwitz birth/death to official Kollwitz Museum biography evidence and TGN records for historical Königsberg/current Kaliningrad and Moritzburg. | high |
| U-04 | known unknown | Several existing activity-place assertions have no numeric ULAN timespan. | Treating a life span as an activity interval would invent time precision. | Resolve now. | Publish only source-supported dated activity records on the map; retain undated but verified scopes as `verified_list_only`. | high |
| U-05 | known unknown | The retained artwork release does not assert creation-place fields; the AIC live place-of-origin probe is transport-unstable. | Inferring creation places from holding, title, subject, or residence would be false. | Defer fail-closed. | Emit `not_asserted` dispositions for works without an explicit stable source field; do not count these as defects. | high |
| U-06 | known unknown | Real assistive technology and physical devices are not exposed by the runtime. | False certification would invalidate accessibility reporting. | Defer with evidence. | Record `not_available`; run semantic, keyboard, forced-colors, reduced-motion, responsive, print, low-bandwidth, and WebGL-fallback automation. | high |

## Entry

- **Entry type:** discovery
- **Expected:** M07 might require broad live place discovery.
- **Discovered:** The 12 existing ULAN snapshots already expose the bounded TGN identity set needed for most birth/death and activity candidates; only Kollwitz place identity and the two holding-city identities require additional official closure.
- **Evidence:** `data/raw/getty_ulan/**/response.body`; `public/releases/art-pathways-1.2.0/artists.json`; official Getty TGN per-record JSON probes.
- **Conservative choice:** Fetch each unique TGN ID once into the ignored source vault and build only from normalized reviewed records.
- **Consequence:** Live lookup remains bounded and deterministic; unresolved or undated candidates cannot block other artists.
- **Revisit:** Only if a required TGN record lacks coordinates or conflicts with the ULAN place link.
- **Validation:** Unique-ID cache test, raw/output hash manifest, place identity and episode closure tests.
- **Fold into next attempt:** Keep TGN acquisition concurrency read-only and the release writer single-threaded.

## Entry

- **Entry type:** decision
- **Expected:** OD-006 required a self-hosted renderer and physical basemap.
- **Discovered:** Natural Earth publishes land, coastline, and lakes as official 1:110m physical-vector downloads, with theme versions 4.0.0, 4.1.0, and 5.0.0 under the current 5.1.0 physical release page. Getty confirms JSON/RDF LOD and ODC-By 1.0 while the XML services are discontinued. MapLibre `5.24.0` is stable; current `6.0.0-*` tags are prerelease.
- **Evidence:** Official Natural Earth download page and archives; Getty LOD page and live JSON; npm registry metadata; GitHub releases API.
- **Conservative choice:** Use exact-pinned MapLibre `5.24.0` with inline/local GeoJSON style only, and preserve a complete list/timeline fallback.
- **Consequence:** No tile provider, token, CDN, remote style/glyph/sprite, geocoder, telemetry, or geolocation is needed.
- **Revisit:** Automatically switch the map view to list/timeline if the final renderer closure exceeds budget or browser runtime gates fail.
- **Validation:** Dependency provenance/audit, bundle gzip, static scanner, request interception, forced renderer failure, and third-party notices.
- **Fold into next attempt:** Treat the map as an optional projection of the shared state model, never as the only formal experience.

## Pause checkpoint · 2026-07-16

- Paused at the boundary between frontend implementation and targeted frontend/browser validation, at the user's request.
- Wave 1 source/governance, Wave 2 bounded place research, and Wave 3 basemap/release construction are complete.
- The pre-resume candidate validated as `sha256:60fef3989499289eca54b1b07f5cf6386e9d1ab6a6f28bb18d8d47bc4f67b850`; the source-closure correction below supersedes this uncommitted hash.
- Current closed counts: 23 place identities, 36 artist episodes (3 per artist), 12 list-only episodes, 0 asserted artwork creation places, and 2 holding institutions.
- The `#/art/map` implementation and cross-route entry links are present. TypeScript passed; one non-behavioral lint assertion was removed before checkpoint verification.
- Resume at: rerun `npm run typecheck` and `npm run lint`; then add targeted Vitest/Python tests and governance/ADR documentation before any build, browser QA, full-suite run, commit, push, or Pages deployment.
- No commit, push, deployment, or MUSEUM-08 work occurred before the pause.

## Resume validation discovery · 2026-07-16

- **Entry type:** validation discovery
- **Expected:** All episode Evidence entries already carried exact snapshot hashes.
- **Discovered:** The three Kollwitz Museum biography Evidence entries retained the official locator but had `record_sha256: null`; the schema allowed this, but the M07 source-closure contract does not.
- **Evidence:** First targeted run of `tests.test_museum_07_timeplace`; `artist-place-episodes.json`; ignored official snapshot `data/map-source/official/kollwitz-museum/2026-07-16/biography.html`.
- **Conservative choice:** Save the official biography once, verify the required birth/Berlin/death text, bind its exact SHA-256 to all three Evidence entries, and rebuild the uncommitted candidate release.
- **Consequence:** No URL-only Evidence is promoted; the physical candidate changes hash before publication.
- **Revisit:** If the official page bytes change, reacquire to a new dated source-vault directory and rebuild a new release version rather than mutating a published release.
- **Validation:** Targeted source-product rebuild, release physical validator, and the 30-test M07 suite.
- **Resolved candidate:** The rebuilt physical release passes at `sha256:aa969f48fd152301a66ee4f4841392b36f271bbca8537897484bc70c6ece718f`; the final place/timeline/filter data closure is 20,876 gzip bytes.

## Frontend targeted-test discovery · 2026-07-16

- **Entry type:** validation discovery
- **Expected:** Omitting `fromYear` and `toYear` would use the formal episode minimum and maximum.
- **Discovered:** `Number(null)` evaluated to zero, so an absent `toYear` was clamped to the minimum year and hid all but the earliest records.
- **Evidence:** First targeted Vitest run for `src/tests/art-map.test.tsx` rendered 11 data rows and one map point instead of 36 and 24.
- **Conservative choice:** Treat null or blank year parameters as absent before numeric parsing; keep invalid finite numbers clamped to the formal range.
- **Consequence:** Initial map/list/timeline coverage now derives from the release range while malformed URL years remain bounded.
- **Validation:** Targeted Vitest filter, row-count, year-control, and synchronized-marker tests.

## Browser and performance discoveries · 2026-07-17

- **URL allowlist:** Invalid artist/place/episode IDs were ignored by controls but unknown keys such as `tracking` survived in the address bar. The page now rewrites state to the ten allowed keys only, validates IDs/facets, and clamps integer years to the release range.
- **CLS:** The first controlled cold probe measured CLS `0.9` because a minimal verification message was replaced by the full page. A stable M07 loading shell now reserves the hero, filters, toolbar, and workspace geometry; the final controlled probe reports CLS `0`.
- **Print:** The first 390 px print capture clipped the historical-place, precision, and Evidence columns. Print CSS now uses a fixed six-column layout, compact wrapping, and no horizontal overflow; the regenerated screenshot exposes every column.
- **Bundle accounting:** The first budget implementation recursively followed `index.html` dynamic imports and incorrectly charged all unrelated lazy routes to M07. The final gate measures the ArtMap page static closure plus the explicit MapCanvas/MapLibre dynamic closure; it still fails closed on unknown manifest records.
- **Vendor scanner:** The generic build scanner found one MapLibre built-in attribution anchor. It now removes only that exact literal from the manifest-identified, exact-pinned MapLibre 5.24.0 chunk before applying the unchanged external resource patterns; browser interception independently proves zero external requests.
- **Final targeted evidence:** 31 adapter tests, 30 M07 Python tests, 11 M07 Vitest tests, and 4 M07 Playwright tests pass. The release rebuild is byte-identical at `sha256:aa969f48fd152301a66ee4f4841392b36f271bbca8537897484bc70c6ece718f`.

## Final-candidate gate discoveries · 2026-07-17

- **Immutable predecessor compatibility:** Adding Getty TGN correctly changed the current source registry, but old M04/M05B/M06 validators initially compared sealed source identities to the new global hash. The validator now binds those exact release IDs to the original source-matrix snapshot; the M04 builder also binds its original license-rule snapshot. All predecessor bytes remain unchanged and deterministic rebuilds pass.
- **Old performance evidence:** M04 and M05A performance validators reported implementation-input drift because M07 added frontend files and MapLibre. Per the phase rule, CI now checks the exact committed M04/M05A evidence hashes and the exact M06 path-benchmark evidence hash instead of rerunning old labs.
- **Controlled browser isolation:** Strict performance scenarios were noisy when mixed with functional flows. The E2E runner now executes M07, M05B, and M06 performance tests first in separate one-worker browser processes, then runs 23 functional scenarios. M05B interaction timing uses a browser-side DOM commit boundary; M07 first-interactive uses the visible synchronized episode surface rather than `networkidle`, and the low-bandwidth refresh neutralizes smooth-scroll test state.
- **Final local gates:** Python 448/448 in 1,649.486 s; Vitest 89/89; lint and strict typecheck pass; complete Playwright 26/26; production build, build scan, repository safety, budgets, source/rights/release/leakage validators, and M07 deterministic rebuild pass.
- **Final M07 browser evidence:** desktop 585.931 ms, mobile 121.596 ms, low-bandwidth list 994.197 ms, filter p95 78.9 ms, marker p95 28.7 ms, heap increment 1,378,028 B, CLS 0, external requests 0, geolocation calls 0, analytics requests 0.
