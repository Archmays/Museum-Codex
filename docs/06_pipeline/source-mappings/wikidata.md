# Wikidata adapter mapping

- Adapter/source: `wikidata` 0.1.0 / Tier 3 discovery
- Endpoint: `https://www.wikidata.org/wiki/Special:EntityData/{QID}.json`
- Object IDs: explicit `Q[1-9][0-9]{0,11}` only
- License: structured data CC0; linked Commons media has a separate non-inheritance rule
- Official basis: [Data access](https://www.wikidata.org/wiki/Wikidata:Data_access), [Licensing](https://www.wikidata.org/wiki/Wikidata:Licensing), [Wikimedia API limits](https://www.mediawiki.org/wiki/Wikimedia_APIs/Rate_limits)
- Reverified: 2026-07-12

读取 labels、aliases、P31、P569/P570、批准的 external IDs 及 P18 locator。日期 claim 保存 rank、qualifier/reference 是否存在；未知 claim property 进入 quarantine。P18 只生成 `unknown/development_only` media candidate，Wikidata CC0 不继承到 Commons 文件。

不运行默认 WDQS discovery，不批量抓取，不因死亡/归属/关系在 Wikidata 出现而升级为 verified。2026-07-12 对 Q42 做两次允许范围内的技术读取：首次验证接口，第二次在 endpoint registry 最终 hash 固定后验证 replay；相同 live body 为 309,251 bytes、`sha256:83e0be1eea4f43a9577d06d9845a25596814d1ea269ff24ac65d44b966d15fe6`。该 ID 只是技术探针，不是首批艺术家候选。
