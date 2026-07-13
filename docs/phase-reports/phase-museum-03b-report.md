---
phase_id: MUSEUM-03B
status: completed
validation_status: pass
baseline_commit: 81ca9d28cfb16f971a582497448d30cd0579ee6c
selection_bundle_hash_verified: true
selection_decision_status: submitted
selection_decision_applied: true
decision_authority: Mays
approved_artist_count: 12
formal_artist_record_count: 12
formal_artwork_record_count: 44
formal_context_entity_count: 31
formal_relationship_record_count: 36
relationship_level_a_count: 0
relationship_level_b_count: 0
relationship_level_c_count: 36
isolated_primary_artist_count: 0
od_004_status: closed
od_007_status: closed
media_strategy: mixed
media_execution_default: metadata_first
media_bytes_downloaded: false
external_iiif_candidate_count: 4
self_hosted_eligible_count: 31
metadata_only_count: 9
formal_public_release_created: false
public_art_content_added: false
reviewed_batch_ready: true
graph_input_ready: true
pages_regression_status: pass
open_decisions_count: 8
museum_04_recommended: true
museum_04_authorized: false
---

# MUSEUM-03B 正式艺术知识批次阶段报告

报告日期：2026-07-13（Asia/Shanghai）。运行时未暴露模型或 reasoning 档位，记录为 `not_exposed_by_runtime`。

## 1. 阶段目标与严格边界

本阶段把用户已批准的首批 12 人方案落实为可验证的内部 reviewed 艺术知识批次：正式艺术家、作品、typed contexts、Claim → Evidence → Source、非因果关系、对象级媒体权利评估、review sign-off、graph input 与物理 package。MUSEUM-03B 不是公开产品发布：没有下载媒体，没有生成 formal public release，没有修改 Pages 艺术内容，没有进入或实现 MUSEUM-04。

## 2. 入口基线与前置门槛

入口 baseline 为 `81ca9d28cfb16f971a582497448d30cd0579ee6c`。开始前核对本地 `main`、`origin/main`、GitHub 默认分支、工作树、MUSEUM-03A 完成报告、selection bundle 物理闭包、Pages public/workflow/HTTPS 状态与空序厅回归。`skill/SKILL_INDEX.md` 不存在，故没有虚构项目 skill；实施遵守项目政策、schema、阶段入口与 stop condition。

## 3. 用户决策、OD-004 与 OD-007

选择包 ID 为 `selection-review-bundle:3843c34b-7a65-5581-baec-1385d53326c5`，bundle hash `sha256:ba7640dbfe554c938fc9bf65ac5fa1eb42514ced015e0b4e56598870428072c7` 已验证。用户提交的 decision 为 `selection-decision:17bcd813-6a96-55e5-aed4-788df44ad006`，authority `Mays`，status `submitted`，scenario `selection-scenario:8966bf75-2830-5a0f-afc5-5d6801e93ccc`，精确选择 12 人、替换 0。OD-004 以该 slate 关闭；OD-007 以 `Mixed` 关闭，首轮执行默认 `metadata-first`。

## 4. 决策应用、陈旧检查与幂等性

application 为 `selection-decision-application:8c2666ef-fdfe-5250-af97-1d3b1d8c4a43`，状态 `applied`、validation `pass`、stale check `fresh`。application 同时绑定 bundle、decision、Recommended 文件与 12 个候选记录 canonical hash，避免只凭语义 bundle hash 接受已漂移输入。重复应用为幂等且不改 bytes；ID 冲突、hash 漂移、越权替换或不同 authority 均 fail closed。

## 5. 实施架构、Wave 划分与变更清单

实施按 decision application、身份门禁、作品选择、正式作品/证据、context、关系/disposition、媒体评估、sign-off、package/graph、泄漏/CI 十个闭合面推进；任一批准艺术家身份/死亡冲突、对象权利不明、reference 不闭合或 expected-invalid 意外通过都会停止后续提升。变更保持在 MUSEUM-03B schema、policy、fixture、builder/validator、正式 reviewed package、CI 与 QA/report；公开 UI 内容未改。

## 6. 身份解析、死亡硬门槛与竞争主张

12/12 均为已识别、确认已故的个人并通过 reviewed 身份门槛；没有把 anonymous、workshop、collective 或 traditional attribution 转成个人。MUSEUM-03A 预审布尔值没有被盲目继承；生卒、职业/创作角色、权威记录、外部 ID、精度差异和反证以独立 Claim/Evidence 保留。Raja Ravi Varma 的既有生平/生产角色冲突被显式解析后才通过，不以静默覆盖换取批次完整。

## 7. 正式 12 人艺术家批次

批准且正式 reviewed 的艺术家为 Albrecht Dürer、Francisco de Goya、Vincent van Gogh、Mary Cassatt、Käthe Kollwitz、Julia Margaret Cameron、Katsushika Hokusai、Kitagawa Utamaro、Shen Zhou、Raja Ravi Varma、José Guadalupe Posada、Henry Ossawa Tanner。正式艺术家数精确为 12；选择与用户决策完全一致，无失败者、无自动替代、无 quota padding。

| 艺术家 | 作品数 | 图 degree |
|---|---:|---:|
| Albrecht Dürer | 4 | 8 |
| Francisco de Goya | 4 | 4 |
| Vincent van Gogh | 4 | 5 |
| Mary Cassatt | 4 | 7 |
| Käthe Kollwitz | 2 | 8 |
| Julia Margaret Cameron | 4 | 6 |
| Katsushika Hokusai | 4 | 9 |
| Kitagawa Utamaro | 4 | 6 |
| Shen Zhou | 4 | 3 |
| Raja Ravi Varma | 2 | 4 |
| José Guadalupe Posada | 4 | 5 |
| Henry Ossawa Tanner | 4 | 7 |

## 8. 44 件作品选择、数量门槛与 held-out 聚合

正式作品精确为 44：10 位艺术家各 4 件，2 位各 2 件，全部处于允许的 2–4 件范围。每件都绑定批准艺术家、官方对象、source object ID、不可变快照、rights preflight 与选择理由。未选中的批准人物替代作品只以聚合 exclusion 记录：count `4`，hash `sha256:95e3e485a7174ec373c992e4a80fc6662e4ab1e721588950ccd65bb4c89b053e`；不在正式作品、关系或媒体评估中泄漏其清单。

## 9. 来源、快照、Adapter 与 Registry 闭合

正式来源为 Met Open Access、Art Institute of Chicago API、Getty ULAN 与 Wikidata，共 4 个；adapter 版本分别为 `0.1.0`、`0.1.0`、`0.1.1`、`0.1.0`。source registry hash 为 `sha256:de65a18fa3a6adcd3216b5c5e1f4426a112c35680b6899507d839e07a1cda7f7`，license rules hash 为 `sha256:19d10386405abf971c5712e955f60c08d2bd43e6f8060a29035033ff3c33ada2`。70 个 unique raw snapshots 通过 81 个 hash/path receipts 提供 provenance locator；包中不复制 raw response bytes。

## 10. 正式作品、归属、年代、机构与登录号

44 件作品均以 canonical entity type 与 ID prefix 调度到具体 artwork schema，包含官方对象 URL/ID、holding institution、accession number、年代 span/precision、creator attribution、title provenance、material/technique/subject bindings、source-license bindings 与 status history。归属声明不因显示标题或 creator label 简化；translated title 明确标记项目翻译及其源 Claim/sign-off。

## 11. 31 个 Typed Context 的正式化

31 个 contexts 分为 material 7、technique 9、subject 11、place 2、museum institution 2。每个 context 有 typed ID、双语 label、定义、Claim/Evidence/Source、review status 与版本；没有用自由文本临时节点绕过 canonical dispatch。它们只用于已审查的比较语境，不生成历史因果或隐含影响。

## 12. 588 Claim–289 Evidence–4 Source 证据链

批次共 588 个 Claim、289 个 Evidence、4 个 Source。艺术家身份/死亡、作品官方记录/归属/日期/机构/登录号、context 与关系语义都能沿 Claim → Evidence → Source 解析；Evidence 绑定 snapshot hash、locator 与适用 content class。Tier 3 只承担发现/crosswalk，不独立支持争议事实或直接影响主张；竞争 claim、反证、reviewer、review date 与 status history 均保留。

## 13. 关系研究方法与历史/策展语义分离

关系研究把 `historical_relationship_strength`、`evidence_confidence`、`computational_similarity` 与 `curatorial_relevance` 分开。形式关系只接受具体所选对象和 typed context 支持的 shared subject/material/technique；不把相似性写成接触、影响、传播、教学、师承或因果。所有正式关系均 `generation_method=reviewed_curatorial_synthesis`、`public_display=false`，并有语义与证据复核。

## 14. 36 条正式关系与图结构

正式关系为 36：shared subject 17、shared material 11、shared technique 8；A/B/C 为 `0/0/36`。全部是无向、非算法 C-level curatorial comparison，computational similarity 为空。graph input 为 12 个 primary nodes、31 个 context nodes、36 条 edges；艺术家 degree 范围 3–9，分布 `{3:1, 4:2, 5:2, 6:2, 7:2, 8:2, 9:1}`，isolated primary artist 为 0。graph content hash 为 `sha256:58fe40930ab6f0e84019bbb0c3f378a2e73d7f3fbd4f810a66aa78f0481d1dd3`。

## 15. 69 项 Disposition 与双向 Backlink 闭合

69 项 research disposition 覆盖 inherited leads 45 与 new curated candidates 24。最终 promoted 36（inherited 12、new 24）、out of scope 27、rejected 2、retained for more evidence 1、superseded 3；36 个 formal relationship backlink 与 3 个 supersession backlink 精确闭合。未提升项保留 privacy-safe rationale 和证据缺口，不伪装成正式关系。

## 16. 44 项媒体权利结论与 31/4/9 分布

44 件作品逐对象完成 metadata/media 分离的权利评估：31 个 future `self_hosted_open_media_eligible`、4 个 `external_iiif_candidate`、9 个 `metadata_only`。35 个仅标记 future-public-media eligible，9 个为 false；这些都不是当前发布许可。44/44 的 `bytes_downloaded`、`media_bytes_present`、`cache_bytes` 均为 false，`development_only=true` 为 0；四个 IIIF URL 只作为元数据存在。

## 17. 208 项 Reviewer 与 Tracked Sign-off 治理

208 项 accepted reviewed sign-off 按职责分离：data 47、artwork attribution 44、multilingual 44、rights 44、art history 13、identity 12、relationship 3、release 1。tracked batch sign-off 与 package 中对应记录 exact-match；三项批次级 tracked sign-off 不能替代作品/身份/权利的逐记录审查。执行者记录为 `ai_assisted_operator`，审查范围、角色、时间和决定均可追溯。

## 18. Schema、Canonical Dispatch 与版本闭合

最终治理仓包含 47 个 schema；schema manifest hash `sha256:bc35d93ade647809d46d0854635cbd3f6c2d6210ab1c0d97fce16717c6695e64`。canonical dispatch 由 entity type、branch 和 ID prefix 决定，不能信任记录自报 schema，也不能以 common base 替换具体 branch schema。验证矩阵覆盖 governance 8 valid/22 invalid、pipeline 14 valid/28 invalid 加 4 recorded、MUSEUM-03A 6 valid/27 invalid、MUSEUM-03B 4 valid/69 invalid；expected-invalid 意外通过即硬失败。

## 19. 18 文件物理 Package 与 Manifest 闭合

正式包位于 `data/reviewed/art/museum-03b/museum-03b-first-slate-v1/package-v1/`。根目录有 18 个声明文件加 `package-manifest.json`，共 19 个 regular Git blobs；声明字节 `3,043,199`，总物理字节 `3,098,124`。package content hash `sha256:1f0f00a0d7f6162fcb0d716e6b86fbcfe42a4e04a0422d7c1c0df63b70c97b86`，根 manifest 文件 SHA-256 `sha256:70a1e28a8bc94e0397fb9617e3d912061a39e0580b48fc905fa45dcb0503b13e`，formal manifest content hash `sha256:44c76db2bc7a0c7bf66fd887c34d96604574fb7d67492935fd4d8defb0a4e9a4`。validator 对 bytes/hash/canonical JSON/path/symlink/exact set/typed ID/reference/source-license/review/no-media/no-public/code-anchor 的失败数为 0。

## 20. Git Code Anchor、确定性与可复现性

formal manifest 固定 code commit `571fb03cfc022d4e6f0d3f60778e7e3992bcc148`；sealed package commit 为 `fd47680b3a0b8ad3787932687bbb4f7cc394244f`，最终实现验证 head 为 `5c529c70a24e5b1928efccb803b8504fe767bb60`，前者均是后者祖先。首次 CI 暴露 shallow checkout 无法解析 code anchor，随后改为完整 history；下一次暴露 tests 依赖 ignored raw，随后改为由 sealed package 投影重建等价测试输入。没有改写历史或 force push；确定性、tamper、stale、idempotency 与 reference closure 测试均通过。

## 21. 隐私、泄漏标签与未批准替代项边界

物理审计对 30 位未批准候选的 ID、名称、别名、ULAN/QID 及其 43 件作品做精确扫描，命中 0；4 个批准人物 held-out 中 3 个完全缺席，第 4 个对象号 `371803` 只作为 Mary Cassatt 身份/工作史的合法 Claim/Evidence 与 receipt closure 出现，不在作品选择、formal artwork、关系或媒体评估中。包内无 MUSEUM-03A 私有路径正文、authorization 原件、私有笔记、长篇来源复制或 secret。tracked leakage label set 共 1,871 项，按 substring、exact token、serialized string 区分，避免把 `Canvas`/`Ink` 等普通网页词误报为正式数据泄漏。

## 22. 无媒体、无 Published State 与 Pages 边界

package 明示 `media_bytes_downloaded=false`、`media_bytes_in_package=false`、`formal_public_release_created=false`、`pages_art_content_added=false`；graph 为 `public_release=false` 且无媒体依赖。`public` 与 `dist` 的 label-backed scan 分别覆盖 1/4 文件，均零命中。公开门户仍为七馆入口，美术馆仍为空序厅，武器馆不可点击；没有艺术家、作品、关系、媒体或第三方 runtime 进入 Pages。

## 23. Fixture、Python、全仓、CI、Pages 与 A–E 审计

本地最终验证：MUSEUM-03B package PASS；4 valid/69 expected-invalid/68 behaviors PASS；Python 全套 218/218（0 skip/xfail），closeout 后定向回归 57/57；frontend lint、strict typecheck、22/22 tests、production build、496-file repository safety PASS；262 个 JSON 可解析，长 base64 为 0。GitHub Actions [29237904962](https://github.com/Archmays/Museum-Codex/actions/runs/29237904962) 在实现 head 上 build 5m26s、deploy 8s，均 success。线上 Home/Art/About/Accessibility、低带宽、7/1/6/0 入口结构、4 个静态资源、console、failed requests、第三方媒体、63 个艺术家 DOM 项和完整 live artifact leakage scan 均通过。Reviewer A–E 均 PASS，无未解决 P0/P1/P2；细节见 `docs/qa/museum-03b/adversarial-review.md` 与 `pages-regression.md`。

## 24. P3、8 项开放决定与下一阶段 Handoff

保留 P3-01（append-only 非 WORM）、P3-02（DNS/系统代理未 cryptographic pinning）、P3-03（discovery helper 非 reference adapter）；均有 owner、缓解、影响和最晚复核阶段，均不阻断 MUSEUM-04。关闭 OD-004/OD-007 后项目 open decisions 为 8；未擅自关闭其他决定。建议把本批作为 MUSEUM-04 的内部 graph input，但进入 MUSEUM-04 仍需用户另行明确授权、后续 publishable graph/release gate、OD-005 性能预算；公开展签前还需处理 OD-002。

## 25. 验收结论、Git 状态与禁止事项确认

MUSEUM-03B 达到 `completed/pass`：选择决策已应用，12/44/31/36 reviewed batch 与 graph input ready，OD-004/007 已关闭，正式 package/CI/Pages/隐私/对抗审查通过。没有下载或提交媒体，没有 formal public release，没有向 Pages 添加艺术内容，没有进入 MUSEUM-04。临时 Playwright 产物不属于交付并在最终 handoff 前清理；closeout 提交后以本地 HEAD、`origin/main`、GitHub `main` 三方一致且工作树干净作为最终 Git 验收。
