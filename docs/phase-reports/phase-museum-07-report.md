---
phase_id: MUSEUM-07
status: completed
validation_status: pass
report_date: 2026-07-17
runtime_model: not_exposed_by_runtime
runtime_reasoning: not_exposed_by_runtime
branch: main
baseline_commit: 6bb66328f75d93aeec5c1661d4d89987120cfd63
implementation_commit: d5ab3aa121a019b3b51439627d004f4dd3ed0d7b
ci_fix_commits: [f008e3084e94d0431b816506bc6d87b279d1d4da, e571709f02a3028bb8db76951076d377472c7428]
online_verified_runtime_commit: e571709f02a3028bb8db76951076d377472c7428
input_release_id: release:art-pathways-1.2.0
input_release_hash: sha256:8a773b00b37f025520e7ea4ef7a7ebc9cd3e0d3f1298925d3c20be29b28fe6f3
input_release_manifest_sha256: sha256:9eb27757c4888784bc79727ba7ce95179e313472a75b99a4b2098d3e4a6fb2dc
output_release_id: release:art-time-place-1.3.0
output_release_hash: sha256:aa969f48fd152301a66ee4f4841392b36f271bbca8537897484bc70c6ece718f
output_release_manifest_sha256: sha256:6022063a0e2620e60d7e1adac8e5b0ea8624e2b4790941a3941546f7e74b4c7c
od_006_status: closed
open_decisions_count: 3
basemap_source: natural_earth
basemap_scale: 1:110m
basemap_license: public_domain
external_tile_provider: none
map_token_required: false
renderer: MapLibre GL JS
renderer_version: 5.24.0
renderer_stability: stable
artist_count: 12
place_identity_count: 23
artist_episode_count: 36
artwork_creation_place_count: 0
holding_institution_count: 2
list_only_episode_count: 12
tgn_adapter_status: pass
human_review_dependency: false
map_route_ready: true
timeline_ready: true
place_list_ready: true
accessible_equivalence_status: pass
performance_status: pass
real_device_status: not_available
real_assistive_technology_status: not_available
external_runtime_request_count: 0
user_geolocation_used: false
analytics_used: false
pages_deployment_status: success
pages_url: https://archmays.github.io/Museum-Codex/
actions_run: 29557600054
actions_attempt_count: 3
pages_deployment_id: 5484885638
online_release_file_count: 293
online_release_matched_bytes: 41339919
online_screenshot_count: 14
museum_08_entered: false
---

# MUSEUM-07｜艺术时空地图阶段报告

## 1. 当前结论

MUSEUM-07 已完成并达到 `completed/pass`：本地最终候选、第三次 Actions、Pages、线上新旧路由、14 张线上截图和 293 个 release 文件逐 bytes/SHA 闭包均通过。OD-006 已关闭，输出 immutable overlay `release:art-time-place-1.3.0`。没有进入 MUSEUM-08。

运行环境没有暴露模型或 Reasoning 选择，因此均记录为 `not_exposed_by_runtime`。真实辅助技术和物理触摸设备不可用，记录为 `not_available`，没有伪称认证通过。

## 2. 入场、范围与缓存复用

- 基线为 `6bb66328f75d93aeec5c1661d4d89987120cfd63`，输入 release 为 `release:art-pathways-1.2.0`，content hash 与 manifest SHA 均精确闭合。
- 仅在 `main` 线性工作，没有 branch、worktree 或 PR；研究范围严格限定 12 位艺术家和 44 件作品。
- 复用 M03C 的 31 件 self-hosted media 与 242 derivatives、M04 星海、M05A 展厅、M05B 导览和 M06 路径数据。没有重新下载、转码或生成媒体。
- M04 1k/10k/50k 图形基准和 M06 synthetic path benchmark 没有重跑，只验证封存 evidence hash。失败后只运行失败项及依赖闭包。

## 3. OD-006、Natural Earth 与 renderer

OD-006 已通过 D-0030 和 ADR-0010 关闭。方案为 Natural Earth 官方 `1:110m` land/coastline/lakes，加 exact-pinned MapLibre GL JS `5.24.0`；运行时只使用本地/inline style 和本地 GeoJSON。

Natural Earth 物理 release 为 `5.1.0`；主题版本分别为 land `4.0.0`、coastline `4.1.0`、lakes `5.0.0`。原始官方 ZIP：

- `ne_110m_land.zip`：69,700 B，`sha256:1926c621afd6ac67c3f36639bb1236134a48d82226dc675d3e3df53d02d2a3de`；
- `ne_110m_coastline.zip`：85,352 B，`sha256:664449b39070027e882abb295974d182afec18ca21107273d17e9e8bf6f64817`；
- `ne_110m_lakes.zip`：23,622 B，`sha256:f2eed3c738a93010770acb0ba44273ea6a83b053641588bc902d9d6fd1cdafcb`。

转换采用 WGS84、无 simplification、无 jitter、移除 properties、stable geometry-hash ordering，转换器为 pyshp `2.3.1`。公开 basemap bundle hash 为 `sha256:a2031daa312021c605cd8f24f357ff1579e96ea02419ee400c3caa060da953b2`，显示 `Made with Natural Earth`。

MapLibre provenance、MIT license、npm/GitHub stable 状态、bundle 和安全已核验。版本为稳定 `5.24.0`，没有使用 `6.0.0-*` prerelease。无 CDN、remote worker/style/glyph/sprite/image、tile provider、token、geocoder、telemetry、geolocation、terrain、satellite、3D building、globe、rotation 或 route line。

## 4. Getty TGN、地点身份与研究终态

新增 production adapter `getty_tgn`，使用 Getty 当前 JSON/RDF LOD 和 persistent TGN IDs/URIs，保留 preferred/alternate/historical names、place type、broader hierarchy、reference coordinates 和 provenance。Getty 许可绑定 ODC Attribution 1.0；已停止的 XML service 被显式禁止。

每个 unique TGN ID 只获取一次并按 ID/hash 缓存。ULAN 地点 assertion 只有在 TGN identity 与 Claim → Evidence → Source 闭合后才能发布；Wikidata 只作 discovery/crosswalk，不作为唯一 episode 证据。

正式地点 23 条：21 `verified_public`、2 `verified_list_only`。地点坐标精度为 20 `city_centroid`、1 `regional_centroid`、2 `unknown`。Getty 对 Allegheny City 无可用坐标，对 Mexico City 返回上游 malformed coordinate；两者均保持 `unknown/list-only`，没有猜测坐标。

## 5. Artist place-time episodes

共 36 条 verified artist episodes，12 位艺术家各 3 条：Albrecht Dürer、Francisco de Goya、Henry Ossawa Tanner、José Guadalupe Posada、Julia Margaret Cameron、Käthe Kollwitz、Katsushika Hokusai、Kitagawa Utamaro、Mary Cassatt、Raja Ravi Varma、Shen Zhou、Vincent van Gogh 均为 `3`。

类型分布为 birth 12、death 12、documented_activity 7、residence 2、publication_or_print_activity 2、studio 1。episode 地点精度为 31 `city_centroid`、2 `regional_centroid`、3 `unknown`；release 状态为 24 `verified_public`、12 `verified_list_only`。

每条记录包含时间精度、地点精度、Claim/Evidence/Source、confidence/uncertainty、public wording、what it proves/does not prove 和状态历史。没有 inferred travel、movement line、guessed coordinate、等待人工审核或 pending user approval。

## 6. 历史命名、创作地与当前馆藏

历史名称按 episode 日期优先，现代名称只作 secondary context。正式区别包括 Edo/Tokyo、Königsberg/Kaliningrad、Ceylon/Sri Lanka、Calcutta/Kolkata、Travancore/Kilimanoor；现代 jurisdiction 不替代复杂历史语境。

44 件作品的 creation-place records 全部为 `not_asserted`：现有稳定正式来源没有明确闭合创作地，因此没有从艺术家 residence、作品标题/subject 或当前馆藏推断。两条 current holding-institution records 作为独立 layer 发布，明确不证明作品创作地或历史活动地点。

## 7. Immutable release 与物理闭包

输出 `release:art-time-place-1.3.0` 的 predecessor 精确为 `release:art-pathways-1.2.0`。旧 release 目录保持逐字节不变；新 overlay 物理闭包为 293 files、41,339,919 B。

- content hash：`sha256:aa969f48fd152301a66ee4f4841392b36f271bbca8537897484bc70c6ece718f`
- manifest SHA：`sha256:6022063a0e2620e60d7e1adac8e5b0ea8624e2b4790941a3941546f7e74b4c7c`
- source-product hash：`sha256:709563279b7df2fcec9e644350dd7a1e0e57a431d5b3e8f00af649578b71e2b0`

Canonical JSON、Draft 2020-12 schemas、canonical dispatch、concrete ID/type、predecessor、references、exact files/bytes/hashes、TGN/ULAN/Natural Earth/MapLibre notices、withdrawals、rights、source permissions 和 deterministic rebuild 均通过。release 不含 private leads、remote URL、token、modern-boundary layer、route line 或未核验地点。

## 8. 路由、等价体验与隐私

新增 `#/art/map`，公开标题为“艺术时空地图 / Art Across Time and Place”，并从 Art landing、artist gallery、artwork detail、constellation、AB paths 和 fixed tours 提供入口。

Map、timeline 和 place table 共享同一 state/filter/selection model，支持 artist、place、episode type、year range、region、precision、layer、view 和 episode 的 allowlisted URL 状态。地图含 24 个可绘制 episode 的同步 DOM marker navigator；timeline/table 覆盖全部 36 条，包括 12 条 list-only。

现代底图轮廓不等于历史政治边界；时间顺序不等于旅行路线；current holding institution 不等于创作地；未显示地点不等于现实中不存在活动；地图不是完整传记。没有用户位置、analytics、tracking、访问历史、地图历史、在线 geocoder 或运行时 API。

## 9. Accessibility 与 fallback

Native filters、range + numeric year inputs、keyboard episode navigator、focus management、live region、DOM marker list、uncertainty/precision text、44 px targets、forced colors、reduced motion、360/390 no overflow 和 print-friendly timeline/table 均通过自动化。

Low bandwidth 默认 list；WebGL unavailable、context loss、forced colors 或 renderer error 自动切换到等价 timeline/list，保留 filters、selection 与 URL，不白屏、不暴露内部错误。真实 AT/物理设备为 `not_available`。

## 10. 性能与 bundle

| 门禁 | 实测 | 上限 |
|---|---:|---:|
| Home gzip | 100,059 B（相对 M06 +0.673%） | 101,377 B |
| Map route total gzip | 532,296 B | 563,200 B |
| Renderer JS/CSS closure gzip | 292,330 B | 409,600 B |
| Basemap GeoJSON gzip | 174,103 B | 256,000 B |
| Place/timeline/filter data gzip | 20,876 B | 102,400 B |
| Desktop first interactive | 585.931 ms | 1,800 ms |
| Mobile first interactive | 121.596 ms | 2,500 ms |
| Low-bandwidth list first interactive | 994.197 ms | 2,000 ms |
| Filter p95 | 78.9 ms | 150 ms |
| Marker selection p95 | 28.7 ms | 100 ms |
| Mobile heap increment | 1,378,028 B | 41,943,040 B |
| CLS | 0 | 0.1 |
| External runtime requests | 0 | 0 |

没有 media preload。受控性能场景在独立、单 worker、新浏览器进程中运行，避免功能流程污染样本。

## 11. Tests 与执行次数

Targeted M07 evidence 共 76 个 unique assertions/scenarios：adapter 31、M07 Python 30、M07 Vitest 11、M07 Playwright 4。

本地最终候选：统一 Python 448/448（1,649.486 s）、Vitest 89/89、lint、strict typecheck、production build、build/resource scan、repository safety、release/source/rights/security/leakage validators 和完整 Playwright 26/26 全部通过。完整 Python runner 曾因本地工具 15/30 分钟超时中断两次，随后使用同一测试闭包完成一次 448/448；没有把中断记成通过。Production build 共执行 4 次：一次候选与三次失败依赖闭包。完整本地 E2E 执行 1 次并通过 26/26。

第一次远端 Actions `29555378992` 在最终浏览器 QA 中 22/23 功能场景通过；唯一失败是旧 M05B 测试在 hash 懒加载后立即 reload，自行取消两个同源 JS chunk。产品、M07 3/3、三个隔离性能场景和其余门禁均通过。`f008e30` 只增加 route ready、invalid heading 和 network-idle 等待，失败项本地精确闭包 1/1 通过；零失败请求门禁未放宽。

第二次 Actions `29556568778` 再次通过浏览器前全部门禁和 22/23 功能场景，但 Linux 的同文档 hash transition 没有稳定进入 invalid route。`e571709` 将该项改为同一 touch context 中的新页面冷加载 invalid route，再 reload 并检查共享 storage；两页面分别维持零 console/失败请求。该失败项本地连续 3/3 通过，没有修改产品、timeout、allowlist 或发布数据。

## 12. 对抗审查 A–F 与 P3

A–F 全部 pass，P0/P1/P2=0。Open P3=4：

1. Getty TGN 对 Allegheny City 无坐标、Mexico City 坐标 malformed；保持 unknown/list-only。
2. 44 件作品暂无明确稳定 creation-place source；保持 `not_asserted`。
3. 真实 AT 与物理设备不可用；保留自动化等价证据，最晚在未来明确要求认证的阶段复核。
4. 公网 cold latency 受 CDN/TLS/地理影响且项目无 RUM/analytics；以受控实验室预算为 release gate，只记录 bounded live smoke。

完整 findings、owner、缓解和最晚复核点见 `docs/qa/museum-07/adversarial-review.md`。

## 13. Git、Actions、Pages 与线上证据

实现提交为 `d5ab3aa121a019b3b51439627d004f4dd3ed0d7b`；CI 浏览器竞态精确闭包为 `f008e3084e94d0431b816506bc6d87b279d1d4da` 与线上 runtime `e571709f02a3028bb8db76951076d377472c7428`。

Actions [29557600054](https://github.com/Archmays/Museum-Codex/actions/runs/29557600054) success：Python 448/448、Vitest 89/89、lint、strict typecheck、build、release/source/rights/security/leakage、3/3 隔离性能和 23/23 功能/fallback/no-script 全部通过。Pages deployment `5484885638` success。

线上 M07 map/timeline/list 为 3/3；core/predecessor routes 初次 5/6，唯一 Art landing → constellation 公网冷加载超过测试的 5 秒 assertion，失败项原样重跑在 4.8 秒内 1/1 通过。14 张线上截图完成，console/external/failed request/HTTP error 为 0。公网一次冷 map observation 为 2,566.743 ms，不套用 controlled-local 1,800 ms 门槛，保留为 P3 观察值。

`release:art-time-place-1.3.0` 在线 293/293 files、41,339,919 B 全部一次请求匹配，manifest SHA 和 content hash 与本地一致；tree hash 为 `sha256:1d02c63753830ad04a95ce11654c4527b0a3fb921e4096f5bed14415ef5370f5`。完整机器证据见 `docs/qa/museum-07/online-evidence.json`。

本报告与 online evidence 的 closeout commit 不在文件内自引用；它会触发一次只增加证据文档的最终 Pages workflow。最终 commit、run、deployment 与部署后 smoke 由 Git history 和 Codex 最终回复记录。

## 14. Storage cleanup 与阶段边界

实现 Git tree 净增长 43,698,470 B；忽略的官方 source vault 为 27 files / 769,187 B；实现与源缓存合计保留 44,467,657 B。正式 release 为 293 files / 41,339,919 B；线上截图另保留 14 files / 5,461,886 B，配套 Playwright JSON 与 online evidence 作为发布证据。临时下载解包、`dist`、`output`、server logs 和 Playwright traces 在候选完成后删除。

OD-006 已关闭；open decisions 仅 OD-008、OD-009、OD-011，共 3。没有关闭 OD-008/009，没有进入 MUSEUM-08。
