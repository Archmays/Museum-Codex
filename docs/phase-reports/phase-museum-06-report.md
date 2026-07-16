---
phase_id: MUSEUM-06
status: partial
validation_status: pass
report_date: 2026-07-16
runtime_model: not_exposed_by_runtime
runtime_reasoning: not_exposed_by_runtime
branch: main
baseline_commit: 41e5805b33f05f4150309c62030b4cc90a8969b7
implementation_commit: pending
final_commit: pending
input_release_id: release:art-gallery-interactions-1.1.0
input_release_hash: sha256:c07330d92d03b41fe57b5e80394e7e89e875945a9d24e7a5c73029b3283a8009
output_release_id: release:art-pathways-1.2.0
output_release_hash: sha256:8a773b00b37f025520e7ea4ef7a7ebc9cd3e0d3f1298925d3c20be29b28fe6f3
output_release_manifest_sha256: sha256:9eb27757c4888784bc79727ba7ce95179e313472a75b99a4b2098d3e4a6fb2dc
artist_count: 12
artwork_count: 44
context_count: 31
relationship_count_before: 36
relationship_count_after: 36
relationship_level_a_count: 0
relationship_level_b_count: 0
relationship_level_c_count: 36
ab_lead_review_count: 9
ab_promoted_count: 0
ab_retained_count: 1
ab_rejected_count: 0
ab_out_of_scope_count: 8
default_pair_count: 66
precomputed_path_count: 198
historical_mode_ready: false
context_mode_ready: false
comparison_mode_ready: true
max_alternative_paths: 3
max_hops: 6
expansion_budget: 10000
human_review_dependency: false
accessible_text_equivalence_status: pass
performance_status: pass
real_device_status: not_available
real_assistive_technology_status: not_available
pages_deployment_status: pending
pages_url: https://archmays.github.io/Museum-Codex/
actions_run: pending
open_decisions_count: 4
open_p3_count: 3
museum_07_entered: false
---

# MUSEUM-06｜AB 路径与可解释关系导航阶段报告

## 1. 当前结论

MUSEUM-06 本地实现与最终候选门禁达到 pass；状态暂为 `partial`，只等待实现提交、Actions、Pages 与线上字节/route 证据闭合。没有进入 MUSEUM-07。

本阶段回答“在当前审核数据中，可以通过哪些可解释关系从 A 走到 B”。它不证明唯一因果链；最短路径不等于最真实或最重要。当前正式关系仍全部为 `C｜策展比较`，没有算法相似、影响力、popular/degree 或媒体权重，也没有依赖人工逐项审核。

## 2. 入场与缓存复用

- 基线、local/origin `main`：`41e5805b33f05f4150309c62030b4cc90a8969b7`，入场工作树干净。
- 输入 release：`release:art-gallery-interactions-1.1.0`，hash `sha256:c07330d92d03b41fe57b5e80394e7e89e875945a9d24e7a5c73029b3283a8009`。
- 复用 M03C 242 个媒体 derivatives、M04 layout/search/星海、M05A 12/44 展厅和 M05B cards/tours/detail regions；没有下载、转码、新媒体或重新生成观察数据。
- M04 scale 1k/10k/50k rendering 未重跑，只复核原 evidence contract。共享前端输入变化后刷新了 M04 current 12-node 4 profiles × 3 samples 与 M05A 5 profiles × 3 samples；M05B 完整性能矩阵未重跑。

## 3. A/B leads 自动复核

只读取 M03A v5 与 M03B 已存在的 9 条 A/B leads：1 A、8 B。

- promoted：0
- retained_for_more_evidence：1
- rejected：0
- out_of_scope：8
- superseded：0

8 条至少一端不在正式 12 位艺术家集合；唯一双端点在集合内的 B lead 缺精确 Paris 活动重叠区间和独立来源闭包。因此没有新 A/B 正式边。所有终态由自动门禁给出，`human_review_dependency=false`，release 只含 aggregate summary，不含 private lead IDs。

## 4. 算法与状态

算法版本为 `museum-paths-bibfs-yen-1.0.0`：

- Graphology `0.26.0` mixed multigraph runtime；
- 单位 hop 的确定性双向 BFS；
- 最多 3 条无环、无完整重复的 bounded Yen alternatives；
- `max_hops<=6`、`K<=3`、shared expansion budget `<=10000`；
- 过滤顺序固定为 release → public → reviewed/verified → not withdrawn → not deprecated → rights/visibility → mode/level → type → direction → time/region；
- tuple 排序为 hops、mode-compatible level、confidence、time coherence、type repetition、stable relation IDs、stable artist IDs。

状态覆盖 `ready`、`no_path_for_current_release_and_filters`、`search_budget_reached`、invalid start/end、same endpoint、withdrawn endpoint/relation、incompatible release、tampered index 和 runtime failure。预算耗尽不显示“无路径”。

## 5. 66 pairs 与路径示例

12 位艺术家形成 66 个无序默认端点对；每对 comparison 预计算 3 条，共 198 条。由于 A/B=0，historical/context 为准确空状态；comparison ready。

示例 Albrecht Dürer → Francisco de Goya：

1. 1 hop：`art-rel:m03b-005`。
2. 2 hops：Dürer → Henry Ossawa Tanner → Goya；`art-rel:m03b-012` → `art-rel:m03b-035`。
3. 2 hops：Dürer → Julia Margaret Cameron → Goya；`art-rel:m03b-018` → `art-rel:m03b-019`。

这些都是 C 级策展比较，不证明相识、影响、师承或传播。

## 6. Immutable release 与物理闭包

输出 `release:art-pathways-1.2.0` 的 predecessor 精确为 M05B。它逐字节继承 predecessor children，只新增 algorithm、graph input、path index、explanations、A/B summary、performance contract 和 route config 七个文件。

- content hash：`sha256:8a773b00b37f025520e7ea4ef7a7ebc9cd3e0d3f1298925d3c20be29b28fe6f3`
- manifest SHA：`sha256:9eb27757c4888784bc79727ba7ce95179e313472a75b99a4b2098d3e4a6fb2dc`
- 272 manifest children；273 physical files；40,654,362 bytes
- 12 artists、36 formal relationships、66 pairs、198 paths

Exact bytes/hashes、schema、predecessor、graph hash、relationship/Claim/Evidence/Source closure、rights/notices/attribution、withdrawal、no private leads、no unreviewed/algorithmic/blocked/hotlink 均 pass。

## 7. UI、图文等价、打印与分享

新增 `#/art/paths`，并在 Art landing、constellation artist panel、artist gallery、artwork detail/compare 和 fixed-tour end state 增加入口。URL allowlist 仅为 `from/to/mode/types/period/region/maxHops/path/view`。

端点支持中文、英文和 alias 过滤、交换、防同端点；三种模式有独立说明。结果提供 Path 1/2/3、节点/边序列、level/type/confidence/time coherence、algorithm/release/filter、逐步 Claim/Evidence/Source、支持作品、rights、withdrawal 与免责声明。

图形复用 M04 layout，固定节点大小，保留并 dim 非路径节点/边，编号路径顺序，C 为点线；方向边才显示箭头。完整文字步骤始终存在，可独立完成选择、过滤、替代路径、证据查看、分享和打印。分享只产生正式 URL，不上传或保存选择。

## 8. 无障碍与隐私

自动化通过 native controls、keyboard、focus、live region、headings/ordered list、direction/A/B/C text、alternative tabs、touch target、360/390 no overflow、forced colors、reduced motion、low bandwidth、WebGL fallback 和 print。真实 AT/物理设备为 `not_available`，未伪称通过。

仅保留既有 locale/low-bandwidth preference；无 path/query/visit history、账户、analytics、tracking 或外部 API。

## 9. 性能

| 门禁 | 实测 | 上限 |
|---|---:|---:|
| Home gzip | 99,390 B | 100,868 B（M05B +2%） |
| Path route total gzip | 125,892 B | 256,000 B |
| Default path index gzip | 40,536 B | 65,536 B |
| Path JS/algorithm closure gzip | 35,780 B | 81,920 B |
| Current 12-node query p95 | 0.509 ms | 50 ms |
| Route interaction p95 | 32.0 ms | 150 ms |
| 66-pair build | 14.09 ms | 1,000 ms |
| 1k V / 5k E median | 10.907 ms | 200 ms |
| 10k V / 60k E median | 206.317 ms | 500 ms |
| 50k V / 300k E | `search_budget_reached` at 10,000 | bounded |
| Mobile JS heap increment | 4,862,852 B | 26,214,400 B |
| CLS | 0 | 0.1 |
| External requests | 0 | 0 |

Synthetic graphs use stable seed `museum-06-path-benchmark-seed-20260716` and are not in the public release.

## 10. Tests 与执行次数

Targeted evidence：

- M06 Python final targeted：26/26；governance/schema wave：50/50；两项 schema-count closure：2/2。
- M06 algorithm/UI + touched gallery regressions：60 unique Vitest scenarios pass；最后 UI effect closure 6/6（与前述重叠）。
- M06 Playwright：5 unique scenarios；first 3 pass/2 fail，exact closure 2/2，performance refresh 1/1。
- M06 synthetic benchmark：1 次完整 12-node/66-pair/1k/10k/50k path run，pass。

Final candidate：

- Full Python：1 次，415 tests / 1265.553 s；413 pass / 2 schema-count failures。未重跑 415 全套，精确闭包 2/2 pass。
- Full frontend：1 次；lint pass、strict typecheck pass、Vitest 78/78、performance runner 10/10。
- Production build：1 次候选 build；M04 home false-positive 后只重建失败依赖闭包 1 次。
- Full local E2E：1 次，22 scenarios；20 pass / 2 assertion failures。未重跑 22 全套，精确闭包 2/2 pass。
- M04/M05A/M05B/M06 budgets、release、rights、source/media、public/dist leakage、repository safety 全部 pass。

## 11. 对抗审查 A–F 与 P3

`docs/qa/museum-06/adversarial-review.md` 记录 A–F 全部 pass，P0/P1/P2=0。Open P3=3：继承 1k informational FPS 27、真实 AT/物理设备不可用、无 analytics/RUM 下公网 cold latency 波动。每项均有 owner、缓解与最晚复核点。

## 12. Git、Actions、Pages 与线上证据

只在线性 `main` 工作，没有 branch、worktree 或 PR。实现提交、Actions、Pages deployment、live new/old route、exact online bytes、local/origin/remote hash 和最终 clean 状态将在部署后写回本节及 `docs/qa/museum-06/online-evidence.json`。

## 13. Storage cleanup

Release staging 使用自动清理的 temporary directory；synthetic fixtures 仅驻留内存；已停止本地 Vite dev/preview 服务，删除 4 个 transient server logs 与 `output/playwright` failure traces。保留固定 `dist`、版本化 release、JSON metrics、Playwright result JSON 和 3 张 M06 QA screenshots 作为正式候选证据。

## 14. 决定与阶段边界

OD-006、OD-008、OD-009、OD-011 保持 open，`open_decisions_count=4`。本阶段没有关闭这些决定，也没有进入 MUSEUM-07。
