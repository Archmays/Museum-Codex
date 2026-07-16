# MUSEUM-05B implementation notes

Date: 2026-07-16 (Asia/Shanghai)

## Task contract

- **Goal:** add evidence-bounded observation cards, fixed artist/thematic tours, deterministic detail navigation, lenses, enhanced compare, print/share, and an immutable `1.1.0` static release.
- **Context:** consume the validated M03C media bundle and M04/M05A public runtime without re-researching or rewriting approved media.
- **Constraints:** `main` only; one formal writer; no arbitrary artist pathfinding, new causal relationship, algorithmic similarity, analytics, local history, remote media hotlink, or MUSEUM-06 work.
- **Done when:** 44 cards, 12 artist tours, 6 thematic tours, 12 hero selections, visual detail regions for image heroes, textual paths for no-image heroes, complete release closure, targeted and final gates, Actions/Pages evidence, and clean synchronized Git.
- **Must not touch:** the immutable M03C bundle, `release:art-constellation-1.0.0`, open decisions OD-006/008/009/011, or other museum halls.
- **Evidence sources:** phase reports, M03C ledger/manifest, M04 manifest, M05A implementation/adversarial notes, policies, schemas, loaders, tests, live official object status, Actions, and Pages.
- **Current stage:** completed online closure.

## Entry 1

- **Entry type:** discovery
- **Expected:** the requested baseline commit is a clean, synchronized `main` with unchanged protected inputs.
- **Discovered:** `HEAD`, `origin/main`, and live remote main are all `3b86d11e7a2c8749d3463baeeb2f6a4f5bdb1996`; `git status --porcelain` is empty. M04/M05A/M03C validators confirm 12/44/31/13/242 and the declared protected hashes.
- **Evidence:** Git preflight plus `validate_museum_04_release.py --require-public`, `validate_museum_05a.py`, and `python -m museum_pipeline.media validate-bundle`.
- **Conservative choice:** reuse the sealed release/media bytes and skip full Python, scale benchmarks, downloads, derivatives, layout, and search-index rebuilds at entry.
- **Consequence:** implementation can proceed without touching protected artifacts.
- **Revisit:** any input hash mismatch or unexpected dirty path.
- **Validation:** baseline validators returned `ok=true` with zero failures/issues.
- **Fold into next attempt:** preserve hash-only entry audit for compatible future overlays.

## Entry 2

- **Entry type:** decision
- **Expected:** M05B needs a new physical release without duplicating the M04 projection implementation.
- **Discovered:** the existing runtime and schemas bind M04 core artifacts to the `1.0.0` release ID, while all 263 manifest children are immutable and independently hashed.
- **Evidence:** `public/releases/art-constellation-1.0.0/manifest.json`, `museum_pipeline/art/public_release.py`, and `src/data/release-loader.ts`.
- **Conservative choice:** create an immutable overlay release. Copy every predecessor child byte-for-byte, replace only `manifest.json`, add one strict `interaction-index.json`, and teach the loader to distinguish the overlay manifest ID from the embedded predecessor core ID.
- **Consequence:** old media, rights, layouts, search index, and the old release remain byte-identical; M05B data gets its own hash and schema.
- **Revisit:** only if the formal validator shows the common release schema cannot represent the overlay.
- **Validation:** pending staged build and deterministic rebuild comparison.
- **Fold into next attempt:** prefer immutable overlays for additive interactions when predecessor bytes remain authoritative.

## Consequential unknown register

| ID | Category | Evidence | Consequence if wrong | Resolve now / defer | Resolution or owner | Confidence |
|---|---|---|---|---|---|---|
| U-01 | known unknown | 13 no-image records have M03C terminal decisions from 2026-07-15. | A changed official media status could require a new bundle. | Resolve now with one bounded official status check per applicable source; no image-byte download. | M05B automated retry. | high |
| U-02 | known unknown | Eight artists have approved media; four have none. | A forced visual hero would fabricate availability. | Resolve now with eight visual heroes plus four `textual_observation_path` heroes. | Deterministic builder. | high |
| U-03 | unknown unknown | New interaction data could accidentally loosen M04 rights or release closure. | Blocked media or unverified references could reach Pages. | Resolve now with predecessor byte equality, strict schema, cross-reference, wording, rights, and physical-file checks. | M05B validator. | high |
| U-04 | known unknown | Real AT and physical touch devices are not exposed. | Automated coverage could be overstated. | Defer as P3 and record `not_available`; retain keyboard/DOM/touch-pointer automation. | Phase report. | high |

## Entry 3

- **Entry type:** deviation
- **Expected:** each bounded media source receives at most one current-status probe.
- **Discovered:** the read-only media audit completed 6 AIC object GETs, 4 AIC IIIF HEADs, and 7 Met object GETs while the primary writer had already started the same bounded script. The writer process was terminated as soon as the overlap surfaced; it emitted no result, but may have reached the first AIC object/IIIF pair.
- **Evidence:** sub-agent request inventory and terminated writer process cell; no media GET, image bytes, derivative, or vault write occurred.
- **Conservative choice:** perform no further network request in M05B, exclude the possible duplicate from evidence, preserve all prior terminal decisions, and mark media retry `partial` because the seven Met responses were sent but their response formatting was not reliably captured.
- **Consequence:** the media outcome remains 31 approved / 13 no-image with zero downloaded bytes; the possible duplicate probe is an efficiency deviation and is not hidden.
- **Revisit:** none in this phase unless a protected input hash fails; do not retry the 13 works again.
- **Validation:** persistent media-retry artifact records the exact usable evidence and cache-reuse boundary.
- **Fold into next attempt:** allocate network ownership before launching parallel discovery, not after.

## Entry 4

- **Entry type:** implementation decision
- **Expected:** additive interactions must remain physically closed without rewriting the M04 release or M03C media.
- **Discovered:** all 263 predecessor manifest children can remain byte-identical while two typed overlay records carry M05B interactions and retry evidence.
- **Evidence:** `interaction-index.json`, `media-retry.json`, exact predecessor byte checks, canonical schema dispatch, and deterministic rebuild tests.
- **Conservative choice:** publish `release:art-gallery-interactions-1.1.0` as an immutable overlay with predecessor `release:art-constellation-1.0.0`.
- **Consequence:** the final content hash is `sha256:c07330d92d03b41fe57b5e80394e7e89e875945a9d24e7a5c73029b3283a8009`; the old release and media bundle remain unchanged.
- **Validation:** 44 cards, 12 artist tours, 6 thematic tours, 12 hero selections, 24 structural regions, 8 visual paths, and 4 textual paths close exactly.

## Entry 5

- **Entry type:** adversarial correction
- **Expected:** bilingual tours, release scanning, and inherited tests should accept only the new validated release contract.
- **Discovered:** independent review found untranslated period/place text, one doubled Chinese title bracket, old E2E URL interceptors, and leakage/schema allowlists that knew only the predecessor release.
- **Conservative choice:** add deterministic Chinese registry labels, fix title wrapping, gate the exact M05B public path behind the full release validator, retain all generic leakage rules, and update E2E interceptors to the current release.
- **Consequence:** no P0–P2 remains; invalid or unregistered release directories still fail closed.
- **Validation:** focused failure closures passed; generic M04 leakage guards remain passing.

## Entry 6

- **Entry type:** final-candidate validation
- **Expected:** run full gates once, then only failed dependency closures.
- **Discovered:** the one full Python run completed 386 tests in 1308.728 seconds with six contract-enumeration/allowlist failures; the one full E2E run passed 14/17 and exposed three predecessor-URL test injectors. No product, media-rights, or runtime failure was found.
- **Conservative choice:** repair only those dependency closures and rerun their exact tests. Shared frontend input hashes required fresh M04 current-graph and M05A route labs, while the 1k/10k/50k scale samples remained untouched and were hash-validated only.
- **Consequence:** lint, strict typecheck, 64/64 Vitest, 10/10 performance-runner contracts, build closure, budgets, release validators, public/dist leakage scans, repository safety, all six Python failure closures, and all three E2E failure closures pass.
- **Validation:** M05B home gzip is 98,891 bytes (+0.21%); tours 110,039; artwork interaction assets 26,670; interaction JSON 22,780; regions 1,918. The committed controlled tours probe records first interactive 1033.6 ms, LCP 820 ms, CLS 0, and interaction proxy 121.3 ms.
- **Runtime disclosure:** model and reasoning settings are `not_exposed_by_runtime`; real assistive technology and physical-device sessions are `not_available`.

## Entry 7

- **Entry type:** CI failure closure
- **Expected:** the first Pages run should rebuild the immutable interaction release byte-for-byte on Linux before deployment.
- **Discovered:** Actions run `29461364375` stopped at the M05B rebuild diff. The rebuilt release remained semantically valid with the exact 44/12/6/12/24 counts, but 61 persisted detail-metric floats differed by at most about `4.49e-4`; all 24 region IDs, rectangles, order, and every non-metric field were identical. Pillow 10.4.0 had decoded the fixed JPEG bytes slightly differently through the Windows and Linux/libjpeg SIMD paths.
- **Conservative choice:** disable libjpeg SIMD before Pillow imports in the release builder, persist the four structural metrics through an explicit `floor_0.01` quantizer, and advance only the detail-navigation algorithm contract to `1.0.1`. Coordinates and source-asset bindings are unchanged.
- **Consequence:** the formal release hash changes to `sha256:c07330d92d03b41fe57b5e80394e7e89e875945a9d24e7a5c73029b3283a8009`; no artwork, media byte, tour, card, lens, route, or semantic claim changes.
- **Validation:** captured Windows/Linux metric pairs quantize identically; an external SIMD override rebuild is byte-identical; M05B 14/14, the public validator, governance validator, compile check, and the affected budget closure pass.

## Entry 8

- **Entry type:** online closure
- **Expected:** the corrected candidate passes the complete Actions/Pages pipeline and resolves online to the exact local release bytes.
- **Discovered:** Actions run `29462218848` passed every build, test, budget, leakage, safety, E2E, upload, and deploy step; Pages deployment `5466417972` serves the expected manifest, interaction index, and retry artifact hashes. Six inherited live scenarios and five M05B non-performance scenarios pass, and an independent tours smoke confirms 12+6 routes, a working fixed tour, zero eager tour images, and zero runtime/external-request errors.
- **Conservative choice:** retain two public-network first-visit observations (3319.7 ms and 2613 ms) as P3 rather than reinterpret them as the controlled OD-005 probe. The committed controlled probe remains 1033.6 ms / LCP 820 ms / CLS 0 / interaction proxy 121.3 ms and passes.
- **Consequence:** M05B closes online without weakening performance budgets or hiding geographic/network variance.
- **Validation:** root and three formal release resources return HTTP 200; all online hashes and counts match; 209,495,583 bytes of generated build, trace, and temporary release output were removed from five verified workspace-local paths.
