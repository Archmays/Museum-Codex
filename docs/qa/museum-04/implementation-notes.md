# MUSEUM-04 media-aware implementation notes

## Task contract

- **Goal:** publish “艺术星海：观察与比较 / Constellation of Art: Observation and Comparison” as a static, media-aware formal release.
- **Inputs:** immutable MUSEUM-03B package (`12/44/31/36`, A/B/C=`0/0/36`) and MUSEUM-03C media bundle `sha256:3aa84fa7df37c4823cd2cb1f92c7e1843e7dea70b7cfd683528b25698951d565`.
- **Public scope:** 12 artists, 44 artwork metadata records, 31 contexts, 36 non-causal C-level relations, necessary Claim → Evidence → Source records, and only approved MUSEUM-03C derivatives.
- **Media boundary:** 31 works have self-hosted media; 13 remain explicit no-image records. No source original, external runtime media, blocked media, unknown-rights media, or development-only record is public.
- **Experience:** graph, artist list, and relationship table remain equivalent; the initial graph has 12 equal nodes and no visible edges; focus reveals one-hop C relations only.
- **Not in scope:** MUSEUM-05 routes, A/B relationships, algorithmic similarity, causal influence, Arms, Biology, MUSEUM-06, or external runtime APIs.

## Consequential decisions

| ID | Evidence and risk | Resolution |
|---|---|---|
| U-01 | The pre-media WIP encoded zero media across schemas, fixtures, loader, UI, workflow, and reports. Partial replacement would create conflicting truths. | Replace the contract end-to-end with release `1.0.0`; remove public `0.1.0`; retain only an explicitly superseded editorial worksheet. |
| U-02 | A manifest could be self-consistent while its source URL, rights, notice, attribution, or withdrawal fields drifted together. | Rebuild the expected projection from sealed M03B/M03C inputs and compare every parent, child, source, rights, attribution, notice, and withdrawal row exactly. |
| U-03 | Initial DTOs or static HTML/CSS could address images while a report still declared zero requests. | Scan the actual Vite build and initial JSON; reject HTML image/preload, CSS image/data URL, external runtime resources, or initial media locators. Browser evidence independently measures requests and bytes. |
| U-04 | Release URLs are data and become navigation targets. | Fail closed unless artwork links match the exact AIC/Met object ID and HTTPS host/path; rights requests allow only the same-origin route or the repository issue URL. |
| U-05 | Performance evidence can become stale after code or release changes. | Bind current evidence to all `src/` files, lockfile, build config, release manifest, contract, and budget scripts; bind scale evidence to its exact harness and contract inputs. |
| U-06 | No physical low-memory Android or real assistive-technology environment is exposed. | Record `not_available`; keep Chromium throttling, forced-colors, reduced-motion, keyboard, and screen-reader semantics as controlled evidence only. |

## Formal release closure

- Release ID: `release:art-constellation-1.0.0`.
- Content hash: `sha256:52835bb9256a9e50c2b73b9ef2e4fb99aa4a40434f20319133fdfb56b09fc462`.
- Manifest SHA-256: `sha256:0fa7046a6b47eb9c73abc2279157f745888eeb76e7445fb18810269b04ec5346`.
- Physical closure: 264 files, 39,436,869 bytes; manifest lists 263 children plus itself.
- Runtime media: 242 JPEG/WebP derivatives, 35,907,176 bytes; roles are 124 thumbnail, 60 detail, and 58 zoom.
- Common media closure: 31 source-provenance parents plus 242 adaptation children = 273 IDs; source originals are not runtime assets.
- Artwork decisions: 31 approved self-hosted and 13 no-image (`7 metadata_only_after_automated_review`, `4 blocked_source_unavailable`, `2 blocked_rights_conflict`).
- Signoff: automated pass; `human_review_dependency=false`; no human reviewer is claimed.

## UI and accessibility implementation

- The formal `1.0.0` loader verifies manifest-bound artifact hashes, typed DTOs, exact local derivative paths, HTTPS object URLs, rights URLs, and blocked/no-image boundaries; the build-time validator separately recomputes the top-level release content hash.
- Representative images and relation thumbnails load only after focus; low-bandwidth mode requires explicit activation. Images use JPEG/WebP `srcset`, `loading=lazy`, `decoding=async`, factual alt text, and visible attribution/license/withdrawal/source context.
- Closing a panel aborts artist, relationship, and rights requests. Loading, loaded, failure, fallback, and filter results are announced without relying on color.
- Keyboard, focus restoration, 44 px media actions, forced colors, reduced motion, 390/360 px layouts, WebGL loss, and no-JavaScript explanations are covered by automated browser scenarios.

## Performance design

- Home remains below the approved +15% gzip ceiling and contains no graph library.
- Initial constellation data excludes runtime media addresses; media/rights/notices/withdrawal JSON is deferred.
- Current graph evidence uses four controlled profiles and records real resource timing, LCP, CLS, interaction, FPS, heap, transferred bytes, initial/deferred media, and deferred governance requests.
- Scale evidence uses a real capped Sigma renderer for 1k, partition/search/local rendering for 10k, and refuses 50k/300k mobile full WebGL while executing a bounded typed-array model and chunk plan.
- Application console warnings/errors, request failures, HTTP failures, and unexpected external resources fail. The sole explicit environment diagnostic classification is Chromium's exact WebGL `GPU stall due to ReadPixels` driver message; it is not treated as an application warning.

## Superseded evidence

- `public/releases/art-constellation-0.1.0/` was unpublished WIP and has been removed.
- `artist-summary-human-editorial-review-packet.md` is retained only with `status: superseded`; it is not formal evidence or a human approval.
- The prior zero-media phase report, adversarial result, performance files, and screenshots are replaced by the media-aware closeout artifacts in this directory and `docs/phase-reports/phase-museum-04-report.md`.
