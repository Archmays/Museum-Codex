# 不可变 raw snapshot 格式

默认路径：

```text
data/raw/<source>/<YYYY>/<MM>/<DD>/<UTC timestamp>-<body hash prefix>/
  manifest.json
  response.body       # 仅首次出现该 body 时存在
```

写入先在同一父目录创建临时目录，完整写入 exact response bytes 与 canonical manifest，再以原子 rename 发布。目标已存在即 `snapshot_overwrite`；不在原位置重排 JSON、换行或 Unicode。路径必须是 canonical POSIX relative spelling，拒绝绝对路径、Windows drive/反斜杠、`..`、`.`、双斜杠、Windows reserved name 与任何 symlink component/root。

## Manifest

记录 snapshot/event/request/run identity、脱敏请求、HTTP method、canonical/final endpoint、query profile、credential alias、UTC 时间、adapter/contract 版本、source registry 与 license-rule snapshot hash、状态、allowlisted headers、redirect chain、content type、bytes、SHA-256、body path/reference、source object IDs、retry count、warnings/errors 和 terms verified date。凭据值及其 hash 均不保存。

校验会重新计算 bytes/hash、验证 source-specific endpoint/object ID、registry/rule hash、adapter 版本、snapshot ID hash suffix、引用来源与引用 body 的物理 bytes，且检测引用环。一个已损坏的旧 body 不会被新的 acquisition event 复用。

## 304 与相同内容

- `304` 创建新的 `not_modified` check event，body hash/bytes 和 snapshot ID suffix 来自已验证的既有 body；不复制 bytes。
- HTTP 200 内容相同创建 `duplicate_content` event，引用最早的有效 body snapshot。
- ETag/Last-Modified 只作为 response header/cache signal，不代替 SHA-256。
- 每次事件保留自己的 fetched_at、request、status、redirect、run 与 adapter 证据。

## Git 边界

`data/raw/**` 和 `data/intermediate/**` 永久忽略。真实 live raw 不提交。`fixtures/pipeline/recorded/` 只提交最小、脱敏 projection；fixture hash 与未提交 live raw hash 分开记录，且无媒体字节。
