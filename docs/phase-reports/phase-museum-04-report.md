---
phase_id: MUSEUM-04
status: partial
validation_status: fail
baseline_commit: 2be73011cb1dca64cb8d3a2d5830f495671d755b
implementation_commit: null
final_commit: null
od_001_status: closed
od_002_status: closed
od_005_status: closed
od_010_status: closed
open_decisions_count: 4
code_rights: all_rights_reserved
original_content_rights: all_rights_reserved
public_release_created: false
public_release_id: null
public_release_hash: null
candidate_release_id: release:art-constellation-0.1.0
candidate_release_hash: sha256:9467b5449e13fd3e89272a62bc614fe776b22d14745bdbf72c4540d5e84e0cc4
public_artist_count: 12
public_context_count: 31
public_relationship_count: 36
relationship_level_a_count: 0
relationship_level_b_count: 0
relationship_level_c_count: 36
public_artwork_metadata_count: 44
public_media_count: 0
media_bytes_downloaded: false
algorithmic_relationship_count: 0
art_constellation_route_ready: true
graph_view_ready: true
artist_list_ready: true
relationship_table_ready: true
accessible_equivalence_status: pass
webgl_fallback_status: pass
low_bandwidth_status: pass
performance_current_graph_status: pass
performance_1k_status: pass
performance_10k_boundary_status: pass
performance_50k_boundary_status: pass
real_device_status: not_available
rights_issue_form_ready: true
pages_deployment_status: failure
pages_url: https://archmays.github.io/Museum-Codex/
museum_05_recommended: false
museum_05_authorized: false
blocking_gate: m04_human_editorial_review_required
---

# MUSEUM-04 艺术星海阶段报告

报告日期：2026-07-14（Asia/Shanghai）。运行环境未暴露模型或 Reasoning 档位，记录为 `not_exposed_by_runtime`。本报告中的 12/31/36/44 是本地 metadata-only 候选投影计数，不表示该候选已经成为正式 public release 或已经部署到 Pages。

## 1. 阶段结论

状态为 **partial / fail**。产品、治理、无障碍、性能、零媒体、物理闭包和自动化门禁均已实现并通过本地验证；正式发布仍被一个不可由 Codex 代行的 P0 根门禁阻断：12 位艺术家的中英文简介均为 AI-assisted draft，尚无已识别、可问责的人类编辑对精确摘要 digest 完成签核。正式 validator 仅返回 `m04_human_editorial_review_required`。因此没有创建 formal public release，没有提交、推送或触发 MUSEUM-04 Pages 部署，也没有进入 MUSEUM-05。

## 2. 基线、入口审计与 Git 锚点

入口 baseline、当前本地 `HEAD`、本地 `main`、`origin/main` 和 GitHub `main` 的已核验锚点均为 `2be73011cb1dca64cb8d3a2d5830f495671d755b`。M03B package semantic hash 保持 `sha256:1f0f00a0d7f6162fcb0d716e6b86fbcfe42a4e04a0422d7c1c0df63b70c97b86`，graph semantic hash 保持 `sha256:58fe40930ab6f0e84019bbb0c3f378a2e73d7f3fbd4f810a66aa78f0481d1dd3`；12 artists、44 artworks、31 contexts、36 relationships、A/B/C=`0/0/36` 与 zero media 均无漂移。入口工作树原本 clean；本阶段所有变更仍为未提交本地工作。

## 3. Decisions 与剩余开放项

OD-001、OD-002、OD-005、OD-010 已写入 decision log、open-decisions 文档和相应治理合同并关闭。开放项精确为 4：OD-006、OD-008、OD-009、OD-011；没有越权关闭搜索、媒体或后续体验相关决定。

## 4. Code 与原创内容权利

项目代码和原创中英文策展文字、翻译、关系解释、UI 文案与原创设计均为 `ALL-RIGHTS-RESERVED`。根目录新增 `RIGHTS.md`，仓库没有项目 `LICENSE`，`package.json` 继续 `private: true`。公开可查看不被表述为开源授权；项目声明不覆盖 AIC、Met、Getty、Wikidata 等第三方 metadata/data 规则、notices 或 attribution。

## 5. Rights Issue Form 与撤回流程

`.github/ISSUE_TEMPLATE/rights-or-attribution.yml` 已建立并通过专门 validator：包含 9 个隐私安全字段，不要求文件上传、身份证件、合同、地址、电话或公开 email。治理流程记录 7 个自然日初步确认、14 个自然日一般初评、明显高风险立即隔离及 72 小时临时移除目标；撤回通过新 release，恢复必须形成新的权利审核记录。

## 6. ADR、依赖与静态架构

ADR-0002 已固化 Graphology 数据/邻域、Sigma WebGL、DOM 列表/关系表等价、确定性构建期布局、可见上限和 1k/10k/50k 边界。生产依赖精确锁定 `graphology@0.26.0` 与 `sigma@3.0.3`，均为 stable、MIT；没有采用 Sigma 4 alpha、CDN、remote worker、远程字体、后端或运行时外部 API。Graphology/Sigma 与星海 route 均按需加载，不进入首页首屏。

## 7. 本地候选与正式发布门禁

本地候选 ID 为 `release:art-constellation-0.1.0`，candidate content hash 为 `sha256:9467b5449e13fd3e89272a62bc614fe776b22d14745bdbf72c4540d5e84e0cc4`。它有 19 个清单闭合文件、1,493,040 bytes，状态严格为 `reviewed`、`public_release=false`。候选结构 validator PASS，独立临时目录重建与 canonical candidate 19/19 文件逐字节一致。正式 `--require-public` 模式以 exit 1 失败，唯一错误码为 `m04_human_editorial_review_required`；正式 `public_release_id/hash` 因而保持 `null`。

## 8. Projection、物理闭包与零媒体

候选安全投影精确包含 12 artists、44 artwork metadata、31 contexts、36 relationships、252 claims、138 evidence、4 sources；关系类型为 shared subject 17、shared material 11、shared technique 8。manifest、schema、typed IDs、引用、bytes/hash、source rule snapshot、license decisions、notices、attribution、withdrawal 和 M03B predecessor basis 全部闭合。media records=0、media bytes=0、下载字节=false；无图片、thumbnail、IIIF、外部媒体 URL、私有路径、raw/rejected/held-out、算法字段或未声明文件。

## 9. 关系语义与解释合同

全部 36 条关系都是无向的 `C｜策展比较`，historical relationship strength 与 computational similarity 均为 `null`，不存在历史因果边、算法相似边或伪造 A/B。每条中英文解释均绑定具体 endpoints、共同 context、支持作品 metadata、Claim → Evidence → Source、confidence、curatorial relevance、review/release/limitations，并明确“共同题材/材料/技法不证明相识、影响、师承、传播、亲密或艺术价值”。关系标题/解释逐条唯一，因果措辞 scanner 与负向夹具 fail closed。

## 10. 12 位艺术家简介与人工审核阻塞

12 位艺术家均有基于 verified claims 组装的双语短简介，覆盖时间、地点、媒材/实践和本展比较意义，无排名、完整传记、复制 museum label 或文化概括。候选 provenance 如实记录 `human_reviewed=false`；摘要集合 digest 为 `sha256:42660e0a7a1d4a33548c82d8e942c747dbe42f20d3b2ef16ae92673114ea1da6`。`docs/qa/museum-04/artist-summary-human-editorial-review-packet.md` 提供 12 组逐项 factual accuracy、translation equivalence、neutral/non-causal wording、unsupported influence 与 source traceability 签核位。Codex 没有自称人类、没有伪造 reviewer，也没有回填日期。

## 11. 路由与访客体验

`#/art` 已成为美术馆入口，说明当前为无图片的艺术星海候选、三种探索方式、来源/权利和“艺术家展厅后续开放”。`#/art/constellation` 提供正式中英文名称、候选状态、语义边界、搜索/筛选、legend、探索、artist/relation/source panels、limitations/rights 与 live region。正式发布前 UI 明示“发布候选 · 待人工审核”，不把候选或未来 gallery 写成已发布功能。

## 12. Graph、Artist list 与 Relationship table

Graph 使用 Graphology + Sigma、12 个等大节点、初始 0 条可见边、focus 后只揭示一跳 C 关系；布局确定性、无持续 force、距离与中心性无事实含义。Artist list 和 Relationship table 共用同一状态模型、URL、search/filter、focus/relation/source 与 hidden counts，可完成相同核心任务。Canvas 对辅助技术为装饰；列表和表格是等价正式体验，不是降级的次等界面。

## 13. Search、filters、A/B 空态与 URL

9,830-byte 静态 search index 覆盖中英文 preferred labels、approved aliases、transliteration/source label、stable ID/type/locale/normalized key；仅 exact/prefix/simple substring 并显示 match reason，无中文分词库、远程/AI 搜索或 analytics，OD-008 保持 open。筛选支持 relation type、A/B/C、period、region/tradition、context type、artist 与 view；A/B 显示“当前暂无经核验关系”，不造边。release/focus/relation/types/level/period/region/view 可安全同步到 query，invalid ID fail closed，不写入说明文本、原始 Claim 或用户历史。

## 14. 无障碍、WebGL 与低带宽

skip link、landmarks、headings、tabs/tabpanel、labels、live status、44px touch targets、可见焦点与颜色外冗余均已实现。Tab、Enter/Space、Escape、Arrow、Home/End、panel close/focus restore 已覆盖；reduced motion 无持续布局或飞行动画。forced colors、360px/受限网络、WebGL unavailable/context lost 自动进入或保留 DOM list/table，filters/focus/URL 不丢失且不白屏。390×844 与 360×800 均无横向溢出；JS disabled 仍有 HTTP 200 的 portal/art/rights 基础说明。

## 15. 当前 12/36 controlled-lab 性能

`performance-current-graph.json` 为 controlled lab，不是 RUM/p75。390×844、4× CPU、Fast 4G：first interactive median 1,280.9 ms，LCP median 912 ms，node p95 3.2 ms，interaction proxy p95 114.8 ms，FPS p95 60.0，heap p95 8.81 MB，CLS p95 0.0998。360×800、6× CPU：1,980.3/1,748/8.0/162.6 ms，60 FPS，6.81 MB，CLS 0.0913。1366×768：451.7/396/0.6/70.4 ms，60 FPS，8.46 MB，CLS 0.0791。1440×900：448.5/388/0.6/62.3 ms，60 FPS，8.47 MB，CLS 0.0806。所有硬目标 PASS。

## 16. 1k、10k 与 50k 合成边界

1k V/5k E 在 390×844、4× CPU、Fast 4G 使用实际 `sigma@3.0.3`，仅渐进渲染 150 V/600 E；first-interactive 三样本 3,586.3/3,458.6/3,397.6 ms，median 3,458.6 ms、p95 3,586.3 ms，interaction p95 74.1 ms，PASS。10k/60k 不作全图首屏，以 partition/search/local neighborhood 运行；model/index/filtered-render medians 为 469.7/21.6/214.4 ms。50k/300k 明确拒绝移动全量 WebGL，以 exact typed-array model 与 834 个有界 chunks 执行；model median 1,815.3 ms，work-slice p95 3.3 ms、yield 110、heap p95 8.86 MB，fallback 始终可见，无 freeze/blank。证据绑定 implementation input hash `sha256:698443b07526a9903b7c619cfed74aaea2326bac7ca955d1a9629d3b122d423c`。

## 17. Bundle 与 gzip 预算

确定性 level-9 gzip：home initial JS+CSS 95,131 B，相对 M03B baseline 89,515 B 增长 6.27%，低于 +15% 上限 102,942 B；constellation route JS+CSS+initial data 72,418 B，远低于 450 KiB；initial data 14,587 B；graph summary 766 B，低于 100 KiB。Graph library 不在 home initial chunk，details 延迟加载，benchmark fixture 不随站点发布，media 与 runtime external requests 均为 0。

## 18. Sources、notices、attribution 与 withdrawal

候选只绑定实际使用的 AIC、Met、Getty ULAN、Wikidata 四组 metadata/data rules；规则快照、stable rule IDs、content class、license decision、notices 与 attribution 精确对应，未把 media rules 或项目 rights-reserved 扩张到第三方数据。Source UI 只显示 title/publisher/official URL/date/locator/license/attribution，不显示 raw JSON、本地路径、长引用或内部 notes。rights request、temporary isolation、new-release withdrawal、cache/replacement/restoration 合同均由 validator 检查。

## 19. Tests 与 validators

最终证据包括：Python 离线全套 257/257；MUSEUM-04 fixture matrix 20/20（19 expected-invalid + 1 valid zero-media）；scanner 定向 17/17；frontend Vitest 32/32；Node performance-runner contract 8/8；Playwright 5/5。Lint、strict typecheck、production build、resource closure、budget、repository secret/large-file scan、governance 49 schemas/8 valid/22 invalid、pipeline 14 valid/28 invalid/4 recorded、M03A、M03B 4 valid/69 invalid/68 behaviors 与 sealed package 均 PASS。`public` 21 files、`dist` 29 files 的 label-backed leakage scan PASS；对 generic lowercase `` `canvas` `` 与 formal context label `"Canvas"` 的扫描大小写边界有专门回归，不会放过真实序列化正式标签。

## 20. E2E 与截图

本地最终 Playwright 5/5 覆盖 desktop graph/list/table/relation/rights/URL/keyboard、1366px no-overflow、390px graph/list/low-bandwidth/refresh、forced-colors/reduced-motion/WebGL unavailable 和 JS-disabled HTTP 200。截图位于 `docs/qa/museum-04/`：`art-landing.png`、`desktop-initial.png`、`focused-artist.png`、`relationship-explanation.png`、`desktop-list.png`、`mobile-graph.png`、`mobile-list.png`、`forced-colors-list.png`、`rights-panel.png`。这些是 QA 证据，不是艺术媒体。

## 21. 对抗性审查 A–F

A：唯一根 P0 `M04-A-001` 为人工编辑签核未完成；36 C、解释/作品/source 与无因果已通过。B：探索、一跳、filters/panels、A/B empty 与 M05 边界通过。C：graph/list/table 等价、keyboard/SR/live/forced colors/reduced motion/low bandwidth/WebGL/mobile 通过。D：stable versions、lazy/budgets/current/1k/10k/50k/no runtime force 通过。E：rights reserved/no LICENSE/notices/zero media/Issue Form/SLA/withdrawal 通过。F：候选闭包与 fail-closed workflow 通过；`M04-F-002` 是由 A-001 派生的 publication block，不是第二个根因。详细 finding register 见 `docs/qa/museum-04/adversarial-review.md`。

## 22. CI、Pages 与线上边界

workflow 已加入 decisions、Issue Form、M04 formal validator、deterministic rebuild、zero-media/closure、semantics、leakage、loader/frontend、performance evidence、budgets、offline/no-external-runtime 与 E2E 门禁。部署前调用 `--require-public`，当前候选会在 upload-pages-artifact 之前正确停止。本阶段没有 commit/push、没有 M04 Actions run、没有 M04 Pages artifact、没有 M04 live assets/console/requests/external/media QA；`pages_deployment_status=failure` 表示验收未完成/未尝试，而非一次部署执行报错。只读收口确认 GitHub `main` 仍为 baseline；最近成功 Pages run 为 [29239839465](https://github.com/Archmays/Museum-Codex/actions/runs/29239839465)，head 也是 baseline `2be73011…d755b`。公开 URL 当前 home HTTP 200、缺失路径 HTTP 404，HTML 不含 M04 中英文标题而仍是七馆 baseline。上述 baseline smoke 不能据此宣称 M04 已上线或 M04 线上 error/external/media 为零。

## 23. Remaining P3

`M04-P3-001`；owner：MUSEUM release QA owner；impact：运行环境没有暴露约 4 GB 的物理 Android，Chromium throttling 只属于 lab proxy；mitigation：设备可用时按 current/1k 同合同补测并追加记录；latest review phase：MUSEUM-04 closeout；本项单独不阻断 M05，因为 phase contract 允许 `real_device_status=not_available`。当前阻断 M05 的仍是 P0 `M04-A-001`。无其他 P3。

## 24. Git、commit 与发布状态

用户建议的 implementation/final commits 均未创建，commit ID 为 `null`；没有 stage、push、force/rewrite、PR、workflow dispatch 或 Pages mutation。这样避免把尚未通过人工审核的 candidate 误升为正式 release。工作树因本地实现和 QA 证据而 dirty，这是有意的未发布状态，不满足 completed 所需的 clean/local-origin-remote 一致门槛。

## 25. M05 建议与解阻手册

`museum_05_recommended=false`、`museum_05_authorized=false`，且未进入 MUSEUM-05。解阻需要一名真实、已识别、可问责的人类编辑对 review packet 中 12 组双语摘要逐项给出 APPROVE/RETURN，提供 reviewer name/stable ID、role、review date，并明确批准 exact digest `sha256:42660e0a7a1d4a33548c82d8e942c747dbe42f20d3b2ef16ae92673114ea1da6`。收到有效签核后才可更新每位 artist provenance 与 release sign-off、重建 formal `public_release=true` bundle、重跑全部 validators/A–F、创建 commits、推送、等待 Actions/Pages 成功并执行线上 HTTP/assets/console/requests/404/external/media/leakage QA。此后仍需用户另行授权才能进入 MUSEUM-05。
