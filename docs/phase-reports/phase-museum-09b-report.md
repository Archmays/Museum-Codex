---
phase_id: MUSEUM-09B
status: completed
validation_status: pass
baseline_commit: a0e25915d5c2f15c565cb5d59c66c5e350e2ef50
batch_id: museum-09-batch-01
batch_input_closure_hash: sha256:8b7020f979895e3bf5f21c042c1e6a2b746628f5108f13050102b31370219770
input_universe_hash: sha256:3db15ca186152c7355263e6b3254d3ff7151f56b834f34e57fd6d7570c42bded
input_release_id: release:art-v1-candidate-1.4.0
input_release_hash: sha256:93365e63792ae1c34667dcb2d002d733b58c68859b1a4e4bcae54d97f2532202
public_release_changed: false
artist_count: 50
artwork_count: 488
gallery_artist_count: 12
collection_artist_count: 38
replacement_count: 0
living_artist_count: 0
unknown_death_count: 0
non_person_count: 0
duplicate_artist_count: 0
artwork_attribution_conflict_count: 0
duplicate_artwork_count: 0
artist_claim_closure_status: pass
artwork_claim_closure_status: pass
gallery_readiness_status: pass
collection_readiness_status: pass
place_time_readiness_status: pass
relationship_candidate_status: pass
media_feasibility_decision_count: 488
approved_self_hosted_candidate_count: 40
approved_external_iiif_candidate_count: 25
metadata_only_ready_count: 423
blocked_media_count: 0
new_media_download_count: 0
new_derivative_count: 0
candidate_public_leakage_count: 0
source_record_checked_count: 538
source_record_changed_count: 87
source_record_unchanged_count: 451
source_record_unavailable_count: 0
deterministic_rebuild_status: pass
candidate_package_id: museum-09b:batch-01-formal-candidate-v1
candidate_package_content_hash: sha256:299bbf0b5baf5522d8fb2a60682a8e5c2571fb5baeb205f4c6d28f549c728eb9
candidate_package_tree_hash: sha256:d662188a097e2549bc964372af445e0f532f1c115552f6f1fbb788ee0627bf87
batch_registry_status: formal_candidate_ready
historical_release_rebuild_count: 0
historical_release_hash_only_count: 4
local_full_gate_count: 0
github_final_full_gate_count: 0
phase_scoped_ci_run_count: 1
pages_artifact_count: 0
runtime_deployment_count: 0
closeout_deployment_count: 0
formal_public_expansion_started: false
museum_09b_media_entered: false
museum_09b_release_entered: false
museum_09c_entered: false
arms_museum_entered: false
open_decisions_count: 1
remaining_open_decisions: [OD-011]
---

# MUSEUM-09B 阶段报告

## 结论

MUSEUM-09B `completed/pass`。Batch 01 的精确 50 位艺术家与 488 件作品已从 M09A 固定总体转换为逐实体可追溯、可确定性复核、可供后续媒体或发布阶段消费的内部正式候选包。它仍不是公开 release；当前 V1 candidate、Pages 与公开 12/44 数据保持不变。

可观测阶段执行窗口从入场证据创建（2026-07-20 04:06:07 +08:00）至本报告冻结约 37 分钟，其中 implementation Actions 从 push 到完成为 36 秒。模型与 Reasoning 的具体运行时标识未暴露，记为 `not_exposed_by_runtime`。

## Git 与受保护输入

- Baseline：`a0e25915d5c2f15c565cb5d59c66c5e350e2ef50`
- M09A implementation：`291b490d3dcbc197f25caca94ff797bf84ee165c`
- M09B implementation：`95f43bee1b4ab04997fd6a041807079f55058b98`
- Final closeout：本报告所在的 docs-only `[skip ci]` 提交（精确 hash 在最终交付回复中）
- Batch input closure：`sha256:8b7020f979895e3bf5f21c042c1e6a2b746628f5108f13050102b31370219770`
- M09A universe：`sha256:3db15ca186152c7355263e6b3254d3ff7151f56b834f34e57fd6d7570c42bded`
- M09A physical tree：`sha256:25be5898c3476b02db7573973475fd0c27c8f16c769a4ab4057691be74558c82`
- 输入 release：`release:art-v1-candidate-1.4.0`
- Release content：`sha256:93365e63792ae1c34667dcb2d002d733b58c68859b1a4e4bcae54d97f2532202`
- Release manifest：`sha256:1eb5cce3264137a20dd18ea7595981585eae2abe125065ea010d542726277114`
- Release physical tree：`sha256:5029d271ae40b39ff3cbaa0fb0a9a05cded3b3d8b9aeb8bef8672f1c9240ebc1`

入场时 local `HEAD`、`origin/main` 与 GitHub remote `main` 均精确等于 baseline，worktree clean；有效全局 `AGENTS.md` SHA-256 为 `sha256:2d9c79e30c66f63afb63ef86237fdd6659147d6054ca8e403b52fce17b10a635`，CI 治理章节唯一。M09A package 和公开数据相对 baseline 的 changed-path count 均为 0。

## 5 waves 与总体闭合

| Wave | Artists | Artworks | Result |
|---|---:|---:|---|
| 1 | 10 | 111 | pass |
| 2 | 10 | 130 | pass |
| 3 | 10 | 100 | pass |
| 4 | 10 | 86 | pass |
| 5 | 10 | 61 | pass |

精确总体为 50 artists / 488 artworks；Gallery 12 / Collection 38。Coverage delta 为 Africa 4、East Asia 6、Europe 17、Latin America and Caribbean 5、North America 7、Oceania 2、South Asia 3、Southeast Asia 3、West and Central Asia 3。Replacement 为 0：所有固定实体通过 hard gates，无需启用 reserve。

50 位均为已识别、确认已故的个人；living、unknown death、non-person 和 duplicate artist 均为 0。名称、alias、transliteration 与中文标签状态显式建模；在缺少可靠中文标签时保守使用 `no_zh_label`，未编造中文名。作品归属冲突与 duplicate work 均为 0。

## 深度研究与正式证据

生成 50 份 dossier、50 份英中双语候选 overview，满足对应 Gallery/Collection 长度与深度门禁。结构化研究闭合为 738 claims、738 evidence、10 official sources、162 contexts、74 place-time episodes 和 24 relationship candidates。

所有可发布候选事实通过 Claim → Evidence → Source 解析。Tier 3/Wikidata 仅作 authority crosswalk，不独立支持争议事实；来源没有明确事件地点时保持 null/`not_asserted`，没有把馆藏机构或研究地理误写为创作/活动地点。

24 个 relationship candidates 仅用于 12 位 Gallery artist 的策展比较，全部将 `historical_relationship_strength` 保持为未断言，将 `evidence_confidence`、`computational_similarity` 和 `curatorial_relevance` 分开；没有从视觉或计算相似性推导历史影响。

## Source drift

按 Batch 01 stable IDs 检查 538 条记录：87 changed、451 unchanged、0 unavailable。累计 14 个网络请求、2,159,930 bytes 元数据响应、0 media bytes；复用 sealed source cache 1,430,997,874 bytes。

初次完整刷新成功闭合 538 条。后续为补齐 per-record `fetched_at`/`source_version` 的重试中，AIC 三批在九次有界尝试后仍发生传输失败；canonical writer 没有把这次网络故障伪装成 87 条来源不可用，而是复用了同阶段已生成、hash-valid、538/538 完整的 sealed receipt，补齐记录级字段，并把失败尝试保留在 `transport_history`。Receipt content hash 为 `sha256:4318a4f2c32a2ad788091bf0ac4e6c7b0c51f1c5b2824526c185a8721d252c1f`，文件 SHA-256 为 `sha256:1b2045167bcb4c0b66a716b5a5ed9b0cf7bf20dd0e34d5d39288ba0bf8635f1d`。

## 媒体可行性

488/488 对象级决策：

| Status | Count |
|---|---:|
| `approved_self_hosted_candidate` | 40 |
| `approved_external_iiif_candidate` | 25 |
| `metadata_only_ready` | 423 |
| blocked statuses | 0 |

未来 M09B-MEDIA allowlist 为 65 件，metadata-only/blocked list 为 423 件，两者互斥且合计 488。每个 approved candidate 都绑定对象级来源规则、媒体许可依据、attribution、notice 与 withdrawal route；availability 没有被当作 permission。`RIGHTS_STATUS: PASS_BY_USER_AUTHORIZATION`，同时继续保持 metadata/media 权利证据分离。本阶段 media download=0、derivative=0、AI image=0。

当前只给出安全上界而非下载量预测：在既有 100 MiB 单对象门禁下，未来下载范围 0–6,815,744,000 bytes；若每个 approved object 最多生成四个宽度的 JPEG/WebP，未来 derivative 范围 0–520。两者在本阶段均为 0。

## Candidate package 与 registry

内部包：`data/reviewed/art/museum-09b/batch-01-formal-candidate-v1/`

- Package ID：`museum-09b:batch-01-formal-candidate-v1`
- Content hash：`sha256:299bbf0b5baf5522d8fb2a60682a8e5c2571fb5baeb205f4c6d28f549c728eb9`
- Physical tree：`sha256:d662188a097e2549bc964372af445e0f532f1c115552f6f1fbb788ee0627bf87`
- Physical package：74 files / 4,022,309 bytes
- Manifest-declared closure：73 files / 4,009,134 bytes（另加 manifest 本身构成 physical 74）

`governance/museum-09-batch-registry.json` 只把 Batch 01 提升为 `formal_candidate_ready` 并绑定上述 ID/hash/tree；Batch 02–10 保持 `registered_not_started`。M09A reviewed package、当前 release 和 public runtime 均未改写。

## 验证、CI、性能与 failure closure

- 最终 targeted：13 个命令；17 个 unittest cases；5 个 wave validators；30 类真实 mutation invalid fixtures。
- Affected-closure unittest rerun：3；formal failed targeted attempts：7，均已关闭。
- Deterministic double build：pass；50 dossiers 与 488 works byte-deterministic。
- 单记录影响：1 artist dossier + 1 artwork shard 改变，unrelated dossier 0。
- 5 次构建：p50 35,600.081 ms，p95/max 35,956.165 ms；peak RSS 86,892,544 bytes；benchmark network/media bytes=0。
- Local full gate=0；GitHub final-full=0；browser/E2E=0；npm install=0；production build=0；screenshots=0。
- Historical releases：4 个 hash-only，当前 V1 candidate 同样 hash-only；historical rebuild=0。
- Actions：[run 29702931823](https://github.com/Archmays/Museum-Codex/actions/runs/29702931823) 为 `phase-scoped/success`；failed-job rerun=0。`classify` 与 `phase-scoped` 成功，`docs-only`、`final-full`、`deploy` 跳过；Pages artifact 与生产构建步骤跳过。
- Pages artifact=0；runtime deployment=0；closeout deployment=0。

七次开发期失败分别为 source adapter 首次传输异常、首包 overview/tree digest、两次 invalid coverage mutation 设计、最终 AIC refresh retry、tracemalloc 超时和 Windows memory signature；均只重跑失败项或受影响依赖闭包，没有降低测试门槛。

## Storage

Raw cache 前后均为 217,387 files / 1,430,997,874 bytes，按受保护输入复用。M09B physical package 为 4,022,309 bytes，source receipt 为 395,137 bytes，合计 retained 4,417,446 bytes；最大 tracked candidate file 773,013 bytes，无大于 5 MiB 文件、无媒体文件、public bundle growth=0。

中断 benchmark 临时目录和一个误生成的 1,187-byte classifier scratch 已在 path verification 后清理；temporary directory remaining=0。中断目录删除前的文件数/bytes 未观测，因此未虚构。Protected input、历史 release、source snapshot、媒体和 evidence 删除数均为 0。

## 对抗审查 A–G

A Identity/deceased、B artist research、C artwork identity/attribution、D sources/provenance、E media feasibility/rights、F engineering/efficiency、G phase/public boundary 均为 pass；P0/P1/P2 全部为 0。

唯一 P3 为 `source-record-drift`。Owner：M09B-MEDIA 或 M09B-RELEASE canonical writer；mitigation：后续 acquisition/release 前按 stable ID/content hash 复核所有对象记录，保留 old/new snapshot 或最小 diff，只重跑受影响 artist/work closure，身份或对象级媒体权限无法闭合时 fail closed；review stage：进入 M09B-MEDIA acquisition 或 M09B-RELEASE 前。

## 阶段边界与建议

Candidate public leakage=0；没有 importance、popularity、market 或 AI aesthetic score；没有 analytics、query history 或 geolocation。M09B-MEDIA、M09B-RELEASE、M09C、武器馆均未进入；formal public expansion 仍未开始；仅 OD-011 remains open。

后续建议是在用户另行授权后，先进入 M09B-MEDIA 对 65 件 allowlist 复核并按对象下载/生成衍生物，或在不需要媒体 acquisition 时另行授权 M09B-RELEASE；本阶段不执行任何下一阶段。
