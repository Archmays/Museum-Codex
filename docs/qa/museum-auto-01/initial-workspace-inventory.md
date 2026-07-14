# MUSEUM-AUTO-01 initial workspace inventory

- Captured at: `2026-07-15` (Asia/Shanghai)
- Model selection: `not_exposed_by_runtime`
- Reasoning selection: `not_exposed_by_runtime`
- Repository: `D:\ChatGPT-Codex-Projects\Museum-Codex`
- Remote: `https://github.com/Archmays/Museum-Codex.git`

## Git state

- Current branch: `main`
- Current HEAD at first observation: `15617a1d4bf4117f2d418424d7cda0ef6c8e0eae`
- Upstream at first observation: `origin/main`
- User-supplied and live-verified remote baseline: `2be73011cb1dca64cb8d3a2d5830f495671d755b`
- Ahead/behind: `+1/-0`
- Worktree at first observation: clean
- Local branches: `main` only
- Live remote branches (`git ls-remote --heads origin`): `main` only
- Non-main unique commits: none
- Main-only commit: `15617a1d4bf4117f2d418424d7cda0ef6c8e0eae Refine museum release data and validation pipeline`
- Merge base of local and remote main: `2be73011cb1dca64cb8d3a2d5830f495671d755b`
- Fast-forward relation: local `main` is a linear descendant of `origin/main`

## Reconstructed pre-checkpoint dirty state

The prompt described approximately 36 modified and 98 untracked files. The live worktree was already clean before this run made any change. Reflog and the exact parent-to-HEAD diff prove that the pre-existing local commit `15617a1d` absorbed precisely that WIP:

- modified paths: `36`
- added paths corresponding to formerly untracked files: `98`
- total paths: `134`
- insertions/deletions: `14,738 / 259`
- commit parent: `2be73011cb1dca64cb8d3a2d5830f495671d755b`
- commit body: empty

This is a reconstruction from immutable Git evidence, not a claim that the original dirty instant was directly observed.

## Required command evidence

- `git status --porcelain=v2 --branch`: clean `main`, ahead 1
- `git branch --all --verbose --no-abbrev`: only local/remote `main`
- `git remote -v`: fetch/push both point to the declared repository
- `git diff --stat`, `git diff --name-status`, `git ls-files --others --exclude-standard`: empty for the live clean worktree
- `git diff --check`: empty for the live clean worktree
- `git diff --check 2be7301..15617a1`: one pre-existing trailing-whitespace finding at `RIGHTS.md:3`; repaired in the explicit Stage A checkpoint without rewriting history

## Symlink, large-file, and secret checks

- Git symlink entries (`mode 120000`): `0`
- WIP files over 1 MiB: `0`
- tracked/untracked files over 5 MiB: `0`
- repository safety scan: `PASS files=594`, no credential patterns and no file over 5 MiB
- common secret signatures checked: GitHub/OpenAI/AWS/private-key patterns
- secret or credential material selected for Git: none
- `node_modules`: ignored, present at audit time, never selected for Git or recovery

## MUSEUM-04 WIP classification

The path-level classification is in `m04-wip-file-classification.json`.

- A — valuable source, governance, contracts, tests, and QA source: `100`
- B — raw/private/sensitive files inside the 134-path checkpoint diff: `0`
- C — reproducible release/QA outputs inside the checkpoint diff: `31`
- D — stale or contract-conflicting evidence documents: `3`

Ignored protected data was separately identified outside the 134-path diff: `data/raw`, `data/intermediate`, and `data/review`. These paths were not modified, deleted, or added to Git.

## Recovery backup and generated-output cleanup

- Recovery root: `D:\ChatGPT-Codex-Projects\Museum-Codex-Recovery\MUSEUM-AUTO-01-20260714T192611Z`
- WIP/regenerable manifest: `recovery-manifest.json`
- Manifest SHA-256: `sha256:f44338ad78102db0d0217127b58d9a84f904315df48b570890636758c8983ab9`
- WIP files copied: `134`
- Total WIP/regenerable entries copied: `209`
- Total WIP/regenerable bytes copied: `10,521,579`
- Protected-data manifest: `protected-data-manifest.json`
- Protected-data manifest SHA-256: `sha256:f046b4e75124aecd20f54fdae96076035fb38cbe7c2ab27337b3b51f9050a751`
- Protected files copied: `1,332`
- Protected bytes copied: `30,373,930`
- Source/destination hash equality: `true` for every entry

Only after hash equality was proven, these ignored/reproducible paths were removed with verified absolute targets inside the repository: `dist`, `test-results`, `output/playwright`, `tmp`, `.pytest_cache`. No `git clean`, reset, stash, branch, worktree, or history rewrite was used.

## Sealed MUSEUM-03B baseline

- Package validator: pass
- Artists/artworks/contexts/relationships: `12/44/31/36`
- Relationships A/B/C: `0/0/36`
- Media assessments self-hosted/external/metadata-only: `31/4/9`
- Actual media bytes: `0`
- Package content hash: `sha256:1f0f00a0d7f6162fcb0d716e6b86fbcfe42a4e04a0422d7c1c0df63b70c97b86`
- Graph content hash: `sha256:58fe40930ab6f0e84019bbb0c3f378a2e73d7f3fbd4f810a66aa78f0481d1dd3`
- Diff from remote baseline in sealed package and M03B phase report: none

## Initial consequential findings

1. No branch consolidation merge is necessary because no non-main branch exists locally or remotely.
2. The pre-existing local commit is a recoverable but unvalidated zero-media M04 checkpoint; it must not be pushed alone.
3. Zero-media assumptions span the projector, schemas, loader DTOs, fixtures, tests, public release, UI copy, workflow, and reports; revision requires a coherent contract change rather than a text-only patch.
4. The sealed M03B package is intact and remains the immutable source of truth.
5. M03C must live-rediscover Met media URLs and revalidate all object-level rights; AIC provides four existing official IIIF candidates.
