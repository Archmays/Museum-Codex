---
phase_id: MUSEUM-09D-WAVE-01
document_type: factory_v1_capability_gap
status: closed_by_factory_v2
baseline_commit: b5f10b33d49bd8ce5e971a9f69299150f6598235
---

# Factory V1 capability gap and V2 closure

## Audited V1 boundary

The sealed V1 implementation remains byte-unchanged in
`museum_pipeline/art/expansion_batch_factory.py` and
`scripts/run_museum_expansion_batch.py`. It continues to be the compatibility
writer for MUSEUM-09C and the historical 1.6.0 reproducibility check.

| V1 gap | Baseline evidence | V2 closure |
|---|---|---|
| Single-batch CLI | `--batch-id` accepts one transaction only | The approved release plan declares an ordered batch list and the V2 CLI executes a contiguous plan slice. |
| Phase ID hard-coded | Claims, evidence, artists, contexts, artworks and search manifest contain a fixed phase | Phase ID is loaded from the release plan and applied before an artifact is committed. |
| Reviewer hard-coded | Reviewer ID/kind are fixed in generated claims and evidence | Reviewer ID/kind are execution-context fields. |
| Build/review date hard-coded | Module constants control every transaction | Build timestamp and review date come from the approved plan. |
| Source authorization scope hard-coded | A source-specific branch chooses one of two fixed phase scopes | Authorization basis, scope and stable rule version come from the plan; no source receives a phase-specific code branch. |
| Artifact paths derived from planned phase | Batch path cannot be moved into a wave namespace | Research, media and release paths are explicit per-batch plan fields. |
| Predecessor supplied ad hoc | CLI accepts any predecessor string | The plan validates a closed predecessor chain before the first write. |
| No wave journal | Only per-package transaction manifests exist | One atomic journal records stable input hash, attempts, checkpoints, failure cursor and deployment state. |
| No resume | Existing package roots are deleted and rebuilt | Committed checkpoints are hash-verified and skipped on resume; immutable byte drift fails closed. |
| No final-only deployment contract | Release completion creates runtime/deployment bindings for every batch | Intermediate releases receive explicit zero-deployment bindings; only the final release can receive the deployment marker. |
| Registry can advance ahead of online state | Release creation marks a batch published/current | Intermediate immutable releases may publish as not-current; the final batch remains predeployment until online closeout evidence is recorded. |
| No cross-batch dedupe | Validation covers one cumulative release | V2 checks all three new artist/work ID sets, introduction uniqueness, predecessor chain, relationship semantics and final totals. |
| Media state inherited from Batch 02 behavior | V1 writes a uniform metadata-only result | V2 writes one decision per object with the sealed availability, metadata license, review hint, user-authorization basis and explicit absence of a technical media locator. |
| Compatibility risk | Refactoring V1 would change the historical builder closure | V1 code is unchanged; V2 uses an isolated temporary registry and commits only context-normalized V2 artifacts. |

## Result

The V2 entrypoint is `scripts/run_museum_expansion_wave.py`. The generic V2
writer contains no fixed phase, batch, version, reviewer, date or authorization
scope. All permanent writes are plan-authorized and atomically committed.
