# 武器博物馆知识模型 Outline

## 状态与边界

本文件只描述未来模型候选，不实现 `arms` concrete schema，不创建正式器物 fixture 或 dataset release。`schemas/common/entity.schema.json` 只登记合法 `branch_id=arms`；任何实际 arms 记录在 `MUSEUM-ARMS-00` 完成前必须由 canonical dispatch fail-closed。

模型沿用 Entity → Claim → Evidence → Source、争议并存、逐字段 provenance、来源独立性、人工审核、版本化发布和可撤回规则。现代分类不能无证据地投射到古代或跨文化器物。

## 候选实体

| 实体 | 目的与边界 |
|---|---|
| `arms_artifact` | 武器类馆藏器物；身份、年代、材料、来源和状态均由 Claim 支持 |
| `armor_artifact` | 甲胄与身体防护器物，不等同于通用防御概念 |
| `weapon_type` | 历史/策展分类；记录词表、适用文化与争议，不宣称跨文化普适 |
| `defensive_equipment` | 盾、防护构件及其他防御装备的策展实体 |
| `maker` | 已解析的个人、组织或传统身份；匿名、作坊和群体不伪造成个人 |
| `manufacturing_tradition` | 一般工艺传统与地域/时期范围，不保存可执行制造参数 |
| `material` | 材料身份、一般性质与保护风险 |
| `mechanism_principle` | 高层次历史/物理原理；不得含操作、优化或可复现工程数据 |
| `provenance_event` | 所有权、保管、掠夺、交易、返还与争议事件 |
| `collection_event` | 入藏、转藏、借展、编目与去藏事件 |
| `conservation_event` | 检查、稳定化、修复和保护事件；公开投影保持非操作性 |
| `conflict_context` | 具体冲突的时间、地点、参与者与人类影响语境 |
| `legal_context` | 法律、条约、监管、裁军与限制的时地适用范围 |
| `ritual_or_symbolic_context` | 礼仪、身份、宗教、纪念、表演和象征语境 |
| `human_impact_context` | 伤亡、平民影响、殖民、压迫、暴力记忆与社会后果 |

## 候选关系

| 关系 | 约束 |
|---|---|
| `made_by` | maker 身份与 attribution 状态可争议 |
| `made_in` | 地点与历史边界需注明精度 |
| `made_during` | 时间段、精度、历法与不确定性可见 |
| `uses_material` | 材料识别与检测/来源证据分开 |
| `uses_high_level_mechanism` | 只解释高层次原理，不导出操作建议 |
| `derived_from_typology` | 表示策展/学术分类来源，不等于直系技术影响 |
| `historically_countered_by` | 只在历史证据和具体语境下表达攻防共演化，不表示现实优劣 |
| `associated_with_conflict` | 连接具体冲突语境及其人类影响 |
| `used_ceremonially_in` | 区分礼仪、象征、表演和实际使用 |
| `held_by_institution` | 记录馆藏身份、时间范围和公开对象页 |
| `transferred_in` | 连接来源/所有权变更事件及争议 |
| `excavated_at` | 连接考古地点、发掘记录、许可与语境 |
| `restored_in` | 连接保护事件；公开说明保持非操作性 |
| `formerly_attributed_to` | 保留历史归属和修订，不覆盖旧说 |
| `depicted_in` | 连接图像/文本中的描绘，不自动把器物转成美术馆作品 |
| `regulated_by` | 绑定法律适用时间、地点、版本和状态 |
| `contextualized_by_human_impact` | 强制将器物与平民、伤亡、压迫、纪念或裁军语境相连 |

## Claim、证据与争议

- 每条关系是一个或多个可审核 Claim 的投影，不能提升底层 Claim 状态；
- Evidence 精确指向 Source、对象记录和定位；同一上游的复制记录不计为独立来源；
- 相互冲突的年代、制造者、分类、用途、来源和归还主张并列保存；
- 计算相似、类型相近、策展比较和直接历史关系保持独立语义；
- 个人、作坊、集体、传统归属、匿名与不确定 attribution 不互相静默转换；
- 每项公开记录保留审核者、日期、状态历史、替代/撤回关系和版本。

## 禁止字段与推导

不得加入或推导：

- `best_target`
- `lethality_score`
- `optimal_range`
- `penetration_optimization`
- `build_steps`
- `modification_instructions`
- `supplier`
- `market_price`
- 可执行尺寸、容差、配方、加工参数、操作步骤、采购路径、人体弱点、现实战术或其他面向现实使用和优化的字段。

一般材料、工艺、机制、保存与修复信息也必须通过非操作化公开投影，不能因为底层研究资料更详细而原样发布。

## 未来 schema 门槛

`MUSEUM-ARMS-00` 必须在实现 concrete schema 前确定：实体/ID 前缀、受控词表、年代与跨文化分类边界、现代武器分级、敏感内容字段、审核角色、关系端点、Claim/Evidence/Source 闭包、权利字段、fixtures、canonical dispatch 和 physical release closure。没有这些门槛时，common entity fallback 永远不是合法替代。
