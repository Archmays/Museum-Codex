---
phase_id: MUSEUM-04
review_kind: adversarial_A-F
review_date: 2026-07-14
overall_status: blocked
formal_publication_allowed: false
museum_05_allowed: false
blocking_finding_ids:
  - M04-A-001
candidate_release_id: release:art-constellation-0.1.0
candidate_release_hash: sha256:9467b5449e13fd3e89272a62bc614fe776b22d14745bdbf72c4540d5e84e0cc4
candidate_summary_digest: sha256:42660e0a7a1d4a33548c82d8e942c747dbe42f20d3b2ef16ae92673114ea1da6
candidate_release_validation: pass
formal_public_release_validation: blocked_expected
performance_scale_validation: pass
m04_commits_created: false
m04_push_performed: false
m04_pages_deployed: false
m04_live_qa_performed: false
---

# MUSEUM-04 adversarial review A–F

## Decision

**BLOCKED.** The metadata-only bundle is a local reviewed candidate, not a formal public release. All 12 bilingual artist summaries have `human_reviewed=false`; the phase brief requires human review of AI-drafted summaries. The formal validator therefore fails closed with only `m04_human_editorial_review_required`. The candidate sign-off value `candidate_pending_human_editorial_review` is not publication authorization.

No MUSEUM-04 commit, push, Pages deployment, or live MUSEUM-04 QA has occurred. Local `HEAD`, `main`, and `origin/main` remain at baseline `2be73011cb1dca64cb8d3a2d5830f495671d755b`. MUSEUM-05 remains unauthorized and was not entered.

Status values: `RESOLVED` means the current local candidate has file, test, or evidence support; `OPEN_EXTERNAL` requires an accountable human; `BLOCKED_DERIVED` is withheld because of another open blocker.

## Findings

### A — Art history and relationships

| ID | Severity | Status | Evidence | Remediation / disposition |
|---|---:|---|---|---|
| M04-A-001 | P0 | OPEN_EXTERNAL | `artists.json` contains 12/12 `summary_provenance.human_reviewed=false`, all with `reviewer_kind=ai_assisted_operator`; `artist-summary-human-editorial-review-packet.md` remains pending; formal validation returns only `m04_human_editorial_review_required`. | An identified, accountable human must review all 12 Chinese/English pairs for factual accuracy, translation equivalence, neutral non-causal wording, unsupported influence/rank, and source traceability. Record every disposition and update the provenance/sign-off without backdating or AI self-approval; then rerun every formal gate. Blocks formal publication and MUSEUM-05. |
| M04-A-002 | P1 | RESOLVED | `relationships.json` has exactly 36 unique, endpoint/context-specific Chinese explanations; every edge is C-level, non-algorithmic, has supporting artwork/source/claim/evidence closure, and states a non-causal boundary. `tests/test_museum_04_release.py` enforces specificity and non-causality; candidate release validation passes. | Retain the deterministic semantic test and strict validator. |
| M04-A-003 | P2 | RESOLVED | Candidate counts are 12 artists, 44 artwork metadata records, 31 contexts, 36 relationships, A/B/C=`0/0/36`; relationship types are shared subject/material/technique only. | No action. |

### B — Product and learning

| ID | Severity | Status | Evidence | Remediation / disposition |
|---|---:|---|---|---|
| M04-B-001 | P1 | RESOLVED | `ArtConstellationPage.tsx`, `Views.tsx`, `DetailPanel.tsx`, and `model.ts` implement graph/list/table, search and filters, one-hop focus, artist/relation/source panels, synchronized URL state, A/B-empty semantics, and visitor-facing language. `playwright-results.json` records 5/5 local E2E scenarios passed. | Preserve equivalent core tasks in all three views. |
| M04-B-002 | P2 | RESOLVED | Local candidate and UI contain no gallery, dashboard/game/ranking, map, A/B path, generated relationship, or MUSEUM-05 experience. | Keep the phase boundary in regression checks. |

### C — Accessibility

| ID | Severity | Status | Evidence | Remediation / disposition |
|---|---:|---|---|---|
| M04-C-001 | P1 | RESOLVED | Graph canvas is decorative to assistive technology; the artist navigator, list, and relationship table expose equivalent tasks. Current code includes labeled tab/panel structures, sortable table headers, live status, keyboard tab navigation, Escape close, focus restore, and visible focus. `online.spec.ts` exercises keyboard/URL state and the recorded E2E run passes. | Retain semantic views as the source of accessible task equivalence. |
| M04-C-002 | P1 | RESOLVED | Low-bandwidth, compact viewport, forced-colors, reduced-motion, unavailable WebGL, and context-loss paths fall back to text/list behavior. The 390×844, mobile-list, and forced-colors screenshots show complete content without horizontal overflow or blank deferred regions. | Keep WebGL optional and never make the graph the sole route to content. |

### D — Performance engineering

| ID | Severity | Status | Evidence | Remediation / disposition |
|---|---:|---|---|---|
| M04-D-001 | P1 | RESOLVED | `performance-current-graph.json` reports `overall_status=pass`; current 12/36 mobile/desktop timing, interaction proxy, FPS, heap, CLS, and deterministic gzip gates pass. Home gzip is 95,131 B, route gzip 72,418 B, initial data gzip 14,587 B, and graph summary gzip 766 B. | Preserve lazy route/data staging and the no-graph-on-home constraint. |
| M04-D-002 | P1 | RESOLVED | The 1k harness uses actual Sigma with capped progressive 150 V/600 E rendering and `full_initial_render=false`. Final uncontended navigation-first-interactive samples are 3,586.2973 / 3,458.5906 / 3,397.6029 ms; median 3,458.5906 ms and p95 3,586.2973 ms both remain below 5 s. Interaction p95 is 74.1 ms. | Preserve the navigation-to-interactive definition; keep post-ready interaction/FPS QA outside that interval and mandatory. |
| M04-D-003 | P1 | RESOLVED | The final 10k/50k harness performs bounded model work, preserves governance fields, refuses 50k/300k mobile WebGL, plans chunks, yields work, keeps fallback visible, and reports no freeze/blank page. Evidence binds exact implementation input hash `sha256:698443b07526a9903b7c619cfed74aaea2326bac7ca955d1a9629d3b122d423c`; canonical evidence validation passes. | Retain the exact input-hash and executed-work assertions. |

### E — Rights

| ID | Severity | Status | Evidence | Remediation / disposition |
|---|---:|---|---|---|
| M04-E-001 | P1 | RESOLVED | `RIGHTS.md` and the governance policy reserve project code and original content rights; there is no project `LICENSE`; `THIRD_PARTY_NOTICES.md`, exact metadata rule snapshots, attributions, and license decisions remain separate. Candidate release declares zero media and zero media bytes. | Do not let project rights statements override third-party metadata obligations. |
| M04-E-002 | P1 | RESOLVED | `.github/ISSUE_TEMPLATE/rights-or-attribution.yml` requests no public sensitive proof or upload. The takedown procedure records 7-day acknowledgement, 14-day initial review, immediate high-risk isolation, and a 72-hour temporary-removal target. | Keep withdrawal and private-evidence handling operational before any publication. |

### F — Release and Pages

| ID | Severity | Status | Evidence | Remediation / disposition |
|---|---:|---|---|---|
| M04-F-001 | P1 | RESOLVED | The local candidate is physically closed and hash-bound with 19 files, exact typed/reference closure, source rules, notices, attribution, withdrawal contract, zero media, zero algorithmic edges, and preserved M03B hashes. Candidate validation passes with content hash `sha256:9467b5449e13fd3e89272a62bc614fe776b22d14745bdbf72c4540d5e84e0cc4`. | Keep it labeled `status=reviewed`, `public_release=false` until M04-A-001 is resolved. |
| M04-F-002 | P0 | BLOCKED_DERIVED | The deploy workflow now invokes the formal validator with `--require-public`; the reviewed candidate is rejected before upload. No M04 commit/push/Pages run/live QA exists. | Resolve M04-A-001, rebuild a human-approved formal bundle, rerun A–F and all CI gates, then—and only then—commit, push, deploy, and perform live HTTP/assets/console/request/404 QA. |
| M04-F-003 | P2 | RESOLVED | `release-loader.ts` verifies SHA-256 bytes and typed DTOs, rejects media/private fields, and permits reviewed candidates only for local candidate QA. HashRouter/base-path, no external runtime API/media requests, leakage scanning, and Arms/M05 regression gates are encoded in tests/workflow. | Preserve the formal workflow's fail-closed candidate rejection. |

## Remaining P3 register

| ID | Owner | Impact | Mitigation | Latest review phase | Blocks MUSEUM-05? |
|---|---|---|---|---|---|
| M04-P3-001 | MUSEUM release QA owner | No physical approximately 4 GB Android device was exposed; controlled Chromium throttling is lab evidence, not a real-device claim. | Run the same current/1k flows on a physical low-memory Android device when available and append results without rewriting this lab record. | MUSEUM-04 closeout | No by itself; the phase contract permits `real_device_status=not_available`. M04-A-001 still blocks MUSEUM-05. |

No other P3 remains at this review snapshot. The earlier valid-fixture count weakness is resolved: `validate_museum_04_fixtures.py` now compares every declared `expected_counts` value.

## Gate summary

- Open P0: `M04-A-001`; derived publication block: `M04-F-002`.
- Performance P1 findings `M04-D-002` and `M04-D-003` are resolved by the final exact-input scale rerun.
- Formal public release: **not created**.
- Git/Pages/live status: **no M04 commits, no push, no M04 Pages deployment, no live M04 QA**.
- MUSEUM-05: **not recommended while P0 remains open; not authorized; not entered**.
