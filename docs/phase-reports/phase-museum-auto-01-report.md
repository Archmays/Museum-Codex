---
phase_id: MUSEUM-AUTO-01
status: completed
validation_status: pass
report_date: 2026-07-15
runtime_model: not_exposed_by_runtime
runtime_reasoning: not_exposed_by_runtime
branch: main
final_commit: recorded_by_enclosing_git_commit
release_candidate_commit: 406665f19c1f041cace733962a33e49dddaa3d66
deployed_runtime_commit: 00a8539ea0d5e901fc2b6be993ea400ff36a0b19
actions_run: "29420441620"
actions_run_url: https://github.com/Archmays/Museum-Codex/actions/runs/29420441620
actions_run_conclusion: success
prior_failed_actions_run: "29418392249"
prior_failed_actions_run_url: https://github.com/Archmays/Museum-Codex/actions/runs/29418392249
pages_deployment_id: "5458604781"
pages_deployment_status: success
pages_url: https://archmays.github.io/Museum-Codex/
online_qa_status: pass_11_of_11
online_screenshot_count: 15
---

# MUSEUM-AUTO-01 单一 main 连续执行总报告

本报告是 Stage A MAIN-CONSOLIDATE、Stage B MUSEUM-03C、Stage C MUSEUM-04-REVISED、Stage D MUSEUM-05A 与最终统一发布的总审计记录。运行环境未暴露模型或 Reasoning 选择，因此两项均准确记录为 `not_exposed_by_runtime`。

## 1. AUTO-01 总体状态

四个实施阶段、最终 clean-install、全仓回归、构建、release/rights/performance/budget/scanner、浏览器门禁、统一 `main` push、GitHub Actions、Pages 部署与真实线上 QA 均达到 `completed/pass`。成功部署的 runtime commit 为 `00a8539ea0d5e901fc2b6be993ea400ff36a0b19`；线上 11/11 浏览器场景、15 张截图与 286 个 public-served 文件逐字节闭合共同构成正式上线证据。

## 2. 初始 dirty 文件统计

任务开始时 live worktree 已被一个先前本地提交清空；通过 `2be7301..15617a1` 的不可变 Git diff 重建原始 WIP：36 modified、98 formerly-untracked/additions，共 134 paths，14,738 insertions / 259 deletions。该统计是证据重建，不伪称直接观察到了 dirty 瞬间。

## 3. Branch 与 unique commits

本地和 live remote 从始至终均只有 `main`；非 main branch、merge、unique commits 均为 0，因此无需归并。初始 local-only commit `15617a1 Refine museum release data and validation pipeline` 是 remote baseline `2be7301` 的线性后代，随后全部工作继续在线性 `main`。

## 4. Checkpoint commits

- `15617a1`：任务开始前已存在的 M04 zero-media WIP commit，不能单独部署。
- `ba4c9d1`：`Checkpoint: preserve pre-media MUSEUM-04 work on main`。
- `df68399`：`Phase MUSEUM-03C automated media acquisition and validation`。
- `9a7f38a`：`Phase MUSEUM-04 media-aware art constellation`。
- `4acbe2e`：`Phase MUSEUM-05A first digital artist galleries`。
- `406665f`：`Complete MUSEUM-AUTO-01 release candidate`。
- `00a8539`：`Fix CI dependency order for Python contracts`，也是已成功部署的 runtime commit。
- `recorded_by_enclosing_git_commit`：最终线上证据与本报告 closeout commit；具体 SHA 由 Git history 与最终交付记录解析。

未创建 branch、worktree、stash、PR 或临时远端 branch；未 reset、clean、改写历史或 force push。

## 5. MUSEUM-03C 状态

`completed/pass`，`human_review_dependency=false`。M03B package/graph 受保护 hash 仍为 `sha256:1f0f00a0d7f6162fcb0d716e6b86fbcfe42a4e04a0422d7c1c0df63b70c97b86` / `sha256:58fe40930ab6f0e84019bbb0c3f378a2e73d7f3fbd4f810a66aa78f0481d1dd3`。

## 6. 44 项自动审核结果

44/44 均由 `automated_cross_validation_pipeline` 完成 identity、rights、bytes 与 quality mandatory closure，并落入七个允许终态之一；不存在 waiting/manual/pending/unknown-passed。

## 7. Self-hosted / external / metadata / blocked

| 决定 | 数量 |
|---|---:|
| `approved_self_hosted` | 31 |
| `approved_external_delivery` | 0 |
| `metadata_only_after_automated_review` | 7 |
| `blocked_rights_conflict` | 2 |
| `blocked_identity_conflict` | 0 |
| `blocked_quality_failure` | 0 |
| `blocked_source_unavailable` | 4 |

当前 44 件实际来源为 Met 38 + AIC 6。Met/AIC 门禁继续有效；补充实现的 Cleveland/Rijksmuseum 合同严格绑定 numeric ID、官方 host、canonical rule、对象/媒体 rights 与 attribution，其中 Rijksmuseum 通过三个受控、逐跳留证的 resolver 请求闭合唯一 PID/IIIF 链。Commons 保持补充检索且永不在闭包不足时自动提升。

## 8. Actual original downloads / bytes

31 个官方 Met originals，合计 `75,611,836` bytes。ignored vault 的 originals 数量与 ledger 精确一致；raw bytes、headers、requests、hop evidence、hash、pHash 与 logs 不进入 Git。

## 9. Derivatives / bytes

242 个 JPEG/WebP derivatives，合计 `35,907,176` bytes；仅 resize、orientation、ICC normalization、metadata-safe strip 与 compression，不 crop、不 upscale、不生成、不修复、不去水印。AVIF 为 `not_available`。M03C bundle content hash 为 `sha256:3aa84fa7df37c4823cd2cb1f92c7e1843e7dea70b7cfd683528b25698951d565`。

## 10. 每位艺术家媒体数

| 艺术家 | 批准作品 | Derivatives | Original bytes |
|---|---:|---:|---:|
| Albrecht Dürer | 4 | 32 | 11,720,579 |
| Francisco de Goya | 4 | 32 | 8,793,397 |
| Henry Ossawa Tanner | 0 | 0 | 0 |
| José Guadalupe Posada | 3 | 20 | 5,286,674 |
| Julia Margaret Cameron | 4 | 30 | 7,859,907 |
| Käthe Kollwitz | 0 | 0 | 0 |
| Katsushika Hokusai | 4 | 32 | 8,652,466 |
| Kitagawa Utamaro | 4 | 32 | 9,808,775 |
| Mary Cassatt | 0 | 0 | 0 |
| Raja Ravi Varma | 0 | 0 | 0 |
| Shen Zhou | 4 | 32 | 3,313,648 |
| Vincent van Gogh | 4 | 32 | 20,176,390 |

媒体可用性不映射为艺术地位、价值或图节点权重。

## 11. MUSEUM-04 release ID / hash

- Release ID：`release:art-constellation-1.0.0`
- Content hash：`sha256:52835bb9256a9e50c2b73b9ef2e4fb99aa4a40434f20319133fdfb56b09fc462`
- Manifest SHA-256：`sha256:0fa7046a6b47eb9c73abc2279157f745888eeb76e7445fb18810269b04ec5346`
- Physical closure：264 files / 39,436,869 bytes，绑定 M03C bundle hash。

## 12. Graph / list / table

图形、艺术家列表与关系表是等价正式任务路径；支持 search/filter/URL state、键盘、screen-reader live region、WebGL fallback、low-bandwidth list、forced colors 与 reduced motion。

## 13. A / B / C

12 artists / 31 contexts / 36 relations，A/B/C=`0/0/36`。36 条关系全部是 C 级、非因果、非算法的观察与策展比较；A/B 有明确空状态，没有虚构历史影响。

## 14. 星海媒体使用

31 件批准作品可按 focus 加载代表图或关系缩略图；13 件保持稳定无图状态。初始 constellation 不预加载 44 张图，runtime external API/hotlink/blocked asset 均为 0。

## 15. Performance

M04 current graph 与 1k/10k/50k scale evidence 均 pass；M05A 五个受控 profile 均 pass。最终 current lab 两个 mobile profile 与 1366×768 的 CLS p95 为 0，1440×900 为 0.000221，均低于 0.1；最终构建预算：home gzip 98,684 / 102,942，增长 10.243% / 15%；constellation 96,319 / 460,800；artist index 81,684、gallery 82,160、artwork 82,194、compare 84,204 bytes，均低于 460,800。真实设备与真实 AT 为 `not_available`，不冒充人工设备/读屏通过。

## 16. MUSEUM-05A 是否执行

已执行，`completed/pass`；前置条件 M03C rights closure、至少一件 self-hosted、M04 release、local build 与 P0/P1 门禁全部满足。

## 17. 12 artist pages / 44 artworks

`#/art/artists`、12/12 artist galleries 与 44/44 artwork details 均可达；31 件显示批准媒体，13 件显示完整 metadata-only/blocked 无图状态与官方来源。

## 18. Zoom / compare

作品详情提供 keyboard/pointer/touch 基础 pan/zoom、reset 与百分比；compare 提供两件作品并置、独立 zoom、metadata/material/technique/subject/date 与非因果观察提示，不生成 AI similarity score 或影响结论。

## 19. Rights / attribution

`RIGHTS.md`、OD-001/002/005/010、license decisions、第三方 notices、逐资产 attribution、source rule snapshot、withdrawal mapping 与 7/14 天及高风险 72 小时流程均闭合。Public release 中 unknown/restricted/development-only/blocked media bytes 为 0。

## 20. All tests

从 clean `npm ci` 安装后，lint、strict typecheck、Vitest 58/58、production build、build closure 与 repository safety 均通过；最终进程级禁网的完整 Python runner 为 `373 tests in 1070.061s / OK`。M04/public Playwright 6/6、M05A Playwright 5/5，合计 11/11；current/scale runner contracts 10/10，performance/budget/rights/release validators、M03B hash、deterministic release rebuild、public/dist candidate-label scans 均通过。没有删测试或放宽门禁。

## 21. Final commit

Release-candidate commit 为 `406665f19c1f041cace733962a33e49dddaa3d66`；成功部署的 runtime commit 为 `00a8539ea0d5e901fc2b6be993ea400ff36a0b19`。本报告、线上截图、浏览器结果和字节闭合证据由 `recorded_by_enclosing_git_commit` 记录；其具体 SHA 在提交后由 Git history 与最终回复给出，不通过自引用伪造。既有 checkpoint 历史未被改写。

## 22. Actions run

首次统一 push 触发 [Actions run 29418392249](https://github.com/Archmays/Museum-Codex/actions/runs/29418392249)，head `406665f19c1f041cace733962a33e49dddaa3d66`，结论 `failure`。根因为 workflow 在 `npm ci` 前执行完整 Python contracts，其中两个测试会调用 Node performance runner，clean Linux runner 因而无法解析 Playwright；其余测试没有显示产品回归。

`00a8539ea0d5e901fc2b6be993ea400ff36a0b19` 将 pinned Node setup 与 `npm ci` 移到 offline Python suite 之前，并增加 workflow 顺序断言；没有删测试或放宽门禁。随后 [Actions run 29420441620](https://github.com/Archmays/Museum-Codex/actions/runs/29420441620) 成功，build job `87369223523` 与 deploy job `87378295007` 全部通过；GitHub Pages deployment `5458604781` 状态为 `success`。

## 23. Actual Pages URL

[https://archmays.github.io/Museum-Codex/](https://archmays.github.io/Museum-Codex/)。Deployment `5458604781` 于 2026-07-15 14:20:16 UTC 成功发布已验证 runtime commit `00a8539ea0d5e901fc2b6be993ea400ff36a0b19`；HTTPS enforced，Pages build type 为 workflow。

## 24. Online QA

真实 Pages Playwright 最终 11/11 通过，耗时 24.051 秒，unexpected/skipped/flaky 均为 0。覆盖 home、Art landing、constellation、artist index、12 artist pages、44 artwork details、compare、About/Rights、Accessibility、mobile/desktop、keyboard、low bandwidth、forced colors、reduced motion、WebGL fallback、no-script、image decode fallback 与 rights/attribution。最终 console warning/error、HTTP ≥400、failed request、external API、WebSocket、unexpected hotlink 和 blocked asset request 均为 0。

本地 `dist` 的 286 个 public-served 文件、40,085,615 bytes 与真实 Pages 逐文件长度/SHA-256 完全一致，tree hash 为 `sha256:6cbd5575deeb1e16f4a25e5853404e2a5825186411ca7d4ebbc17b209c0e1aeb`。唯一不在公开闭包中的 `.vite/manifest.json` 是未被 runtime 引用且由 Pages 按 dot-directory 规则不提供的内部 Vite 构建元数据；不将其 404 伪装成公开文件匹配。证据见 `docs/qa/museum-auto-01/final-online/site-byte-closure.json`。

## 25. Screenshots

最终线上目录 `docs/qa/museum-auto-01/final-online/` 包含 15 张 PNG（12,472,976 bytes）、Playwright JSON、线上 QA summary 与 site byte closure。截图覆盖桌面/移动星海、列表、focus、关系、rights、Art landing、artist index/gallery、artwork detail、desktop/mobile compare 与 forced colors；只读视觉复核未发现错位、裁切、占位图冒充作品或移动端横向溢出，P0/P1 为 0。

## 26. Reviewer findings

独立 A–F/静态审计确认 M03B hash、M03C bundle、M04 release、M05A routes 与 safety closure。最终审计发现并关闭：M05A CI 门禁缺失、no-script 标题漂移、3 个新增 release schema 未同步全仓 required 清单、Cleveland/Rijksmuseum 缺可执行 source gate、移动 loading-state CLS 回归、About/Rights 与 Accessibility 缺浏览器路由证据、workflow tests 未锁定 M05A 门禁，以及 compiled loader 暴露两个正式候选 source label。

部署阶段另关闭两项：一是首次 Actions 的 dependency-order 问题；二是首次 live E2E 9/11 中，测试在主动导航/关闭页面前没有等待 source list 与响应式图片 decode，产生 `ERR_ABORTED`。没有忽略 abort，而是记录 `request.failure().errorText`，等待必需来源列表、`decode()` 和 `naturalWidth` 后重跑；最终全量 11/11、failed request 0。所有已知 P0/P1/P2 finding 均已关闭。

## 27. Remaining P3

- M03C：4 个 AIC IIIF 在当前环境 HTTP 403；AVIF 不可用；watermark/site-chrome heuristic 不等同 OCR。
- M04：无真实低内存 Android、无真实 AT；1k supplemental FPS median 27。
- M05A：正常带宽 decode/srcset 为代表性抽测；无真实触摸/AT；未单独构造重签恶意 bundle 触发 `blocked_runtime_ids` 的专项 fixture，仍由上游 M04 fail-closed gate 覆盖。
- Online visual：桌面 compare 的长短标题会使两张图顶端不齐；超长作品标题使详情主图落在首屏下方；移动星海可增加跳到图形/折叠高级筛选；密集 rights 说明可增加行高与段距。
- Cleveland/Rijksmuseum 合同已做 synthetic 正负门禁，并分别以官方 Cleveland `141444` 与 Rijksmuseum Night Watch 示例完成真实 metadata smoke；Rijks 三个 resolver 均 HTTP 200 并闭合 `200107928 → 202107928 → 500711199912110510799100 → PJEZO`。当前批次没有 Cleveland/Rijks 对象，因此没有对应 original bytes；现有 bundle collector 也不会收集未来 Rijks 的两个 follow-up metadata event，未来正式批次纳入 Rijks 前必须扩展该 closure。

以上均为非阻断 P3；已知未解决 P0/P1/P2 为 0。

## 28. Worktree clean

最终线上证据由本报告的 enclosing commit 收口；提交前仅移除已核实的 ignored Playwright tmp/trace/log，并重跑 diff、secret、large-file、symlink、protected-package 与 public-artifact 检查。enclosing commit 后要求 `git status --porcelain` 为空；实际 post-commit clean 结果由最终交付记录确认。

## 29. Local / origin / remote 一致

成功部署时 local `main`、`origin/main` 与 live remote 均为 `00a8539ea0d5e901fc2b6be993ea400ff36a0b19`，且是 baseline `2be73011cb1dca64cb8d3a2d5830f495671d755b` 的线性后代。enclosing evidence commit 推送后再次要求 local HEAD = `origin/main` = `git ls-remote origin main`；实际最终 SHA 与一致性由最终交付记录确认。

## 30. 未进入的后续阶段

未进入 MUSEUM-05B、MUSEUM-06、武器馆、生物馆或其他分馆；没有为这些阶段创建代码、branch、worktree、release 或 Pages 路由。
