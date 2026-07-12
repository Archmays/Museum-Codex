# ADR-0008：录制契约 fixtures 与受控 live probes

- Status: accepted; implemented in MUSEUM-02
- Date: 2026-07-12

## Context

CI 不能依赖四个上游的实时可用性、速率或字段状态；仅手写 fixture 又可能与真实接口脱节。真实响应可能很大，并包含不适合提交的无关数据。

## Decision

CI 完全离线，只读取 `fixtures/pipeline/recorded/<source>/`。每个来源提交一个从真实官方 per-record 响应裁出的最小确定性 projection、fixture manifest 与第三方 notice。manifest 同时记录 projection bytes/hash 和未提交 live raw 的 snapshot ID、原始 bytes/hash、抓取时间、脱敏请求、adapter/contract 版本及 canonical rule IDs，明确 `media_bytes_included=false` 与 `curatorial_selection=false`。

真实探针只能在离线测试通过后由 `acquire ... --live` 单对象、并发 1 执行，写入 ignored `data/raw/`。上游漂移先保存不可变 raw event，再阻断 normalize；不得用 recorded fixture 伪装 live pass。CI/workflow 不出现 `--live`，也不读取凭据自动联网。

## Alternatives

- CI 实时请求：能发现变化，但不可复现且可能违反速率或因上游故障误阻断发布。
- 只保留完整响应：真实性强但体积、隐私和无关内容风险高。
- 只手写 synthetic fixture：稳定但无法证明与当前官方响应相容。

## Consequences

projection hash 不等于 live raw hash，两个 hash 必须同时记录，且 notice 说明做过最小化。接口变化需要新的 live event、adapter 版本和 fixture 更新，旧 raw 不覆盖。

## Revisit when

来源提供签名 schema/versioned test endpoint，或 fixture 规模需要独立许可仓库时。
