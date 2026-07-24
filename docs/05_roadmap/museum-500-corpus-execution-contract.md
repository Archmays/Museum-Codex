---
phase_id: MUSEUM-09G-K-FINAL-CORPUS
contract_status: approved_for_local_execution_after_web_closeout
source_web_phase: MUSEUM-500-KG-WEB-00
source_remote_main_before_web_docs: 0e6e45f9564f93a0530160259e285e5f5341793e
input_release_id: release:art-expansion-batch-05-1.9.0
planned_final_release_id: release:art-final-corpus-2.5.0
current_artist_count: 258
current_artwork_count: 2471
target_artist_count: 500
target_artwork_count: 5000
relationship_rebuild_in_this_phase: false
single_main: true
branch_worktree_pr_allowed: false
arms_museum_authorized: false
---

# Museum 500/5,000最终语料执行合同

## 1. 合同目的

本合同规定在重构艺术关系知识图谱之前，先完成美术馆既定内容总体：500位已故艺术家与5,000件作品。关系图谱的3.0.0重构不与本阶段混写；本阶段只保留现有关系页面、路径、地图和搜索的无回归合同，并为后续知识图谱研究保留稳定ID、来源、地点、事件和作品上下文。

## 2. 已核验基线

当前公开真源：

- release：`release:art-expansion-batch-05-1.9.0`
- artists：258
- artworks：2,471
- Gallery：71
- Collection：187
- relationships：60，全部为C级策展比较
- place-time episodes：400
- tours：18
- Batch 01–05：published
- Batch 06–10：未进入
- MUSEUM-10A：未进入
- arms museum：未进入
- OD-011：open

## 3. 目标总体闭合

现有M09批次计划定义：

`44 legacy works + 121 legacy supplement + 4,835 new-artist batch works = 5,000 works`

艺术家总体：

`12 legacy artists + 488 new target artists = 500 artists`

剩余工作：

| 事务 | 新艺术家 | 新作品 |
|---|---:|---:|
| Batch 06 | 49 | 484 |
| Batch 07 | 49 | 483 |
| Batch 08 | 48 | 480 |
| Batch 09 | 48 | 481 |
| Batch 10 | 48 | 480 |
| Legacy supplement | 0 | 121 |
| 合计 | 242 | 2,529 |

最终硬目标：

- artists=500
- artworks=5,000
- Gallery=125
- Collection=375

每批Gallery/Collection、stable IDs、source set、coverage、closure hash和reserve顺序必须从同步后的canonical registry读取；不得依据本文件手工重排。

## 4. Release链

建议形成不可变链：

1. Batch06 → `release:art-expansion-batch-06-2.0.0`
2. Batch07 → `release:art-expansion-batch-07-2.1.0`
3. Batch08 → `release:art-expansion-batch-08-2.2.0`
4. Batch09 → `release:art-expansion-batch-09-2.3.0`
5. Batch10 → `release:art-expansion-batch-10-2.4.0`
6. Legacy supplement + final stabilization → `release:art-final-corpus-2.5.0`

2.0.0–2.4.0必须是tracked、immutable、可hash-only验证和rollback的中间release，但deployment=0。只有2.5.0在全部事务和500/5,000总体门禁通过后成为current并部署一次。

## 5. Factory V3要求

在Factory V2基础上新增：

- 五个batch顺序调度；
- `legacy_supplement`事务类型；
- `final_stabilization`事务类型；
- release plan驱动，不硬编码batch或版本；
- dry-run、resume、from-transaction、from-stage；
- journal和per-stage checkpoint；
- 已提交事务的hash-only复用；
- current release延迟切换；
- intermediate deployment显式拒绝；
-跨全部历史包的artist/work/source/media SHA去重；
- 500/5,000最终整体validator；
- Batch11和未授权ID fail closed。

始终只有一个canonical writer、registry writer、release writer、ledger writer、Git owner和deployment owner。

## 6. Batch 06–10每批事务

每批顺序执行：

1. 输入closure和source drift；
2. artist identity/deceased/non-person/dedupe；
3. artwork attribution/title/date/material/institution/source；
4. Claim → Evidence → Source；
5. child-facing `public_intro`、`look_for`、`evidence_boundary`；
6. contexts和place-time；
7. object-level media decision；
8. original content-address reuse或受控采集；
9. faithful derivatives；
10. candidate/media/release deterministic double build；
11. batch registry单调状态推进。

硬门禁：living、unknown-death、non-person、duplicate artist/work、attribution conflict均为0；无法保持固定数量和coverage时标记partial/blocked，不发布。

## 7. Legacy supplement事务

121件作品属于既有12位legacy艺术家。必须建立独立、不可变的：

- supplement assignment snapshot；
- formal artwork candidate；
- object-level media decisions；
- supplement media bundle；
- duplicate/attribution/source closure；
- gallery sequence proposal；
- withdrawal/replacement mapping。

不得：

- 改写既有艺术家身份、出生/死亡、主介绍或已发布作品；
- 为补作品自动改写18条正式tour；
- 重复当前作品；
- 把馆藏机构推断为创作地点；
- 为无图作品制造图像。

## 8. 关系图谱边界

本阶段明确**不执行MUSEUM-10A关系知识图谱重构**。

只要求：

- 当前focused relation explorer不退化；
- 默认全局图仍为0节点；
- 不恢复全局圆环或500节点大图；
- 现有60条C级策展比较保持语义与证据；
- 不为新艺术家自动制造关系；
- 可在candidate中保存未来关系研究线索，但不得公开为正式边；
- stable IDs、作品、contexts、episodes、sources为后续KG提供输入；
- 3.0.0产品规范在本阶段不得提前以半成品形式部署。

## 9. 500/5,000最终稳定化

最终2.5.0必须闭合：

- 500/500 artist identities；
- 5,000/5,000 artwork routes；
- Gallery125/Collection375；
- 500份自然英中儿童介绍；
- 5,000作品search/compare/print/source/rights/no-image等价；
- cross-batch artist/work/slug/alias/source/media dedupe；
- withdrawal和rollback；
- search分片与首次查询预算；
- artist index分页和筛选；
- map/timeline/list；
- current relation explorer和paths无回归；
- tours仍为18，除非有另行正式授权和完整证据；
- candidate leakage=0；
- public originals=0；
- historical rebuild=0。

## 10. 测试和部署

开发期：

- targeted waves；
- local full=0；
- 失败只重跑受影响项和依赖闭包；
- 历史release只验hash。

最终：

- 原则上一个accepted clean GitHub final-full；
- 全Python、frontend、Playwright；
- 500/5,000 corpus validators；
- source/rights/security/privacy/leakage；
- production build和performance；
- 只部署2.5.0一次；
- online byte closure；
- online functional smoke；
- closeout `[skip ci]`且deployment=0。

## 11. 完成后的下一步

2.5.0线上闭合后，不直接让Codex开发最终关系UI。先进入：

`MUSEUM-10A-RELATION-KG-WEB-01`

由ChatGPT网页端基于实际500位艺术家执行关系缺口、来源和代表性问题审计；之后本地Codex制作不部署的关系知识图谱候选，供用户人工审阅。

## 12. 阶段边界

本合同授权500/5,000总体封板，不授权：

- MUSEUM-10A正式实现或部署；
- 关系3.0.0提前上线；
- 武器馆；
- 关闭OD-011；
- branch/worktree/PR；
- Git历史改写。
