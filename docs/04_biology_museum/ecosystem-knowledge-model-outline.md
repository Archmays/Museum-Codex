# 生态系统知识模型纲要

## 实体

`taxon/species`、`habitat`、`ecoregion`、`ecosystem`、`behavior`、`life_stage`、`conservation_status`、`observation_record`，以及通用 place/time/source/claim/evidence/media。

## 关系

| 类别 | 示例 | 关键范围 |
|---|---|---|
| 营养 | predation、herbivory、scavenging、decomposition | 参与者角色、life stage、频率、地点/季节 |
| 非营养生物交互 | competition、mutualism、commensalism、parasitism、pollination | 方向、受益/受损角色、证据场景 |
| 空间 | observed_at、reported_range、uses_habitat、endemic_to | observation 与推断层级、几何/日期/精度 |
| 分类 | accepted_name、synonym_of、parent_taxon | 来源 checklist/version、有效期 |
| 保护 | assessed_as、threatened_by、protected_in | assessment/version/date/scope |

`biological_interaction` 是具参与者角色的关系，不是只有 source/target 的无语义边。食物网展示也要保留分解者、环境物质库和关系范围，不能暗示固定、完整网络。

## 证据粒度

一个 occurrence 是一次记录；distribution Claim 是经方法推断的范围；habitat association 需要重复/研究证据；behavior animation 还需说明可观察事件与简化。聚合 API 记录必须保留原始 dataset/study、record ID 和版本。

## 版本和冲突

分类名随 checklist release 解释；不覆写历史记录的 originalNameUsage。保护状态按 assessment ID/version/date 保存。相互矛盾的交互或分布记录并存为 Claims，由适用范围和审核说明解释。
