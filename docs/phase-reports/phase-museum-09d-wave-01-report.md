---
phase_id: MUSEUM-09D-WAVE-01
status: completed
validation_status: pass
baseline_commit: b5f10b33d49bd8ce5e971a9f69299150f6598235
implementation_commit: 88334f00156f5c34c14b4fc23e9721476aea14fc
runtime_commit: 49ed213ae0a44517374461b72bc267090c7b94c9
online_verifier_fix_commit: 99694b8b08750e6d7abc502eeaf6bd1003e6da72
final_closeout_commit: recorded_in_final_delivery
current_release: release:art-expansion-batch-05-1.9.0
artist_count: 258
artwork_count: 2471
gallery_artist_count: 71
collection_artist_count: 187
local_full_gate_count: 0
github_workflow_run_count: 4
github_final_full_gate_count: 1
runtime_deployment_count: 1
closeout_deployment_count: 0
pages_deployment_id: 5583535045
pages_url: https://archmays.github.io/Museum-Codex/
online_release_file_count: 630
online_release_matched_bytes: 136196196
online_functional_test_count: 6
screenshot_count: 12
rights_status: PASS_BY_USER_AUTHORIZATION
batch_06_through_10_entered: false
museum_09g_entered: false
arms_museum_entered: false
remaining_open_decisions: [OD-011]
---

# MUSEUM-09D-WAVE-01 阶段报告

## 结论

MUSEUM-09D-WAVE-01 为 `completed/pass`。Factory V2 依计划连续处理 Batch 03–05，形成不可变 release 1.7.0、1.8.0、1.9.0；中间 release deployment=0，只有 1.9.0 完成一次 Pages deployment。公开美术馆由 111 artists / 1,017 artworks 扩展为 258 / 2,471，净增 147 / 1,454；Gallery / Collection 总量为 71 / 187。

模型与 Reasoning 的运行时标识未暴露，记录为 `not_exposed_by_runtime`。权利状态按用户授权记录为 `PASS_BY_USER_AUTHORIZATION`；隐私、secrets、source immutability、发布完整性及产品边界仍独立执行。

## Git、Factory V2 与恢复边界

- Baseline：`b5f10b33d49bd8ce5e971a9f69299150f6598235`
- Implementation：`88334f00156f5c34c14b4fc23e9721476aea14fc`
- Deployed runtime：`49ed213ae0a44517374461b72bc267090c7b94c9`
- Online verifier entrypoint fix：`99694b8b08750e6d7abc502eeaf6bd1003e6da72`
- Final closeout：本报告与线上证据所在的 `[skip ci]` 提交；精确 SHA 记录在最终交付回复

`museum_pipeline/art/expansion_wave_factory.py` 与 `scripts/run_museum_expansion_wave.py` 是本 wave 的 canonical writer/CLI。V1 `expansion_batch_factory.py` 和 `run_museum_expansion_batch.py` 保持未改。V2 从 release plan 注入 phase、reviewer、authorization scope、批次、前序 release 和版本，不在通用 writer 中硬编码本 phase/date/reviewer。

Journal、dry-run、idempotence、checkpoint 与 resume tests 通过。受控恢复证据保留了缺失 Getty ULAN authority key 的 research hard stop，以及 schema target、source binding、notice closure 的 deep-gate failures；修复均从失败 checkpoint 恢复，没有覆盖已提交 stage。最终 stable wave input hash 为 `sha256:d08db710f4983f049000e075fd9ad08f2e937155ee0a51a0b17e679d399ce566`。

## Batch 03–05 assignment、candidate 与 media

| Batch | Assignment | Gallery / Collection | Input closure | Source drift | Replacement |
|---|---:|---:|---|---:|---:|
| 03 | 49 artists / 485 works | 12 / 37 | `sha256:2f401a1fbf6d8f9d7f773b11c54b6c7c388c8d3a47725c9bedd3af7f13bf528d` | 534 unchanged / 0 changed / 0 unavailable | 0 |
| 04 | 49 / 485 | 12 / 37 | `sha256:81e07ced806a68819a6fa300cefff2f0ae9e89f8dfb95ae31ed82fde379c4ee0` | 534 / 0 / 0 | 0 |
| 05 | 49 / 484 | 11 / 38 | `sha256:1983735d38fa32b3666e401ef1144ae58ce119b4fe5072d71893535e105d0527` | 533 / 0 / 0 | 0 |

Candidate / media IDs 与 hashes：

- Batch 03 candidate `museum-09d-wave-01:batch-03-formal-candidate-v2`: content `sha256:29aa23bd30de71b889ac746bc0cd9735b6f340a24cec94e6ecb6d79c28446cf8`; tree `sha256:c87fbf0a84ad98a184ce547984f361b0c50421311131540c05647f3cde3fdd5d`。Media `museum-09d-wave-01-media:batch-03-media-bundle-v2`: content `sha256:d6b3a5cc5649c7ddd7c459eb36e8c4738ad8c863d89f45ffc4caebc4ec97c297`; tree `sha256:cdd737060df31e87cb05b4eccfcd888863e35f7ad53e0bd36fad51ff030f0f23`。
- Batch 04 candidate `museum-09d-wave-01:batch-04-formal-candidate-v2`: content `sha256:176edc28d0678f3d518264bc03a9462b4a5cd7e193ae37b86908a906740f62c7`; tree `sha256:22068109241af8ae9c0381b1659c6d2a5b461e995a478d0fbca72ee241b20703`。Media `museum-09d-wave-01-media:batch-04-media-bundle-v2`: content `sha256:eb96688569106a8b783311ccb45c9265b2c51d79412fc44456cd08d07c03afaf`; tree `sha256:d30d69b3405cd747338e800d376dc8b567eacaffe5362b14f2f7a0a09fe26d98`。
- Batch 05 candidate `museum-09d-wave-01:batch-05-formal-candidate-v2`: content `sha256:9b7a6350ba645ee64f5d08241e06eee7f3573b15a60fb643882e73879dd123b2`; tree `sha256:a5fa697c15471f980a0bc0664154588354645abfb048fb9588cbc6af915fa17f`。Media `museum-09d-wave-01-media:batch-05-media-bundle-v2`: content `sha256:0747f8ceca1e11d1de354e5e7baad42abd90d394e5ad037d32c54e0f3580f8c1`; tree `sha256:3dc0cc212746bd7198efc479d0f69584339ea46ce8521596a8216294cd88e594`。

三个 media 包逐对象完成 485 / 485 / 484 terminal decisions，全部为 `metadata_only_after_media_review`，technical locator=0、downloads=0、new originals=0、new derivatives=0。公开累计媒体分区为 71 self-hosted / 25 external-link-only / 2,375 metadata-only；受保护 source originals 未改、未进入 Git/public。

147 份新增英中儿童友好介绍全部保留逐句 Claim → Evidence → Source provenance，distinct signatures=147、duplicate intros=0、banned governance jargon=0。身份、deceased、attribution、typed ID、claim/evidence/source、notice/attribution/withdrawal closure 均通过。

## 不可变 release 与确定性

| Release | Counts: artists / works / contexts / claims / evidence / episodes | Content | Manifest | Physical tree |
|---|---|---|---|---|
| `release:art-expansion-batch-03-1.7.0` | 160 / 1,502 / 511 / 2,156 / 2,042 / 256 | `sha256:9967fcbf86beb8badd84a19cf0dfda657861900084c518c0a8c1ab811c0c3135` | `sha256:c69b8b9f2ec9a5412a667b7f1dac7f76cdb9fbc462589450ef3698b66c8de318` | `sha256:07a10d1422055e3324b124bce44061b05763a03745547e84f55343c118ec4ff9` |
| `release:art-expansion-batch-04-1.8.0` | 209 / 1,987 / 670 / 2,739 / 2,625 / 329 | `sha256:f3c70a1424099098474818aab9188f47e9471016ce0b4b299629f89c7b2574d0` | `sha256:79bf569ac5e81aa3884c36132e80bcc7bd430ba2333eb4467b9a356f57ba3d1c` | `sha256:b978b31bd03c2f4dbf423b032507b0eba8983254995958cbafe6818b229cb42c` |
| `release:art-expansion-batch-05-1.9.0` | 258 / 2,471 / 828 / 3,321 / 3,207 / 400 | `sha256:7e810b9a450eadc061b53e8b385f450c470579a832731e0cc6cb44165ad804aa` | `sha256:3bd894c8de5c0ac98f962ecea4260e93614be8125c3eb28ef16ed82aa8367668` | `sha256:be22ce6edca6ae10f40315ac83c936fbcb1ad91987e9ff793f2f2783ad198e00` |

每个 release 均为 68 个 physical files；predecessor chain 1.6→1.7→1.8→1.9 闭合。Research、media、release 的 deterministic repeat 与 cross-batch checks 通过；历史 release 未重建。Closeout 后 integrity ledger 为 `sha256:41f5198cf2f97fba96d04dfe6e762dfcceeba51725979d745a64068cec2cfa6d`，hash-only 验证 11 releases / 1,817 files / 344,497,768 bytes。

正式 relationships 保持 60 条 C-level；没有把视觉/计算相似转成历史影响。Place-time episodes=400，tours=18；holding/creation、unknown/null 与 asserted travel 继续分离。

## 浏览器、a11y、性能与隐私

七个既有 viewport 及新增 Gallery/Collection、三种媒体、compare、search、relationship starter/focus/expanded/theme/table、paths、map/list/timeline、dense rights/source 均覆盖。44px controls、200% reflow、keyboard/focus/live regions、forced colors、reduced motion、low bandwidth、no-script 和无横向溢出通过。

| Metric | Observed | Limit | Status |
|---|---:|---:|---|
| Automated a11y serious / critical | 0 / 0 across 18 routes | 0 / 0 | pass |
| CLS p95 | 0 | ≤0.1 | pass |
| Interaction p95 | 34.1 ms | ≤150 ms | pass |
| Desktop FTI p95 | 600.50 ms | ≤1,800 ms | pass |
| Mobile FTI p95 | 616.45 ms | ≤2,500 ms | pass |
| Low-bandwidth initial transfer p95 | 365,217 bytes | ≤373,171 | pass |
| Current search p95 | 2.390 ms | ≤80 ms | pass |
| Synthetic 5,000 search p95 | 9.010 ms | ≤120 ms | pass |

Home initial=97,064≤102,060 bytes；search initial route=117,023≤220,000；full search index=277,271≤300,000；map route=632,542≤642,756。External runtime/image requests=0、unexpected preload=0、analytics/query history/geolocation=0。真实 AT 与物理设备为 `not_available`，未声称认证。

正式视觉证据为 12 screenshots / 6,591,319 bytes，覆盖 desktop/mobile/forced-colors/low-bandwidth、关系三 lane 与解释边界、新 Gallery/Collection、metadata-only、evidence/rights。Playwright skill 用于真实 Chromium、截图与失败闭包检查；原始 JSON runner 输出因含机器绝对路径未提交。

## Tests、Actions、Pages 与线上闭环

开发期保持 `local_full_gate_count=0`。定向闭包包括最终 86 个受影响 Python tests、15 Vitest files / 105 tests、10+4 Node lab tests、local effective browser 52/52，以及 lint、typecheck、build、release validators、privacy/leakage、安全、determinism、search 与 bundle budgets。线上 verifier direct-file 回归模块 15/15 通过。

GitHub Actions 共 4 次：

| Run | Commit | Classification | Result | Closure / deployment |
|---|---|---|---|---|
| `30062410019` | `88334f0…` | final-full | failure | 520 Python tests 中 3 条旧 schema-count/allowlist assertions；skip=1；deployment=0 |
| `30063883318` | `49ed213…` | phase-scoped | success | assertion 修复影响闭包；deployment=0 |
| `30063954074` | `49ed213…` | final-full | full job success; workflow post-deploy failure | job `89391128695`: 520 Python tests（skip=1）、15/105 Vitest、47 Playwright、全部 validators/build/budgets/privacy/a11y 通过；唯一 Pages deployment=1；随后 verifier 在发网前因 CLI import 失败 |
| `30065913004` | `99694b8…` | phase-scoped | success | verifier entrypoint regression + M09D release closure；deployment=0 |

Accepted final-full 为 job `89391128695`，39m53s，失败 job rerun=0。Deployment `5583535045` 精确绑定 `49ed213…`；deploy action 成功。初始 environment status `15877678023` 因 post-deploy verifier import failure 标记 failure；修复后完整线上 byte closure 与 browser smoke 通过，追加可审计 recovery success status `15877936952`，未删除原失败状态、未二次部署。

线上 byte closure 为 630/630 files、136,196,196/136,196,196 bytes、hash failures=0；分类为 67 release-manifest、245 predecessor-reference、318 build-materialized。Build identity=`49ed213…`、gate=`final-full`，1.9 release ID/hashes 与 258/2,471、828 contexts、3,321 claims、3,207 evidence、60 relationships、400 episodes、18 tours 一致。

线上 Playwright functional smoke 最终接受 6/6。首轮 5/6，desktop relationship shard 在 30 秒总超时内仍处于 on-demand loading；只重跑该失败场景后 1/1 通过（14.9s），没有全量重跑或放宽断言。Console error、failed same-origin request、HTTP error、external runtime resource 均为 0。

## Reviewer、storage 与阶段边界

Reviewer A–H 分别覆盖治理、身份/死亡、Claim/Evidence/Source、media/rights/privacy、release/determinism、runtime/a11y/mobile、performance/request discipline、CI/deployment/phase boundary。八组均为 pass；本 phase 新增 P0/P1/P2/P3=0。既有 `OD-011` 保持 accepted-open，不被本阶段关闭，也不授权下一阶段。

Closeout 删除 2,362 个可重建文件 / 412,044,539 bytes，包括 `dist`、`output/playwright`、`tmp` 与 Python bytecode caches；remaining targets=0，受保护输入删除=0。保留三个 formal candidates、三个 media bundles、三个 immutable releases、journals、source snapshots、schemas/tests、12 screenshots、CI/online evidence，以及 protected ignored media vault 171 files / 240,845,468 bytes。

Batch 03/04/05 状态历史单调并为 `published`；Batch 03/04 保持非 current、deployment=0，Batch 05 为 current 1.9.0、deployment=1、online closed、`next_authorized_phase=null`。Batch 06–10 保持 `registered_not_started`；未进入 MUSEUM-09G 或 arms museum，OD-011 保持 open。本阶段到此停止。
