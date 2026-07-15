---
phase_id: MUSEUM-04
status: completed
validation_status: pass
report_date: 2026-07-15
runtime_model: not_exposed_by_runtime
runtime_reasoning: not_exposed_by_runtime
baseline_commit: 2be73011cb1dca64cb8d3a2d5830f495671d755b
implementation_commit: 9a7f38a3bdcfcfb222116f2ead4438e81073f0af
final_commit: recorded_by_museum_auto_01_closeout_commit
deployed_runtime_commit: 00a8539ea0d5e901fc2b6be993ea400ff36a0b19
public_release_created: true
public_release_id: release:art-constellation-1.0.0
public_release_hash: sha256:52835bb9256a9e50c2b73b9ef2e4fb99aa4a40434f20319133fdfb56b09fc462
public_release_manifest_sha256: sha256:0fa7046a6b47eb9c73abc2279157f745888eeb76e7445fb18810269b04ec5346
formal_release_validation: pass
fixture_matrix_status: pass_28_of_28
public_artist_count: 12
public_artwork_metadata_count: 44
public_context_count: 31
public_relationship_count: 36
relationship_level_a_count: 0
relationship_level_b_count: 0
relationship_level_c_count: 36
approved_media_artwork_count: 31
no_image_artwork_count: 13
public_derivative_count: 242
public_derivative_bytes: 35907176
physical_file_count: 264
physical_byte_count: 39436869
algorithmic_relationship_count: 0
human_review_dependency: false
human_reviewer_claimed: false
performance_current_graph_status: pass
performance_scale_status: pass
real_device_status: not_available
real_assistive_technology_status: not_available
pages_deployment_status: completed_via_museum_auto_01
pages_url: https://archmays.github.io/Museum-Codex/
museum_05_gate_status: completed_via_museum_auto_01
---

# MUSEUM-04 media-aware 艺术星海阶段报告

报告日期为 2026-07-15（Asia/Shanghai）。运行环境未暴露模型或 Reasoning 选择，均记录为 `not_exposed_by_runtime`。

## 1. 当前结论

MUSEUM-04 已生成并单独验证正式、media-aware、静态的 `release:art-constellation-1.0.0`。正式 release validator 以 `--require-public` 运行并返回 `ok=true`、零 failure；release 包含 12 位艺术家、44 件作品元数据、31 个 typed contexts、36 条关系和 242 个已批准 derivative 文件，全部关系仍为 C 级非因果策展比较。

MUSEUM-04 当前结论为 **`completed/pass`**。28-fixture matrix 以四个互斥 shard 完整执行：4×7 个 fixture、四个进程退出码均为 0、28 个唯一 fixture ID 全部通过；其中 27 个 expected-invalid 均被拒绝，1 个 expected-valid 被接受。持久证据为 `docs/qa/museum-04/fixture-matrix.json`，run ID 为 `fff290ead038447096fcc9b1cc337639`，且不依赖人工逐项审核。

Pages 未在本阶段单独推送或部署，这是原阶段边界。随后 MUSEUM-AUTO-01 按单一 `main` 线性流程完成统一 push；Actions run `29420441620` 与 Pages deployment `5458604781` 成功，真实站点与本地 public-served `dist` 已逐字节闭合，因此当前公开 Pages 是本 release 的正式上线证据。

## 2. 正式 release 身份与物理闭包

| 项目 | 实际值 |
|---|---|
| Release ID | `release:art-constellation-1.0.0` |
| Profile | `media_aware` / `publishable` / `public_release=true` |
| Content hash | `sha256:52835bb9256a9e50c2b73b9ef2e4fb99aa4a40434f20319133fdfb56b09fc462` |
| Manifest SHA-256 | `sha256:0fa7046a6b47eb9c73abc2279157f745888eeb76e7445fb18810269b04ec5346` |
| M03C bundle hash | `sha256:3aa84fa7df37c4823cd2cb1f92c7e1843e7dea70b7cfd683528b25698951d565` |
| Physical closure | 264 regular files / 39,436,869 bytes |
| Manifest closure | 263 listed children plus the manifest itself |
| Runtime derivatives | 242 JPEG/WebP files / 35,907,176 bytes |
| Media identity closure | 31 source-provenance parents + 242 derivative children = 273 media IDs |

Validator 从 sealed MUSEUM-03B 与 validated MUSEUM-03C 输入重建预期投影，而不是信任 public projection 的自洽值。它核对 typed IDs、实体计数、引用、文件路径、SHA-256、字节长度、JPEG/WebP magic bytes、parent chain、rights、license rule、attribution、notice、withdrawal 和运行时 delivery policy。同步篡改 public media、rights、attribution、notice 或 withdrawal 仍必须失败。

## 3. 公共数据与关系语义

- 12 artists / 44 artworks / 31 contexts / 36 relationships。
- Claim 252 条，Evidence 138 条，Source 4 条；公开事实保持 Claim → Evidence → Source 闭包。
- A/B/C=`0/0/36`；A、B 均为明确空状态。
- 关系类型为 shared subject 17、shared material 11、shared technique 8。
- 36 条关系全部 `algorithmic=false`、`causal=false`、`directed=false`。
- 每条关系都明确不证明相识、影响、师承、传播或价值排序。
- 初始图为 12 个等大节点且不显示全部边；focus 后只显示一跳 C 级点线关系。

媒体可用性不参与节点尺寸、关系强度、排序或艺术价值判断；13 件无图作品仍保留完整元数据、正式来源和可达的 no-image 状态。

## 4. M03C 媒体消费边界

44 件作品在公开 release 中分成：

- 31 件 `approved_self_hosted`，消费 M03C 批准的本地 derivative；
- 7 件 `metadata_only_after_automated_review`，保持无图；
- 4 件 `blocked_source_unavailable`，保持无图；
- 2 件 `blocked_rights_conflict`，保持无图；
- 0 件 approved external runtime delivery；
- 0 件 unknown、restricted 或 development-only media。

运行时只公开 242 个 adaptation children；31 个 source-provenance parent 仅用于权利与来源闭包，不作为 public `src`，source originals 也未复制进 release。Derivative roles 为 thumbnail 124、detail 60、zoom 58；生成变换仅包含已记录的 orientation/ICC normalization、metadata-safe strip、resize 与 compression，不放大、不裁切作品内容、不去水印、不生成替代图。

## 5. Graph / list / table 等价体验

艺术星海正式名称为“艺术星海：观察与比较 / Constellation of Art: Observation and Comparison”。图形、艺术家列表和关系表均支持检索、筛选、focus、关系说明、来源与 rights 查看，并共享 URL state。WebGL 图不是唯一访问路径；不可用、context loss、forced colors、reduced motion 或低带宽时均保留文本体验。

Artist panel 可在 focus 后加载一张批准的代表图；relation panel 只在打开后加载支持作品缩略图。初始 HTML、CSS 与 initial JSON 不携带 runtime media address，初始 image request 为 0。低带宽模式默认 metadata-only，需用户明确触发后才请求图片。

## 6. 媒体渲染、rights 与失败降级

- JPEG/WebP responsive `srcset`，缩略图优先 320/640，focus 代表图不预加载全部作品。
- `loading=lazy`、`decoding=async`，加载失败切换为稳定 no-image state。
- Alt text 使用艺术家、作品名和日期等事实字段，不输出主观评价。
- 每个已显示媒体均可追溯到 license、attribution、changes、official source 与 withdrawal 信息。
- Runtime locator 仅允许 release 内的精确本地 derivative 路径；external API、external media hotlink、cookie 和任意 URL 均为 0。
- 关闭 panel 会中止尚未完成的 artist、relationship 与 rights 请求；UI 有 loading、success、failure 和 live-region 状态。

## 7. 无障碍证据边界

自动化证据覆盖 keyboard、Escape close、focus restore、live region、可见焦点、非颜色唯一表达、forced colors、reduced motion、390/360 px、WebGL unavailable/context loss、no-JavaScript 说明、About/Rights、Accessibility 和 graph/list/table 等价任务。最终本地 M04/公共路由 Playwright 结果为 6/6 passed。

本运行环境没有暴露真实 assistive technology session，因此 `real_assistive_technology_status=not_available`。这里不把 DOM/keyboard/forced-colors 自动化等同于真实 NVDA、JAWS、VoiceOver 或 TalkBack 人工验证，也不伪造 screen-reader pass。

## 8. Current graph 性能

`docs/qa/museum-04/performance-current-graph.json` 的 `overall_status=pass`，覆盖四个受控 Chromium profile。关键结果包括：

- 390×844 / 4×CPU / fast 4G graph：first interactive median 1,258.4 ms，LCP median 884 ms，interaction proxy p95 77.9 ms，FPS median 60，CLS p95 0；
- 360×800 / 6×CPU / constrained network list：first interactive median 1,994.6 ms，LCP median 1,756 ms，interaction proxy p95 109.8 ms，FPS median 60.00，CLS p95 0；
- 1366×768 desktop：first interactive median 448.7 ms，LCP median 392 ms，interaction proxy p95 24.2 ms，FPS median 60，CLS p95 0；
- 1440×900 desktop：first interactive median 446.2 ms，LCP median 388 ms，interaction proxy p95 31.1 ms，FPS median 60.00，CLS p95 0.000221；
- 四个 profile 的 initial image requests/bytes 与 initial deferred-governance requests 均为 0；媒体和 governance data 只在 focus/panel 后按需加载；
- deterministic gzip budgets：home 98,684 ≤ 102,942 bytes；current-lab constellation closure 116,892 ≤ 460,800 bytes，其中 initial JSON 32,897 bytes、graph summary 827 bytes；
- 当前证据文件记录 `source_worktree_dirty=true`，并绑定最终 M05A 源码树 implementation input hash `sha256:a79b9170e0a50818ff5e3ce70804bf54119d73b593a7040fcddc63e24d6aec26`；不能被描述为来自最终 commit 的 RUM 或真实设备数据。

## 9. 1k / 10k / 50k scale evidence

`docs/qa/museum-04/performance-scale-benchmarks.json` 的 `overall_status=pass`：

- 1k 使用真实 Sigma 3.0.3，但只 progressive render 150 vertices / 600 edges；first interactive median 3,737.49 ms、p95 3,806.75 ms，低于 5,000 ms gate；node/interaction median 95.9 ms、p95 104.4 ms，heap p95 11.44 MB。
- 10k 使用 partition/search/local-neighborhood strategy，不请求 full render；model build median 636.9 ms，index build median 32.2 ms，filtered render median 380.6 ms，heap p95 28.62 MB。
- 50k/300k mobile full WebGL 明确 refused；实际构建 50,000 vertices / 300,000 edges 的 bounded typed-array model 与 chunk plan，保持 fallback 可见，model build median 1,831.1 ms，max work slice p95 5.0 ms，fallback paint p95 13.6 ms，heap p95 8.86 MB；work slice 低于 50 ms gate，未出现 blank page 或 freeze assertion failure。

1k 的 supplemental FPS median 27.00 是非门禁诊断值；interaction p95 已改善至 104.4 ms。正式 first-interactive 与 bounded-render gates 均 pass，但低端 FPS 仍登记为非阻断 P3，不被隐藏或改写成达标指标。

Scale evidence 绑定 implementation input hash `sha256:14828963568b75da4780cc5244dce21625c9763950f102e847d016b816c4f0ed`。

没有约 4 GB Android 物理设备可用，`real_device_status=not_available`。Chromium CPU/network throttle 是 controlled lab evidence，不是 real-device pass，也不是 RUM。

## 10. 治理与 rights

- OD-001、OD-002、OD-005、OD-010 已关闭；open decisions 保持 OD-006、OD-008、OD-009、OD-011 四项。
- 项目代码与原创内容为 All Rights Reserved；仓库没有项目级开源 `LICENSE`。
- 第三方作品、媒体与 metadata 权利独立表达，项目 rights 声明不覆盖第三方许可。
- 31 parents 与 242 children 具有精确 rights/license/source-rule/attribution/notice/withdrawal closure。
- Rights Issue Form 不请求公开上传敏感证明；流程保留 7 天确认、14 天初查和高风险 72 小时临时下架目标。

Release signoff 的 executor 是 `automated_release_validation_pipeline`，`editorial_review_status=automated_pass`、`human_review_dependency=false`、`human_reviewer_claimed=false`。不存在也不声称存在人工 curator/editor 审核、签名、日期或资质。

## 11. 旧 `0.1.0` 与 human-review P0 的 supersession

旧 `release:art-constellation-0.1.0` 是未 push、未部署的 pre-media WIP，依赖 zero-media 契约，并把一个拟议的人类编辑流程登记为 P0。该 public candidate 已移除，旧 worksheet 仅以 `status: superseded` 保留审计轨迹，不是当前 release dependency、approval 或 finding。

MUSEUM-AUTO-01 的正式契约要求自动交叉验证、禁止 `waiting for manual review` 与 `pending curator`，并明确不把人工逐项批准作为默认阻塞条件。`1.0.0` 通过 deterministic source、Claim → Evidence → Source、non-causality、translation-shape、allowlist、media-rights 和 adversarial validators 形成自动 signoff。因此旧 `M04-A-001` 及其派生 `M04-F-002` 均标记为 **SUPERSEDED**，而不是虚构“人工审核已完成”。

## 12. 本地 E2E 与截图

当前 `docs/qa/museum-04/playwright-results.json` 记录 5 个本地场景全部通过，覆盖 desktop graph/list/table/relation/rights/URL、1366 无溢出、390 low-bandwidth、forced colors/reduced motion/WebGL fallback 与 no-script HTTP 200。

`docs/qa/museum-04/` 下的截图仍是本地 media-aware QA 证据；统一 push 后的最终线上证据已写入 `docs/qa/museum-auto-01/final-online/`，包含 15 张真实 Pages 截图、11/11 Playwright 结果与 286-file byte closure。

## 13. 已通过的阶段门禁与全流程门禁

MUSEUM-04 阶段内已直接观察并通过：

- formal `--require-public` release validator：pass，counts 与 media bytes 精确匹配，零 failure；
- 28-fixture matrix：28/28 pass；27 个 expected-invalid rejected，1 个 expected-valid accepted；
- current graph evidence：pass；
- scale evidence：pass；
- targeted Python M04 tests：19/19 pass；
- lint、strict typecheck、Vitest 42/42、production build 与 static budgets：pass；
- final local M04/public-route Playwright：6/6 pass；
- 已知未修复 P0/P1：0。

最终 clean install、全仓离线 Python、前端 check、release/rights/performance/budget/scanner、本地浏览器、GitHub Actions、Pages 与真实线上 11/11 门禁均由 MUSEUM-AUTO-01 统一收尾通过；Actions run 为 `29420441620`，deployment 为 `5458604781`。

## 14. Git、Pages 与下一阶段

MUSEUM-04 implementation commit 为 `9a7f38a3bdcfcfb222116f2ead4438e81073f0af`。本阶段没有单独 push；统一 AUTO-01 runtime commit `00a8539ea0d5e901fc2b6be993ea400ff36a0b19` 已通过 Actions 并部署，最终线上证据由 AUTO-01 closeout enclosing commit 记录。

fixture matrix 与其余 M04 final gates 已实际 pass，已知 P0/P1 为 0，public release valid 且本地 Pages build 可用；MUSEUM-05A gate 已被 AUTO-01 消费并完成。仍未进入 MUSEUM-05B、MUSEUM-06、武器馆或生物馆。

## 15. Remaining P3

| ID | 状态 | 影响 | 后续动作 | 阻断 M04/M05A？ |
|---|---|---|---|---|
| M04-P3-001 | open | 无约 4 GB Android 物理设备；controlled Chromium 不能代表真实设备。 | 设备可用时按相同 current/1k contract 补测并追加记录。 | 否 |
| M04-P3-002 | open | 无真实 AT session；自动语义/键盘证据不能代表 NVDA/JAWS/VoiceOver/TalkBack 人工体验。 | 环境可用时补充真实 AT smoke，不改写现有自动证据。 | 否 |
| M04-P3-003 | open | 1k supplemental FPS median 27.00，虽不属于当前 pass/fail gate，但提示低端持续交互仍有优化空间；interaction p95 已改善至 104.4 ms。 | M05A 后续性能回归中保持可见，避免扩大初始 render cap。 | 否 |

除上述非阻断 P3 外，本阶段不登记已知未修复 P0/P1；MUSEUM-04 阶段门禁结论为 `completed/pass`。
