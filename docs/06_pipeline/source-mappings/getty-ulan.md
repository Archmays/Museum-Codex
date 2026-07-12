# Getty ULAN adapter mapping

- Adapter/source: `getty_ulan` 0.1.1 / Tier 1 identity authority
- Endpoint: `https://vocab.getty.edu/ulan/{9-digit-id}.json`
- License: ODC Attribution 1.0；attribution template 由 canonical rule 和 fixture notice 保留
- Official basis: [Obtain Getty vocabularies](https://www.getty.edu/research/tools/vocabularies/obtain/), [Linked Open Data](https://www.getty.edu/research/tools/vocabularies/lod/index.html)
- Reverified: 2026-07-12

当前官方 per-record JSON 返回 compacted Linked Art JSON-LD object。Adapter 映射 canonical ID、名称/语言、人物/组织类型、生卒 timespan、活动地点/时期、role/classification 与 equivalent same-as；未映射的 biography、scope note、关系和 contributor branches 进入 quarantine。关系不会变成作品归属或历史影响。

首次 live probe 对 500115493 返回 200、170,122 bytes、`sha256:6a6d7dedc0b40ebc8b7e888d618a25258348413a707a1b4ff5c7892604c05dd3`，揭示旧 expanded fixture 与当前 compacted shape 的差异；raw event 保留，adapter fail closed。修正并升至 0.1.1 后第二次 live probe 返回同一 body，contract/normalize/run closure 通过。旧 XML/Web Service 不作 fallback。该记录只是身份映射技术探针，不是策展选择。
