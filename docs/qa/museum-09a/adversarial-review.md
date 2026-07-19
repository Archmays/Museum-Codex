# MUSEUM-09A 对抗审查 A–G

## 结论

- P0：0
- P1：0
- P2：0
- P3：1
- 状态：pass

21 个命名反例通过临时包变异实际触发校验器，不是清单式自报。覆盖 duplicate artist、living、unknown death、workshop as person、Wikidata-only、missing evidence、sensitive inference、duplicate work、attribution conflict、少于三件作品、coverage failure、来源集中、隐藏 popularity score、非确定顺序、candidate leakage、media bytes、current release mutation、batch overlap、reserve 无理由和 manual waiting state。

## A｜Identity and deceased

500 位 target 均为有稳定 ID 的个人、确认已故、至少一个非 Wikidata 正式来源和闭合死亡证据。Living、unknown-death、anonymous、workshop、school、circle、follower、culture、dynasty、tradition 和 Wikidata-only target 均为 0。跨源合并依 ULAN/QID 或规范化姓名+死亡年份；冲突不静默覆盖。

结果：pass，P0/P1/P2=0。

## B｜Global representation

九个 primary bucket 精确合计 500；Europe 34%，其他最低 guardrail 全部满足。区域标签有来源 basis，不表示国籍、族裔、血缘、价值或历史影响；没有模型推断敏感身份。

结果：pass，P0/P1/P2=0。

## C｜Sources and provenance

12 个正式机构来源均记录入口、snapshot/bulk、ID 稳定性、metadata/media 分离、terms、correction route、hash 与 fail-closed 行为。433 位 target 具有多个正式来源身份；最高单一来源作品占比 16.48%，未使用搜索摘要、AI 回答或 Wikipedia 作为正式证据。

结果：pass，P0/P1/P2=0。

## D｜Artwork mapping

9,000 件候选作品和 5,000 件目标作品全部闭合 artist、source object、attribution、evidence locator、来源和重复簇。每位 target 至少三件目标作品；目标中 attribution conflict 和重复作品簇为 0。没有从标题推断地点、事件、意义或关系。

结果：pass，P0/P1/P2=0。

## E｜Selection and batches

500 target、120 ordered reserve、6,397 rejected 均有状态历史与 reason code。选择不含重要性、流行度、市场或审美分数。10 个批次互不重叠，精确闭合 488 位新艺术家；M09B 首批为 50 人/488 件，状态 `recommended_not_started`。

结果：pass，P0/P1/P2=0。

## F｜Engineering and efficiency

相同输入的双构建 byte-identical。大型集合分为逐 shard hash/bytes/count/order/physical-closure 校验的确定性清单，最大文件约 3.76 MB，repository safety 通过。真实候选选择与提交目标一致；25 次 batch builder p95 95.47 ms；单一既有艺术家变更只改变一个 candidate shard hash；网络下载 0，public bundle 增长 0。

结果：pass，P0/P1/P2=0。

## G｜Public and phase boundary

当前 release content/manifest/tree hash 未变，5 个 release 通过 hash-only ledger。Public leakage=0，新增媒体=0，runtime/Pages/deployment=0。M09B 未进入，武器馆未进入，OD-011 保持 open。

结果：pass，P0/P1/P2=0。

## P3

`source-record-drift`：官方 bulk/API 记录未来可能被机构更正。Owner 为对应后续批次 canonical writer；每次批次提升前按 stable ID 和 content hash 刷新变化记录，只重跑受影响适配器与依赖闭包，并保留来源更正入口。该风险不阻断当前 hash-locked M09A 候选包。
