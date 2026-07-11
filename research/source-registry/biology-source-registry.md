# 生物馆来源注册表

核验日期：`2026-07-11`。本文件建立 MUSEUM-BIO-00 的研究边界，不授权采集或公开发布。

## 分类与观测

### Catalogue of Life

[元数据](https://www.catalogueoflife.org/data/metadata)；[下载](https://www.catalogueoflife.org/data/download)；[API](https://api.catalogueoflife.org/)。当前核验发行版 `COL26.6 XR`（2026-06-19，DOI `10.48580/dgy8b`），Base 为 2026-06-12；CC BY 4.0。公开 GET/完整 release 无 key，部分 ChecklistBank 下载需 GBIF 账户，限速未声明。Base 可作 Tier 1 分类框架；XR 的程序合并记录保留 `merged`、上游和 release。

### GBIF

[API](https://techdocs.gbif.org/en/openapi/)；[数据使用条款](https://www.gbif.org/terms/data-user)；[批量下载](https://techdocs.gbif.org/en/data-use/api-downloads)；[媒体](https://techdocs.gbif.org/en/data-publishing/multimedia-publishing)。查询多数无认证，异步 DOI 下载需账户；页面最多 300，`offset+limit` 最大 100,000，动态限流返回 429。数据/记录为 CC0、CC BY 或 CC BY-NC；媒体许可独立且可能更严格。GBIF 是 Tier 1 基础设施，但单条 occurrence 的证明力依发布者/记录质量而定，不能自动成为稳定分布。

### NHM London Data Portal

[下载/API](https://data.nhm.ac.uk/about/download)；[条款](https://data.nhm.ac.uk/terms-conditions)；[馆藏标本集](https://data.nhm.ac.uk/dataset/collection-specimens)。CKAN/API 多数无 key，要求缓存、User-Agent 且低于 5 req/s。数据集 metadata CC0；核心标本数据 CC0、标本图片 CC BY 4.0，但其他数据集逐项许可，`License not specified` 必须阻断。

## 生态、关系与解释

### Encyclopedia of Life

[Data Services](https://eol.org/docs/what-is-eol/data-services)；[API terms](https://eol.org/docs/what-is-eol/terms-of-use-for-eol-application-programming-interfaces)；[版权政策](https://eol.org/docs/what-is-eol/copyright-and-linking-policy)。Classic/Structured API、TSV 和 Zenodo bulk；注册/key 要求依接口，数字限速未声明。页面包含多种对象级 CC/PD 许可，Overview 自动摘要 CC0 不能覆盖其他对象。回溯到提供者时 Tier 2，否则 Tier 3。

### GloBI

[数据](https://www.globalbioticinteractions.org/data)；[How-to](https://www.globalbioticinteractions.org/how-to)；[官方仓库](https://github.com/globalbioticinteractions/globalbioticinteractions)。无 key API 与多格式快照；稳定研究引用用 Zenodo DOI `10.5281/zenodo.3950589`。集成数据通常 CC BY 4.0。作为 Tier 2 关系发现/交叉核验，动画仍需回到原始研究；实时索引变化且标准化名称可能不同于原记录。

### RESOLVE Ecoregions 2017

[官方数据](https://ecoregions.appspot.com/) 提供 844 个陆地生态区、约 150 MB Shapefile，CC BY 4.0，无 key、限速未声明。Tier 1 分析框架，适合构建期简化为 GeoJSON/矢量分片。2017 边界是模型，不是实时生态状态或绝对自然边界。

## 高权威但高发布限制：IUCN Red List

[API v4](https://api.iucnredlist.org/)；[API help](https://api.iucnredlist.org/help)；[FAQ](https://nrl.iucnredlist.org/about/faqs)；[空间数据](https://nrl.iucnredlist.org/resources/spatial-data-download)；[条款](https://www.iucnredlist.org/terms/terms-of-use)。当前 API 版本标示 `2025-2`；评估必须保存 assessment/version/date。API 需 token、动态未公布限速，缓存/批量使用需遵守专门条款。

IUCN 评估为 Tier 1，但不能概括为普通开放许可：商业/创收、衍生作品和全部或部分原格式再发布通常需书面许可；许多图片来自第三方，IUCN 通常不能授权。在获得明确书面许可前，公开 release 只保留允许的来源链接/自有说明，不提交 API 响应、评估文本、范围数据或地图。

## 发布前强制检查

- taxon/assessment/geometry 记录 source version、date、DOI/ID、hash；
- 数据和媒体许可分列，保留原始 provider/研究；
- 单 occurrence 不升级为分布/栖息地；
- GloBI/EOL 聚合关系不单独批准行为动画；
- IUCN 未获再发布许可自动阻断；
- 任何媒体许可缺失或从聚合页继承均自动阻断。
