# MUSEUM-09 全球艺术家扩展计划

## 总体

MUSEUM-09A 已将 M08 的 synthetic 规模就绪转换为一个真实、非公开、可审计的执行总体：

| 项目 | 闭合值 |
|---|---:|
| Raw source artist identities | 49,406 |
| Deduplicated、已故、具备三件作品的候选 | 7,017 |
| Program target artists | 500 |
| Legacy / new target artists | 12 / 488 |
| Ordered reserve artists | 120 |
| Candidate artworks | 9,000 |
| Program target artworks | 5,000 |
| Legacy / new target artworks | 44 / 4,956 |
| Gallery / Collection targets | 125 / 375 |
| Registered future batches | 10 |

这不是公开 release，也不改变当前 12/44 网站内容。所有目标和 reserve 均为确认去世的个人；anonymous、workshop、tradition、living、死亡未知与 Wikidata-only target 均为 0。

## 来源组合

正式来源组合为 Art Institute of Chicago、British Museum、Cleveland Museum of Art、Cooper Hewitt、Metropolitan Museum of Art、Minneapolis Institute of Art、MoMA、National Gallery Singapore、National Gallery of Art、Smithsonian、Tate 和 V&A，共 12 个官方来源。

目标作品贡献为：

| 来源 | 目标作品 |
|---|---:|
| AIC | 824 |
| Cleveland | 824 |
| MoMA | 824 |
| NGA | 824 |
| Met | 823 |
| Tate | 661 |
| National Gallery Singapore | 80 |
| Cooper Hewitt | 45 |
| V&A | 44 |
| Smithsonian | 27 |
| Minneapolis Institute of Art | 23 |
| British Museum | 1 |

最高单一来源占比 16.48%，低于 30% 门禁。433 位 target 有多个正式来源身份，67 位由一个正式来源身份支持；单来源不等于弱来源，但后续批次应优先补充可得的交叉核验。媒体权利没有在 M09A 推断或继承，新媒体下载为 0。

## 程序阶段

1. **MUSEUM-09A — completed foundation**：真实发现、身份/死亡/作品门禁、精确总体、代表性矩阵、reserve 和批次注册。
2. **MUSEUM-09B — recommended, not started**：执行首批 50 位新艺术家约 500 件作品的深度研究；需用户另行授权。
3. **MUSEUM-09C 至 MUSEUM-09K — registered, not started**：按治理注册逐批处理其余新艺术家和作品。
4. **Formal public expansion — not started**：只有未来 publishable candidate bundle 通过完整实体、证据、来源、媒体、notice、attribution、physical bundle 和 runtime 门禁后才能进入。

## 执行约束

- 每批输入由 stable IDs、input closure hash、source set 和 coverage delta 固定；批次互不重叠。
- Legacy 12/44 只引用不重做；为满足 5,000 件总体，另注册 121 件 legacy-artist target supplement，仍未执行。
- 同一输入必须 byte-identical 重建；每次变更先运行 phase-scoped classifier。
- 开发波次只运行目标测试、受影响 schema/dispatch smoke、release hash-only 和 repository safety；不运行 local full gate 或 GitHub final-full。
- public runtime、Pages、历史 release、M03C 媒体、武器馆和 OD-011 保持不变。

## 已知 P3

官方 bulk/API 数据会随机构修订而漂移。后续批次 owner 必须锁定输入 hash、保留更正入口，并在 source snapshot 变化时只重跑受影响适配器与依赖闭包。该风险不降低当前 M09A 审计包的确定性，但禁止把旧 snapshot 当作永久最新事实。
