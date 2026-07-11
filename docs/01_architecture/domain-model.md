# 领域模型

## 通用核心

| 概念 | 职责 | 核心不变量 |
|---|---|---|
| Entity | 稳定描述“什么对象” | 稳定 ID、类型、版本、生命周期；名称可多语 |
| Relationship | 命名、带方向和语境的实体连接 | 类型、端点、范围、证据等级、四类独立度量、展示政策 |
| Claim | 可验证的原子命题 | 状态、证据、反证、审核与历史不可缺失 |
| Evidence | 对 Claim 的支持/反驳材料与精确定位 | 至少一个 Source；区分引文、记录、图像、数据分析等 |
| Source | 来源身份与访问/许可事实 | URL、访问日、Tier；元数据和媒体许可分开 |
| Place | 规范地点和几何/时间适用性 | 不把现代边界投射为永久事实 |
| Time Span | 起止、精度、历法/不确定性 | 模糊日期不伪装成日级精度 |
| Media Asset | 可展示或开发引用的媒体记录 | 逐资产权利、归属、许可范围和到期时间 |
| Exhibition | 经策展选择的对象和叙事 | 引用固定数据版本与展签 Claim |
| Exploration Path | 可解释的节点/边序列 | 记录允许边型、过滤器和算法版本 |
| Interactive Module | 互动能力及适用条件 | 内容/素材/权利/无障碍门槛全部满足才启用 |
| Dataset Release | 不可变发布集合 | semver、schema 版本、hash、来源时间、构建版本与状态 |

通用实体类型包括 `museum_branch`、`person`、`organization`、`place`、`time_period`、`event`、`concept`、`source`、`claim`、`evidence`、`media_asset`、`exhibition`、`interactive_module`、`dataset_release`。

## 美术馆扩展

`artist`、`artwork`、`art_movement`、`art_group`、`technique`、`material`、`genre`、`subject`、`collection`、`museum_institution`、`exhibition_event`、`art_historical_period`。

### 创作者身份

- `artist` 仅表示身份已解析且死亡已确认的个人；正式发布需可靠出生/死亡 Claim。
- 匿名作者、工作室、群体、传统归属和“可能为”不伪造成个人。`artwork.creator_attributions` 记录 `anonymous / workshop_of / circle_of / attributed_to / formerly_attributed_to / collective / unknown`，并链接相应实体或受控描述。
- 同名、别名和不同文字系统通过 canonical ID、BCP 47 labels、外部身份 ID 和合并提案处理。自动相似只可生成 merge candidate。

## 生物馆扩展

`taxon`、`species`、`habitat`、`ecoregion`、`ecosystem`、`biological_interaction`、`behavior`、`life_stage`、`conservation_status`、`observation_record`。

观测记录、物种分布 Claim、稳定栖息地和保护状态是不同对象：单次观测不能自动升级为长期分布；保护状态必须绑定评估机构、版本、范围与日期。生态关系具有参与者角色、生命周期/季节、地点和证据范围；不压缩成单一线性食物链。

## 聚合与引用

- Entity 是身份聚合根；可删除展示投影但不删除已引用 canonical ID。
- Claim 独立版本化，并通过 Evidence 引用 Source。实体常用字段是经过验证 Claim 的可重建投影。
- Relationship 是一个或多个关系 Claim 的策展/计算投影；它不能提升底层 Claim 状态。
- Dataset Release 按 ID 固定所有记录版本和撤回集，不接受可变“latest”作为可复现引用。

关系端点按谓词约束：`member_of` 是 `artist → art_group/organization`，`associated_with_movement` 是 `artist → art_movement`；艺术家之间的共展、共享赞助人/机构/题材/技法/材料边必须携带相应 `context_entity_ids`。作品的 confirmed/attributed/workshop 等归属必须链接 artist，collective 链接 group/organization，anonymous/traditional/unknown 不伪造个人端点。

## 生命周期

实体/关系/媒体可处于 `candidate / reviewed / publishable / published / disputed / deprecated / withdrawn` 的适用子集。`deprecated` 表示有替代但保留历史；`withdrawn` 表示不得继续公开分发，并需发布撤回说明。删除只适用于从未发布且无审计价值的错误临时对象。
