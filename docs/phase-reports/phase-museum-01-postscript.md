---
phase_id: MUSEUM-01
record_type: additive_postscript
verified_at: 2026-07-12
original_status_changed: false
original_validation_changed: false
first_successful_deployment_run: 29155093901
final_evidence_deployment_run: 29155301910
final_evidence_commit: 9a7f80b691ae95db7ba35150ed35af2abb138b2a
---

# MUSEUM-01 追加证据

本文件是 MUSEUM-02 入口审计产生的追加式证据，不改写 `phase-museum-01-report.md`，不把当时未发生的功能回填到 MUSEUM-01，也不改变其 `completed/pass` 结论。

2026-07-12 通过 GitHub API/CLI 重新核验：

| 关系 | Workflow run | Head commit | Run | Build job | Deploy job |
|---|---:|---|---|---|---|
| 首次成功部署证据 | [29155093901](https://github.com/Archmays/Museum-Codex/actions/runs/29155093901) | `10ca32802650211f5b449a3b492dd51dcb6e820f` | success | success | success |
| 最终证据提交后的成功部署 | [29155301910](https://github.com/Archmays/Museum-Codex/actions/runs/29155301910) | `9a7f80b691ae95db7ba35150ed35af2abb138b2a` | success | success | success |

因此，原报告中的 `29155093901` 仍是首次完整成功的 Pages 部署证据；`29155301910` 则证明 MUSEUM-01 最终证据 commit 随后也成功完成 build 与 deploy。两者是先后相容的证据，不互相替代。

同期复核 Pages API：仓库与 Pages 均为 public，`build_type=workflow`，`https_enforced=true`，公开地址仍为 <https://archmays.github.io/Museum-Codex/>。
