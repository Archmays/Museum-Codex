# MUSEUM-02 数据管线范围

MUSEUM-02 建立构建期、candidate-only 的可信导入底座，不建立后端或远程审核系统，也不创建正式 dataset release。公开门户保持 MUSEUM-01 的四条路由与占位内容；本阶段的 source records、候选人/作品、身份 proposal、raw、review bundle 和录制响应均不得进入 `public/`、`dist/` 或 Pages。

## 数据流

```text
explicit source object ID
  -> fixed adapter + allowlisted HTTPS request
  -> append-only raw acquisition/check event
  -> adapter contract + drift gate
  -> normalized candidate + field provenance + candidate claims
  -> identity proposals (never auto-merge)
  -> local review bundle + hash-bound decisions
  -> reversible merge records only
```

任何一步都不能写 `data/reviewed/`、`data/releases/` 或 publishable record。来源关系只可作为 source assertion/quarantine，不创建历史影响关系。

## 实现边界

- Python 3.12 包：`museum_pipeline/`；入口 `python -m museum_pipeline`。
- 仅四个真实 adapter：`wikidata`、`getty_ulan`、`met_open_access`、`aic_api`。
- JSON Schema 是规范源；`schemas/pipeline/` 使用 Draft 2020-12 与 canonical entity dispatch。
- 网络默认关闭；只有显式 `acquire ... --live` 可联网。
- live raw 在 `data/raw/`；中间 candidate/review 在 `data/intermediate/`；两者均被 Git 忽略。
- 可提交的上游内容仅限四个最小 recorded contract projections，均有 manifest、notice 和双 hash。
- Candidate/proposal/bundle/decision result 输出若目标已存在即失败；只有 run manifest 作为命令闭包索引追加输入/输出引用，不原地覆盖既有数据 artifact。
- 无 API key、Cookie、媒体下载、批量搜索、WDQS 发现、首批艺术家名单或 MUSEUM-03 功能。

## CLI

```text
verify-sources
list-adapters
acquire --source SOURCE --object-id ID --live
validate-snapshot SNAPSHOT
normalize SNAPSHOT
propose-identities RUN
build-review-bundle RUN
validate-review-bundle BUNDLE
apply-decisions BUNDLE DECISIONS
explain-field CANDIDATE JSON_POINTER
validate-run RUN
```

所有命令有稳定退出码：0 成功、3 验证失败、4 网络未显式授权、5 transport 失败、6 受控 I/O/JSON 失败。`--json` 输出 canonical、排序确定且不打印绝对敏感路径。

## 完成定义

完成意味着四个 adapter contract、不可变快照、provenance/license closure、identity/review/merge 契约、离线 CI 和 Pages 泄漏门禁可复核；不意味着任何技术探针成为策展候选、艺术家已确认去世、图片可发布或 MUSEUM-03 已获授权。
