# 美术馆来源注册表

核验日期：`2026-07-11`。完整可机读比较见 `source-comparison-matrix.csv`。所有来源仅用于构建期采集；正式站点读取审核后的版本化快照。

## Tier 1 身份、馆藏与机构来源

### Getty Vocabularies / ULAN

- 官方：[ULAN](https://www.getty.edu/research/tools/vocabularies/ulan/)；[获取方式与许可](https://www.getty.edu/research/tools/vocabularies/obtain/)
- 用途：稳定 ULAN ID、多语名称/别名、角色和生卒线索；不证明作品归属或艺术影响。
- 接口：SPARQL、OpenRefine、N-Triples 和单记录 RDF/JSON-LD，无 key，限速未声明。元数据为 ODC Attribution 1.0；无作品图像。
- 风险：旧 XML/关系表/XML Web Services 已停止，适配器必须面向当前接口并做 contract test。

### 馆藏开放数据

| 来源 | 获取/限制 | 元数据 | 媒体 | 特别风险 |
|---|---|---|---|---|
| [The Met](https://metmuseum.github.io/) | REST/CSV；无 key；≤80 req/s | CC0 | 仅明确 OA/CC0 公版对象 | `primaryImage` 不等于 OA；见[开放政策](https://www.metmuseum.org/hubs/open-access) |
| [Smithsonian](https://www.si.edu/openaccess/devtools) | api.data.gov key 或 S3 bulk | CC0 OA/基础元数据 | 仅显式 CC0 | [bulk GitHub](https://github.com/Smithsonian/OpenAccess) 已于 2026-05-21 归档并迁 S3；平台默认限额非馆方保证 |
| [Rijksmuseum](https://data.rijksmuseum.nl/) | Search/PID/OAI/LDES/IIIF/dumps；无 key | 逐记录 PDM/CC0/CC BY | 逐对象 | 2026-06-29 canonical PID/redirect 变更，OAI-PMH 可能 breaking change；见[政策](https://data.rijksmuseum.nl/policy/information-and-data-policy) |
| [NGA Washington](https://github.com/NationalGalleryOfArt/opendata) | 官方 CSV | CC0 | 数据集不含图像许可；对象页明确 OA 图为 CC0 | CSV image URL 不是许可证明；见[政策](https://www.nga.gov/terms-and-notices) |
| [Art Institute of Chicago](https://api.artic.edu/docs/) | REST/dump/IIIF；60/min；抓取≤1/s | artwork `description` 为 CC BY 4.0，其余 artwork data CC0；其他 endpoint 不同 | 仅 `CC0 Public Domain Designation` | IIIF 可返回非公版图像；字段级而非全 API 单一许可；见[条款](https://www.artic.edu/terms) |
| [Cleveland Museum of Art](https://www.clevelandart.org/open-access-api) | REST/dumps；无 key；数字限速未声明 | CC0 | 仅 `share_license_status=CC0` | 更新频率文档不一致，保存 retrieved_at/hash；见[条款](https://www.clevelandart.org/terms-and-conditions) |

这些机构对自身馆藏事实建议 Tier 1，但每个 Claim 仍受机构职责和记录范围限制。

## Tier 3 发现与聚合

### Wikidata

[数据访问](https://www.wikidata.org/wiki/Wikidata:Data_access)；[许可](https://www.wikidata.org/wiki/Wikidata:Licensing)；[Wikimedia API 限额](https://www.mediawiki.org/wiki/Wikimedia_APIs/Rate_limits)。结构化主数据 CC0，读取无 key。2026 平台限额为未识别 10/min、合规标识客户端 200/min、成熟认证用户 2,000/min，建议最多 3 并发；WDQS 独立数字额度未声明。只用于候选、多语名、外部 ID 和关系线索。

### Wikimedia Commons

[外部复用指南](https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia)；[许可说明](https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia/licenses)。结构化文件数据 CC0，但图像/音视频逐文件许可，常见 PD/CC0/CC BY/CC BY-SA/GFDL；保存文件页、作者、许可版本、署名与改动。上传者判断并非保证，仍检查人格、隐私、商标和文化敏感风险。

### Europeana

[API](https://pro.europeana.eu/page/apis)；[API key](https://pro.europeana.eu/page/get-api)；[元数据指南](https://www.europeana.eu/eu/rights/usage-guidelines-for-metadata)；[条款](https://www.europeana.eu/eu/rights/terms-of-use)。聚合元数据 CC0；媒体/缩略图/IIIF 必须读取对象级 `edm:rights`。除 SPARQL 外通常需免费 key。数字限速未公布，FAQ 与 project key 页对请求率表述不一致，批量前确认。

## 共同行动

适配器保存请求（脱敏）、fetched_at、响应 hash、source object ID、字段级/对象级许可和条款核验日。Tier 3 发现的死亡、归属、直接影响和争议信息必须回到 Tier 1/2。任何可访问图片、IIIF manifest 或 URL 在 rights review 前均为 `unknown` 或 `development_only`。

## MUSEUM-02 追加复核（2026-07-12）

四个参考来源的官方 endpoint、许可、限速和字段语义已再次核验，并固化到 `pipeline-endpoint-registry.json`。许可语义与 2026-07-11 canonical rules 一致，因此未改写 `source-license-rules.json` 或其 snapshot hash。技术变化是 Getty ULAN 当前 per-record JSON 返回 compacted Linked Art JSON-LD object；adapter 0.1.1 显式支持该形态，同时继续阻断旧 XML/Web Service 无声 fallback。Wikidata、The Met 与 AIC 当前接口与既有许可分层一致；AIC `description` 的 CC BY 4.0 和其余 artwork data 的 CC0 仍必须按 exact fields 分开。
