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
