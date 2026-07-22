---
phase_id: MUSEUM-09B-UX-01
status: completed
validation_status: pass
baseline_commit: 917021458393b28dd27215f94f98a68be6565d5a
implementation_commit: e573a29cd5c78b22bc3009e586099fbff82f90b5
runtime_commit: 51ca3ea9ffbd300e879336ca4322ec3a63bef72e
input_release_id: release:art-expansion-batch-01-1.5.0
input_release_hash: sha256:364dffe96d35b16ba2ffdc6395cb28793411bd8be3bd3e89fad8cdc85036b6c9
input_release_manifest_sha256: sha256:7b03506242135a885ddf2c5b00bf284155e6d6b673c63440c001d56a008f60f9
input_release_tree_sha256: sha256:9dd52292a39a72fd5cec81bd4833fb55dbfe182443a86da431dfc64fe0ed948f
output_release_id: release:art-expansion-batch-01-1.5.1
output_release_hash: sha256:1f9853b514ccc2312ce00a493d47a16acc72c95f6f5aff580b954ef530dff21b
output_release_manifest_sha256: sha256:5030b164d198260c588b1321881d8aa8c6467888d8f055cc0ba87ef67c9472f5
output_release_tree_sha256: sha256:88d09842e10d4d5b011e3b6cab8b979086983eb48e661779378b2b4a21b57fdc
artist_count: 62
artwork_count: 532
relationship_count: 60
place_time_episode_count: 110
tour_count: 18
self_hosted_work_count: 71
external_link_only_work_count: 25
metadata_no_local_image_work_count: 436
new_derivative_count: 318
new_original_public_count: 0
legacy_circle_layout_removed: true
relationship_explorer_ready: true
default_global_graph_node_count: 0
starter_artist_limit: 9
focus_initial_node_limit: 13
focus_expanded_node_limit: 20
per_lane_neighbor_limit: 4
theme_visual_artist_limit: 16
path_visual_node_limit: 13
label_overlap_status: pass
node_overlap_status: pass
list_table_equivalence_status: pass
child_facing_intro_count: 62
child_facing_intro_provenance_count: 62
primary_copy_banned_jargon_count: 0
duplicate_intro_count: 0
metadata_only_prompt_status: pass
external_link_prompt_status: pass
technical_boundary_separated: true
mobile_matrix_status: pass
automated_a11y_status: pass
low_bandwidth_status: pass
performance_status: pass
real_at_status: not_available
physical_device_status: not_available
historical_release_hash_only_count: 6
historical_release_rebuild_count: 0
local_targeted_wave_count: 9
local_full_gate_count: 0
github_final_full_gate_count: 1
runtime_deployment_count: 1
closeout_deployment_count: 0
pages_deployment_status: success
pages_deployment_id: 5559246553
pages_url: https://archmays.github.io/Museum-Codex/
online_release_file_count: 629
online_release_matched_bytes: 109643591
formal_screenshot_count: 12
museum_09c_entered: false
arms_museum_entered: false
open_decisions_count: 1
remaining_open_decisions: [OD-011]
rights_status: PASS_BY_USER_AUTHORIZATION
---

# MUSEUM-09B-UX-01 阶段报告

## 结论

MUSEUM-09B-UX-01 为 `completed/pass`。本阶段没有增删艺术家、作品、关系、地点时间片段或导览；正式计数保持 62 / 532 / 60 / 110 / 18。问题被定位为公开投影和信息架构错误：正确的数据被默认投射为全体艺术家圆环，访客看见了密集标签、无起点的边和可能被误读为价值或历史影响的空间关系。该圆环已由任务导向的关系探索取代，62 位艺术家的儿童友好双语叙事也已重写并逐句绑定既有 Claim → Evidence → Source。

公开 successor 为 `release:art-expansion-batch-01-1.5.1`。它通过唯一成功的 GitHub `final-full` 运行部署到 Pages；前序 1.5.0 保持字节不变。完成后未进入 MUSEUM-09C 或武器馆，仅 OD-011 保持 open。

## Git、release 与不可变边界

- Baseline：`917021458393b28dd27215f94f98a68be6565d5a`。
- 主实现：`e573a29cd5c78b22bc3009e586099fbff82f90b5`，提交信息为 `Phase MUSEUM-09B-UX-01 repair relationship exploration and artist narratives`。
- 后续完整性/回归修复：`b102e8ece5c97048101cca8c9b029c0cf5b21531`、`c1a80b9aa58618278b1437d4c0c7583cffe50b85`、`b91160f5c7db8b5a815167310542d1145bf258be`、`2096e5dcd476102c6386b75cada0ee86fe3452b3`、`51ca3ea9ffbd300e879336ca4322ec3a63bef72e`。
- Deployed runtime：`51ca3ea9ffbd300e879336ca4322ec3a63bef72e`。
- Final closeout：本报告与在线证据所在的 docs-only `[skip ci]` 提交；精确 SHA 在最终交付回复中回读。
- Predecessor 1.5.0：content `sha256:364dffe96d35b16ba2ffdc6395cb28793411bd8be3bd3e89fad8cdc85036b6c9`，manifest `sha256:7b03506242135a885ddf2c5b00bf284155e6d6b673c63440c001d56a008f60f9`，tree `sha256:9dd52292a39a72fd5cec81bd4833fb55dbfe182443a86da431dfc64fe0ed948f`，65 files / 11,897,641 bytes；阶段前后相同。
- Successor 1.5.1：content `sha256:1f9853b514ccc2312ce00a493d47a16acc72c95f6f5aff580b954ef530dff21b`，manifest `sha256:5030b164d198260c588b1321881d8aa8c6467888d8f055cc0ba87ef67c9472f5`，tree `sha256:88d09842e10d4d5b011e3b6cab8b979086983eb48e661779378b2b4a21b57fdc`，67 files / 12,346,187 bytes；净增长 448,546 bytes。

Integrity ledger 覆盖 7 个 release、1,545 files、227,384,659 bytes；6 个历史 release 仅 hash-only，historical rebuild=0。successor-only builder 可重复生成 byte-identical 结果。318 个既有 derivative 按 hash 复用，新增下载=0、re-encode=0、公开 original=0。

## 根因与新信息架构

旧 `layout.json` 把“全部展示”误当成首要任务，所有艺术家沿环分布；限流只能减少节点，不能回答“从谁开始”“为什么相连”“这不代表什么”。Sigma/WebGL 路径又使普通、低带宽、forced-colors 与无 WebGL 体验结构不一致。因此只调间距、颜色或标签偏移不足以修复。

新 IA 使用同一数据、不同投影：

1. 初始图为 0 节点，以搜索、完整艺术家列表和不超过 9 个 coverage-balanced starter 开始。
2. 聚焦模式以一个艺术家为中心，按 shared subject / shared material / shared technique 三条语义 lane 显示，每 lane 最多 4 个邻居，初始总节点最多 13，主动扩展最多 20。
3. 每条关系都有键盘可操作的 “Why connected?”，解释所指、所不指以及 Claim → Evidence → Source 入口。
4. 主题模式以主题作标题，视觉集合最多 16 人，同时保留完整文字列表。
5. Artist list 完整发现 62 人；relationship table 完整审计 60 条正式关系。Paths 继续承担 A–B 路径任务，并使用当前路径加最多 6 个直接语境节点的确定性布局，总节点最多 13，不再依赖全局环。
6. 图形使用 DOM + SVG，不依赖 WebGL；low-bandwidth、forced-colors、reduced-motion、键盘和屏幕阅读路径保留相同任务。

自动 bounding-box 检查与 12 张正式截图均报告 label overlap=0、node overlap=0。视觉距离、中心、节点大小不表达价值、亲近、师承或影响；只有已发布的 60 条正式 C-level 关系可以形成边，computational similarity 不创建关系。

## 62 位艺术家的儿童友好叙事

62/62 位艺术家均有中英文 `public_intro`、`look_for`、`evidence_boundary` 与逐句 provenance。中文为 2–3 句、55–120 字，英文为 2–4 句、45–90 words；banned jargon=0、duplicate full intro=0、distinct template signatures=62。公共开场先介绍人物、地点/时代、材料/实践及可观察问题；治理、权利、来源与证据限制保留在次级可展开层。

Tanner 修复示例：

> 旧：亨利·奥萨瓦·坦纳（1859—1937）的身份、活动地点与历史时期来自经审核的声明。本次星海以油画、版画制作、水彩、画布相关元数据支持跨时空观察。所列地点、年代与媒材仅描述本展可核验的观察范围，并明确不把比较解释为影响、师承或价值排序。

> 新：亨利·奥萨瓦·坦纳（1859—1937）的作品记录连接着费城和巴黎，其中包括油画和版画制作。这些条目在本站没有本地图像；试着比较标题、年代、材料与收藏机构，看看哪些线索重复出现，哪些发生变化。

三种媒体状态的提示保持诚实：71 件 self-hosted 可在用户主动后加载本站图像；25 件 external-link-only 明示本站不托管并提供对象页链接；436 件 metadata/no-local-image 不要求儿童观察不存在的图像，而是比较标题、日期、材料与收藏机构。证据边界、权利、撤回与来源没有删除，只从儿童主叙事中移到较低的信息层。

`RIGHTS_STATUS: PASS_BY_USER_AUTHORIZATION`

## Mobile、accessibility、低带宽与性能

七个 viewport（360×800、390×844、412×915、768×1024、1024×768、1366×768、1440×900）均通过；最小交互目标 44 CSS px、横向溢出 0、主任务裁切 0、200% zoom reflow pass。键盘回退/前进、深链恢复、artist recenter、edge explanation、visible focus、live region、forced-colors、reduced-motion、low-bandwidth、no-script/text equivalent 和 unavailable WebGL parity 均通过。自动 a11y 覆盖 18 个 route/state，serious=0、critical=0。真实 AT 与物理设备在当前环境不可用，记录为 `not_available`，未声称人工认证。

受控本地浏览器性能不是 RUM：desktop first-interactive p95 568.828 ms，mobile p95 501.775 ms，CLS p95 0，focus interaction p95 44.5 ms，low-bandwidth initial transfer p95 226,171 bytes，external request=0、unexpected media preload=0、geolocation call=0。Bundle 阈值未降低：constellation route gzip 31,822 / 180,000 bytes，map 549,956 / 550,000 bytes。Search 当前 979 records p95 0.687 ms，synthetic 5,000 p95 1.924 ms。

线上有界 cold probe 为 GitHub runner/本地 verifier → GitHub Pages，不是 RUM：3 runs，median 387.124 ms，p95 570.062 ms。

## Tests、GitHub Actions 与失败闭环

本地只运行 9 个 targeted waves，`local_full_gate_count=0`。主要闭包包括 successor/schema/governance/reproducibility、12 Python unit tests、47 feature Vitest、52 touched-set Vitest、完整 frontend 15 files / 105 tests、TypeScript、ESLint、production build、M06 path browser 4/4、远端失败精确复现 3/3 与修复后 3/3、M09B 主体验 9/9、local online 6/6、map regression 1/1、budget/privacy/safety/leakage 和截图检查。

GitHub final-full 共 6 次尝试，其中前 5 次逐项暴露并关闭真实或历史契约漂移：

| Run | Failure | Closure |
|---|---|---|
| `29927767509` | integrity ledger drift | `b102e8e` 对齐 canonical ledger 写入与算法标签。 |
| `29927927167` | 旧 Python assertions | `c1a80b9` 更新受新 successor 合同影响的期望，不弱化验证。 |
| `29930465086` | 旧 1.5.0 validator 与 historical hash-only 策略冲突 | `b91160f` 让全门禁对历史 release 只验证 sealed hash。 |
| `29931044432` | 旧 frontend heading/duplicate-copy assertions | `2096e5d` 只更新过时期望；完整本地 frontend 105/105 通过。 |
| `29933537391` | 44/47 browser；两个旧标题断言与 Paths 仍读取已删除全局 layout | `51ca3ea` 更新旧标题断言，并把 Paths 改为任务聚焦确定性布局；精确 3/3 与 M06 4/4 本地闭环。 |
| `29936952664` | none | 唯一成功验收：497 Python、105 frontend、47 browser、build/scans/budgets、artifact binding、online byte verification 与 deployment 全部成功。 |

自动 phase-scoped runs `29933433574` 与 `29936903016` 均在 artifact upload/deploy 前取消；没有产生额外部署。成功 run `29936952664` 的 final-full job `88980950921` 用时 26m01s；deploy job `88987558894` 用时 38s。因此验收计数为 `github_final_full_gate_count=1`、`runtime_deployment_count=1`。

## Pages、在线字节与功能闭包

Pages：<https://archmays.github.io/Museum-Codex/>。Deployment `5559246553` / status `15805716825` 为 success，runtime commit 精确为 `51ca3ea9ffbd300e879336ca4322ec3a63bef72e`。

独立在线 verifier 一次收敛：629/629 files、109,643,591/109,643,591 bytes，hash failures=0；分类为 318 build-materialized、245 predecessor-reference、66 release-manifest。Release ID、content/manifest hash、62/532/110/18、71/25/436 与 318/0 media counts 均在线一致。

专用线上 Playwright 为 6/6 passed，覆盖 desktop relationship explorer、list/table/evidence/rights/URL state、1366 宽屏、About/Rights/Accessibility、390px low-bandwidth、forced-colors/reduced-motion/no-WebGL、no-script HTTP 200；console/HTTP/failed-request 均为 0。正式 12 张截图共 6,625,945 bytes，另保留 9 张专用线上截图 3,444,193 bytes。

补充的本地主套件对公开 origin 做高速连续路由时为 6/8；trace 显示两项仅由路由离开时主动取消延迟 fetch 的 `net::ERR_ABORTED` 构成，HTTP error=0。它不作为线上验收套件；逐字节闭包、direct HTTP 200 和 network-idle 专用线上 6/6 排除了缺文件、4xx/5xx 与产品功能失败。未修改产品代码，也未放宽正式门禁。

## 对抗审查、P3 与 storage

Reviewer A–G（关系语义、可理解性、儿童叙事、事实/溯源、移动/无障碍/低带宽、性能/CI/storage、公开/阶段边界）全部 pass；P0/P1/P2=0。

唯一 P3 是真实辅助技术与物理设备认证 `not_available`。Owner：Museum accessibility reviewer。Mitigation：自动 DOM/a11y、键盘、7 viewport、forced-colors、reduced-motion、no-script/text、no-WebGL、low-bandwidth 和 200% reflow。最晚复核点：用户授权下一个公开体验阶段之前，或 2026-08-22，以先到者为准。

收尾按精确路径删除可重建输出：`dist/`、`output/` 与 8 个 `tmp/museum-09b-*` 目录，共 2,290 files / 340,007,375 bytes；另删除 2 个冗余原始瞬时诊断结果 38,396 bytes，保留 compact diagnostic。清理目标剩余 0。发布包、provenance/config、schemas、validators、tests、12+9 screenshots、CI/deployment/online evidence、历史 release 均保留；清理前本阶段 QA 为 60 files / 14,969,433 bytes。删除内容可由正式输入和 builder 重建。

## 阶段边界

本阶段没有增删正式实体，没有下载或重编码媒体，没有 analytics、query history 或 user geolocation，没有启动 MUSEUM-09C，也没有进入 arms 数据、schema、adapter、媒体或公开路由工作。仅 OD-011 保持 open；下一阶段必须由用户另行授权。
