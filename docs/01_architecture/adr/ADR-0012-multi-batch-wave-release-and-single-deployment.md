# ADR-0012｜多批次 Wave Release 链与单次部署

- Status：Accepted for MUSEUM-09D-WAVE-01
- Date：2026-07-24
- Decision owners：project owner + canonical batch/release writer
- Scope：Batch 03–05；不授权 Batch 06–10 或武器馆

## Context

M09C 已证明单个 registry-driven batch 可以依次生成 research candidate、media bundle、immutable release，并通过一次 final-full 与一次 Pages deployment 公开。当前公开真源为 `release:art-expansion-batch-02-1.6.0`，规模111 artists / 1,017 artworks。

继续逐批运行虽安全，但会为 Batch 03–10 重复产生大量阶段调度、full-gate、deployment与closeout成本。用户明确允许更长、更大的任务，希望单次任务承担更多工作。同时，不能把三个批次压缩成一个不可恢复的单体事务，也不能牺牲每批的独立审计、rollback和immutable release。

现有工厂V1是单批次CLI，且phase/reviewer/date/source authorization scope仍含M09C硬编码；直接重复运行会造成provenance错误。

## Decision

采用“一个Wave、三个顺序Batch事务、三份不可变Release、一次最终部署”的模式。

### Release chain

1. Batch03：`release:art-expansion-batch-03-1.7.0`
2. Batch04：`release:art-expansion-batch-04-1.8.0`
3. Batch05：`release:art-expansion-batch-05-1.9.0`

Predecessor chain：

`1.6.0 → 1.7.0 → 1.8.0 → 1.9.0`

1.7.0和1.8.0是完整、tracked、immutable、可hash-only验证和rollback的release，但不部署。只有1.9.0在三个batch全部闭合后成为current release并部署一次。

### Transaction boundaries

每批独立执行：

- research
- media
- release
- deterministic validation
- registry state transition

Wave层维护：

- release plan
- transaction journal
- resume cursor
- predecessor chain
- cross-batch dedupe
- final runtime switch
- single deployment binding

### Failure behavior

任一batch失败：

- 不切换current runtime；
- 不部署partial wave；
- 已成功的内部package/release可作为正式证据保留；
- 失败batch不标记published；
- 修复后从失败batch/stage恢复；
- 不重做已闭合前序batch；
- 当前线上1.6.0继续服务。

### Factory V2

工厂必须从execution context、registry与release plan取得：

- phase ID
- batch IDs
- counts/tier/coverage/source set/closure
- reviewer identity
- review/build time policy
- authorization scope
- predecessor/output release
- artifact paths

通用writer不得硬编码具体batch、phase、日期或version。旧工厂和历史脚本保留为兼容wrapper。

### Content and UX gates

新增147位艺术家的儿童友好叙事、provenance、媒体状态提示与关系探索合同必须在research/release内建，不允许发布后再做补救UX阶段。

关系可视化保持任务聚焦，不因258位艺术家恢复全局圆环或全节点标签。

## Consequences

### Positive

- 三批次只需一次正式部署；
- 每批仍拥有独立candidate/media/release与rollback点；
- 失败可局部恢复；
- 后续可扩展为Batch06–10 wave；
- 减少重复full-gate与Pages操作；
- 将儿童叙事与关系体验标准前移为生产门禁。

### Costs

- 单次任务墙钟时间可能达到15–30小时；
- 需要wave journal、resume和predecessor chain验证；
- 最终cross-batch验证规模更大；
- 在最终部署前不会公开已完成的中间batch；
- 本地存储和Git tracked release将增长。

### Risks and mitigations

- **Risk：中途失败造成状态混乱。** Mitigation：原子事务、journal、单调registry、current runtime最后切换。
- **Risk：中间release被误部署。** Mitigation：deployment marker只允许final release ID，CI fixture拒绝1.7.0/1.8.0 deployment。
- **Risk：通用工厂仍隐藏phase硬编码。** Mitigation：scanner与mutation fixtures覆盖phase/date/reviewer/scope常量。
- **Risk：258位规模导致关系图退化。** Mitigation：视觉节点上限保持不变，完整任务交给list/table/search/path。
- **Risk：媒体下载放大存储。** Mitigation：对象级权限、SHA-256复用、protected originals、no public originals。
- **Risk：最终full失败需要反复重跑。** Mitigation：push前本地复核历史常见漂移；失败只重跑affected closure，最终仅一个accepted clean full计入验收。

## Rejected alternatives

### A. 三批合并为一份release

拒绝。会失去Batch03/04独立审计、rollback与registry状态，且失败定位困难。

### B. 每批独立部署

拒绝。会产生三次final-full、三次Pages切换和更多线上收敛时间，不符合批量治理目标。

### C. 三批完全并行正式writer

拒绝。predecessor链、registry、ledger、media content-address与Git存在单writer冲突。

### D. 只生成候选包，稍后统一release

拒绝。会延迟验证release builder、route/search/runtime在每批规模下的可组合性；采用中间immutable release但不部署能同时保留验证与效率。

## Validation

MUSEUM-09D-WAVE-01必须证明：

- Batch03/04/05各自deterministic candidate/media/release；
- predecessor chain完整；
-中间deploy=0；
- final deployment=1；
-失败resume fixture通过；
- current runtime只在1.9.0全门禁通过后切换；
-历史release rebuild=0；
-最终258/2,471及Gallery71/Collection187闭合；
- Batch06–10保持未启动。
