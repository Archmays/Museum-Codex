---
phase_id: MUSEUM-05B
status: completed
validation_status: pass
report_date: 2026-07-16
runtime_model: not_exposed_by_runtime
runtime_reasoning: not_exposed_by_runtime
branch: main
baseline_commit: 3b86d11e7a2c8749d3463baeeb2f6a4f5bdb1996
implementation_commit: caa3ae77c25ce93bff6807972943924244b567ea
determinism_fix_commit: 946a5e40b6aade6090382488a9a3bc48a280196e
online_verified_runtime_commit: 946a5e40b6aade6090382488a9a3bc48a280196e
input_release_id: release:art-constellation-1.0.0
output_release_id: release:art-gallery-interactions-1.1.0
output_release_hash: sha256:c07330d92d03b41fe57b5e80394e7e89e875945a9d24e7a5c73029b3283a8009
output_release_manifest_sha256: sha256:2c865d0c1bbcba861b53546b70d7bc1a9eafa6276805ab10cfed4bee9fd8dab5
m03c_media_bundle_hash: sha256:3aa84fa7df37c4823cd2cb1f92c7e1843e7dea70b7cfd683528b25698951d565
release_physical_file_count: 266
release_physical_byte_count: 39691590
artwork_count: 44
observation_card_count: 44
artist_tour_count: 12
thematic_tour_count: 6
hero_work_count: 12
visual_detail_region_count: 24
textual_observation_path_count: 4
approved_media_count_before: 31
approved_media_count_after: 31
no_image_count_after: 13
media_retry_status: partial
human_review_dependency: false
public_media_rights_status: pass
tour_routes_ready: true
print_share_status: pass
accessible_equivalence_status: pass
performance_status: pass
real_device_status: not_available
real_assistive_technology_status: not_available
pages_deployment_status: success
pages_url: https://archmays.github.io/Museum-Codex/
actions_run: 29462218848
actions_run_conclusion: success
prior_failed_actions_run: 29461364375
pages_deployment_id: 5466417972
open_decisions_count: 4
open_p3_count: 3
museum_06_recommended: false
museum_06_authorized: false
---

# MUSEUM-05B 深度观察、固定策展导览与互动增强阶段报告

## 1. 结论

MUSEUM-05B 达到 `completed/pass`。正式艺术站现有 44 张双语观察卡、12 条艺术家观察导览、6 条固定主题导览、12 个 hero 选择、24 个结构细节区域、4 条无图 hero 文字路径，以及材料、技法、题材三类观察透镜。作品详情、混合有图/无图 compare、打印与 URL 分享均已上线。

本阶段完成的是深度观察与固定策展导览。没有实现任意 AB 路径、BFS、Yen alternatives、自动推荐、地图、历史因果或算法相似；没有依赖人工逐项审核；没有进入 MUSEUM-06。OD-006、OD-008、OD-009、OD-011 仍保持 open。

运行环境没有暴露模型或 Reasoning 选择，均记录为 `not_exposed_by_runtime`。真实辅助技术与物理触摸设备不可用，记录为 `not_available`，没有伪称真实设备通过。

## 2. 入场、缓存复用与输入边界

入场时 local `HEAD`、`origin/main` 与 live remote main 均为 `3b86d11e7a2c8749d3463baeeb2f6a4f5bdb1996`，工作树干净。受保护输入通过 hash/count 审计：

- M04 release：`release:art-constellation-1.0.0`，`sha256:52835bb9256a9e50c2b73b9ef2e4fb99aa4a40434f20319133fdfb56b09fc462`。
- M03C media bundle：`sha256:3aa84fa7df37c4823cd2cb1f92c7e1843e7dea70b7cfd683528b25698951d565`。
- `package-lock.json`：`sha256:57113cd49cead7c62265df0f4ff37151d8c94ea8697374581b06d3ef9cdafa9d`。
- 基线计数：12 artists、44 artworks、31 approved media、13 no-image、242 derivatives。

因此入场时没有重跑 373 项旧 Python 全套、没有重新下载 31 件 originals、没有重建 242 derivatives、layout 或 search index，也没有重跑 1k/10k/50k benchmark。共享前端输入变化后，只刷新 M04 current-graph 4 profiles × 3 samples 与 M05A 5 profiles × 3 samples；既有 scale evidence 仅做 hash/contract 验证。

## 3. 有上限的 13 件无图媒体补查

补查结果为 `partial`，但这是允许的非阻断终态，不是阶段失败：

- 13 次 official object GET；4 次 official media HEAD。
- 0 media download attempts、0 downloaded bytes、0 new approvals。
- 6 个 AIC object GET 返回 200；4 个 AIC IIIF HEAD 返回 403，另 2 项在 rights gate 停止。
- 7 个 Met 请求已发送，但本次响应字段格式化捕获失败，因此继续使用 2026-07-15 的 official cache 和旧终态证据。
- 并行所有权建立前可能发生最多 2 个重复 probe；它们被明确排除在正式证据之外，之后未再发请求。
- `human_review_dependency=false`，没有创建等待人工复核状态。

批准媒体保持 31，无图保持 13；终态为 7 `metadata_only_after_automated_review`、4 `blocked_source_unavailable`、2 `blocked_rights_conflict`。没有新 media bundle，M03C bundle 与 242 derivative bytes 均未修改。

## 4. Cards、hero、detail regions 与导览

44/44 观察卡均包含中英文标题、3–5 个观察提示、材料/技法/题材语境、日期/机构、直接观察、需要来源支持的解释、当前证据不能证明的内容、Claim → Evidence → Source、rights、image availability、无障碍版本、review 与 release 版本。13 件无图作品不含肉眼细节任务或假 placeholder。

12 个 hero 选择使用确定性权利、分辨率、metadata/context 完整度和稳定 ID 规则：8 个 `visual_detail_path`，4 个 `textual_observation_path`。8 个 visual hero 各有 3 个区域，共 24 个。区域只命名为“细节区域 1/2/3 / Detail region 1/2/3”，不生成语义标签。

区域算法使用 edge density、local contrast、entropy、saliency、minimum area、overlap control 与 border exclusion。首次 Ubuntu 重建确认 24 个区域的 ID、坐标、顺序完全一致，但 JPEG 解码路径令 61 个持久化指标浮点值出现最多约 `4.49e-4` 差异。关闭修复把算法契约升至 `1.0.1`，禁用 decoder SIMD，并以 `floor_0.01` 固定发布指标；源 asset SHA/dimensions、坐标和选择没有变化。

六条固定主题导览为：

1. 纸、墨与复制实践 / Paper, Ink, and Reproduction
2. 纸面线条 / Line on Paper
3. 人物、肖像与观看 / Figures, Portraits, and Looking
4. 照护、成对人物与日常相遇 / Care, Pairing, and Everyday Encounter
5. 支撑物与表面：画布、木板与纸 / Support and Surface: Canvas, Panel, and Paper
6. 跨时空的山水、水与神圣叙事 / Landscape, Water, and Sacred Narrative Across Time

每条主题导览包含 6 位艺术家、6 件作品、至少 2 个地区/时期与 2 件 metadata-only 路径；全部是固定 reviewed-context 并置，不是路径搜索或自动推荐。12 条艺术家导览的 material/technique/subject focus 分布为 4/4/4。

## 5. Release 物理闭包

新 release 为 `release:art-gallery-interactions-1.1.0`，predecessor 精确为 `release:art-constellation-1.0.0`。它采用 immutable overlay：263 个 predecessor children 逐字节复用，只新增 `interaction-index.json` 与 `media-retry.json`，旧 release 未覆盖。

- Release content hash：`sha256:c07330d92d03b41fe57b5e80394e7e89e875945a9d24e7a5c73029b3283a8009`。
- Manifest file SHA：`sha256:2c865d0c1bbcba861b53546b70d7bc1a9eafa6276805ab10cfed4bee9fd8dab5`。
- Interaction index SHA：`sha256:f93d9dacb71d4255f36876e2557ec7783ee3febf0584c3fde941ca26ec302e23`。
- 目录 266 files / 39,691,590 bytes；manifest 登记 265 children。

Canonical dispatch、schema、references、exact files/bytes/hashes、rights/notices/attributions、withdrawal mapping、source permissions、no private/raw、no blocked media、no hotlink、no algorithmic relation 与 no causal wording 均通过。确定性重建在 Windows、外部 SIMD override 与 Ubuntu Actions 上闭合。

## 6. UI、透镜、compare、打印与分享

新增 `#/art/tours` 与 `#/art/tours/:tourId`，并增强艺术首页、artist gallery、artwork detail 与 compare。三类透镜严格来自正式 contexts：material 7 entries、technique 9、subject 11；共同题材不被转写为影响。

Compare 现在包含双方观察卡、三类透镜、shared/different fields、来源并置、image/no-image mixed compare、独立 detail/zoom 状态、明确 reset、print 与正式 URL state。没有 AI similarity score、影响判断、优劣评分或“最佳对比”。

单作品、艺术家导览、主题导览与 compare 均有 print mode。打印只使用批准的小图或明确无图状态，包含 metadata、prompts、sources、rights/attribution、release/version 和页面 URL；黑白与 forced colors 可辨识。分享状态只含正式 ID 与允许的 view/region/lens 参数，不带 tracking，不上传数据。

## 7. 无障碍与无图等价体验

自动化覆盖 native controls、键盘、focus、live region、detail navigator、touch targets、screen-reader labels、事实型 alt、image/no-image 等价、reduced motion、forced colors、low bandwidth、360/390 无溢出、打印、compare headings 与 invalid route。低带宽默认不创建图像；print 不加载大图。

13 件无图作品保留完整 metadata、证据型观察卡、材料/技法/题材、artist/thematic tour、compare、sources/rights、print/share 与清晰无图原因；不显示假图，也不要求视觉细节任务。

## 8. 性能与 bundle

| 门禁 | 实测 | 上限 |
|---|---:|---:|
| Home gzip | 98,891 B | 103,618 B |
| Home 相对 98,684 baseline | +0.21% | +5% |
| Tours route total gzip | 110,039 B | 307,200 B |
| Tours initial JSON gzip | 86,349 B | 122,880 B |
| Artwork interaction assets | 26,670 B | 184,320 B |
| Interaction JSON | 22,780 B | 122,880 B |
| Detail-region data | 1,918 B | 30,720 B |

受控浏览器证据为 first interactive `1033.6 ms`、LCP `820 ms`、CLS `0`、interaction proxy `121.3 ms`，均 pass。初始不加载全部 tour 图片，analytics/history-storage 扫描命中 0。

Pages 公网 composite test 的两次首访 first-interactive 观察为 `3319.7 ms` 与 `2613 ms`；独立 tours smoke 的 ready 观察为 `1533 ms`。这些值受当前地理位置、TLS/CDN 与公网条件影响，不替代受控门禁，作为 P3 保留。线上功能、字节、HTTP 与运行时错误闭包仍通过。

## 9. Targeted 与 final tests

主要 targeted gates：

- M05B Python：最终 14/14。
- Governance：65 schemas、8 valid fixtures、22 expected-invalid fixtures、1 physical bundle；对应 50 个记录化检查均 pass。
- Targeted Vitest：31/31；本地化修复后 5/5；另一个 37-pass selection 与前述重叠，不重复计数。
- M05B Playwright：6 个唯一场景；初次 3 pass / 3 fail，精确修复闭包后全部通过。
- Dedicated controlled performance scenario：1 pass。

Final candidate 全套仅在本地执行一次：

- Full Python：1 次，386 tests / `1308.728 s`。初次暴露 6 个 contract-enumeration/allowlist failure；没有再跑第二次 386 全套，只运行 schema/media 13、M05A budget 1、M05B release 13、leakage/preflight 5 的精确闭包，均 pass。
- Full frontend：1 次；lint、strict typecheck、Vitest 64/64、production build 均 pass。
- Performance-runner contracts：10/10。
- Full local E2E：1 次，先 14/17；精确重跑 3 项得 2/3，再只跑最后 1 项并通过，最终闭合 17/17。

成功 Actions run 又按正式 CI 契约执行一次全套：Python 389 tests / `1272.931 s`。首次失败 run 在确定性 diff 处停止，没有到达全套测试。成功 CI 的 Python 步骤为 21m13s，全部 workflow 为 31m10s；CI E2E 为 40s。

持久 Playwright 时长：targeted initial 104.133s、targeted final closure 76.135s、targeted performance 75.227s、full candidate 28.489s、3-test closure 14.639s、1-test closure 6.902s。可确认的本地实施证据窗口至少为 2h23m07s；首次 CI 失败为 5m35s，确定性诊断至修复提交为 12m58s，成功 Actions/Pages 为 31m10s，随后线上验证至证据时间为 7m41s。完整总时长没有更细粒度计时器，因此不虚构精度。

## 10. 对抗性审查 A–F 与 P3

- A pass：观察/解释/不可证明边界、翻译、source/evidence、无虚构视觉细节、无因果或文化泛化。
- B pass：12 artist tours、6 thematic tours、非机械 focus 分布、image/no-image 等价、无 AB path 抢跑。
- C pass：补查有界、31/13/242 不变、rights/attribution/withdrawal、无 blocked/hotlink。
- D automated pass：cards/tours/detail/compare/print、keyboard/SR semantics/touch emulation/low bandwidth/forced colors/reduced motion；真实 AT/设备为 `not_available`。
- E pass：cache reuse、deterministic rebuild、release closure、budgets、runtime errors 与跨平台指标关闭。
- F pass：`main`、Actions、Pages、旧/新 routes、Git scope；无 M06、analytics、map、search dependency 或其他分馆修改。

Open P0/P1/P2 = 0。Open P3 = 3：

1. 继承的 supplemental 1k graph FPS median 为 27，低于 informational 30；正式 scale gate 仍 pass。Owner：frontend performance；最晚在未来另行授权的 scale expansion 前处理。
2. 真实 AT 与物理触摸设备不可用。Owner：accessibility QA；在未来明确要求真实设备认证的阶段前安排。
3. 当前公网首访 tours latency 高于受控 first-interactive 目标。Owner：web performance；保留 cold-request 证据，未来有单独公网性能要求时再做无 RUM/无 analytics 的地理采样。

## 11. Git、Actions、Pages 与在线证据

工作只在线性 `main` 上进行，没有 branch、worktree 或 PR。

- 实现提交：`caa3ae77c25ce93bff6807972943924244b567ea`。
- 首次 run `29461364375` 在 Ubuntu M05B byte diff 失败，deploy 被正确阻断；这条失败和根因未被删除或隐藏。
- 确定性修复提交：`946a5e40b6aade6090382488a9a3bc48a280196e`。
- 成功 run `29462218848`：build job `87507940926` 与 deploy job `87512038067` 均 success，无失败步骤。
- Pages deployment `5466417972`：success，URL `https://archmays.github.io/Museum-Codex/`。

线上 root、manifest、interaction index 与 media retry 均 HTTP 200；三份 release 文件的 bytes/SHA 与本地完全一致。CI production artifact E2E 17/17 pass；线上六个 inherited scenarios、五个 M05B non-performance scenarios 与独立 tours smoke pass，console、failed request、external request、HTTP error 均为 0。详情见 `docs/qa/museum-05b/online-evidence.json`。

包裹本报告的 closeout commit 只增加 `docs/` 证据，不改变 `public/`、`src/`、release、schema、test 或 workflow 输入；它使用 GitHub 原生 `[skip ci]` 指令，避免对已经成功部署且逐字节在线验证的 runtime 候选再执行一次无影响的全量 pipeline。线上已验证 runtime commit 因此保持 `946a5e40b6aade6090382488a9a3bc48a280196e`。

## 12. Screenshots

- `docs/qa/museum-05b/screenshots/tours-index-desktop.png` — 1440×3788。
- `docs/qa/museum-05b/screenshots/artwork-detail-region-desktop.png` — 1280×5949。
- `docs/qa/museum-05b/screenshots/compare-mixed-desktop.png` — 1440×7706。
- `docs/qa/museum-05b/screenshots/no-image-observation-mobile.png` — 360×9341。
- `docs/qa/museum-05b/screenshots/textual-tour-print-mobile.png` — 390×4356。

截图在本地正式 candidate 上生成并做视觉检查；线上同一 release 字节与同一 Actions 构建已通过 live browser closure。精确 SHA 记录在 online evidence。

## 13. Storage cleanup 与下一阶段

关闭前删除了五个经绝对路径校验、且位于 workspace 内的生成目标：`dist`、`output`、`tmp/m05b-seed1`、`tmp/m05b-seed2`、`tmp/museum-05b-final-rebuild`，合计 `209,495,583 bytes`；未触碰旧 MUSEUM-AUTO-01/M05A 临时证据或受保护数据。

本报告不建议自动进入 MUSEUM-06：M05B 的固定导览目标已完成，MUSEUM-06 需要新的明确授权与独立验收边界。`museum_06_authorized=false`，本阶段到此停止。
