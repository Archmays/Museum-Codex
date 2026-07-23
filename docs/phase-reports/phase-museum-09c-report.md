---
phase_id: MUSEUM-09C
status: completed
validation_status: pass
baseline_commit: 6b6670b53cdfe4de1527878cd7bde337c31cdad8
implementation_commit: bfd9d2be1a6b39857e59d255952f01e153d5300e
runtime_commit: a116556bb03b076e9bbf5d3357df6a55c998bea1
final_closeout_commit: recorded_in_final_delivery
batch_id: museum-09-batch-02
batch_input_closure_hash: sha256:02b962ad03917cac733f8be584c0f710f624f3039c04c869b92772bb31b2681d
candidate_package_id: museum-09c:batch-02-formal-candidate-v1
media_package_id: museum-09c-media:batch-02-media-bundle-v1
release_id: release:art-expansion-batch-02-1.6.0
artist_count: 49
artwork_count: 485
current_artist_count: 111
current_artwork_count: 1017
gallery_artist_count: 12
collection_artist_count: 37
current_gallery_artist_count: 36
current_collection_artist_count: 75
replacement_count: 0
local_full_gate_count: 0
github_workflow_run_count: 5
github_final_full_gate_count: 1
runtime_deployment_count: 1
closeout_deployment_count: 0
pages_deployment_id: 5569033795
pages_url: https://archmays.github.io/Museum-Codex/
online_release_file_count: 630
online_release_matched_bytes: 116204745
online_functional_test_count: 6
screenshot_count: 12
museum_09d_entered: false
batch_03_entered: false
arms_museum_entered: false
remaining_open_decisions: [OD-011]
---

# MUSEUM-09C 阶段报告

## 结论与执行窗口

MUSEUM-09C 为 `completed/pass`。Batch 01 的治理真源已修复，CI docs-only 精确路径合同已补齐，通用扩展批次工厂已建立，Batch 02 已依次完成 research、media、immutable release、runtime、Pages 与线上闭环。公开美术馆从 62 位艺术家 / 532 件作品扩展到 111 位 / 1,017 件，Gallery / Collection 总量为 36 / 75。

从 execution-contract 提交时间 2026-07-23 10:40 +08:00 到线上证据冻结 19:19 +08:00，墙钟窗口约 8 小时 39 分钟；其中包含用户要求的关机暂停、GitHub Actions 排队与 Pages 收敛，不代表连续主动计算时间。模型与 Reasoning 的具体运行时标识未暴露，记录为 `not_exposed_by_runtime`。

## Git、治理修复与通用工厂

- Baseline：`6b6670b53cdfe4de1527878cd7bde337c31cdad8`
- Implementation：`bfd9d2be1a6b39857e59d255952f01e153d5300e`
- Final-full compatibility：`7cca187928a25edec0cc0bce2666a124e407dac4`
- Deployed runtime：`a116556bb03b076e9bbf5d3357df6a55c998bea1`
- Final closeout：本报告与线上证据所在的 docs-only `[skip ci]` 提交，精确 SHA 记录在最终交付回复中

Batch 01 保持 `published`，四步状态历史完整，initial release 为 1.5.0、current successor 为 `release:art-expansion-batch-01-1.5.1`；runtime、两次 deployment、线上闭环及 `next_authorized_phase=null` 已回填，没有倒退或改写 sealed input。

CI classifier 只把 exact `docs/05_roadmap/museum-09c-execution-contract.md` 加入 docs-only；同名目录或伪装 descendant 不获授权。Targeted fixture 证明本合同和 phase-report/QA closeout 为 heavy=0、browser=0、release rebuild=0、deploy=0，未知 Markdown 仍 fail closed。

`museum_pipeline/art/expansion_batch_factory.py` 与 `scripts/run_museum_expansion_batch.py` 从 registry 读取 batch assignment、计数、输入闭包、predecessor 和 output version。Research、media、release 是三个独立事务，各有 manifest、确定排序与原子写入边界；核心工厂未硬编码 Batch 02 人数、作品数或 1.6.0 版本。

## Batch 02 candidate、media 与 release

| Artifact | ID | Content hash | Manifest / tree hash |
|---|---|---|---|
| Formal candidate | `museum-09c:batch-02-formal-candidate-v1` | `sha256:32b8b8a227f0f61a59717a4cc931ff0fb9e6bd32f7327079be7944ed16bfcd86` | tree `sha256:5b87928188e59a907928a18080e7760acad24c6f7fba250b77c01a1307999495` |
| Media bundle | `museum-09c-media:batch-02-media-bundle-v1` | `sha256:222eb8f609f871622d5930f5dbe21c927e68ef140b3dd9fec88577ff6b1dabae` | tree `sha256:2eb35ff5358d9dcaed6aecea157c62ea4c49bf2566821c9e1364484712bbdce4` |
| Immutable release | `release:art-expansion-batch-02-1.6.0` | `sha256:266d8b655182dab60ee82a472a6937c99976e28d74afee402180f1d566c0ea71` | manifest `sha256:3fe1613d9c1f969cb31294132f995b3147aae648fa762c5c4b772c460e859c4f`; tree `sha256:d1ed04f15eec22f241b55ab0915d6876f7788f63ea27249ace3d2ddc4028842c` |

Batch 02 精确贡献 49 artists / 485 artworks，Gallery / Collection 为 12 / 37；公开累计为 111 / 1,017 / 36 / 75。Coverage delta 为 Africa 3、East Asia 7、Europe 17、Latin America and Caribbean 5、North America 7、Oceania 1、South Asia 4、Southeast Asia 3、West and Central Asia 2。Replacement=0；living、unknown-death、non-person、duplicate artist、duplicate artwork 与 attribution conflict 均为 0。

Source set 为 AIC、Cleveland、Met、MIA、MoMA、National Gallery Singapore、NGA、Smithsonian 与 Tate。对本批次引用闭包复核 534 records：changed=0、unchanged=534、unavailable=0；没有下载新媒体或用 Tier 3 推断替代证据。

49 份新增英中儿童友好叙事全部保留逐句 Claim → Evidence → Source provenance；49/49 签名唯一，duplicate=0，primary-copy banned governance jargon=0。公开 release 累计 62 份 child-facing introductions、352 contexts、1,573 claims、1,459 evidence。

## 关系、地点、地图、路径与媒体

正式关系保持 60 条，全部为 C-level；A/B-level=0，未把计算相似或视觉相似写成历史影响。Explorer 默认全图节点=0，starter≤9、初始 focus≤13、expanded≤20、每 lane≤4、theme≤16、path≤13，节点/标签 overlap=0；无正式关系时保持自然空状态，list/table/text equivalents 完整。

Place-time episodes 从 110 增至 183；map/list/timeline 保持 holding 与 creation 分离、null/not-asserted 不推断坐标或旅行路线。Tours 保持 18，没有把候选 hook 写成正式 tour。

公开媒体继续复用 Batch 01 的 560 个 assets：71 self-hosted-image works、25 external-link-only works、921 metadata-only works。Batch 02 的 485 件作品均以 metadata-only 终态闭合；新增 originals=0、derivatives=0、downloads=0、旧内容复制复用=0。Build 只按 content-addressed manifest 引用既有 318 derivatives / 61,418,168 bytes，reencoded=0；受保护的 40 originals / 240,328,162 bytes 未改、未进入 Git/public。

Research、media 与 release 双构建结果 byte-identical：repeat=2、directory diff=0。Release 为 68 physical files / 19,055,048 bytes；历史 release 仅 hash-only，historical rebuild=0。

## Mobile、a11y、性能、隐私与截图

七个目标 viewport（360×800、390×844、412×915、768×1024、1024×768、1366×768、1440×900）覆盖新增 Gallery/Collection、三种媒体、compare、search、relationship states、paths、map/list/timeline 与 dense rights/source。44px controls、200% reflow、keyboard/focus/live region、forced colors、reduced motion、low bandwidth、no-script 和无横向溢出均通过；automated serious/critical=0。真实 AT 与物理设备为 `not_available`，未声称认证。

| Metric | Observed | Limit | Status |
|---|---:|---:|---|
| CLS p95 | 0 | ≤0.1 | pass |
| Interaction p95 | 51.8 ms | ≤150 ms | pass |
| Desktop FTI p95 | 613.619 ms | ≤1,800 ms | pass |
| Mobile FTI p95 | 644.819 ms | ≤2,500 ms | pass |
| Low-bandwidth initial transfer p95 | 261,839 bytes | ≤262,921 | pass |
| Current search p95 | 1.09 ms | ≤80 ms | pass |
| Synthetic 5,000 search p95 | 4.035 ms | ≤120 ms | pass |

External runtime/image requests=0、unexpected media preload=0、analytics=false、query history=false、geolocation calls=0。正式 QA 截图为 12 张 / 6,581,199 bytes，覆盖默认关系起点、三 lane focus、移动 focus、关系解释、无关系空状态、theme、新 Gallery/Collection、metadata-only、证据层及 forced-colors/低带宽等价体验；未改历史截图。

## Tests、Actions、Pages 与在线闭环

开发期仅运行 targeted waves，`local_full_gate_count=0`。本地定向闭包包括 54 Python tests、8 Vitest files / 52 tests、9 M09C browser tests、24 affected historical browser tests，以及 lint、typecheck、build、隐私/泄漏、安全、确定性、search 与 bundle budgets。

GitHub 共记录 5 次 workflow runs：

| Run | Commit | Classification | Result | Closure |
|---|---|---|---|---|
| `29985227484` | `bfd9d2b...` | final-full | failure | 4 个旧 schema/lifecycle/phase-boundary assertions；deployment=0 |
| `29987045088` | `7cca187...` | phase-scoped | success | 修复影响闭包通过；deployment=0 |
| `29987125901` | `7cca187...` | final-full | failure | 1 个旧 successor-lifecycle invalid fixture；deployment=0 |
| `29988608695` | `a116556...` | phase-scoped | success | fixture 修复影响闭包通过；deployment=0 |
| `29988679460` | `a116556...` | final-full | success | accepted source-of-truth；deployment=1 |

没有删除/跳过测试、加 `xfail`、降低阈值、force push 或重建历史 release。唯一计为验收的 clean final-full 是 run `29988679460` / job `89146279631`：506 Python tests、15 Vitest files / 105 tests、47 Playwright tests、全 validators、clean build、privacy/leakage、安全、性能、Pages artifact binding/upload 均成功，job 用时 34m07s。因此 accepted `github_final_full_gate_count=1`。

同一 run 的唯一 Pages deployment `5569033795` / job `89151596387` 成功，environment status `15833884460` 为 success；build type=`workflow`、HTTPS enforced、public=true，deployed commit 精确为 `a116556...`。Runtime deployment=1，closeout deployment=0。

Batch 02 独立线上 byte closure 验证 630/630 files、116,204,745/116,204,745 bytes，hash failures=0；分类为 67 release-manifest、245 predecessor-reference、318 build-materialized。Release ID、content/manifest hashes 与 111/1,017、352 contexts、1,573 claims、1,459 evidence、60 relationships、183 episodes、18 tours 在线一致。

在线 Playwright functional smoke 的接受结果为 6/6。首轮 5/6，accessibility hash-route 懒加载在 5 秒断言窗口仍显示 `Loading page`；仅重跑该失败闭包后 1/1 通过。没有掩盖该尝试，也没有全量重跑或放宽断言；最终接受的六项场景 console error、failed same-origin request、HTTP error、external runtime/image request 均为 0。

## Reviewer、storage 与阶段边界

Reviewer A–G 分别覆盖治理、身份/死亡、Claim/Evidence/Source、媒体/权利/隐私、release/determinism、runtime/a11y/mobile、performance/request discipline，均为 pass、P0/P1/P2/P3=0。Reviewer H 的 CI/deployment/phase-boundary 为 pass，保留既有 `OD-011` 为 accepted-open P3；它不阻塞 Batch 02，也不授权下一阶段。

实现期已删除 2,878 个可重建文件 / 543,789,071 bytes，包括 `dist`、`output/playwright`、M09C deterministic/tmp backups 与调试日志；closeout 再删除线上测试 output 与 Python bytecode caches 221 files / 4,183,092 bytes。累计清理 3,099 files / 547,972,163 bytes，均可由正式输入和测试命令重建。保留 formal candidate 67 files / 4,818,211 bytes、media bundle 12 / 170,436、release 68 / 19,055,048、protected media vault 171 / 240,845,468，以及正式 tests、screenshots、CI/online evidence。

Batch 03–10 均保持 `registered_not_started`，assignment 未改；MUSEUM-09D=false、ARMS-MUSEUM=false、`next_authorized_phase=null`，OD-011 保持 open。阶段完成后停止。
