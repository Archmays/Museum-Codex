# Art Institute of Chicago adapter mapping

- Adapter/source: `aic_api` 0.1.0 / Tier 1 collection object
- Endpoint: `https://api.artic.edu/api/v1/artworks/{id}`
- Rate policy: anonymous 60/min；AIC User-Agent；本项目 live ≤1 request/second、并发 1
- Official basis: [API docs](https://api.artic.edu/docs/), [Open-access images](https://www.artic.edu/open-access/open-access-images), [Terms](https://www.artic.edu/terms)
- Reverified: 2026-07-12

请求必须有且只有一个 `fields` 参数，并精确等于批准 profile：

- `default`：12 个明确字段，不含 `description`，data rule 为 CC0；
- `description`：在同一集合中增加 `description`，只有该字段绑定 CC BY 4.0 与署名，其他字段仍绑定 CC0。

字段顺序变化、增减、重复参数、search path、错误 query profile 或 response extra field 均不能绕过 rule selector。`image_id`、IIIF base、`is_public_domain`、copyright/credit 只作为 rights hints；IIIF 可访问不等于媒体许可，媒体始终 unknown/development-only 且不下载。

2026-07-12 artwork 27992 技术探针使用 default exact-field profile：HTTP 200，1,077 bytes，`sha256:bf1b7aaf1e9ddc33a860f35ae88c377d055d15342d102b1776b5dbb7624722f6`；contract/normalize/run closure 通过。该对象不是正式作品选择，image ID 未被下载或公开。
