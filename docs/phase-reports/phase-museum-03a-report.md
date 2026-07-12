---
phase_id: MUSEUM-03A
status: completed
validation_status: pass
baseline_commit: 6c5f44da7fd2e568c2f5dca9078362ab0e720151
candidate_pool_generated: true
candidate_pool_count: 42
qualified_candidate_count: 24
selection_scenarios_generated: 3
recommended_slate_count: 12
alternate_candidate_count: 8
user_confirmation_package_ready: true
user_confirmation_received: false
od_004_status: open
od_007_status: open
formal_artist_records_added: false
formal_artwork_records_added: false
formal_relationships_added: false
media_downloaded: false
candidate_names_committed_to_public_repo: false
candidate_data_publicly_exposed: false
public_portal_changed: false
pages_regression_status: pass
open_decisions_count: 10
museum_03b_ready_for_user_decision: true
museum_03b_authorized: false
---

# MUSEUM-03A 阶段报告

报告日期：2026-07-13（Asia/Shanghai）。模型或 Reasoning 档位：`not_exposed_by_runtime`。

## 1. 阶段目标与边界

本阶段建立人工确认前的艺术家宽池、硬门槛、对象权利预审、关系研究线索、三套情景、综合推荐、备选与确认模板。真实研究包只在 ignored 本地 review 区；没有批准艺术家、正式作品或正式关系，没有进入 MUSEUM-03B，没有关闭 `OD-004` / `OD-007`，也没有修改公开门户。

## 2. 基线审计与回归

入口时 `main`、本地 HEAD、`origin/main` 与 GitHub 默认分支均为基线 `6c5f44da7fd2e568c2f5dca9078362ab0e720151`，工作区干净；Pages 为 public、workflow、HTTPS。没有 MUSEUM-03 正式数据或旧未跟踪候选输入，`data/raw/`、`data/intermediate/` 和 review 区仍被忽略。

修改前重新通过：26 schemas、30 governance fixtures、17 sources、14 pipeline valid、28 expected-invalid、4 recorded source sets、4 reference adapters、143 Python tests、22 Vitest/RTL、physical release、lint、strict typecheck、production build、repository/public/dist/arms leakage 与在线 Pages smoke。

## 3. 保留 P3

- `P3-01`（data maintainer）：应用层 append-only 不是 WORM；本地管理员仍可能改 raw。MUSEUM-03B 前复核；当前以 immutable final path、bytes/hash、manifest 与 stale closure 缓解。
- `P3-02`（security reviewer）：DNS 公网预检不是 cryptographic pinning，系统代理仍在信任边界。任一凭据/新 host 或 MUSEUM-03B 前复核；当前无凭据/cookie、固定 HTTPS host、redirect/size/timeout 与 response hash。
- `P3-03`（data maintainer）：search/discovery utility 不是 reference adapter。MUSEUM-03B source plan 前复核；采用对象必须回到 official detail record/reference adapter。

当前研究为单机、无凭据、并发 1、固定官方 host、无媒体字节的最小预审，风险仍可接受。凭据、cookie、镜像回退、批量抓馆藏、媒体下载、未知 host 和 candidate promotion 继续禁止。

## 4. 候选研究方法与硬门槛

执行 `宽池 → 个人/死亡/身份 → Tier 1/2 → 正式对象与权利路径 → relation leads → scenario → bias review → user decision`。0–3 只表示准备度与组合贡献，不能抵消硬门槛，也不产生艺术价值、重要性、影响力、市场或正典排名。

宽池 42 位；合格池 24 位；研究队列 18 位。退出/停留原因包括身份或生卒证据未闭合、权威独立来源不足、正式对象或权利路径不足，以及一例权威记录内部生卒冲突。匿名、工作室、群体和传统归属没有被伪造成个人；Tier 3 只承担发现、多语名和外部 ID 线索。

## 5. 来源与 adapter gap

研究使用 Getty ULAN、正式博物馆对象记录及已登记来源规则；Wikidata 仅为 Tier 3 discovery。GitHub repository 按发布机构而非平台分级：只有机构官方账号、组织身份、license、commit/tag/hash、上游链和撤回状态闭合后才可成为 Tier 1/2，fork、镜像或个人整理只用于发现。

当前主要缺口是若干机构只有人工对象页/搜索预审，没有 production adapter；搜索 utility 不升级为 MUSEUM-02 reference adapter；新机构 official repositories 仍需 source registry 与 license-rule 预研；对象详情、身份和搜索接口的 contract drift 需分别处理。缺 adapter 没有成为排除非西方候选的理由。

## 6. 作品权利与关系线索

91 件作品完成对象级 preflight：53 `rights_path_clear_candidate`、4 `external_iiif_candidate`、34 `metadata_only_candidate`。所有记录分离 metadata/media，保留对象 URL、rights evidence、delivery/caching/attribution/modification/Pages 风险与 source-rule binding；8 位合格候选使用逐人较小配额理由。状态均不是 publishable/approved/released，媒体字节为零。

45 条关系线索包括 A 1、B 8、C 36；正式关系 0、公开关系 0、computational similarity 0。A 指向直接证据类别，B 绑定具体地点/时期/机构/团体/展览语境，C 明确为策展比较；每条均写明 MUSEUM-03B 待核验项。

## 7. 组合方案与偏差

三个 scenario 与 Recommended 均恰好 12 个唯一合格 ID、`user_approved=false`。非姓名化统计：每套覆盖 6 个地区/传统桶、4 个历史区段、3 位女性、11 类媒介/材料；每套有 8 位达到至少 4 条清晰对象媒体路径。A/B/Recommended 的 lead counts 分别为 17/18/18；Recommended 可审查地接近数据/权利方案。

结构性偏差仍包括英语与欧美机构发现优势、开放图片不均、前现代女性署名与对象记录缺失、非西方馆藏 API/rights 表达不足，以及把现代地理标签套到历史身份的风险。组合只是一组受范围、证据、权利、学习与工程条件约束的试点建议，不代表完整或普世艺术史。

## 8. OD-007 选项

确认包比较 Metadata-first、External IIIF/source delivery、Self-hosted open media only 与 Mixed 的权利、访问、性能、撤回、缓存、署名、Pages 体积、复杂度和 MUSEUM-05 影响。代理建议 `Option D Mixed`，但首轮默认 metadata-first，只有逐对象权利闭合后才升级；`OD-007` 保持 open。

## 9. 本地用户确认包

- 目录：`data/review/curation/museum-03a/bundle-20260713-v5/`
- handoff：`selection-handoff.md`
- decision template：`selection-decision-template.json`，状态 `pending_user_decision`
- bundle hash：`sha256:ba7640dbfe554c938fc9bf65ac5fa1eb42514ced015e0b4e56598870428072c7`
- payload：13 个精确文件，manifest 对 bytes/SHA-256/schema/source snapshot/adapter/input closure 做物理闭合。

Bundle validator 验证 exact set、canonical JSON、path/symlink escape、stale、hash/bytes、candidate/source/artwork/lead/scenario/alternate/decision closure；review/raw/bundle 均被 Git 忽略。

## 10. Schema、fixture、CLI 与测试

新增 7 个 curation schemas，schema 总数 33；5 个 synthetic valid 和 26 个 expected-invalid fixtures。CLI 提供 build、validate、compare、render、explain 和 pending decision template，不提供 approve 或自动应用 decision。

最终本地验证：33 governance schemas、30 governance fixtures、17 sources、physical release、14 pipeline valid、28 pipeline expected-invalid、4 recorded、4 reference adapters、5/26 curation fixtures、159/159 offline Python、22/22 Vitest/RTL、lint、strict typecheck、production build、4 files/286,923 bytes、repository/build/public/private-label/arms/no-media/no-live-CI scans，全部 pass。

## 11. 公开边界与 Pages

候选姓名、QID、ULAN、作品清单、relation leads、scenario、recommended slate、decision、raw、review bundle 和媒体均未被 Git 跟踪，也未进入 `public` / `dist`。公开报告只含方法与非姓名化统计。门户仍是七馆；美术馆仍为空序厅；武器馆仍不可点击；无第三方 runtime 或媒体。

部署 workflow 与在线首页、Art、About、Accessibility、console、failed requests、404 和 candidate leakage 的最终证据记录于 `docs/qa/museum-03a/pages-regression.md`。

## 12. 对抗性审查 A–E 与修订

- A：识别一个权威身份记录内部生卒冲突；候选退回研究队列并重放合格池 identity raw。
- B：修订场景，使 12/6 traditions/4 periods/3 women/11 media/8 clear-path 闭合；保留 8 个小配额理由与 8 个带损益备选。
- C：429 后 fail closed；IIIF/image URL/public-domain flag 不作许可；metadata/media 分离且无媒体下载。
- D：保留失败/中断工件，final raw 不同 bytes fail closed；v5 修正日志计数并通过 bundle closure。
- E：Git/public/dist/private-label/arms/no-media/no-live-CI 扫描通过；门户不变。

全部 P0–P2 已解决；上述 P3 有 owner、影响、复核阶段和当前缓解。

## 13. Git、未决事项与 handoff

实施 commit 为 `55c83900dcfc6c0bf6fb9a02a0c9dffef91337e4`，已推送 `main`；GitHub Actions run `29202030756` 的 build 与 deploy 均 success。线上 4 个资源全部 HTTP 200；首页、Art、About、Accessibility 回归通过；console errors/warnings、failed/404 requests、candidate label leakage 与第三方媒体均为 0。不改写历史、不 force push。

`OD-004` 和 `OD-007` 均保持 open，项目 open decisions 数量仍为 10；没有关闭其他决定。

MUSEUM-03A 已达到 `completed/pass`，确认包可供用户决策。只有用户明确选择 12 人/替换与公开媒体策略后，才可另行授权 MUSEUM-03B；本阶段没有该授权。
