# MUSEUM-09 数百艺术家扩展就绪

## 状态边界

- `scale_architecture_ready: true`
- `synthetic_scale_validated: true`
- `real_content_expansion_started: false`
- `museum_09_entered: false`

MUSEUM-08 只移除 V1 的架构阻塞，并不授权或启动 MUSEUM-09。没有采集、审核、下载或发布新的真实艺术家、作品、媒体、关系、地点或导览。

## 已闭合的阻塞

### CI 与 release

- Changed-path classifier 先生成依赖影响闭包，再选择 docs-only、phase-scoped、shared-core 或 final-full。
- 历史 release 默认只通过 integrity ledger 校验 manifest/content/tree hash。
- 只有 builder、validator、input closure、consumed schema、source/rights rule 或 release 字节变化才局部重建。
- Ledger 为每个 release 保存稳定的 builder/input/schema/source/rights hash；新增 batch 不要求线性执行全部历史 builder。

### 搜索与 stable-ID 加载

- V1 candidate 索引已经是带 hash/bytes 的分片 manifest；当前小 release 按实体类型生成小分片。
- 通用 `sharded-entity-loader` 可按实体类型、语言与 stable hash prefix 选择、同源加载并校验分片；无关分片不请求。
- 20,000-record synthetic 索引重复构建 byte-identical，单 stable-ID 查询只加载一个目标分片，未变化分片只验 hash。
- 排序不使用 query log、流行度、重要性、艺术价值或 embedding。

### 图谱、列表与路由

- Sigma 只接收最多 120 节点/1,000 边的聚焦邻域 + stable-ID 有界子图；不会一次渲染未来全部节点和边。
- 完整艺术家文字任务以 50 条稳定分页呈现，关系表以 100 条稳定分页呈现；两者保留语义按钮、键盘顺序和 200% reflow contract。
- 路由错误边界阻止 missing chunk 导致全站白屏；unknown/missing/withdrawn stable ID 使用自然语言恢复状态。
- 未来实体分片可按 stable ID 懒加载；V1 小 release 继续兼容现有完整 catalog 文件。

### 媒体与存储

- ADR-0011 采用 SHA-256 内容身份、manifest 引用、逐引用权利/withdrawal 边界。
- MUSEUM-08 只验证 synthetic prototype，不改写 M04–M07，不删除旧 URL，不迁移真实媒体。

## Synthetic contract

固定 seed `20260719`，不进入 public build：

| 数据 | 数量 |
|---|---:|
| Synthetic artists | 500 |
| Synthetic artworks | 5,000 |
| Searchable public-shape records | 20,000 |
| Typed relationships | 10,000 |
| Path/index records | 50,000 |

Fixture 包含中英双语、approved aliases、转写、source-language labels、长标题、同名实体与撤回记录；名称均为 synthetic 占位结构，不借用第三方人物或作品，没有媒体文件。

## 证据与执行

- Contract：`fixtures/museum-08/scale-contract.json`
- Generator：`scripts/generate_museum_08_scale_fixtures.py`
- Validator：`scripts/validate_museum_08_scale.py`
- Leakage gate：`scripts/scan_museum_08_synthetic_leakage.py`
- Evidence：`docs/qa/museum-08/scale-readiness.json`
- Python tests：`tests/test_museum_08_scale.py`
- Frontend tests：`src/tests/museum-08-scale.test.ts`

## MUSEUM-09 入场前仍需完成

1. 用户明确授权进入 MUSEUM-09；
2. 定义真实扩展批次、代表性与审核资源；
3. 复核共享媒体 namespace 的真实 staging 迁移；
4. 对真实数据运行 Claim → Evidence → Source 与独立 privacy/secrets/release closure；
5. 对 M08 P3 和本文件的 migration gate 逐项复核。

本文件不构成 MUSEUM-09 entry authorization。
