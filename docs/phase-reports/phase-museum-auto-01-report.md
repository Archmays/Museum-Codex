---
phase_id: MUSEUM-AUTO-01
status: local_release_candidate_pass
validation_status: pass
report_date: 2026-07-15
runtime_model: not_exposed_by_runtime
runtime_reasoning: not_exposed_by_runtime
branch: main
final_commit: pending_online_evidence
actions_run: pending
pages_url: https://archmays.github.io/Museum-Codex/
online_qa_status: pending
---

# MUSEUM-AUTO-01 单一 main 连续执行总报告

本报告是 Stage A MAIN-CONSOLIDATE、Stage B MUSEUM-03C、Stage C MUSEUM-04-REVISED、Stage D MUSEUM-05A 与最终统一发布的总审计记录。运行环境未暴露模型或 Reasoning 选择，因此两项均准确记录为 `not_exposed_by_runtime`。

## 1. AUTO-01 总体状态

四个实施阶段及最终本地 clean-install、全仓回归、构建、release/rights/performance/budget/scanner 和浏览器门禁均达到 `completed/pass`。当前状态是未推送的本地 release candidate；Actions、Pages 与线上 QA 在统一 push 后才可完成，本文不提前声称上线。

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

Release-candidate commit 由本报告的 enclosing Git commit 记录；最终 commit 需在 Pages 部署及线上证据回填后确定，不改写既有 checkpoint 历史。

## 22. Actions run

`pending`。只在最终本地 clean/pass 后 push；随后记录真实 Actions run ID、URL 与结论。

## 23. Actual Pages URL

[https://archmays.github.io/Museum-Codex/](https://archmays.github.io/Museum-Codex/)。当前报告在新 release 部署完成前不把旧线上内容作为本任务上线证据。

## 24. Online QA

`pending`。部署后检查 home、Art、constellation、artist index、12 artist pages、artwork detail、compare、About/Rights、Accessibility、mobile/desktop、keyboard、low bandwidth、forced colors、reduced motion、WebGL fallback、console/network/image/rights 与 local-dist 一致性。

## 25. Screenshots

本地阶段截图已在 `docs/qa/museum-04/` 与 `docs/qa/museum-05a/screenshots/`。最终线上截图将写入 `docs/qa/museum-auto-01/final-online/` 并在在线 QA 后回填数量。

## 26. Reviewer findings

独立 A–F/静态审计确认 M03B hash、M03C bundle、M04 release、M05A routes 与 safety closure。最终审计发现并关闭：M05A CI 门禁缺失、no-script 标题漂移、3 个新增 release schema 未同步全仓 required 清单、Cleveland/Rijksmuseum 缺可执行 source gate、移动 loading-state CLS 回归、About/Rights 与 Accessibility 缺浏览器路由证据、workflow tests 未锁定 M05A 门禁，以及 compiled loader 暴露两个正式候选 source label。所有 P0/P1/P2 finding 均已关闭；线上部署复验仍按 FINAL 流程执行。

## 27. Remaining P3

- M03C：4 个 AIC IIIF 在当前环境 HTTP 403；AVIF 不可用；watermark/site-chrome heuristic 不等同 OCR。
- M04：无真实低内存 Android、无真实 AT；1k supplemental FPS median 27。
- M05A：正常带宽 decode/srcset 为代表性抽测；无真实触摸/AT；未单独构造重签恶意 bundle 触发 `blocked_runtime_ids` 的专项 fixture，仍由上游 M04 fail-closed gate 覆盖。
- Cleveland/Rijksmuseum 合同已做 synthetic 正负门禁，并分别以官方 Cleveland `141444` 与 Rijksmuseum Night Watch 示例完成真实 metadata smoke；Rijks 三个 resolver 均 HTTP 200 并闭合 `200107928 → 202107928 → 500711199912110510799100 → PJEZO`。当前批次没有 Cleveland/Rijks 对象，因此没有对应 original bytes；现有 bundle collector 也不会收集未来 Rijks 的两个 follow-up metadata event，未来正式批次纳入 Rijks 前必须扩展该 closure。

以上均为非阻断 P3；已知未解决 P0/P1/P2 为 0。

## 28. Worktree clean

`pending`。最终 commit 前将停止本任务 preview、仅清理已核实的 ignored tmp/trace/log 产物、重跑 diff/secret/large/symlink 检查并要求 clean。

## 29. Local / origin / remote 一致

`pending`。发布前 live remote baseline 仍为 `2be73011cb1dca64cb8d3a2d5830f495671d755b`，local `main` 是其线性后代；最终在 Actions/线上证据 commit 后要求 local HEAD = `origin/main` = `git ls-remote origin main`。

## 30. 未进入的后续阶段

未进入 MUSEUM-05B、MUSEUM-06、武器馆、生物馆或其他分馆；没有为这些阶段创建代码、branch、worktree、release 或 Pages 路由。
