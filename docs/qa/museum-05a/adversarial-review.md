# MUSEUM-05A adversarial review

Date: 2026-07-15 (Asia/Shanghai)
Scope: artist index, 12 artist galleries, 44 artwork details, basic zoom, compare, release loader, build/performance gates and browser evidence.

## Result

Final severity count is `P0=0 / P1=0 / P2=0`. The remaining items are non-blocking P3 evidence limits listed below. This review does not treat automated Chromium as a real device or assistive-technology session.

## A — Data identity and evidence

- The gallery consumes only `release:art-constellation-1.0.0`; 12 artists and 44 artworks close exactly once through the artist records.
- Artwork details validate artwork to artist to Claim to Evidence to Source references before rendering.
- The Claim parser accepts both schema-valid entity objects and literal value objects; it no longer fails on reviewed artist claims while selecting artwork claims.
- Each displayed Evidence item now links its exact Source record, followed by the complete source-and-rights list.
- Unknown route IDs fail closed to a stable not-found state.

Status: pass.

## B — Rights, media and withdrawal

- Runtime media contains 242 release-local derivatives for exactly 31 `approved_self_hosted` works.
- Seven metadata-only, four source-unavailable and two rights-conflict records expose no image path; blocked runtime assets are zero.
- Local asset selection is same-origin and restricted to the versioned release derivative path. Official object URLs are links, never image hotlinks.
- Attribution, license, changes statement and withdrawal status remain visible with rendered media. Decode failure preserves metadata and official-source access.
- No generated substitute, crop, upscale, watermark removal, remote tile service or external delivery was introduced.

Status: pass.

## C — Security and routing

- Artist/artwork IDs and compare query values must exist in the formal catalog; invalid or duplicate selections are removed from URL state.
- The loader verifies manifest hashes and same-origin artifact URLs before parsing.
- Static validation scans JSX single/double-quoted literal media URLs, JSX string expressions and CSS remote `url(...)`; browser checks additionally require zero external requests, request failures and HTTP errors.
- Repository safety, secrets, large-file and public/private leakage gates remain part of final AUTO-01 validation.

Status: pass.

## D — Accessibility and responsive interaction

- Native search/select/button/link controls, visible focus, 44-pixel targets, factual localized alt text and non-color-only states are present.
- Loaded SPA routes focus `main#main-content`; retry/loading/failure states are distinct.
- Zoom supports buttons, `+`, `-`, `0`, arrow-key pan and pointer pan; decode failure has a polite status announcement.
- Duplicate zoom instances use unique ARIA IDs. Compare stacks at 390/360 pixels.
- Forced colors, reduced motion, no horizontal overflow and low-bandwidth behavior pass browser automation.

Status: pass within automated evidence; real AT/device status remains `not_available`.

## E — Performance and layout stability

- The gallery shell and four pages are direct lazy chunks and absent from the home initial closure.
- Home is 98,684 bytes gzip against 102,942; gallery initial JSON is 63,263 against 131,072; the largest gallery route is compare at 84,204 against 460,800.
- Home embeds zero of 242 media locators. Low-bandwidth index and compare request zero images.
- Zoom uses approved JPEG `srcset`/`sizes`; the mobile normal-bandwidth profile transfers a 74,246-byte image, while the on-demand desktop observation route may choose the approved 1600w derivative and remains below its one-megabyte image budget.
- Initial loading states reserve the route viewport and detail loading keeps the final page width. Controlled-lab CLS is 0 for all five profiles; the first run's 0.13–0.85 regression was not waived.
- Performance evidence uses a fixed implementation-input set, three samples, five fixed profiles and validator-recomputed median, p95, targets, assertions and hashes.

Status: pass.

## F — Test integrity and remaining limits

- M05A browser suite: 5/5 pass, covering all 12 artist and 44 artwork routes, exact 31/13 image states, focus, zoom, compare, mobile, forced colors, reduced motion, decode failure and runtime network monitoring.
- Performance-validator adversarial tests: 13/13 pass; build-budget adversarial tests: 4/4 pass.
- Formal M05A validator requires the complete M04 release first, then rechecks gallery counts, media decisions, paths and blocked-media exclusion.

Remaining P3:

1. All 44 artwork routes are traversed in low-bandwidth mode; normal-bandwidth decode and responsive-candidate behavior are sampled across representative approved works rather than all 31.
2. The defense-in-depth `blocked_runtime_ids` branch is protected by the stricter upstream M04 physical-release gate and is not independently reached by a deliberately re-signed malicious bundle fixture.
3. Static source scanning cannot prove the value of every runtime variable; zero external requests in real Chromium and same-origin loader enforcement supply the runtime closure.
4. No physical touch device or real NVDA, JAWS, VoiceOver or TalkBack session was available. Pointer, keyboard, forced-colors and DOM automation are not reported as substitutes.

These P3 items do not permit blocked media, rights ambiguity, broken routes or unmeasured layout instability into the release.
