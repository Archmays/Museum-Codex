# 数据流水线与发布模型

## 流程

`register source → acquire candidate → immutable raw snapshot → normalize → deduplicate/resolve identity → bind Claim/Evidence → rights check → discipline review → release validation → versioned static data → site build`

每一阶段输出新的工件和日志，不原地覆盖上一步。

## 分区与记录

| 阶段 | 必备记录 | 失败处置 |
|---|---|---|
| source registration | 官方 URL、Tier、条款/许可核验日、访问限制 | 未分离元数据/媒体许可则不采集媒体 |
| acquisition | adapter/version、request（脱敏）、HTTP 信息、fetched_at、SHA-256 | 保留失败日志；不回退到非权威镜像 |
| normalization | mapping/schema version、输入 hash、字段变换 | 未知字段隔离，适配器进入变更队列 |
| identity | match signals、冲突、merge proposal、reviewer | 高风险冲突不自动合并 |
| evidence binding | Claim、Evidence 定位、Source | 无证据候选不提升状态 |
| rights | 逐资产许可、归属、允许行为、期限 | unknown/development-only 阻止发布 |
| review | 决策、角色、日期、说明 | 争议保留，不覆盖 |
| release | manifest、全部 hash、schema/build version、predecessor | 任一门禁失败则不生成 publishable release |

## 版本

- schema 使用语义版本；破坏性字段/语义变更提升 major。
- dataset release 使用语义版本：内容修正 patch，兼容新增 minor，消费者契约破坏 major。
- 原始快照以来源、UTC 抓取时间和内容 hash 定址；相同内容仍可记录新的检查事件。
- build version 标识转换代码提交；release manifest 同时记录所有输入 schema 版本。

## 冲突、合并与上游变化

- 对冲突值分别生成 Claim；规范投影只指向当前审核结论。
- 实体合并生成 `merge_record`：survivor、aliases、证据、reviewer、日期、可逆映射。禁止删除被合并 ID。
- 上游字段变化先让 adapter contract test 失败并隔离新快照；不得用空值悄悄覆盖已审核字段。
- 来源过时触发 `reverification_due`，不会自动撤回历史引用；若 URL/条款改变，保留原访问日和存档定位。

## 发布、回滚与撤回

发布构建只读取审核输入和一个固定 release manifest，并以完整物理 bundle 做 fail-closed 验证：每个 included ID 必须唯一解析到正确类型和允许发布状态；Entity/Relationship/Claim/Evidence/Source/Media 引用形成双向闭包；included、withdrawal、deprecation 互斥；每个 POSIX 相对路径留在 release root；实际字节数和 SHA-256 与 manifest 相同；source 条款、媒体授权、第三方 notices 与逐资产 attribution 同时通过。缺文件、空扫描或缺上下文均失败。回滚通过重新指向上一不可变 release 完成，并记录原因。

撤回不是 Git 历史删除：新 release 的结构化 withdrawal 记录列出 ID、原因类别、`effective_at`、`scope`、replacement（可选）和 `public_notice`；它不能与 included/deprecation 集合重叠。站点不再分发受限资产。若法律或安全要求删除字节，执行专门响应流程，同时保留最小非敏感审计记录。

## GitHub Pages 容错

运行时不请求权威 API。JSON/GeoJSON、搜索索引和获准衍生图按内容 hash 缓存；失败时可回到 release 内的文本目录与错误状态。服务工作者/离线缓存不是 MVP 必需，只有缓存失效和撤回传播策略明确后才启用。

## 物理 release 契约

物理目录的文件集合必须精确等于 `manifest.json + manifest_files`，未登记文件同样使构建失败。每条数据记录的 `entity_type + branch_id + ID prefix` 被分派到 canonical concrete schema，输入不得自行降级到 common 基础 schema。单一 schema 数据文件须在 manifest 声明该 schema；混合数据文件声明 `schema_path=null`，但其中每条记录仍逐条分派。

Release 除数据文件外必须闭合：Source 规则快照、许可决策快照、第三方 notices、逐媒体 attribution，以及所有自托管媒体字节。每个 artifact 具有独立 schema、字节数、SHA-256 和精确 record ID 集合；`content_hash` 覆盖完整 manifest 文件集合。Source/Media 授权或审核日期不得在未来、不得超过复核窗口；有限授权要求 `public_until` 不晚于到期日，无限期 release 不能消费有限授权。

`schema_versions` 不是自报说明：它必须与本次数据记录和 artifact 实际消费的 canonical schema 集合及 `schema-manifest.json` 版本精确一致，缺项、多项或伪报版本均失败。任何带 `review_status` 的 publishable entity（包括 artwork/taxon）都必须同时达到 publishable/published review 状态。
