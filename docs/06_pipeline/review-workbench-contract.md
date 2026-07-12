# 本地 review workbench contract

Review workbench 是可版本化文件契约与 CLI，不是 Pages、后端或远程管理 UI。

`build-review-bundle` 汇总 candidate records、逐字段 provenance、conflicts、identity proposals、media rights warnings、adapter drift、所需 reviewer roles、所有输入文件的 exact SHA-256/bytes 与 bundle hash。`pipeline-run.json`、bundle 本身和 decision result 不进入自身输入 hash，避免自引用；其他输入发生任何字节变化，bundle physical validation 失败。

允许 decision：`approve_same`、`approve_distinct`、`defer_uncertain`、`reject_bad_source_record`、`request_more_evidence`、`approve_field_mapping`、`reject_field_mapping`。每条记录包含 reviewer/role、decided_at、rationale、完整 bundle input hashes、schema version、supersedes、current status 与 history。

`apply-decisions` 先验证 schema，再将 decision 的 `input_hashes` 与 bundle 的 `exact_input_hashes` 做精确相等比较。不同即标记 stale，不应用，也不创建 merge。`approve_same` 还要求 identity/discipline reviewer、proposal target 和 survivor；输出仅包含 decision result 与 reversible merge records，`publishable_records_created=false`。

Review bundle 与 decision 文件默认位于 ignored `data/intermediate/`。只有未来阶段明确授权并经过独立 release 门禁后，审核结果才可转化为 reviewed data；MUSEUM-02 不执行该转换。
