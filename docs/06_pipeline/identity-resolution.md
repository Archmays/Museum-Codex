# 身份解析与可逆 merge

候选 ID 使用 source-specific namespace + source object ID 的 UUIDv5，显示名或语言变化不会改变 ID。它只稳定定位一个来源候选，不是跨来源最终实体。

## Signals

Proposal engine 支持：

- strong：权威外部 ID 精确相同、来源明确 same-as；
- moderate：兼容生卒、活动地点/时期、机构；
- weak：名称/别名、script/transliteration、作品/馆藏线索；
- hard conflicts：生卒明显不兼容、candidate 内 hard conflict、个人与匿名/工作室/collective/传统归属/约定身份类型冲突。

来源独立性以 canonical source 和可选 `upstream_lineage_id` 计算；两个页面若复制同一上游，不算独立证据。任何 strong signal 仍只生成可审核 `same` proposal；name-only 永远 `uncertain`；hard conflict 强制 `distinct`。所有 proposal 均 `auto_merge=false`，记录 input hashes、版本、rationale、source independence 与 deterministic proposal hash。

## Merge / reverse

只有 active、非 stale 的 `approve_same` decision 可以创建 merge record。Reviewer 必须选择 survivor；所有 loser ID 保留为 alias，写 mapping before/after hash 和状态历史。reverse 将 alias 标为 inactive，保留 survivor、loser、decision 和全部历史，不删除或复用 ID。

匿名、工作室、collective、traditional attribution、“Master of …”约定身份与 uncertain attribution 保持原类型或进入人工队列，不被自动转换成可发布个人 artist。
