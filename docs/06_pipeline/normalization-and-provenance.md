# 规范化、Claim–Evidence–Source 与 provenance

Raw source record 与 normalized candidate 是两层对象。Candidate 永远为 `review_state=candidate`、`publishable=false`；它不是确认艺术家、正式作品或 release record。

## Field provenance

每个映射字段记录 candidate/field pointer、source/source object、raw snapshot、原始 locator/value、normalized value、transform ID/version/warnings、canonical source tier、实际 license rule/content class、language/script、observed_at、inferred 和 review state。validator 将 rule ID 回解到 canonical registry，并核对来源、内容类别、tier 与 AIC 字段 selector。

名称用 NFC 和空白规范化但保留 original text；preferred/alternate/historical/transliteration 分开，语言为 BCP 47 或 `und`。名称不生成跨来源最终 ID，同名不触发 merge。

日期保留 source display，明确 exact/year/range、precision、circa、uncertain 和 calendar。年份不会伪装成日级精度；出生晚于死亡或来源间明显冲突形成 hard conflict。本阶段 candidate death 不变成 `confirmed_deceased`。

## Candidate Claim / Evidence / Source

Adapter 可创建 candidate Claim；Evidence 必须精确指向 raw snapshot + locator，Source 使用 canonical registry identity。Tier 3 Wikidata claim 保持 candidate；rank、qualifier/reference 是否存在随 source assertion metadata 保留。算法推断必须 `inferred=true` 并写算法/规则版本。反证与冲突并列保存，不用空值覆盖旧观察。

来源 relationship 只可保留为 source assertion/quarantine，不生成 `artist-relationship`，更不能把来源关系或计算相似度描述为历史影响。

## Drift 与媒体

未知上游字段进入 quarantine 或 contract drift；新 root field、必需字段缺失与字段类型改变 fail closed。Met constituents 作为作品记录里的独立 source assertions 保留，不因 creator display 自动建立艺术家身份。

媒体只保存 URL/identifier、raw locator、rights hints 与 canonical media rule。全部强制 `rights_status=unknown`、`development_only=true`、`publish_status=blocked`、`bytes_downloaded=false`。父记录的 CC0、OA 标志、图片 URL 或 IIIF 可达性不传播为媒体许可。
