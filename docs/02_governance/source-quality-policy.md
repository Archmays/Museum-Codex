# 来源质量政策

## 目的

来源 Tier 表示其对特定 Claim 的适用性，不是机构声望总分。同一聚合平台中的具体记录可能因原始提供者、版本、引用和许可而不同。任何 Tier 都不能替代精确引用定位。

## 分层

| Tier | 定义 | 可承担 | 不可单独承担 |
|---|---|---|---|
| 1 | 官方馆藏/档案/身份控制、第一手文献、catalogue raisonné、正式科学数据库、同行评审研究、官方标准 | 身份、馆藏事实、直接记录、特定评估；仍受范围限制 | 超出机构职责或记录范围的解释 |
| 2 | 大学项目、学术出版社、策展研究、专业学会、可靠专著及保留原始链的高质量聚合 | 历史语境、学术解释、交叉核验 | 缺乏直接依据的确定师承/影响 |
| 3 | Wikidata、Wikipedia、Commons、Europeana 等开放发现层 | 候选、多语名、外部 ID、待核验线索 | 争议归属、直接影响、重要历史判断、死亡状态的唯一证明 |
| 4 | 普通博客、无作者/来源页、聚合转载、社媒、来源不明图片、自动生成内容 | 待核验队列 | 任何正式发布事实或媒体许可结论 |

## 评估维度

登记者分别评估：生产者权限、与 Claim 的直接性、可引用稳定性、版本/日期、方法透明度、引用链、独立性、字段完整性和许可清晰度。聚合记录回溯到原始馆方/研究后，Evidence 可引用原始来源；不能把聚合平台整体自动升级。

## 使用规则

- 直接影响、作者身份、死亡状态、作品归属、保护状态等高风险 Claim 需要适当 Tier 1/2；Tier 3 只能发现候选。
- 多个互相复制的页面是一条来源链，不是独立佐证。
- 机器可读字段与网页叙述冲突时同时保留，创建冲突 Claim 并请求审核。
- 未公开限速写 `not stated`，不解释为无限；不一致条款写 `conflicting documentation`。
- 每次核验记录官方 URL、访问日、页面/数据版本、内容 hash 或存档定位。来源变化不覆写旧 Evidence。
- 每条来源许可用 `content_class + applies_to` 规则表达 metadata/data/media、endpoint、字段、对象或 JSON Pointer 范围，并强制 `no_inheritance=true`；没有匹配规则即 unknown，不能继承父页面或 API 的开放许可。AIC `description` 等字段级例外必须独立成规则。

## 当前来源的特殊门槛

- Wikimedia/Wikidata/Europeana 默认 Tier 3，馆方 provenance 可回到 Tier 1。
- GBIF 基础设施为 Tier 1，但 occurrence 的证明力取决于发布者、basisOfRecord 与识别质量；单次记录不证明稳定分布。
- GloBI 是关系发现/交叉核验层；行为动画必须回溯原始研究。
- IUCN 评估事实为 Tier 1，但再发布权利受专门条款约束，证据质量与发布许可必须分开判断。
- Catalogue of Life Base 可作 Tier 1 分类框架；程序合并的 XR 记录保留 `merged` 与上游来源并复核。

## 复核周期

许可/条款与 API 文档至少每 12 个月、重大来源变更或每个公开 release 前复核；高变化 API 适配器每次运行做 contract check。过期不自动等于错误，但阻止新增资产发布直至复核。

`source-comparison-matrix.csv` 是研究摘要；`source-license-rules.json` 是字段/对象范围的机器规则。真正进入 release 的 Source 记录还必须明确 public static redistribution、derivative/commercial use、permission status/reference/scope、条款版本/核验日/复核期限；IUCN 等来源默认 prohibited/pending，直到书面许可被记录并覆盖 Pages、公开教育和地域。

每条规则还有由 `source_id + content_class + applies_to hash` 派生的稳定 `rule_id`；canonical 规则文件的 SHA-256 固定在 `minimum-source-set.json`。Release Source 必须记录 `registry_source_id`、完整规则数组及 `license_rules_snapshot_hash`，消费记录逐条绑定选中的 rule ID。Tier 4、未来日期、超过 366 天的复核窗口、已撤销许可或有限许可供无限期 release 使用均自动失败。

Binding 同时记录实际 `scope_locator` 并与 Evidence locator/对象 URL 共同审核。每条规则强制包含可执行 `scope_match`（规范化模式、正则、允许 scheme、精确 host、相对路径策略）；URL path 在匹配前反复 percent-decode 到稳定值，防止编码绕过。绝对 URL 只能使用列出的 HTTPS 官方 host，伪后缀、scheme-relative、`file:` 或其他来源均失败。AIC `/api/v1/artworks/description` 只能选择专用 CC BY rule；默认 artwork 字段规则、其他 endpoint 和单/双编码 description 均不能误匹配。未来新增字段级例外时必须先增加可执行匹配契约与反例 fixture，不能只补自然语言说明。

## 来源身份与字段查询闭包

- Canonical Source 不只锁定许可规则，还必须锁定 `registry_identity`：官方名称、官方 host 与来源矩阵快照 hash 三者同时匹配；把真实 `registry_source_id` 套到镜像站、同形域名或不同发布者会阻断发布。
- `minimum-source-set.json` 同时固定来源矩阵与许可规则注册表的 SHA-256。矩阵、规则或 Source 身份任一变化，都必须生成新快照并重新审核，不能沿用旧 release 声明。
- AIC artwork detail/search API 的字段许可由真实 endpoint 与 `fields` 查询参数共同决定。Binding 的 `scope_fields` 必须与解码后的查询字段集合完全一致；缺少 `fields`、隐藏或多重编码 `description`、未知 endpoint、非 HTTPS 或非官方 host 均 fail closed。
- Source snapshot 必须逐条复制并核对 `registry_identity`、规则数组与规则 hash，避免构建阶段把已核验身份替换为同路径的第三方响应。
