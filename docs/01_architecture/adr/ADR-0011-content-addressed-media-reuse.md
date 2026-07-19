# ADR-0011：跨 release 的内容寻址媒体复用

- Status: accepted
- Date: 2026-07-19
- Phase: MUSEUM-08

## Context

MUSEUM-04 至 MUSEUM-07 是不可变物理 release。当前 overlay 为保持旧 URL 可解析，会在每个 release 目录中保留相同媒体路径；Git 对相同 blob 已做对象级去重，但工作树和 Pages artifact 仍可能重复物理字节。后续数十个批次不能靠删除旧 release、改写历史或让每个 builder 重新复制 originals/derivatives 来扩展。

## Decision

1. 未来共享媒体字节以文件 SHA-256 为唯一内容身份，目标命名空间为 `assets/sha256/<prefix>/<digest>`。
2. Release manifest 只通过精确 digest、bytes、content type 与同源相对路径引用共享字节；同一 digest 可被多个 release 引用，但每个引用分别绑定对象身份、用途、权利状态、署名、notice 与 withdrawal 状态。
3. 撤回会禁用新 release 中的具体引用并更新 notice，不删除或改写已经发布的历史 release，也不把“同字节”推导成“同权利”。
4. Builder 使用单一 canonical writer。输入 digest 未变化时只验证共享字节 hash；不重新下载、转码或复制。只有受影响引用/衍生规格进入局部重建闭包。
5. MUSEUM-08 只交付兼容设计与 fixed-seed synthetic prototype。V1 candidate 继续保持 M04–M07 URL 和字节不变，不在本阶段迁移真实媒体。

## Validated prototype

- Synthetic prototype 让两个 synthetic release 引用同一个 SHA-256 身份，并声明一个存储副本。
- `docs/qa/museum-08/scale-readiness.json` 记录 prototype、局部重建和 hash-only 证据。
- `scripts/generate_museum_08_scale_fixtures.py` 不生成媒体文件，也不进入 public build。

## Migration gate

MUSEUM-09 首个真实扩展批次前必须单独复核：

1. 旧 URL 与旧 release physical tree hash 保持不变；
2. Pages 对共享 namespace 的缓存、404、回滚与撤回行为；
3. manifest → asset → rights/notices/attribution 的完整引用闭包；
4. 同 digest 不同权利/用途的隔离；
5. staging bundle 与 predecessor rollback；
6. 迁移后的工作树、Git object、artifact 与 Pages 存储差异。

若任一门禁不闭合，继续依赖现有不可变路径；不得用删除旧 release 或破坏 URL 换取空间。

## Consequences

- `scale_architecture_ready=true` 不等于真实媒体已迁移。
- MUSEUM-08 的 candidate overlay 仍含与 predecessor 字节一致的路径，且不重建 31 originals 或 242 derivatives。
- 风险 owner 为 release engineering；正式迁移复核点为 MUSEUM-09 首批真实内容进入前。
