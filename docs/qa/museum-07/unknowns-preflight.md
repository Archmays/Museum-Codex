# MUSEUM-07 unknowns preflight

## High-tweak decisions

1. **Data model:** one immutable overlay adds strict place, episode, creation/holding, basemap, attribution, style, and shared-state artifacts while preserving all M06 bytes.
2. **Public behavior:** map, timeline, and table share one allowlisted URL state; map rendering is optional and never required to inspect, filter, select, cite, share, or print an episode.
3. **Release boundary:** all runtime assets are local; raw Natural Earth and TGN responses stay in `data/map-source/**`; reviewed normalized data and canonical GeoJSON are versioned.
4. **Historical semantics:** TGN coordinates are finding aids. City and region centroids show explicit precision/halos; modern jurisdictions are secondary; no borders or inferred routes are rendered.
5. **Fail-closed rule:** unresolved identity, coordinate, time, or creation-place evidence becomes list-only, retained, rejected, or not-asserted—never guessed.

## Blindspot pass outcome

- The repository has no `skill/SKILL_INDEX.md`; no project skill was selected or invented.
- `main` is clean at the requested baseline `6bb66328f75d93aeec5c1661d4d89987120cfd63`.
- The M06 manifest/hash/count closure matches the user-provided entry contract.
- Existing release loaders are fail-closed and route-specific; M07 should follow the established lazy overlay pattern.
- M06 recorded real-device and real-AT status as unavailable; M07 must preserve that honesty.
- M06's reliable release order remains: contract/release closure, leakage, targeted tests, frontend/build, browser/performance, full candidate, Git/Actions/Pages, live screenshots/byte closure.
