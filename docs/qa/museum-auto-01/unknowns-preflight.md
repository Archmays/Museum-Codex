# MUSEUM-AUTO-01 unknowns preflight

## Task contract

- Goal: consolidate the existing M04 WIP on one linear `main`, acquire and validate real media, publish a media-aware constellation, conditionally build M05A, then pass CI and live Pages QA.
- Context: sealed M03B plus a pre-existing local zero-media M04 checkpoint.
- Constraints: no branch, worktree, PR, force push, history rewrite, sealed-data overwrite, unknown-rights media, secret, generated substitute, or automatic advancement beyond M05A.
- Done when: every public media byte has identity/rights/byte/quality closure, formal release closure passes, required UI and tests pass, Actions/Pages pass, and local/origin/remote converge with a clean worktree.
- Must not touch: sealed M03B package contents, source snapshots, licensed originals, unrelated museum branches, or M05B/M06.
- Evidence sources: AGENTS files, M03B package/report, source registry and rights policy, Git/reflog/remote state, M04 checkpoint diff, automated validators, source APIs, acquired-byte records, production build, Actions, and live Pages.
- Current stage: pre-implementation.

## Consequential unknown register

| ID | Category | Evidence | Consequence if wrong | Resolution |
|---|---|---|---|---|
| U-01 | unknown unknown | Prompt described dirty WIP; live state was clean and ahead one commit | Could duplicate, overwrite, or lose WIP | Resolved from reflog and exact `A=98/M=36` parent diff; preserve commit |
| U-02 | known unknown | M03B has eligibility decisions but no media bytes | Public media could lack live identity/rights closure | Resolve per object in live M03C pipeline; fail closed |
| U-03 | known unknown | Met assessments do not preserve current image URLs | Download plan could use stale or wrong bytes | Live official object rediscovery before every acquisition |
| U-04 | known unknown | Four AIC objects are external-IIIF candidates | Runtime hotlink policy or rights may not close | Re-evaluate official API/IIIF; self-host only if full closure passes, otherwise external/metadata-only |
| U-05 | unknown unknown | Current M04 contract is systemically zero-media | Partial edits could make release/loader/UI disagree | Change projector, schemas, fixtures, tests, bundle, loader, UI, workflow together |
| U-06 | known unknown | Real browser/device environments vary | Performance/accessibility claims could be overstated | Use executable lab/E2E evidence; record real device as `not_available` when absent |
| U-07 | known unknown | GitHub/Pages state can change during long run | Push/deploy could diverge | Reverify remote before push, poll Actions, byte-match live Pages after deploy |

## Selected discovery methods

- `blindspot-pass`: smallest method that exposes Git/data/rights/release boundary risks before writing.
- `implementation-notes`: required because the multi-stage run can reveal source drift, media failures, and gate deviations.

## Stop conditions

Stop before public mutation or push only for sealed-package damage, secret exposure, systemic rights failure, unresolved data-loss conflict, non-fast-forward main drift, unfixable P0/P1, blocked media in release, or force push as the only path. Individual media failures degrade per object and do not stop the run.
