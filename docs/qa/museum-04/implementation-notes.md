# MUSEUM-04 implementation notes

## Task contract

- **Goal:** publish the metadata-only “艺术星海：观察与比较 / Constellation of Art: Observation and Comparison” release and its accessible graph, artist-list, and relationship-table experiences.
- **Context:** implementation starts from commit `2be73011cb1dca64cb8d3a2d5830f495671d755b` and the sealed MUSEUM-03B reviewed package.
- **Constraints:** exactly 12 artists, 31 contexts, and 36 reviewed C-level relationships; zero media and zero algorithmic relationships; no causal claims; no runtime external APIs; project code and original content remain all rights reserved.
- **Done when:** the public release is physically closed and validated, all three views complete the same core tasks, accessibility and performance gates pass, Actions deploys `main`, and live Pages QA is clean.
- **Must not touch:** MUSEUM-05, artwork media, A/B paths, time-space maps, digital galleries, the Arms Museum, MUSEUM-03B snapshot bytes, or Git history.
- **Evidence sources:** the user-approved MUSEUM-04 brief; `AGENTS.md`; MUSEUM-03B report/package; interaction, visual, rights, release, accessibility, roadmap, and risk policies; targeted validators and tests; local and live browser evidence.
- **Current stage:** implementation.

## Baseline evidence

- Local `HEAD`, local `main`, `origin/main`, and GitHub `main` matched `2be73011cb1dca64cb8d3a2d5830f495671d755b`; worktree was clean.
- MUSEUM-03B package content hash matched `sha256:1f0f00a0d7f6162fcb0d716e6b86fbcfe42a4e04a0422d7c1c0df63b70c97b86`.
- MUSEUM-03B graph content hash matched `sha256:58fe40930ab6f0e84019bbb0c3f378a2e73d7f3fbd4f810a66aa78f0481d1dd3`.
- Counts matched 12 artists, 44 artworks, 31 contexts, 36 relationships, 588 claims, 289 evidence records, 4 sources, and 0 media bytes; relationship levels were `0/0/36`.
- Modification-before baseline passed 47 schemas, governance/pipeline/M03A/M03B fixtures, the sealed package, 218 Python tests, 22 frontend tests, lint, typecheck, build, build closure, and repository safety scan.

## Consequential unknown register

| ID | Category | Evidence | Consequence if wrong | Resolve / defer | Resolution or owner | Confidence |
|---|---|---|---|---|---|---|
| U-01 | known unknown | Sigma 3.0.3 has no built-in dotted-edge preset, while all 36 public edges must be visibly C-level dotted lines. | A solid-only graph would fail the relationship-semantics contract. | Resolve now | Implement and test a local Sigma custom edge program; retain text and icon redundancy in all views. | high |
| U-02 | unknown unknown | The generic physical validator supports zero media but predates public M04 projection records. | A projection could bypass canonical dispatch or fail to close hashes and references. | Resolve now | Reuse the canonical dataset-release manifest and physical checks, then add a stricter M04 projection schema and semantic validator. | high |
| U-03 | known unknown | No approximately 4 GB Android device is exposed in this runtime. | Lab throttling could be misreported as physical-device evidence. | Defer honestly | Record `real_device_status=not_available`; report controlled lab results separately. | high |
| U-04 | known unknown | New bilingual artist summaries are AI-assisted prose derived from reviewed Claims. | Crediting Mays or claiming unperformed human copy review would falsify provenance. | Resolve now | Bind summaries to reviewed Claim/source IDs and record the actual AI-assisted operator review provenance; do not invent a human reviewer. | high |
| U-05 | known unknown | Shared CI timing is noisy and cannot establish real-user p75. | Brittle millisecond gates could fail randomly or overstate field performance. | Resolve now | Keep structural/gzip/cap gates hard in CI; store repeated controlled-lab median/p95 with environment metadata and tolerances. | high |
| U-06 | known unknown | Pages results do not exist until the final `main` deployment completes. | Local success could be mistaken for public release completion. | Resolve later in phase | Wait for Actions, then verify HTTP/assets/console/requests/404s and local/live byte hashes. | high |

## Implementation log

- **Discovery:** `skill/SKILL_INDEX.md` is absent, so no project-specific skill was invented or used.
- **Decision:** use stable `graphology@0.26.0` and `sigma@3.0.3`; Sigma 4 remains alpha and is out of scope.
- **Decision:** preserve the sealed MUSEUM-03B package byte-for-byte and generate a separate allowlisted MUSEUM-04 projection.
- **Decision:** low-bandwidth and forced-colors modes default to the artist list and do not initialize Sigma.
- **Decision:** do not idle-prefetch graph libraries; load them only when the visitor explicitly selects the graph view.
- **Decision:** define the initial data budget as `manifest + graph-summary + artists + layout + facets + search-index`; load relationships/contexts on first focus or table entry, artwork/evidence/source detail on relation selection, and rights/notices only when requested.
- **Decision:** measure gzip with deterministic Node zlib level 9. The preserved MUSEUM-03B home build is 89,515 bytes gzip, so the hard 15% ceiling is 102,942 bytes.
- **Decision:** ship production dependency notices inside the Pages artifact and mechanically compare them with every non-dev lockfile package; this does not create a project-level open-source license.
- **Validation:** the Rights Issue Form now has a pinned YAML parser and a fail-closed nine-field contract check; it requests no public email, upload, identity document, contract, address, or telephone field.
