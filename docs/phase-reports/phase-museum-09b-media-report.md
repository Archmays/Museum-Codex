---
phase_id: MUSEUM-09B-MEDIA
status: completed
validation_status: pass
baseline_commit: 108c5623547fb9eb11210ac11c05937060fbbc67
implementation_commits: [3c15cc81e44a75c18588f48191aad4e14c474cec, 551ca990d92ae4e576e59fe70d1fcc240749f047]
batch_id: museum-09-batch-01
input_candidate_package_id: museum-09b:batch-01-formal-candidate-v1
input_candidate_content_hash: sha256:299bbf0b5baf5522d8fb2a60682a8e5c2571fb5baeb205f4c6d28f549c728eb9
input_candidate_tree_hash: sha256:d662188a097e2549bc964372af445e0f532f1c115552f6f1fbb788ee0627bf87
input_release_id: release:art-v1-candidate-1.4.0
input_release_hash: sha256:93365e63792ae1c34667dcb2d002d733b58c68859b1a4e4bcae54d97f2532202
public_release_changed: false
allowlist_count: 65
initial_self_hosted_candidate_count: 40
initial_external_iiif_candidate_count: 25
excluded_metadata_only_count: 423
rights_checked_count: 65
source_record_changed_count: 4
source_record_unchanged_count: 61
source_record_unavailable_count: 0
final_self_hosted_count: 40
content_reused_original_count: 0
external_iiif_link_only_count: 25
external_iiif_manifest_only_count: 0
metadata_only_after_review_count: 0
blocked_count: 0
unresolved_count: 0
original_download_count: 40
original_download_bytes: 240328162
original_reused_bytes: 0
derivative_count: 318
derivative_bytes: 61418168
new_media_download_count: 40
candidate_public_leakage_count: 0
media_package_id: museum-09b-media:batch-01-media-bundle-v1
media_package_content_hash: sha256:d98e3409fb9512054acf532c541e4c4219fcf767564c846f78cfb2439b6c3c50
media_package_tree_hash: sha256:39c855c8640271310d448d819a8fc80e6ae2b95852bfe6e5211faffb1f173a5e
deterministic_package_status: pass
deterministic_derivative_status: pass
attribution_status: pass
withdrawal_status: pass
batch_registry_status: media_bundle_ready
historical_release_rebuild_count: 0
historical_release_hash_only_count: 4
local_full_gate_count: 0
github_final_full_gate_count: 0
phase_scoped_ci_run_count: 2
pages_artifact_count: 0
runtime_deployment_count: 0
closeout_deployment_count: 0
formal_public_expansion_started: false
museum_09b_release_entered: false
museum_09c_entered: false
arms_museum_entered: false
open_decisions_count: 1
remaining_open_decisions: [OD-011]
---

# MUSEUM-09B-MEDIA 阶段报告

## 结论

MUSEUM-09B-MEDIA `completed/pass`。Batch 01 精确 65 件 allowlist 已完成对象级来源/权利复核：40 件 Cleveland 媒体形成受保护 originals 与 tracked 响应式衍生物，25 件 AIC 媒体保持 external IIIF link-only；423 件 excluded metadata-only 作品没有被下载。内部正式媒体包已晋升为 `media_bundle_ready`，但不是公开 release。

从首个受控 acquisition 进程（2026-07-21 22:03:29 +08:00）到证据冻结的可测窗口约 65 分钟；更早的只读预检未单独计时，因此不虚构完整会话 wall time。运行环境未暴露模型或 Reasoning 标识，均记录为 `not_exposed_by_runtime`。

## Git 与受保护输入

- Baseline：`108c5623547fb9eb11210ac11c05937060fbbc67`
- 既有 M09B implementation：`95f43bee1b4ab04997fd6a041807079f55058b98`
- Media implementation：`3c15cc81e44a75c18588f48191aad4e14c474cec`
- Bounded metric-closure repair：`551ca990d92ae4e576e59fe70d1fcc240749f047`
- Final closeout：本报告所在 docs-only `[skip ci]` 提交；精确 SHA 由 Git history 与最终交付回复记录，避免自引用伪造。
- Input candidate：`museum-09b:batch-01-formal-candidate-v1`，content `sha256:299bbf0b5baf5522d8fb2a60682a8e5c2571fb5baeb205f4c6d28f549c728eb9`，tree `sha256:d662188a097e2549bc964372af445e0f532f1c115552f6f1fbb788ee0627bf87`，input closure `sha256:8b7020f979895e3bf5f21c042c1e6a2b746628f5108f13050102b31370219770`。
- Current release：`release:art-v1-candidate-1.4.0`，content `sha256:93365e63792ae1c34667dcb2d002d733b58c68859b1a4e4bcae54d97f2532202`，manifest `sha256:1eb5cce3264137a20dd18ea7595981585eae2abe125065ea010d542726277114`，tree `sha256:5029d271ae40b39ff3cbaa0fb0a9a05cded3b3d8b9aeb8bef8672f1c9240ebc1`。

入场时 local `HEAD`、`origin/main` 与 GitHub remote `main` 均等于 baseline；branch=`main`、单 worktree、worktree clean。有效全局 `AGENTS.md` SHA-256 为 `sha256:2d9c79e30c66f63afb63ef86237fdd6659147d6054ca8e403b52fce17b10a635`，跨项目 CI 治理章节唯一；项目 skill index 不存在，因此未使用或虚构项目 skill。

## Allowlist 与对象级权利

输入分区精确为 40 `approved_self_hosted_candidate`、25 `approved_external_iiif_candidate`、423 `metadata_only_ready`，互斥并合计 488。最终 65/65 均为终态：

| Final status | Count |
|---|---:|
| `approved_self_hosted` | 40 |
| `approved_external_iiif_link_only` | 25 |
| `approved_self_hosted_by_content_reuse` | 0 |
| `approved_external_iiif_manifest_only` | 0 |
| `metadata_only_after_media_review` | 0 |
| blocked | 0 |

Rights changed=0、endpoint changed=0、downgraded=0、blocked=0、unresolved=0。Cleveland 的当前对象记录提供逐对象 CC0 媒体状态，才能进入本地保存/衍生；AIC 的可用性和 public-domain 字段未被当作本地再分发许可。`RIGHTS_STATUS: PASS_BY_USER_AUTHORIZATION`，同时第三方媒体的实际门禁仍由对象级证据决定，用户授权没有替代该证据。

## Source drift

规范化后为 4 changed / 61 unchanged / 0 unavailable。三个 AIC 对象只变化 `source_updated_at`，一个 Cleveland 对象变化 `creation_date`；没有 rights 或 endpoint 变化。每个 changed record 保存 old/new hash、字段 diff 与受影响 work closure。

采集期旧 CSV creator 字符串与当前结构化 creator description 曾产生 43 个格式性假阳性；canonical writer 归一化等价表示后只保留上述 4 个实质变化。收口交叉核对又发现 `download-manifest` 一度保留原始 43/22 计数；五路径 repair 将其绑定到 canonical 4/61/0，并新增 cross-manifest validator，未改变任何媒体字节。

## 下载、质量与 content addressing

40 次 original download 全部成功，0 失败，共 240,328,162 bytes；另有 40 个官方 preview 用于身份/质量对照。Original 均为官方 Cleveland `print.jpg` rendition，保存在 ignored/protected source vault，tracked original bytes=0。质量为 39 `display_high`、1 `display_standard`、0 corrupt/blocked。

40 个 originals 对应 40 个唯一 SHA-256：Batch 内 duplicate physical original=0，M03C content match=0，因此 content-reused original=0 / 0 bytes，content-addressed dedup saved=0 bytes。最大 original 为 `artwork:m09b-candidate-work-cleveland-open-access-151029`，8,219,822 bytes，3400×2787。

累计官方请求 203、响应 262,190,075 bytes、cache hits 80、misses 115。该累计值包含 cold acquisition 与有界 AIC repair；repair build 没有重下已验证 original，也没有重转码 unchanged derivative。

## External IIIF

25 个 AIC 对象全部为 `approved_external_iiif_link_only`；localized=0、manifest-only=0、image download=0。包保存 exact IIIF Image API 2 service identity、documented presentation-manifest identity、provider、object binding、source rule、object rights record和 transport result。

本环境的 `info.json` 探针返回 HTTP 403，后续有界对象刷新出现 TLS EOF。系统没有把瞬时传输失败伪装成 source unavailable，也没有声称取得不存在的 manifest/service response；同阶段 sealed object receipt 仅闭合对象身份与当时权利决定，最终保持外部链接/no-image fallback 且不产生 runtime 外部图像假设。

## Derivatives

复用 M03C canonical recipe `museum-03c-responsive-v1.1.0`：JPEG quality 85、WebP quality 82、320/640/960/1600w、原图不足 1600 时不生成该档。结果为 JPEG 159 + WebP 159 = 318 files / 61,418,168 bytes；320/640/960 各 80，1600 为 78。

所有 derivative 均保留完整画面和纵横比，no crop/upscale/content alteration/watermark removal/AI modification。最大 derivative 为 `derivative:a9229e99…-1600w-jpeg`，1,171,684 bytes，1600×2170。代表性与全包 clean double build 均逐字节一致。

## Attribution、notice 与 withdrawal

Attribution、third-party notice 与 withdrawal 各 65/65 `pass`。每个 work 保留独立 rights/attribution/withdrawal 引用；若未来共享字节，撤回只移除受影响 work reference，不自动删除仍有独立合法引用的字节。Replacement 必须产生新的 immutable package version。

## 正式内部媒体包

Canonical path：`data/reviewed/art/museum-09b-media/batch-01-media-bundle-v1/`

- Package ID：`museum-09b-media:batch-01-media-bundle-v1`
- Content hash：`sha256:d98e3409fb9512054acf532c541e4c4219fcf767564c846f78cfb2439b6c3c50`
- Physical tree：`sha256:39c855c8640271310d448d819a8fc80e6ae2b95852bfe6e5211faffb1f173a5e`
- Manifest SHA-256：`sha256:e08f5d0ff4ddaf7f3c9682bd2f0c8c08a2f469e1583bab32dbb705ea5a11cc64`
- Physical package：336 files / 62,877,348 bytes
- Manifest-declared artifacts：335 files / 62,804,875 bytes；manifest 自身为 72,473 bytes。
- Public status：`internal_media_bundle_not_released`

Registry 仅把 Batch 01 晋升为 `media_bundle_ready` 并绑定上述 hash、65 件处置、original/derivative、attribution/withdrawal 和 drift 统计；Batch 02–10 保持 `registered_not_started`。

## 确定性、测试、CI 与 failure closure

- 最终 targeted gate groups=8；affected unittest=74/74；invalid mutation fixtures=28/28。
- Clean builds=2，full package 与 derivatives byte-identical；p50 157,353.481 ms，p95/max 158,472.525 ms；peak RSS 434,835,456 bytes，100 ms psutil sampling，不是 RUM。
- Unchanged canonical rebuild 8,850.441 ms，复用 40 derivative groups / 61,418,168 bytes，redownload=0、re-encode=0。
- Local full=0；GitHub final-full=0；frontend install/build=0；Playwright=0；screenshots=0。
- Historical releases：4 historical hash-only + current V1 hash-only；validated 5 releases / 1,413 files / 203,140,831 bytes；rebuild=0。
- Actions runs [29841095845](https://github.com/Archmays/Museum-Codex/actions/runs/29841095845) 与 [29842171431](https://github.com/Archmays/Museum-Codex/actions/runs/29842171431) 均为 `phase-scoped/success`。第二次只验证 post-CI drift-metric closure；failed-job rerun=0。两次都跳过 docs-only、final-full、frontend/build/browser、Pages artifact 与 deploy。

七个开发/验收 failure closure 为：CLI import root、AIC 403 状态分类、AIC TLS EOF sealed-receipt fallback、creator 等价表示 drift 归一化、runtime timing 移出 content identity、predecessor validator 的合法 registry progression，以及 post-CI download metrics 交叉闭包。每次只重跑失败对象或依赖闭包，未降低门槛、skip/xfail 测试、重下 Cleveland originals 或重转码已验证 derivatives。

## Storage cleanup

阶段 source vault 为 171 files / 240,845,468 bytes；正式包为 336 files / 62,877,348 bytes；retained phase storage 为 303,722,816 bytes。最大 tracked file 1,171,684 bytes；超过 5 MiB 或 100 MiB 的 tracked files 均为 0。

经路径核实后删除 1,680 个阶段临时/回滚文件、314,266,868 bytes。Benchmark scratch 由隔离临时目录自动清除，但其删除前 bytes 未观测，未加入上述数字。Partial、failed body、decoder/conversion scratch、phase temp、dist 和 Playwright output remaining=0。M03C media、M09A/M09B inputs、历史 releases、official snapshots、formal evidence 与来源不明用户文件删除数均为 0。

## 对抗审查 A–G 与 P3

Reviewer A allowlist/identity、B rights/provenance、C retrieval/security、D fidelity/quality、E IIIF/external-only、F engineering/storage、G public/phase boundary 均 pass；P0/P1/P2=0。

唯一 P3 为 `source-record-drift`。Owner：MUSEUM-09B-RELEASE canonical writer；mitigation：任何公开投影前重查 65 个 stable object IDs、rights 与 exact media/service identities，保留 old/new hash 和最小字段 diff，只重跑受影响 work/media/package closure，不确定时 fail closed；latest review stage：MUSEUM-09B-RELEASE public projection 前。

## 公开与阶段边界

`public/`、当前 V1 candidate 与全部历史 release 逐字节不变；candidate/media public leakage=0，public bundle growth=0。Pages artifact=0、runtime deployment=0、closeout deployment=0；既有 Pages deployment 仍为 `5508931387` / runtime `b36ac365b13ca24afa2d89f6dac6b680036a04af`。

没有生成替代作品、AI 修改艺术作品、analytics、query history 或 geolocation。MUSEUM-09B-RELEASE、MUSEUM-09C 与武器馆均未进入；仅 OD-011 remains open。若用户另行授权，下一阶段可从本包进入 MUSEUM-09B-RELEASE，并先重做 P3 live drift check；本阶段到此停止。
