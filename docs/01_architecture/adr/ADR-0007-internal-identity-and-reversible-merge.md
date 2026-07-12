# ADR-0007：内部身份 ID 与可逆合并

- Status: accepted; implemented in MUSEUM-02
- Date: 2026-07-12

## Context

内部 ID 不能随显示名称、语言或标签变化；fixture 又需要确定性。跨来源相同外部 ID 仍可能错误或共享同一上游，不能无痕自动合并。

## Decision

source record 的 provisional candidate ID 使用每个 adapter 固定 namespace 下的 UUIDv5，seed 仅为 canonical `source_object_id`，不含显示名称。它是来源范围内可复现的候选 ID，不宣称跨来源同一实体。跨来源只生成 `same/distinct/uncertain` proposal，且始终 `auto_merge=false`。人工 `approve_same` 后生成独立 merge record：保留 survivor、所有 loser ID、活动 alias mapping、输入 hash 与状态历史；reverse 操作只关闭 alias，不删除 ID。

共享权威 ID或来源明确 same-as 是 strong signal，但仍需 proposal；同名、转写、地点、时期、机构和馆藏线索不能单独自动合并。hard conflict 强制 `distinct`。匿名、工作室、collective、traditional attribution 和约定身份不得被强制转换成个人。

## Alternatives considered

- 随机 UUID：稳定但 fixture 不能确定复现，需要额外映射存储。
- 以名称 slug 为 ID：可读但标签变化、同名和多文字系统会破坏身份。
- 全局 source-seeded ID 直接当最终实体：会把来源断言误当项目身份结论。
- 单一全局 UUIDv5：若 seed 依赖外部 ID，来源改名或错误映射会污染全局身份。

## Consequences

候选 ID 是 provisional；merge/alias 层增加记录量，但所有决定可解释、可撤销。来源 ID 改名通过显式 alias/migration 处理，不重算既有 ID。

## Revisit when

MUSEUM-03 首批正式身份审核证明现有 signal 或 alias 模型不足时，只能追加迁移/映射，不删除历史 ID。
