---
phase_id: MUSEUM-09A
status: completed
validation_status: pass
baseline_commit: d16817943ed404bf47ed222ebd2800438dd00602
input_release_id: release:art-v1-candidate-1.4.0
input_release_hash: sha256:93365e63792ae1c34667dcb2d002d733b58c68859b1a4e4bcae54d97f2532202
public_release_changed: false
pages_deployment_count: 0
raw_discovered_artist_count: 49406
deduplicated_artist_count: 7017
deceased_verified_candidate_count: 7017
program_target_artist_count: 500
existing_target_artist_count: 12
new_target_artist_count: 488
reserve_artist_count: 120
candidate_artwork_count: 9000
program_target_artwork_count: 5000
existing_target_artwork_count: 44
new_target_artwork_count: 4956
source_count: 12
official_source_count: 12
wikidata_only_target_count: 0
living_artist_target_count: 0
unknown_death_target_count: 0
non_person_target_count: 0
coverage_guardrails_status: pass
deterministic_rebuild_status: pass
batch_registry_ready: true
batch_count: 10
museum_09b_first_batch_ready: true
new_media_download_count: 0
candidate_public_leakage_count: 0
historical_release_rebuild_count: 0
historical_release_hash_only_count: 4
local_full_gate_count: 0
github_final_full_gate_count: 0
phase_scoped_ci_run_count: 1
runtime_deployment_count: 0
closeout_deployment_count: 0
real_content_expansion_started: true
formal_public_expansion_started: false
museum_09b_entered: false
arms_museum_entered: false
open_decisions_count: 1
remaining_open_decisions: [OD-011]
---

# MUSEUM-09A 阶段报告

## 结论

MUSEUM-09A `completed/pass`。真实内容扩展已开始，但没有公开新内容：500 位目标艺术家和 5,000 件目标作品形成内部、tracked、可确定性复跑的审计总体；当前 V1 candidate release、Pages 和公开 12/44 保持不变。

可观测执行窗口从首个 raw source cache 创建至 implementation Actions 完成为至少 4 小时 1 分钟。确定性时间字段固定，不用文件时间参与内容 hash。

## Git 与输入

- Baseline：`d16817943ed404bf47ed222ebd2800438dd00602`
- Implementation：`291b490d3dcbc197f25caca94ff797bf84ee165c`
- Final closeout：本报告所在的 docs-only `[skip ci]` 提交（精确 hash 在最终交付回复中）
- 输入 release：`release:art-v1-candidate-1.4.0`
- Content：`sha256:93365e63792ae1c34667dcb2d002d733b58c68859b1a4e4bcae54d97f2532202`
- Manifest：`sha256:1eb5cce3264137a20dd18ea7595981585eae2abe125065ea010d542726277114`
- Physical tree：`sha256:5029d271ae40b39ff3cbaa0fb0a9a05cded3b3d8b9aeb8bef8672f1c9240ebc1`

## Universe 与状态

49,406 个 raw source artist identities 经个人、死亡年份、正式来源、身份合并、冲突和三件作品门禁，形成 7,017 个 deduplicated/deceased verified candidates。其中 500 target、120 ordered reserve、6,397 rejected；现有/新增 target 精确为 12/488。Living、死亡未知、non-person、Wikidata-only、anonymous、workshop 和 tradition target 均为 0。

作品闭合为 9,000 candidate / 5,000 target；现有/新增 target works 精确为 44/4,956。每位 target 至少三件作品，attribution conflict 和目标重复簇为 0。Gallery/Collection 分布为 125/375。

## Coverage

| Bucket | Target |
|---|---:|
| Europe | 170 |
| East Asia | 65 |
| Africa | 40 |
| Latin America and Caribbean | 55 |
| North America | 75 |
| South Asia | 30 |
| Southeast Asia | 25 |
| West and Central Asia | 25 |
| Oceania | 15 |

Europe 为 34%，所有区域 guardrails 均通过。时期覆盖 before-1400、1400–1599、1600–1799、1800–1899、1900–1949 和 1950-onward；媒介覆盖 painting、drawing、printmaking、sculpture、photography、ceramics、textile/fiber、architecture/design、decorative arts 和有来源的 mixed/installation/performance documentation。没有从姓名或外貌推断敏感身份。

## Sources 与贡献

12 个正式来源为 AIC、British Museum、Cleveland、Cooper Hewitt、Met、Minneapolis Institute of Art、MoMA、National Gallery Singapore、NGA、Smithsonian、Tate 和 V&A。

目标作品贡献依次为 AIC 824、Cleveland 824、MoMA 824、NGA 824、Met 823、Tate 661、National Gallery Singapore 80、Cooper Hewitt 45、V&A 44、Smithsonian 27、MIA 23、British Museum 1；最高单一来源占比 16.48%。433 位 target 有多个正式来源身份，67 位有一个正式来源身份。Wikidata/QLever 只用于发现或 crosswalk，不作为独立正式证据。

## Package、确定性与批次

候选包位于 `data/reviewed/art/museum-09a/global-expansion-universe-v1/`，38,098,067 bytes。大型集合使用逐 shard hash/bytes/count/order/physical-closure 校验；最大文件 3,761,185 bytes，低于仓库 5 MiB 门禁。双构建 byte-identical，artifact content hash 为 `sha256:3db15ca186152c7355263e6b3254d3ff7151f56b834f34e57fd6d7570c42bded`。

10 个不重叠批次闭合 488 位新艺术家和 4,835 件对应作品，另注册 121 件 legacy-artist supplement；与 44 件 legacy works 合计 5,000。M09B 推荐首批为精确 50 位新艺术家、488 件作品，状态 `recommended_not_started`。

## 验证、CI 与效率

- Targeted final pass：8 个命令，81 个 unittest cases，21 类实际变异 invalid fixtures。
- Formal development failures：6 次，全部按失败项/依赖闭包修复并复跑通过。
- Local full gate：0；GitHub final-full：0；browser/E2E：0。
- 真实选择：3,675.543 ms；已加载候选宇宙 traced baseline 603,203,611 bytes；选择增量峰值 402,125 bytes。
- Batch builder：25 次，p95 95.47 ms，max 97.376 ms；与 committed registry 一致。
- 单一既有艺术家更新：仅 1 个 candidate shard hash 改变。
- Cache reuse：1,430,997,874 bytes ignored official-source cache 按输入 hash 复用；规模基准网络下载 0，本阶段新增媒体下载 0。
- Public bundle growth：0；candidate leakage：0；媒体下载：0。
- Historical release：4 个历史 release hash-only；当前 V1 candidate 同步 hash-only 验证；rebuild 0。
- Actions：[run 29691255422](https://github.com/Archmays/Museum-Codex/actions/runs/29691255422) 为 `phase-scoped/success`；failed-job rerun 0。
- Pages artifact、runtime deployment、closeout deployment：均为 0。

## Storage

候选 package 从早期 46,552,782 bytes 经人物级死亡证据去重与确定性分片降到 38,098,067 bytes；没有超过 5 MiB 的 tracked 文件。Raw cache 1,430,997,874 bytes 保留在 ignored source vault，因为它是可复跑的正式输入闭包，不属于可删除 scratch。临时 staging 目录剩余 0；历史 release、source snapshot、媒体和 evidence 删除 0。

## 对抗审查 A–G

- A Identity/deceased：pass；P0/P1/P2=0。
- B Global representation：pass；P0/P1/P2=0。
- C Sources/provenance：pass；P0/P1/P2=0。
- D Artwork mapping/attribution：pass；P0/P1/P2=0。
- E Selection/batches：pass；P0/P1/P2=0。
- F Engineering/efficiency：pass；P0/P1/P2=0。
- G Public/phase boundary：pass；P0/P1/P2=0。

P3 仅 `source-record-drift`：官方 bulk/API 记录未来可能更正。Owner 为对应后续批次 canonical writer；进入每一批前按 stable ID/content hash 刷新变化记录，只重跑受影响适配器和依赖闭包，并保留 correction route。

## 阶段边界

M09B 未进入；武器馆未进入；OD-011 仍 open。没有公开发布新增艺术家或作品，没有下载新媒体，没有用 living、unknown-death、anonymous、workshop 或 tradition 凑数。下一阶段必须由用户另行授权。
