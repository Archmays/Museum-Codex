---
phase_id: MUSEUM-09B-RELEASE
status: completed
validation_status: pass
baseline_commit: 3317f4e0f146bc19a3ba34fe94a72703d24aba5e
batch_id: museum-09-batch-01
input_candidate_package_id: museum-09b:batch-01-formal-candidate-v1
input_candidate_content_hash: sha256:299bbf0b5baf5522d8fb2a60682a8e5c2571fb5baeb205f4c6d28f549c728eb9
input_media_package_id: museum-09b-media:batch-01-media-bundle-v1
input_media_content_hash: sha256:d98e3409fb9512054acf532c541e4c4219fcf767564c846f78cfb2439b6c3c50
input_release_id: release:art-v1-candidate-1.4.0
output_release_id: release:art-expansion-batch-01-1.5.0
output_release_hash: sha256:364dffe96d35b16ba2ffdc6395cb28793411bd8be3bd3e89fad8cdc85036b6c9
output_release_manifest_sha256: sha256:7b03506242135a885ddf2c5b00bf284155e6d6b673c63440c001d56a008f60f9
output_release_tree_sha256: sha256:9dd52292a39a72fd5cec81bd4833fb55dbfe182443a86da431dfc64fe0ed948f
artist_count: 62
legacy_artist_count: 12
new_artist_count: 50
artwork_count: 532
legacy_artwork_count: 44
new_artwork_count: 488
gallery_profile_count: 24
collection_profile_count: 38
self_hosted_work_count: 71
external_link_only_work_count: 25
metadata_no_local_image_work_count: 436
new_derivative_count: 318
new_original_public_count: 0
promoted_relationship_count: 24
excluded_relationship_candidate_count: 0
place_time_episode_count: 110
tour_count: 18
search_ready: true
path_status: pass
map_status: pass
mobile_matrix_status: pass
automated_a11y_status: pass
low_bandwidth_status: pass
performance_status: pass
real_at_status: not_available
physical_device_status: not_available
external_runtime_request_count: 0
analytics_used: false
query_history_stored: false
user_geolocation_used: false
candidate_public_leakage_count: 0
historical_release_rebuild_count: 0
historical_release_hash_only_count: 5
local_full_gate_count: 0
github_final_full_gate_count: 1
runtime_deployment_count: 1
closeout_deployment_count: 0
pages_deployment_status: success
pages_deployment_id: 5550987880
pages_artifact_bytes: 243665307
pages_url: https://archmays.github.io/Museum-Codex/
online_release_file_count: 627
online_release_matched_bytes: 109195638
source_drift_changed_count: 87
source_drift_unchanged_count: 451
source_drift_unavailable_count: 0
museum_09c_entered: false
arms_museum_entered: false
open_decisions_count: 1
remaining_open_decisions: [OD-011]
---

# MUSEUM-09B-RELEASE 阶段报告

## 结论与执行窗口

MUSEUM-09B-RELEASE 为 `completed/pass`。Batch 01 已发布为新的不可变 predecessor overlay，公开美术馆从 12 位艺术家 / 44 件作品扩展为 62 位 / 532 件；当前 Pages 指向 `release:art-expansion-batch-01-1.5.0`。完成后未进入 MUSEUM-09C、MUSEUM-09B-MEDIA-V2、MUSEUM-10 或武器馆。

从 baseline 提交时间 2026-07-21 23:13:18 +08:00 至本报告冻结约 15 小时 41 分钟。该窗口包含用户要求的关机暂停、GitHub Actions、Pages 收敛和在线验证，并非连续主动计算时间。模型与 Reasoning 的具体运行时标识未暴露，记录为 `not_exposed_by_runtime`。

## Git、输入与不可变 release

- Baseline：`3317f4e0f146bc19a3ba34fe94a72703d24aba5e`
- Runtime implementation：`861f6eaa260e173c50c6069fd92e5d8f06cbc869`，提交信息为 `Phase MUSEUM-09B-RELEASE publish expansion batch 01`
- Deployed runtime：`4097e5ffaaf7237777ee8b9d20dc682c317f5f44`
- Online verifier repair：`f8326bfda32af7cf0853df1a3f1ac5b7ce19c428`；只修复验证器，不改变或重部署 runtime
- Final closeout：本报告与在线证据所在的 docs-only `[skip ci]` 提交，精确 SHA 记录在最终交付回复中
- Candidate：`museum-09b:batch-01-formal-candidate-v1` / `sha256:299bbf0b5baf5522d8fb2a60682a8e5c2571fb5baeb205f4c6d28f549c728eb9`
- Media：`museum-09b-media:batch-01-media-bundle-v1` / `sha256:d98e3409fb9512054acf532c541e4c4219fcf767564c846f78cfb2439b6c3c50`
- Predecessor：`release:art-v1-candidate-1.4.0` / content `sha256:93365e63792ae1c34667dcb2d002d733b58c68859b1a4e4bcae54d97f2532202`
- Output：`release:art-expansion-batch-01-1.5.0` / content `sha256:364dffe96d35b16ba2ffdc6395cb28793411bd8be3bd3e89fad8cdc85036b6c9` / manifest `sha256:7b03506242135a885ddf2c5b00bf284155e6d6b673c63440c001d56a008f60f9` / tree `sha256:9dd52292a39a72fd5cec81bd4833fb55dbfe182443a86da431dfc64fe0ed948f`

新 release physical bundle 为 65 files / 11,897,641 bytes（manifest 自身加 64 个 manifest entries）。它通过 predecessor reference 继承 legacy 12/44，不复制或重建历史 release；ledger 现覆盖 6 个 releases、1,478 files、215,038,472 bytes，其中 5 个历史 release 仅做 hash-only 验证，historical rebuild=0。

## P3 live drift 与公开数据闭包

按 stable ID/content hash 完成 538 条 source records 复核：87 changed、451 unchanged、0 unavailable。变化均为可闭合的 metadata enhancement；没有下载新 original、生成新 derivative、替换实体或静默改写 sealed candidate/media package。唯一正式 P3 保持为 `source-record-drift`：owner 为下一次 acquisition/release canonical writer；mitigation 为按 stable ID/hash 复核变化记录并仅重跑受影响闭包；最晚在下一次公开 release 前复核。

Release validator 的精确结果：

| Closure | Legacy | Batch 01 | Public total |
|---|---:|---:|---:|
| Artists | 12 | 50 | 62 |
| Artworks | 44 | 488 | 532 |
| Gallery profiles | 12 | 12 | 24 |
| Collection profiles | 0 | 38 | 38 |
| Self-hosted-image works | 31 | 40 | 71 |
| External-link-only works | 0 | 25 | 25 |
| Metadata/no-local-image works | 13 | 423 | 436 |

Living、unknown-death、non-person、duplicate artist、attribution conflict、duplicate artwork 均为 0。Public slug registry 使用稳定 entity ID 映射、Unicode normalization、稳定 collision suffix 与 alias/redirect contract，validator pass；主要公开 URL 未暴露 phase、candidate、adapter 或内部 tier 名称。

## Artist、artwork 与媒体行为

Artist index 覆盖 62 位艺术家，使用稳定、非 popularity/market 的排序，可按 region、period、profile type、practice/media 和 image availability 过滤；分页为 24 items/page。12 位新增 Gallery 与 38 位 Collection 均有双语公开概述、作品、context、place-time、source/rights drawers 和诚实 profile 表达。532 个 artwork detail、mixed compare、print/share、unknown/withdrawn/no-image states 均闭合。

40 件新增 self-hosted works 复用 M09B-MEDIA 审核衍生物；318 个 derivative 由 build 按 content-addressed manifest materialize，61,418,168 bytes，input hash 未变时 `reencoded=0`。Public/Git 新增 original=0，受保护 originals 未进入 Git 或 public。25 件 AIC 作品保持 external-link-only：不嵌入、不代理、不 preload 远程图像或 IIIF，页面只提供 verified object-page link 与本站未托管说明。423 件新作品保持 metadata-only，并保有 search、compare、print、source 和 rights 等价任务。

## Search、关系、paths、map 与 tours

- Search index 覆盖 979 records（artists、artworks 及正式辅助页面/实体），支持 NFKC、alias/prefix/token/substring/transliteration/source-language；确定性排序，无 AI/remote search、query history 或媒体 preload。
- 24/24 个 M09B relationship candidates 通过端点、类型和 Claim → Evidence → Source 门禁并晋升；excluded=0。公开 C-level typed relationships 总数为 60，历史关系强度、证据置信度、计算相似与策展相关性保持分离；没有算法边或把相似性写成历史影响。
- Constellation 及完整文本关系表覆盖 62 位艺术家；默认聚焦邻域，low-bandwidth/forced-colors/reduced-motion 使用文本等价。
- AB paths 只消费正式边，bounded algorithm、无路径空状态和新规模 benchmark 均 pass；未用视觉相似补路。
- Map/timeline/place table 合并 36 legacy + 74 Batch 01 = 110 episodes；null/not-asserted 不被推断为坐标或旅行路线，WebGL/低带宽/forced-colors 有 list/timeline fallback，未调用用户定位或外部地理服务。
- Tours 保持 18；候选 tour hooks/sequencing proposals 未伪装成正式 tour。

## Mobile、a11y、低带宽与线上功能

七个 viewport（360×800、390×844、412×915、768×1024、1024×768、1366×768、1440×900）覆盖 Art landing、artist index、两类 artist profile、三种 artwork media state、compare、search、constellation/text、paths、map/list/timeline、dense rights/source 与 unknown route。Keyboard/focus/skip/live region、44px target、200% reflow、forced colors、reduced motion、no-script、print、graph/map text equivalence 和 no-image equivalence 均通过；automated serious/critical a11y=0。

Low-bandwidth 模式不初始化 Sigma/MapLibre，不预取全量实体，不在用户主动前创建 artwork image，external-link-only 不发出远程请求。真实 AT 与物理设备在当前环境不可用，明确记录为 `not_available`，未声称认证。

独立线上 Playwright smoke 为 11/11 passed，覆盖 18 route templates、7 viewports 和三种媒体状态；console error=0、failed same-origin request=0、HTTP error=0、external runtime request/image=0、geolocation call=0。没有 analytics、query history 或 user geolocation。

## 性能

| Budget | Observed | Limit | Status |
|---|---:|---:|---|
| Home closure gzip | 97,200 bytes；相对基线 -2.857% | ≤102,060 | pass |
| Search route gzip | 136,932 bytes | ≤220,000 | pass |
| Search index gzip | 72,525 bytes | ≤300,000 | pass |
| First-query shards gzip | 71,095 bytes | ≤100,000 | pass |
| Largest non-map route gzip | 136,932 bytes | ≤350,000 | pass |
| Map route gzip | 548,947 bytes | ≤550,000 | pass |
| Low-bandwidth initial p95 | 170,968 bytes | ≤250,000 | pass |
| Desktop core FTI p95 | 452.851 ms | ≤1,800 | pass |
| Controlled mobile FTI p95 | 459.126 ms | ≤2,500 | pass |
| Interaction p95 | 18.1 ms | ≤150 | pass |
| Current-corpus search p95 | 1.388 ms | ≤80 | pass |
| Synthetic 5,000-record p95 | 6.263 ms | ≤120 | pass |
| CLS | 0 | ≤0.1 | pass |

Public cold probe 是 GitHub runner → GitHub Pages 的三次有界 synthetic probe，不是 RUM：samples 582.828 / 375.715 / 363.372 ms，median 375.715 ms，p95 582.828 ms。

## Tests、CI、failure closure 与部署

本地遵循阶段要求，只运行 targeted closure，没有运行完整 local full suite，因此 `local_full_gate_count=0`。最终本地 affected browser files 为 38/38 passed；完整 E2E 开发检查为 5 isolated performance passed，functional 首轮 44/45，唯一 Windows screenshot handle `UNKNOWN open` 的失败项单测重跑 1/1 passed。Lint、strict typecheck、Vitest 15 files / 103 tests 均 pass。

GitHub 有 7 次 final-full classified attempts，前 6 次分别关闭 ledger、CRLF/LF historical evidence hash、Python compatibility、旧 frontend assertions、长 integration timeout 和旧 browser assertions。没有降低阈值、跳过测试、重建历史 release 或 force push。唯一作为最终验收计数的 clean final-full job 是 Actions run `29896080595` / job `88846478793`：493 Python tests、15 Vitest files / 103 tests、5 isolated performance + 45 functional Playwright、production build、release/source/rights/security/privacy/leakage、performance、Pages binding/upload 全部成功；final-full job 用时 28m54s。因此 `github_final_full_gate_count=1`。

同一 run 的 Pages deployment action 成功，deployed runtime 为 `4097e5f...`；deployment ID `5550987880`，artifact ID `8520573618`，artifact 243,665,307 bytes。父 workflow 最终显示 failure，是因为部署后的旧 verifier 假定所有 predecessor reference 都有 `resolved_path`，对 242 个只带 `path` 的合法历史媒体引用抛出 `KeyError: 'resolved_path'`。`f8326bf...` 将 verifier 改为显式接受 `resolved_path` 或 `path`、两者都缺失时仍 fail closed；随后实际线上 closure 通过。没有为相同 runtime 再部署；既有 deployment 的环境 status `15782348955` 被更新为 success，并明确说明 online byte closure + functional smoke passed。Runtime deployment=1，closeout deployment=0；不隐藏父 Actions run 的失败结论。

## Online byte closure 与截图

Pages：<https://archmays.github.io/Museum-Codex/>

线上 build identity 精确为 `4097e5ffaaf7237777ee8b9d20dc682c317f5f44` / gate `final-full`。逐文件验证 627/627、109,195,638/109,195,638 bytes，hash failures=0；closure 分类为 64 release-manifest、245 predecessor-reference、318 build-materialized。Release ID、content/manifest hashes 与 62/532 等全部 counts 在线一致。

正式 QA 截图保留 12 张、9,570,308 bytes：Art landing、artist index mobile、新 Gallery desktop、新 Collection mobile、三种 artwork media state、mixed compare、search、constellation text、map low-bandwidth list、rights/source dense view。未重生成 M04–M09B-MEDIA 历史截图。

## Withdrawal、rollback 与对抗审查

Synthetic rehearsal 覆盖撤回新增 self-hosted media、external-link reference、metadata-only artwork、Collection artist、promoted relationship 和 place-time episode，并验证 successor、共享字节引用、profile/detail/search/graph/path/map 闭包及 current→predecessor rollback；predecessor 和历史 release bytes/hash 不变。

Reviewer A（release/ledger/history）、B（artist/artwork projection）、C（media/rights/external-only）、D（search/graph/paths/map/tours）、E（mobile/a11y/low-bandwidth）、F（performance/CI/storage）、G（public/privacy/phase boundary）均为 pass；P0/P1/P2=0。唯一 P3 为上文 `source-record-drift`。

## Storage 与阶段边界

Baseline tree 为 3,101 tracked blobs / 416,703,659 bytes；deployed runtime tree 为 3,204 / 438,864,832，增长 103 blobs / 22,161,173 bytes。M09B media package 的 336 files / 62,877,348 bytes 被按 hash 复用，318 derivatives 未在 release/public Git tree 中重复存储，re-encode=0。

收口前只读确认并删除可重建临时目录：`dist/` 1,842 files / 278,576,343 bytes，`output/` 12 files / 6,710,668 bytes；合计 1,854 files / 285,287,011 bytes。删除后两目录均不存在。没有删除 protected originals vault、M03C media、M09A/M09B/MEDIA sealed packages、历史 releases、official snapshots、正式 evidence 或来源不明用户文件；临时构建产物不可直接恢复，但可由正式输入和构建命令重建。

Batch 02–10 未改动，MUSEUM-09C 与武器馆均未进入；仅 OD-011 保持 open。M09C 的输入完整性已具备，可在用户另行授权后进入，但本阶段到此停止。
