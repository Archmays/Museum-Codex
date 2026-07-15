# MUSEUM-AUTO-01 implementation notes

## Entry 1

- Entry type: discovery
- Expected: approximately 36 modified and 98 untracked M04 files.
- Discovered: clean `main` at `15617a1d`, ahead of `origin/main` by one commit.
- Evidence: status, reflog, commit parent, and exact `A=98/M=36` parent diff.
- Conservative choice: preserve the commit, reconstruct the dirty inventory from Git evidence, and add a separate validated checkpoint without rewriting history.
- Consequence: the original dirty instant is not directly observable, but its exact path set is recoverable.
- Validation: local `main` is a fast-forward descendant of remote `main`.

## Entry 2

- Entry type: validation
- Expected: M03B is the immutable input baseline.
- Discovered: package validator, package hash, graph hash, counts, media distribution, and zero-byte state all match the declared baseline; checkpoint diff is empty for M03B sealed paths.
- Evidence: package validator plus package/graph manifest checks.
- Conservative choice: consume M03B but never rewrite it.
- Consequence: M03C outputs must live under new versioned paths.
- Validation: `12/44/31/36`, `0/0/36`, `31/4/9`, zero media bytes.

## Entry 3

- Entry type: decision
- Expected: generated outputs can be rebuilt.
- Discovered: old dist/test/tmp outputs and tracked M04 candidate release are reproducible; protected raw/review data is separate.
- Evidence: path classification and recovery manifests.
- Conservative choice: hash-copy all WIP and protected data outside the repository; remove only verified ignored build/test/cache directories.
- Consequence: no source or reviewed data is lost; stale outputs cannot contaminate later validation.
- Validation: every recovery entry has equal source/destination SHA-256.

## Entry 4

- Entry type: live acquisition
- Expected: 31 self-hosted candidates, 4 external IIIF candidates and 9 metadata-only works receive real automated review.
- Discovered: 44/44 official object responses and identities closed; 35 open locators remained current; 31 Met downloads succeeded, while four AIC IIIF requests returned HTTP 403.
- Conservative choice: approve only byte-closed media; record AIC as `blocked_source_unavailable` instead of treating reachability or rights eligibility as delivery approval.
- Consequence: M03C still exceeds the 28-work quality target with 31 approved self-hosted works.
- Validation: `31 approved_self_hosted / 7 metadata_only / 2 blocked_rights / 4 blocked_source_unavailable`, zero unknown/manual states.

## Entry 5

- Entry type: bundle closure
- Expected: responsive derivatives, exact hashes, notices, attribution and withdrawal mapping form one physical bundle.
- Discovered: 31 originals support 242 no-upscale JPEG/WebP derivatives; AVIF is unavailable in the installed runtime.
- Conservative choice: one media ID per derivative file, with artwork-level responsive aggregation deferred to M04.
- Consequence: the existing one-self-hosted-ID/one-storage-path physical validator can remain strict.
- Initial bundle validation was superseded after an independent blindspot review found provenance, semantic-closure, symlink-parent and quality-evidence gaps.
- Hardened recovery: pre-hardening bundle/ledger copied outside the repository to `D:\ChatGPT-Codex-Projects\Museum-Codex-Recovery\MUSEUM-AUTO-01-M03C-pre-hardening-20260715T004538Z`; 257 files / 36,926,213 bytes; recovery manifest SHA-256 `sha256:1695d0e9352b70745796c0499a11fb867774a849e8f988b7d02a69a6a286dad9`.
- Hardened validation: bundle content hash `sha256:3aa84fa7df37c4823cd2cb1f92c7e1843e7dea70b7cfd683528b25698951d565`, exact M03B/rights/parent/source/count closure, 0 validation issues.

## Entry 6

- Entry type: release revision and validation boundary.
- Expected: the pre-media M04 WIP would need end-to-end replacement rather than a narrow media-count patch.
- Discovered: the old unpublished `release:art-constellation-0.1.0` encoded zero media and a proposed human-editorial P0 across release, fixtures, loader, reports and workflow; it could not coexist safely with the M03C media bundle.
- Conservative choice: generate formal media-aware `release:art-constellation-1.0.0` from sealed M03B plus validated M03C, remove the public `0.1.0` candidate, and retain its editorial worksheet only as explicitly superseded audit history. Automated signoff records `human_review_dependency=false` and `human_reviewer_claimed=false`; no human review is inferred or fabricated.
- Consequence: the public bundle now closes 12 artists / 44 artworks / 31 contexts / 36 C relations, 31 approved-media works / 13 no-image works, 242 derivatives / 35,907,176 bytes, and exact rights/attribution/notices/withdrawal data. Physical closure is 264 files / 39,436,869 bytes.
- Validation: formal `--require-public` validation passed with content hash `sha256:52835bb9256a9e50c2b73b9ef2e4fb99aa4a40434f20319133fdfb56b09fc462` and manifest SHA-256 `sha256:0fa7046a6b47eb9c73abc2279157f745888eeb76e7445fb18810269b04ec5346`; current-graph and scale evidence report pass.
- Completed gate: the 28-fixture MUSEUM-04 matrix passed in four disjoint 7-fixture shards with exit codes `0/0/0/0`; 28 unique IDs passed, 27 expected-invalid fixtures were rejected, and one expected-valid fixture was accepted. Evidence run ID: `fff290ead038447096fcc9b1cc337639`. M04 is `completed/pass` and M05A is authorized; final push and Pages deployment remain deferred to the unified AUTO-01 closeout.

## Entry 7

- Entry type: frontend performance hardening.
- Expected: media-aware panels and governance data would remain deferred without weakening the approved current/scale budgets.
- Discovered: the initial implementation had avoidable sequential bootstrap fetches and panel-transition latency; repeated current-lab runs also exposed real threshold failures before optimization.
- Conservative choice: preload only the small initial manifest/artist/graph/search/layout/facet artifacts, keep all media/governance payloads deferred, render the panel shell immediately, swap already-open panel state synchronously, and preserve the original thresholds and visible render caps.
- Consequence: all current profiles pass with zero initial image bytes and zero initial deferred-governance requests. The constrained 360×800 profile reaches first-interactive median 2,288.6 ms and interaction p95 137.6 ms; 1k first-interactive median is 3,737.49 ms. Supplemental 1k FPS median 27.00 remains an explicit non-blocking P3.
- Validation: canonical current/scale evidence validators pass; the performance runner tests, static budgets and 5/5 local Playwright flows pass.
