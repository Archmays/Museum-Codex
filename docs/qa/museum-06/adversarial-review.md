---
phase_id: MUSEUM-06
review_status: pass
reviewed_at: 2026-07-16
p0_count: 0
p1_count: 0
p2_count: 0
p3_count: 3
---

# MUSEUM-06 adversarial review A–F

## A — Historical and relationship semantics: pass

- Historical, context, and comparison modes are level-separated at filter time and in every serialized result.
- The formal graph remains A/B/C = 0/0/36. Historical and context modes therefore return the accurate no-path state; comparison is always labeled `C｜策展比较`.
- All nine existing A/B leads reached an automated terminal disposition: 0 promoted, 1 retained for more evidence, 0 rejected, 8 out of scope, 0 superseded. No human-review or user-approval state exists.
- Every path step closes to Claim → Evidence → Source, supporting works, rights attribution, direction, confidence, and active withdrawal state.
- No shortest path is described as a historical transmission chain. Comparison copy explicitly denies acquaintance, influence, instruction, and transmission.

## B — Algorithm: pass

- Python reference and TypeScript Graphology implementations use unit-hop bidirectional BFS and bounded loopless Yen alternatives.
- `K<=3`, `max_hops<=6`, and the shared candidate expansion limit `<=10000` are fail-closed.
- Sorting is the declared tuple; no scalar influence score, popularity, degree, media, or algorithmic-similarity weight exists.
- All 66 default pairs match exactly between build and browser implementations, including path nodes, relation IDs, and ranking tuples.
- Synthetic 50k/300k returns `search_budget_reached` at exactly 10,000 expansions; no-path remains a distinct status.

## C — Product and learning: pass

- Native endpoint search/select controls cover Chinese, English, and aliases; swap, same-endpoint prevention, three modes, filters, alternatives, print, and share URL are present.
- Graph highlights preserve non-path nodes and edges in a dim state, use fixed node sizes, number path order, retain dotted C edges, and reserve arrows for directed relations.
- The full text path remains present independently of the graph and supports ordered steps, alternatives, Evidence/Source expansion, and links to supporting works.
- Invalid start/end, identical endpoints, incompatible release, tampered index, runtime failure, no path, and budget exhaustion have distinct UI states.

## D — Accessibility: automated pass; real AT/device unavailable

- Keyboard navigation, native controls, visible focus, live status, headings, ordered lists, textual direction and A/B/C labels, 44px controls, 360/390 overflow, forced colors, reduced motion, print, and low-bandwidth/WebGL fallback pass automated checks.
- Text is not hidden when graph view is active; canvas/WebGL is never the only channel.
- Real assistive-technology and physical-device sessions are `not_available`; no real-device pass is claimed.

## E — Engineering and performance: pass

- Release `release:art-pathways-1.2.0` is an immutable seven-file overlay over the byte-identical M05B predecessor; 273 physical files and exact hashes close.
- Home gzip is 99,390 B, path route 125,892 B, default index 40,536 B, and path JS/algorithm closure 35,780 B.
- Current query p95 is 0.509 ms; 66-pair build is 14.09 ms; 1k/5k median is 10.907 ms; 10k/60k median is 206.317 ms.
- Controlled route interaction p95 is 32.0 ms, mobile heap increment is 4,862,852 B, CLS is 0, and external requests are 0.
- M04 current 12-node and M05A current gallery profiles were refreshed because shared inputs changed. M04 1k/10k/50k scale rendering and the M05B full performance matrix were not rerun.

## F — Scope, rights, and publication: pass

- Work stayed on linear `main`; no branch, worktree, or PR was created.
- No M07, map, analytics, path/query history, new media, dependency update, open-web relationship search, private lead, hotlink, blocked media, or algorithmic relation was added.
- M03C 242-file media closure, source registry, publishable media rights, public/dist leakage, and repository safety scans pass.
- OD-006, OD-008, OD-009, and OD-011 remain open.
- Actions, Pages bytes, and live-route closure are recorded after deployment in the phase report and online evidence.

## Resolved findings

| Severity | Finding | Resolution |
|---|---|---|
| P1 | Dataset manifest declared two referenced nested schemas as top-level consumed schemas. | Reduced `schema_versions` to exact physical top-level bindings; query/result schemas remain versioned and recursively validated. |
| P1 | A hidden mode ordinal intercepted pointer input. | Removed the decorative ordinal from layout and pointer flow; targeted Playwright closure passed. |
| P1 | M04 home scanner treated the lazy chunk filename `graphology-*` in a preload map as initial graph code. | Kept the engine lazy and assigned a neutral `relationship-engine` chunk name; home code remains graph-library free and the inherited gate passes. |
| P2 | Two schema-count tests remained fixed at 65 after three M06 schemas were added. | Updated the exact expected count to 68; the two-test closure passed. |
| P2 | Two E2E assertions still named the 1.1 asset path / treated CSP-blocked no-script JS as a network failure. | Bound current asset assertions to 1.2 and required any no-script failure to be an expected JS `csp` block. |

## Open P3 register

| Finding | Owner | Mitigation | Latest resolution point |
|---|---|---|---|
| Inherited supplemental M04 1k graph FPS median is 27 versus informational 30; formal scale evidence otherwise passes. | Frontend performance owner | Preserve lazy graph/data boundaries; do not widen visible graph caps. | Before a separately authorized scale-expansion phase. |
| Real AT and physical touch-device sessions are unavailable. | Accessibility QA owner | Retain automated semantics, keyboard, forced-colors, reduced-motion, touch-emulation, mobile, print, and text-equivalence evidence. | Before a future phase explicitly requiring real-device certification. |
| Public cold-route latency varies with CDN/TLS/geography and has no analytics/RUM stream. | Web performance owner | Keep controlled budgets as the release gate and record bounded live smoke timing without tracking. | Before a future phase raises the public-network latency requirement. |

No P0, P1, or P2 remains open.
