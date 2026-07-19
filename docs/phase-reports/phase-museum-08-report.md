---
phase_id: MUSEUM-08
status: completed
validation_status: pass
report_date: 2026-07-19
runtime_model: not_exposed_by_runtime
runtime_reasoning: not_exposed_by_runtime
branch: main
baseline_commit: dfb91005b1302568079d16a3ceb60e6bae85041f
implementation_commit: b652d3cf3f7ad34b7861baad74f8b510a44d988b
final_runtime_commit: b36ac365b13ca24afa2d89f6dac6b680036a04af
final_verifier_commit: 7e0210765651dd3026ea93f15caa7964f2b10563
input_release_id: release:art-time-place-1.3.0
input_release_hash: sha256:aa969f48fd152301a66ee4f4841392b36f271bbca8537897484bc70c6ece718f
input_release_manifest_sha256: sha256:6022063a0e2620e60d7e1adac8e5b0ea8624e2b4790941a3941546f7e74b4c7c
output_release_id: release:art-v1-candidate-1.4.0
output_release_hash: sha256:93365e63792ae1c34667dcb2d002d733b58c68859b1a4e4bcae54d97f2532202
output_release_manifest_sha256: sha256:1eb5cce3264137a20dd18ea7595981585eae2abe125065ea010d542726277114
output_release_tree_sha256: sha256:5029d271ae40b39ff3cbaa0fb0a9a05cded3b3d8b9aeb8bef8672f1c9240ebc1
od_008_status: closed
od_009_status: closed
open_decisions_count: 1
remaining_open_decisions: [OD-011]
ci_impact_classifier_ready: true
release_integrity_ledger_ready: true
docs_only_heavy_ci_count: 0
historical_release_rebuild_count: 0
historical_release_hash_only_count: 4
final_full_gate_count: 1
runtime_deployment_count: 1
closeout_deployment_count: 0
search_route_ready: true
search_index_gzip_bytes: 45663
analytics_used: false
query_history_stored: false
user_geolocation_used: false
route_inventory_count: 87
automated_a11y_status: pass
mobile_matrix_status: pass
low_bandwidth_status: pass
withdrawal_rehearsal_status: pass
rollback_rehearsal_status: pass
performance_status: pass
pages_deployment_status: success
pages_url: https://archmays.github.io/Museum-Codex/
pages_deployment_id: 5508931387
scale_architecture_ready: true
synthetic_scale_validated: true
synthetic_artist_count: 500
synthetic_artwork_count: 5000
real_content_expansion_started: false
museum_09_entered: false
---

# MUSEUM-08｜V2 候选强化、CI 架构、移动/无障碍、低带宽与规模扩展就绪

## 1. 阶段结论

MUSEUM-08 已达到 `completed/pass`。V1 candidate、四级 CI、changed-path impact classifier、release integrity ledger、搜索与隐私决定、全路由移动/无障碍/低带宽门禁、synthetic withdrawal/rollback、规模就绪、一次 GitHub clean final-full validation、一次 Pages runtime deployment 和完整线上 byte closure 均已完成。

当前公开内容仍精确冻结为 12 artists、44 artworks、31 approved media / 13 no-image works、36 C relationships、18 tours、198 paths、23 places / 36 episodes；没有新增真实内容，没有进入武器馆或 MUSEUM-09。运行环境没有暴露模型与 Reasoning，均记录为 `not_exposed_by_runtime`。

## 2. 用户级治理门禁、入场与证据复用

进入仓库写入前，真实 Windows `%USERPROFILE%` 已解析并验证，未使用 Linux、容器或临时 home 替代。用户级 `AGENTS.md` 修改前为 4,589 bytes / 48 lines，SHA-256 `b39392ada206e539f2f086480ccae20acdd66b4e49de9dc71833230b13a17229`；备份为 `AGENTS.md.20260719-094536.bak`。语义去重合并后为 6,618 bytes / 61 lines，SHA-256 `2d9c79e30c66f63afb63ef86237fdd6659147d6054ca8e403b52fce17b10a635`，核心 CI 治理章节唯一且不含 Museum 仓库、路径、commit、release 或 phase 身份。

入场基线为 `dfb91005b1302568079d16a3ceb60e6bae85041f`，M07 online runtime 为 `e571709f02a3028bb8db76951076d377472c7428`。输入 release manifest/content/tree、M03C bundle、lockfiles、requirements、workflow、route inventory、CI inventory 和现有 test/performance evidence 均先验 hash 闭合。

受保护输入未变化，因此：

- 没有重新下载 31 originals 或生成 242 derivatives；
- 没有重新采集 Getty TGN / Natural Earth；
- 没有重跑 M04 1k/10k/50k、M06 path synthetic benchmark 或历史 screenshots；
- 没有重建 M04–M07；四个历史 release 仅校验 manifest/content/tree hash；
- candidate 复用封存输入与浏览器/npm/Python 缓存，只有受影响闭包重建。

Museum 仓库正式规范见 `docs/00_project/ci-execution-governance.md`；同一原则已安装为今后 Codex 项目的用户级默认。

## 3. 四级 CI、classifier 与 workflow

新增 `scripts/classify_ci_impact.py`，不依赖第三方 path-filter action。它处理 first push、空 before SHA、多 commit、delete/rename、manual targeted/full、mixed docs/runtime 和 closeout docs，输出：

`docs_only`、`runtime_changed`、`public_changed`、`full_required`、`shared_core_changed`、`dependencies_changed`、`workflow_changed`、`affected_phases`、`releases_to_rebuild`、`releases_hash_only`、`browser_suites`、`deploy_required`、`reason_codes`。

27 个 fixed synthetic fixtures 验证：

- docs-only：仅文档解析、front matter、secret/absolute-path、evidence link/hash 和 changed-path assertion；heavy jobs=0、Pages artifact=0、deploy=0；
- phase-scoped：只运行当前 phase validators/builder、touched shared smoke、对应 route/browser suite；runtime/public 未变时不 build/deploy；
- shared-core：common schemas/canonical dispatch、release loader、source/rights/security、shared state、lock/build tooling、workflow/scanner 变化只扩展到 impact matrix 闭包；
- final-full：candidate 首发、shared/dependency/workflow/security/rights 变化或显式 manual full；不会成为每个 push 的默认路径。

Workflow 文件：

1. `.github/workflows/docs-check.yml`
2. `.github/workflows/validate-and-build.yml`
3. `.github/workflows/full-gate.yml`
4. `.github/workflows/deploy-pages.yml`

Validation concurrency 为 `museum-validate-${{ github.ref }}` / `cancel-in-progress: true`；Pages 为独立 `pages` / `cancel-in-progress: false`。部署要求 validation success、`deploy_required=true`、runtime/public artifact 变化、同一 commit build marker 和 artifact SHA closure。纯文档 closeout 不创建 Pages artifact，也不部署相同 runtime。

## 4. Release integrity ledger

`governance/release-integrity-ledger.json` 与 `scripts/validate_release_integrity_ledger.py` 对五个 releases 保存 release ID、manifest SHA、content/tree hash、file/byte count、predecessor、builder/validator/input closure、schema/source/rights hashes、route consumers 和 immutable status。

Ledger SHA 为 `sha256:05e650db4d7b7e4939a86e8ae5fc1a3ef80beeabd81b872119ff807e0e76d61a`，覆盖 1,413 files / 203,140,831 bytes。历史 release rebuild count 为 0，hash-only count 为 4。只有 builder、validator、input closure、consumed schema、source/rights rule 或 release 文件变化时才允许重建对应 closure；不会随 release 数量线性执行全部 builder。

## 5. 执行次数、Actions、失败闭包与耗时

从用户级门禁备份时间 09:45:36 到阶段报告定稿 16:08:44，可确认执行窗口为 6h23m08s；closeout push 后的只读同步核验另由最终回复记录。

可审计的本地 targeted invocation 为 22 次，包含 Python/Vitest、四轮逐步收敛的 M08 browser、contended/isolated search benchmark、CI runner/classifier、受影响 shell/path/online browser、三次 CLS 修复后重复门禁、lint、strict typecheck 与 production build。本地 full gate 为 0。

M08 共产生 7 个 validation runs：

| Run | 结论 | 影响闭包 |
|---|---|---|
| `29672785687` | failure | 修复 Windows CRLF / Linux LF ledger path-hash |
| `29673299174` | failure | 修复旧 workflow scanner 与 schema assertions |
| `29674899804` | failure | 修复 M05B 遗留的 candidate 数量 copy |
| `29675941832` | cancelled | 被更新的 validation 按 concurrency 正确取消 |
| `29675953101` | failure | 修复 M06 隔离 CLS `0.1185024`，阈值未改变 |
| `29677859518` | final-full job pass；父 run failure | clean full、Pages 成功；仅部署后 verifier 缺依赖 |
| `29678982443` | success | 42 秒 affected closure；无 build、browser、deploy |

没有使用 GitHub 原生 failed-job rerun，因为每次失败都需要代码修复；code-fix affected-closure runs 为 5，superseded validation cancellation 为 1。没有删测试、skip/xfail、降低覆盖或放宽阈值。

Run `29677859518` 的 final-full job 用时 34m47s，并通过：

- clean install；
- Python 474/474，1,307.141 s；
- Vitest 13 files / 98 tests；
- Node CI lab 10 + 4 tests；
- lint、strict typecheck、release/source/rights/security/privacy/leakage 与全部 validators；
- production build 1,453 files / 205,076,046 bytes；
- Playwright 39/39，约 1.9m；
- sealed performance evidence 6/6。

同一 run 的 Pages action 与 deployment `5508931387` 成功。随后 post-deploy verifier 因最小 runner 没有 `referencing` package 立即失败，使父 run 结论为 `failure`；这不被隐藏。`7e0210765651dd3026ea93f15caa7964f2b10563` 将 verifier 改为纯 Python 标准库，保留全部 schema/reference/hash/byte closure，并在不进行第二次 full 或 deploy 的前提下完成线上验证；后续 Actions `29678982443` 证明影响闭包通过。

Workflow before/after：

- M07 旧 workflow 每次 push：33m56s；
- M08 唯一 intentional final-full：34m47s；
- verifier-only scoped Actions：42s；
- docs-only `[skip ci]` closeout：0 Actions、0 deploy。

因此 full gate count=1、runtime deployment count=1、closeout deployment count=0。

## 6. OD-008 搜索与 OD-009 隐私

OD-008 已由 D-0031 关闭。`#/art/search` 使用 Unicode NFKC、case/diacritic/whitespace normalization、exact、approved alias、prefix、optional `Intl.Segmenter` token、substring、transliteration 和 source-language labels。Segmenter 缺失时功能完整。排序是可解释 tuple：preferred exact、alias exact、prefix、token、substring、visitor-task entity type、stable ID；不使用 AI embedding、远程搜索、查询日志、流行度、重要性或艺术价值。

Candidate 搜索索引含 367 records、8 个带 hash/bytes 的 shards，覆盖公开 artists、artworks、contexts、tours、places、relationships、paths 与 help/source/rights endpoints。首个 query 才加载必要分片；initial shell 和 search route 不加载媒体，external requests=0。

最终预算：

- search route total：87,894 bytes gzip / 220,000；
- search index：45,663 bytes gzip / 150,000；
- current 367-record p95：23.2662 ms / 80；
- fixed 1,000-record p95：52.9409 ms / 120。

OD-009 已由 D-0032 关闭。站点无 analytics、account、server-side profile、telemetry SDK、cookies、fingerprinting、geolocation、remote logging，也不保存 search query、访问、选择、compare、path、map filter、tour、print/share history。只保留 locale 与 low-bandwidth 等明确的本地 UI 偏好。当前 open decisions count=1，仅 OD-011。

## 7. Route、移动、无障碍与低带宽

正式 inventory 为 16 route templates / 87 concrete routes，覆盖 home、Art landing、constellation、artist index、12 galleries、44 artwork details、compare、18 tours、paths、map、search、About、Rights、Accessibility 和 unknown route。每项记录 lazy chunk、data dependency、media、low-bandwidth/WebGL、print、keyboard/no-script、rights/source entry 与 withdrawal fallback。

Art landing 与主导航可发现星海、艺术家、作品比较、深度导览、AB 路径、时空地图和搜索；公开 UI 不含 Phase/MVP 术语。Locale、low-bandwidth、release/missing/withdrawn state、route focus、loading reservation、error wording、print/source/right drawer 行为已统一，不保存访问历史。

七个 viewport（360×800、390×844、412×915、768×1024、1024×768、1366×768、1440×900）通过 no-overflow、44px target、折叠 filter、stacked compare、bottom-sheet、安全键盘布局、orientation、touch zoom/pan、长标题、dense rights、print、skip/focus 和 200% reflow。

自动无障碍覆盖 landmarks/headings、name/role/value、focus order/visible focus、skip/live、dialog/panel、table/list、graph/map text alternative、form/image/no-image、forced colors、reduced motion、no-script、print 与 reflow。Serious=0、critical=0。真实 AT 与物理设备为 `not_available`，没有伪称人工设备认证。

Low-bandwidth 默认不初始化 Sigma/MapLibre、不预取大 route、不创建 artwork image；tours/compare metadata-first，map 使用 list/timeline，paths 使用 text，search/print 不加载媒体，source/evidence 按需。Slow/Fast 4G、abort/retry、static reload、failed image、missing chunk、stale release、withdrawn record 均保留完整核心任务；没有新增 service worker。

## 8. Withdrawal、rollback 与恢复

完全 synthetic rehearsal 分别撤回一项 media、一条 relationship、一个 place episode 和一件 artwork metadata。派生 candidate 排除撤回记录，gallery/no-image、constellation/path、map/list、notices、natural withdrawn URL 和 reference closure 均通过，旧 release bytes/hashes 保持不可变。

Candidate → predecessor rollback 验证 loader、routes、media/path/map、manifest/content/tree hashes、无 private data 与自然 fallback。RTO 为 15 minutes，已发布 immutable records 的 RPO 为 0 mutation。证据包括 withdrawal rehearsal record、rollback rehearsal record、recovery checklist 与 Pages rollback procedure。

## 9. 数百艺术家扩展就绪

本阶段只交付 synthetic architecture gates：

- 500 synthetic artists；
- 5,000 synthetic artworks；
- 20,000 searchable records；
- 10,000 typed relationships；
- 50,000 path/index records；
- seed `20260719`，中英、别名、转写、长标题、同名与 withdrawal，0 media、0 real person/work substitute、public leakage=0。

重复构建 byte-identical；20k query p95 38.2346 ms，first result 2.0518 ms，peak memory 46,736,112 bytes。总 search shards=128、所有 synthetic shards=192；一个 stable-ID 变化只重建 1 shard，193 个无关 shards 只验 hash。

共享运行时/schema/test tools 的 current-count hard-code scanner 通过；12/44 等数量只保留为 candidate manifest invariant 与精确 regression fixture。Stable-ID loader 支持 entity type/language/hash prefix 分片与单条失败隔离。

图谱只渲染聚焦的 120-node / 1,000-edge neighborhood；完整任务始终可由 50-item artist pagination 与 100-item relationship table 完成，并保持键盘与 200% reflow。Artist/artwork/compare/tour/path/map 按 stable ID 或 route chunk 懒加载，不把未来全集注入 initial shell。

ADR-0011 使用 SHA-256 内容身份、manifest reference、逐引用 rights/withdrawal boundary。Synthetic two-release prototype 证明相同 bytes 可复用一次；M08 没有迁移真实媒体、删除历史 release 或破坏旧 URL。状态明确为：

- `scale_architecture_ready: true`
- `synthetic_scale_validated: true`
- `real_content_expansion_started: false`
- `museum_09_entered: false`

完整 readiness 见 `docs/05_roadmap/museum-09-scale-expansion-readiness.md` 与 `docs/qa/museum-08/scale-readiness.json`。

## 10. V1 candidate release

输出 immutable overlay `release:art-v1-candidate-1.4.0`，predecessor 为 `release:art-time-place-1.3.0`。Candidate 物理目录为 317 files / 42,018,091 bytes；manifest 引用闭包为 316 files / 41,848,680 bytes。

- manifest SHA：`sha256:1eb5cce3264137a20dd18ea7595981585eae2abe125065ea010d542726277114`
- content hash：`sha256:93365e63792ae1c34667dcb2d002d733b58c68859b1a4e4bcae54d97f2532202`
- physical tree hash：`sha256:5029d271ae40b39ff3cbaa0fb0a9a05cded3b3d8b9aeb8bef8672f1c9240ebc1`

Overlay 新增 search config/index、route inventory、privacy snapshot、CI impact contract、ledger snapshot、accessibility/mobile/low-bandwidth summary、withdrawal/rollback records、V1 freeze/checklist 与 notices。Claim → Evidence → Source、source/rights/security、typed IDs、reference closure、notices/attribution 与 old-release immutability 均通过。

## 11. Performance、Pages 与 online closure

| Gate | Final | Budget |
|---|---:|---:|
| Home gzip | 101,981 B（M07 +1.921%） | ≤ +2% |
| Search route | 87,894 B | 220,000 B |
| Search index | 45,663 B | 150,000 B |
| Largest non-map route | 87,894 B | 307,200 B |
| Map route | 533,958 B | 563,200 B |
| Low-bandwidth initial p95 | 151,339 B | 250,000 B |
| Desktop FTI p95 | 167.9666 ms | 1,800 ms |
| Mobile FTI p95 | 439.0007 ms | 2,500 ms |
| Interaction p95 | 17.7 ms | 150 ms |
| CLS p95 | 0 | 0.1 |
| External runtime requests | 0 | 0 |
| Unexpected media preload | 0 | 0 |

Pages URL 为 `https://archmays.github.io/Museum-Codex/`，在线 build identity 为 runtime commit `b36ac365b13ca24afa2d89f6dac6b680036a04af` / gate `final-full`。Manifest/content hashes精确匹配，316/316 files 与 41,848,680/41,848,680 bytes 一次闭合。

三次有界 public cold probes 为 582.2071、364.4022、402.0312 ms；median 402.0312 ms、p95 582.2071 ms。它们是 CI-equivalent synthetic probes，不是 RUM，也没有收集真实用户数据。

## 12. Screenshots

保留 5 张候选截图，共 2,865,485 bytes：

- Art foyer 390×844；
- stacked compare 768×1024；
- low-bandwidth map list 1440×900；
- search empty 390×844；
- search results 390×844。

精确路径、尺寸、bytes 与 SHA-256 见 `docs/qa/museum-08/screenshot-index.md`。截图为候选 QA evidence；没有重生成 M04–M07 历史截图。

## 13. Reviewer A–G 与 P3

A–G 全部 pass：

- A：classifier、hash-only、四级 CI、concurrency、一次 full/一次 deploy；
- B：candidate overlay、ledger、immutability、withdrawal/rollback；
- C：deterministic search、解释排名、Segmenter fallback、零查询/行为收集；
- D：全路由 mobile/touch/no-image/graph/map fallback 与低带宽；
- E：自动 a11y、keyboard/focus/live/forced colors/reduced motion/no-script/print/reflow；
- F：bundle、FTI/CLS/interaction、lazy/cache/cold probes、synthetic scale 与 storage contract；
- G：only OD-011、no arms/no M09、rights/source、Pages、main 与 closeout no-deploy。

Open P0/P1/P2=0。P3=5：

1. Getty TGN 对 Allegheny City 无坐标、Mexico City 坐标 malformed；保持 unknown/list-only；
2. 44 artworks 没有明确 creation-place source；保持 `not_asserted`；
3. 真实 AT 与物理设备 unavailable；
4. 公网 cold latency 受 CDN/TLS/geography 影响且隐私契约禁止 RUM；
5. Content-addressed media reuse 是 synthetic prototype，不是历史 release 迁移。

每项 owner、缓解和 M09 前复核点见 `docs/qa/museum-08/adversarial-review.md`。

## 14. Storage、Git 与 closeout

累计删除 7,305 个可重建临时文件 / 1,066,438,763 bytes，包括多轮 `dist`、targeted/full repair outputs、synthetic temp、Playwright temp 与 local `output`。保留 5 张正式 screenshots / 2,865,485 bytes，以及 release/evidence/source vault 中应长期保留的已跟踪或受保护内容。没有删除 immutable historical release、source snapshot 或正式 evidence。

Runtime 实现线：

1. `b652d3cf3f7ad34b7861baad74f8b510a44d988b` — candidate/CI architecture；
2. `76d89e9ac8f336bf0e7bad7ada3e65ad4b226817` — cross-platform ledger closure；
3. `03424b945043323e13974ac7946cc19dbe7eff3d` — full-gate regression contracts；
4. `9107326c397f6fd78d338d8edf76f8795672ff3c` — browser impact classification；
5. `b36ac365b13ca24afa2d89f6dac6b680036a04af` — deployed runtime；
6. `7e0210765651dd3026ea93f15caa7964f2b10563` — self-contained online verifier。

本报告与 online evidence 作为纯文档 closeout，不在文件内自引用最终 commit。提交前必须由 classifier 证明 `docs_only=true`、`full_required=false`、`deploy_required=false`，commit message 使用 `[skip ci]`；最终 commit、三方 main hash、worktree clean、Actions run count 不变与 deployment ID 不变，由 Git history 和 Codex 最终回复记录。

## 15. 阶段边界

纯文档 closeout 不再触发重型 CI 或 Pages；历史 release 默认只验 hash；每阶段完整 full gate 原则上只运行一次；今后所有 Codex 项目采用同一跨项目 CI 治理规范。

站点没有 analytics、query history 或 user geolocation。已经为至少数百位 artists 与数千件 artworks 建立 synthetic scale readiness，但没有采集、审核或发布新内容。仅 OD-011 remain open；`real_content_expansion_started=false`，`museum_09_entered=false`。MUSEUM-08 在此停止。
