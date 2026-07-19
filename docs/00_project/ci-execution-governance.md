# CI 执行治理

本规范是 Museum-Codex 的正式工程契约，并作为后续 Codex 项目的跨项目默认做法。质量、隐私、安全、权利、release 不可变性和证据要求不因执行提速而降低。

## 影响图优先

每次 CI 先由 `scripts/classify_ci_impact.py` 根据 before SHA、after SHA、rename/delete 状态与手动模式生成 changed-path / dependency impact graph。任何重建、浏览器套件或部署都必须能回溯到该输出中的 `reason_codes`、`affected_phases` 与影响闭包。

CI 分四级：

1. `docs-only`：只解析 Markdown/YAML/JSON、front matter、secret/absolute-path、evidence link/hash 和 changed-path assertion；重型 tests、release rebuild、browser、Pages artifact 与 deployment 均为 0。
2. `phase-scoped`：只跑受影响阶段 validator/builder、touched shared smoke、相关 route/browser；只有 runtime/public 字节变化才 build/deploy。
3. `shared-core`：按 impact matrix 跑受影响阶段；common schema、canonical dispatch、release loader、source/rights/security、共享 route/state、lock/build/workflow/scanner 变化不得静默降级。
4. `final-full`：用于首次 candidate、依赖/workflow/shared/security/rights 核心变化或显式 `workflow_dispatch(mode=full)`。

## Release 与缓存

- M04–M07 等历史 release 默认只验证 manifest SHA、content hash 与 physical tree hash。
- 只有对应 builder、validator、consumed schema、input closure、source/rights rule 或 release 文件本身变化，才重建该 release；旧发布目录永不覆盖。
- 输入 hash 未变化时，不重复下载、转码、布局、索引、截图、历史基准或等价高成本工作。
- 每个权威 artifact 只有一个 canonical writer；manifest、Git 与 deployment 也各有唯一正式 owner。

## 执行与部署

- 开发波次运行 targeted tests；每阶段原则上只执行一次最终 full gate。
- 失败后优先重跑 failed job；有代码修复时只跑受影响闭包，不连续 push 中间小修。
- validation 使用 `museum-validate-${{ github.ref }}` 且 `cancel-in-progress: true`；Pages deploy 使用独立 `pages` 且 `cancel-in-progress: false`。
- 只有同一 commit 的 validation 成功、`deploy_required=true` 且 runtime/public artifact 改变时才部署。
- 纯 closeout 必须先本地通过 docs-only classifier，提交信息使用 `[skip ci]`，不得再次部署相同 runtime。

## 禁止的捷径与报告

不得通过删测试、降低覆盖、放宽阈值、`skip`/`xfail` 或删除证据换取速度。阶段报告必须记录 targeted/full 次数、Actions runs、failed-job reruns、deployment 次数、cache reuse、历史 hash-only/rebuild 数量与 storage cleanup。
