# MUSEUM-05A implementation notes

Date: 2026-07-15 (Asia/Shanghai)

## Release boundary

MUSEUM-05A consumes the validated static `release:art-constellation-1.0.0`; it does not introduce a second artwork dataset or a runtime API. The gallery loader requires 12 artists, 44 artwork records and 242 approved derivatives before a route becomes ready. Artwork detail loading additionally validates artwork to artist to Claim to Evidence to Source closure.

Only release-local paths matching the approved derivative contract can become image `src` values. The 31 `approved_self_hosted` works can render reviewed derivatives; the remaining 13 records preserve their exact metadata-only or blocked decisions and expose no runtime media. Official object links remain metadata navigation, not image hotlinks.

## Routes and experiences

- `#/art/artists`: release-order index for all 12 artists, with text, period and image-state filters. Image availability is explicitly separated from artistic standing.
- `#/art/artists/:artistId`: reviewed introduction, timeline summary, two to four formal works, exact media decisions, source and rights records, and non-causal C-level related artists.
- `#/art/artworks/:artworkId`: all 44 records are addressable. Each page retains metadata and official-source access when no image is approved.
- `#/art/compare`: two independently selected works, URL state, metadata comparison, independent zoom, observation prompts, and an explicit boundary against AI similarity scores or influence claims.

## Media and observation controls

Index and gallery images use approved responsive derivatives with lazy loading and asynchronous decode. The observation component chooses the largest approved local JPEG as its fallback while supplying the full approved JPEG width set through `srcset` and `sizes`. Its maximum zoom is calculated from the image width actually decoded by the browser, so a smaller responsive choice is never enlarged beyond its natural pixels.

Low-bandwidth mode creates no artwork image element until the visitor explicitly requests that individual image. Decode failure replaces the image with a stable no-image state, preserves metadata and official links, and announces the failure through a polite status region. No crop, upscaling, generated substitute, remote tile service or content-changing operation occurs in the browser.

## Accessibility and responsive behavior

All four routes have keyboard-reachable native controls, visible focus, factual alt text, 44-pixel control targets, forced-colors rules, reduced-motion rules, and 360/390-pixel layouts. Route transitions focus the loaded `main` landmark. Zoom supports buttons, `+`, `-`, `0`, arrow-key panning and pointer/touch panning. Compare stacks on mobile and keeps the two zoom instances' ARIA references and state independent.

Automated checks cover DOM semantics, keyboard paths, forced colors, reduced motion, narrow layouts, request failures and image decode failure. No real assistive-technology or physical-device session was available; those statuses remain `not_available` and are not inferred from Chromium automation.

## Closed integration findings

1. The initial detail implementation required a `role=zoom` derivative and hid one approved lower-resolution work. The selector now falls back to the largest approved detail/thumbnail derivative and retains the natural-pixel cap.
2. Artist relationship/source fetch failures were initially indistinguishable from reviewed empty data. Loading, failed and valid-empty states are now distinct; failure is announced and never represented as an empty relationship result.
3. Decode failure initially removed the image without a live announcement. The stable fallback now includes a screen-reader status message.
4. Route retry initially set loading state synchronously inside an effect. Attempt identity now derives the visible loading state without a cascading effect update.

## Evidence outputs

- Browser suite: `e2e/museum-05a.spec.ts`
- Browser result: `docs/qa/museum-05a/playwright-results.json`
- Local screenshots: `docs/qa/museum-05a/screenshots/`
- Build budget evidence: `docs/qa/museum-05a/bundle-budget.json`
- Controlled performance evidence: `docs/qa/museum-05a/performance.json`

These local artifacts are phase evidence, not proof of the final GitHub Pages deployment. Online evidence is recorded separately under `docs/qa/museum-auto-01/final-online/` only after the final unified push.
