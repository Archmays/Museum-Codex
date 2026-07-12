# The Met Open Access adapter mapping

- Adapter/source: `met_open_access` 0.1.0 / Tier 1 collection object
- Endpoint: `https://collectionapi.metmuseum.org/public/collection/v1/objects/{id}`
- License: OA collection metadata/data CC0；media 只接受对象级明确证据，且本阶段仍 blocked
- Official basis: [Collection API](https://metmuseum.github.io/), [Open Access](https://www.metmuseum.org/hubs/open-access)
- Reverified: 2026-07-12；官方文档上限 80 requests/second，本项目 live 并发固定 1

保留 object ID、collection URL、accession、title、creator display、date、medium、department、object/artist external IDs、`isPublicDomain`、rights text 和 constituent assertions。Artwork candidate 与 artist identity 分开：creator display/constituent name 不是 identity merge 证据。

`primaryImage`、small/additional image URL 只形成 media locator；`isPublicDomain=true` 只是后续对象级 rights candidate，URL 本身不证明许可。2026-07-12 object 1 技术探针：HTTP 200，1,665 bytes，`sha256:a3fb36ebf2149f568cb8fe74f4feb439dc9519fcb6e8ab8c4d2cadeea249354d`，返回 `isPublicDomain=false` 且无 primary image；contract/normalize/run closure 通过。它不是正式作品数据。
