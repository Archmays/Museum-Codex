# MUSEUM-09 批次计划

## 分配闭合

治理注册包含 10 个未来批次，共 488 位新目标艺术家和 4,835 件对应作品；另有 121 件面向 legacy 12 人的 target supplement。它们与现有 44 件作品合计精确闭合 5,000 件目标作品：

`44 legacy + 121 legacy supplement + 4,835 new-artist batch works = 5,000`

批次 assignment 由 stable ID、coverage deficit、tier/readiness 和确定性 tie-breaker 生成。艺术家在批次间不重叠；reserve 120 人有固定替补顺序，只在 hard gate 失败时使用。

## 注册表

| Batch | 计划阶段 | 状态 | 新艺术家 | 作品 | Coverage delta（Africa / East Asia / Europe / LAC / North America / Oceania / South Asia / Southeast Asia / WCA） |
|---|---|---|---:|---:|---|
| 01 | MUSEUM-09B | registered_not_started | 50 | 488 | 4 / 6 / 17 / 5 / 7 / 2 / 3 / 3 / 3 |
| 02 | MUSEUM-09C | registered_not_started | 49 | 485 | 3 / 7 / 17 / 5 / 7 / 1 / 4 / 3 / 2 |
| 03 | MUSEUM-09D | registered_not_started | 49 | 485 | 3 / 6 / 16 / 7 / 6 / 1 / 3 / 4 / 3 |
| 04 | MUSEUM-09E | registered_not_started | 49 | 485 | 3 / 6 / 16 / 5 / 7 / 2 / 3 / 3 / 4 |
| 05 | MUSEUM-09F | registered_not_started | 49 | 484 | 4 / 6 / 17 / 6 / 7 / 1 / 2 / 4 / 2 |
| 06 | MUSEUM-09G | registered_not_started | 49 | 484 | 5 / 6 / 17 / 5 / 7 / 2 / 2 / 3 / 2 |
| 07 | MUSEUM-09H | registered_not_started | 49 | 483 | 5 / 6 / 16 / 5 / 8 / 2 / 3 / 2 / 2 |
| 08 | MUSEUM-09I | registered_not_started | 48 | 480 | 5 / 7 / 16 / 5 / 8 / 2 / 2 / 0 / 3 |
| 09 | MUSEUM-09J | registered_not_started | 48 | 481 | 4 / 5 / 17 / 5 / 8 / 1 / 4 / 2 / 2 |
| 10 | MUSEUM-09K | registered_not_started | 48 | 480 | 4 / 7 / 17 / 6 / 8 / 1 / 2 / 1 / 2 |

具体 stable IDs、source set、input closure hash、Gallery/Collection 计数、工作量、风险和依赖以 `governance/museum-09-batch-registry.json` 为规范；candidate package 中保存 byte-identical snapshot。

## M09B recommended first batch

首批建议精确包含 50 位新艺术家和 488 件作品，coverage delta 为 Africa 4、East Asia 6、Europe 17、Latin America/Caribbean 5、North America 7、Oceania 2、South Asia 3、Southeast Asia 3、West/Central Asia 3。

首批记录包含选择理由、来源集合、metadata readiness、媒体后续可行性提示以及 P0/P1/P2 风险字段。其状态固定为 `recommended_not_started`：MUSEUM-09A 没有执行 M09B，没有下载媒体，也没有创建或修改公开 release。

## 后续批次门禁

每个批次开始前必须重新证明：

- 用户已授权进入该阶段；
- 输入 hash、stable ID 和 predecessor release 未漂移；
- 每位 artist 仍满足个人、确认已故、非 Wikidata 正式来源和至少三件作品；
- attribution、重复簇、Claim → Evidence → Source 与 coverage delta 闭合；
- 媒体可用性不被当作媒体许可；
- P0/P1/P2 为 0，且 public bundle 通过完整物理闭包后才可发布。
