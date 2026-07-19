# 全球艺术家扩展章程

## 阶段身份

MUSEUM-09A 建立真实、可审计、非公开的全球艺术家扩展总体。它已经开始真实内容扩展，但没有开始正式公开扩展；500 位目标艺术家和 5,000 件目标作品只是后续执行计划的内部总体。

本阶段输入固定为 `release:art-v1-candidate-1.4.0`。现有 12 位艺术家、44 件作品和全部历史 release 只读复用，不重建、不改写。MUSEUM-09B、武器馆、Pages 发布及 OD-011 决策均不在本阶段范围内。

## 能力缺口

| 分类 | 能力或资产 | MUSEUM-09A 处理 |
|---|---|---|
| 可直接复用 | M03B 的 12/44 身份与作品基线、Claim → Evidence → Source、stable ID、状态历史 | 作为 legacy baseline 精确纳入，不重做 |
| 可直接复用 | M08 changed-path classifier、release integrity ledger、候选泄漏扫描、规模与分片架构 | 用于 phase-scoped 运行、历史 release hash-only 和 public 边界证明 |
| M09A 必须增量扩展 | 多来源真实人物发现、跨源身份归一、已故硬门禁、作品映射、代表性矩阵 | 新增单一确定性写入器、四份 schema、审计包和验证器 |
| M09A 必须增量扩展 | 精确 500/5,000 总体、100+ reserve、10 批注册、首批建议 | 新增治理注册与不可公开的候选包 |
| 不应修改 | `public/`、当前 candidate release、历史 release、运行时、Pages、已有媒体 | 保持字节和 hash 不变 |
| 留给 M09B | 首批 50 位艺术家的深度研究、逐对象媒体可行性与权利决策、公开候选构建 | 只提供 `recommended_not_started` 输入闭包，不执行 |

## 硬门禁

`program_target` 必须同时满足：

1. 记录表示一位可识别的个人；
2. 官方来源明确支持其已故状态和死亡年份；
3. 至少一个非 Wikidata 的正式来源身份；
4. 至少三件可解析到官方对象记录的目标作品；
5. 无未闭合身份或归属冲突；
6. stable ID、重复簇、证据和来源引用闭合；
7. 选择有确定性的 coverage/readiness reason code。

Living、死亡未知、anonymous、workshop、school、circle、follower、culture、dynasty 和 tradition 不得计入目标人数。Wikidata/QLever 仅可作为发现与交叉索引入口，不能独立把候选提升为目标。

## 选择和证据

正式选择只使用身份与已故硬门禁、来源可验证性、作品映射、coverage contribution、来源多样性、批次可执行性以及 stable ID tie-breaker。禁止重要性、流行度、市场价值、西方经典、机构名气、社交媒体、查询频率或 AI 审美分数。

每项可发布事实仍须保持 Claim → Evidence → Source。区域是有来源依据的研究路由标签，不是国籍、族裔、血缘、价值或历史影响判断；历史影响与计算相似性也不由本阶段推断。

## 产物边界

规范写入器是 `museum_pipeline/art/global_expansion.py`。它从 ignored raw cache 和既有只读基线生成 `data/reviewed/art/museum-09a/global-expansion-universe-v1/`，并同步写入治理批次注册。大型集合沿用确定性分片清单，逐 shard 校验 hash、bytes、count、顺序和物理闭包。生成物必须可确定性复跑、无媒体字节、无 secret/个人信息、无 public 候选标签泄漏，并满足仓库 5 MiB 单文件门禁。

`program_target`、`reserve`、`rejected` 和 `blocked` 都是内部状态。不能证明的候选自动 fail closed；不得进入 `waiting_for_user_review`、`waiting_for_manual_review` 或逐项点击审批状态。
