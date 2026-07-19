# MUSEUM-09B capability gap

The review was completed before the formal candidate writer was introduced. The smallest complete path is an immutable M09B overlay; no public runtime, shared schema registry, dependency, workflow, or historical release migration is needed.

| Capability | Existing evidence | Classification | M09B action |
|---|---|---|---|
| Fixed 50/488 assignment and ordered reserve | `museum-09b-first-batch.json`, `museum-09-batch-registry.json` | Reuse | Consume exact stable IDs and preserve Batch 02–10 |
| Identity, deceased, duplicate, source and work universe | M09A normalized/deceased/duplicate/target shards | Reuse | Hash-check; do not rerun discovery, dedupe or 500/5,000 selection |
| Claim/Evidence/Source vocabulary | Existing M03–M08 schemas and validators | Reuse without shared-core change | Emit phase-local canonical records with explicit closure |
| Official source and rights rules | `research/source-registry/source-license-rules.json` | Reuse | Bind exact source-rule IDs and keep metadata/media rights separate |
| Batch 01 current-record drift | No M09B receipt or local-impact ledger | Incremental implementation | Bounded metadata-only refresh, old/new hashes, affected closure and fallback semantics |
| Fifty formal artist dossiers | Not present | Incremental implementation | One canonical JSON writer plus 50 read-only Markdown projections |
| 488 formal artwork records | M09A candidates only | Incremental implementation | Preserve M09A IDs; add formal catalog, evidence, uncertainty and correction fields |
| Gallery/Collection depth | Tier assignment exists; research depth absent | Incremental implementation | Close 12 Gallery and 38 Collection contracts in five 10-artist waves |
| Object media feasibility | M09A says not assessed/no download | Incremental implementation | Produce 488 decisions and future allow/block partitions; download zero bytes |
| Candidate leakage and phase boundary | Existing public scanner and release ledger | Reuse plus M09B markers | Scan stable private markers; prove current release and public tree unchanged |
| Large-file and deterministic-shard infrastructure | Existing canonical JSON/hash patterns | Reuse | Two 244-record artwork shards and byte-identical double build |
| Canonical schemas | Current fields can express the overlay | Data only; no shared-core change | Use phase semantic validator and invalid fixtures; do not create a competing schema |
| Media acquisition, source bytes, derivatives | Not authorized in this phase | Defer to M09B-MEDIA | Emit exact candidate allowlist only |
| Public route/release integration | Not authorized in this phase | Defer to M09B-RELEASE | Create projections only; no route, build, artifact or deploy |
| Later artists and works | Batch 02–10 registered | Defer to M09C+ | Keep `registered_not_started` |
| Arms museum | Out of scope | Defer | No entry or content mutation |

The M03A/M03B/M03C and M04–M08 paths were inspected as precedent for preflight, reviewed packages, media separation, physical release closure, immutable releases and leakage scanning. Their artifacts remain inputs or historical evidence, not rewrite targets.
