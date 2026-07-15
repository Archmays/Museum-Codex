---
phase_id: MUSEUM-05A
status: completed
validation_status: pass
report_date: 2026-07-15
runtime_model: not_exposed_by_runtime
runtime_reasoning: not_exposed_by_runtime
implementation_commit: recorded_by_enclosing_git_commit
public_release_id: release:art-constellation-1.0.0
public_release_hash: sha256:52835bb9256a9e50c2b73b9ef2e4fb99aa4a40434f20319133fdfb56b09fc462
m03c_media_bundle_hash: sha256:3aa84fa7df37c4823cd2cb1f92c7e1843e7dea70b7cfd683528b25698951d565
artist_index_count: 1
artist_page_count: 12
artwork_route_count: 44
approved_media_artwork_count: 31
no_image_artwork_count: 13
runtime_derivative_count: 242
runtime_derivative_bytes: 35907176
zoom_status: pass
compare_status: pass
browser_e2e_status: pass_5_of_5
performance_status: pass_5_of_5
real_device_status: not_available
real_assistive_technology_status: not_available
pages_deployment_status: deferred_to_museum_auto_01_final_push
---

# MUSEUM-05A 首版数字艺术家展厅阶段报告

## 1. 结论

MUSEUM-05A 达到 `completed/pass`。首版数字展厅在 MUSEUM-04 正式静态 release 上实现艺术家索引、12 个艺术家展厅、44 个作品详情、基础放大观察和双作比较。31 件通过权利门禁的作品使用正式本地衍生图；13 件 metadata-only 或 blocked 作品保持完整无图卡、元数据、权利状态和官方来源。没有进入 MUSEUM-05B、MUSEUM-06、武器馆或生物馆。

运行时没有暴露模型或 Reasoning 选择，记录为 `not_exposed_by_runtime`。本阶段没有单独 push 或部署；Pages 延后到 MUSEUM-AUTO-01 的最终统一门禁。

## 2. 正式输入与路由闭合

消费的唯一数据源为 `release:art-constellation-1.0.0`，content hash 为 `sha256:52835bb9256a9e50c2b73b9ef2e4fb99aa4a40434f20319133fdfb56b09fc462`，并绑定 M03C bundle hash `sha256:3aa84fa7df37c4823cd2cb1f92c7e1843e7dea70b7cfd683528b25698951d565`。

实现路由：

- `#/art/artists`：12 位艺术家，按正式 release 顺序展示，支持姓名、时期和图像状态筛选。
- `#/art/artists/:artistId`：12/12 可达；每位展示 2–4 件正式作品、经审核简介、时间线、媒材、语境、来源、rights 和 C 级相关艺术家。
- `#/art/artworks/:artworkId`：44/44 可达；展示机构、登录号、年代、材料、技法、题材、官方来源、许可、署名和逐条 Claim → Evidence → Source 链。
- `#/art/compare`：两件不同作品的 URL 状态、并置元数据、独立 zoom、交换和观察提示；不产生 AI 相似分数或影响判断。

未知 ID 和不完整 release 均 fail closed。Public runtime 不调用外部 API。

## 3. 媒体、rights 与无图状态

媒体分布保持正式 M03C 决定：31 `approved_self_hosted`、7 `metadata_only_after_automated_review`、4 `blocked_source_unavailable`、2 `blocked_rights_conflict`。运行时 blocked media 为 0，external delivery 为 0。

242 个 JPEG/WebP derivative 共 35,907,176 bytes，只属于 31 件批准作品。列表/展厅使用 responsive lazy thumbnails；作品观察使用批准 JPEG `srcset`/`sizes`，按浏览器实际 `currentSrc` 对应的 manifest 像素宽限制 zoom，绝不超过所选文件自然像素。390px 正常带宽抽测选择 320/640 候选且没有请求 1600w；desktop 观察路由可使用批准的 1600w 大图并通过 125% 按钮、150% 键盘缩放。

低带宽模式在用户明确触发前不创建作品 `<img>`。Decode failure 切换为可访问无图状态，并保留元数据、rights、withdrawal 和官方来源。没有 placeholder 冒充作品、生成替代图、crop、upscale、去水印或远程 tile。

## 4. 无障碍与交互

- Artist index/list/grid、gallery、detail、zoom 和 compare 均可用键盘完成。
- SPA route 加载后聚焦 `main`；skip link 保持有效。
- Zoom 支持按钮、`+/-/0`、箭头平移和 pointer/touch pan；两个 compare zoom 的状态与 ARIA ID 相互独立。
- 360/390、mobile stack、forced colors、reduced motion、可见焦点、事实型本地化 alt、非颜色唯一状态和无横向溢出均通过自动化。
- JS-off 页面提供数字展厅、44 件详情、zoom/compare 需要 JavaScript 的基本说明。

真实 assistive-technology 和物理设备均不可用，准确记录为 `not_available`；自动化没有被描述成真实 NVDA/JAWS/VoiceOver/TalkBack 或触摸设备 pass。

## 5. 构建预算

`docs/qa/museum-05a/bundle-budget.json` 的 `status=pass`，input hash 为 `sha256:1f86a4871577bbc58425069a4efc2c5e17dff4a5de974b34b71f12fd191ec8d8`：

| 门禁 | 实测 | 上限 |
|---|---:|---:|
| Home gzip | 98,678 | 102,942 |
| Home 相对基线增长 | 10.236% | 15% |
| M04 constellation total gzip | 96,262 | 460,800 |
| Gallery initial JSON gzip | 63,263 | 131,072 |
| Artist index total gzip | 81,642 | 460,800 |
| Artist gallery total gzip | 82,119 | 460,800 |
| Artwork detail total gzip | 82,146 | 460,800 |
| Compare total gzip | 84,155 | 460,800 |

Gallery shell 和四个 page chunk 均保持 lazy，不进入 home initial closure；home 对 242 个 derivative locator 的嵌入数为 0。

## 6. Controlled-lab 性能

`docs/qa/museum-05a/performance.json` 绑定 implementation hash `sha256:6e46380dbcd207af68bf077825a122179652cdc413a2aaf510339a357413abb9`，五个 profile 各三次采样并由独立 validator 重算：

| Profile | First interactive median | LCP median | CLS p95 | Images p95 | Image bytes p95 | Transfer p95 |
|---|---:|---:|---:|---:|---:|---:|
| Desktop artist index | 1,017.0 ms | 780 ms | 0 | 6 | 83,878 | 271,597 |
| Mobile index / low bandwidth | 2,505.7 ms | 1,984 ms | 0 | 0 | 0 | 187,719 |
| Desktop artwork detail | 951.4 ms | 828 ms | 0 | 1 | 404,230 | 667,535 |
| Mobile artwork detail / Fast 4G | 1,807.7 ms | 1,812 ms | 0 | 1 | 74,246 | 337,551 |
| Mobile compare / low bandwidth | 1,829.4 ms | 1,828 ms | 0 | 0 | 0 | 190,533 |

所有 profile 的 overflow、console warning/error、failed request、HTTP error 和 external request 为 0。首轮 CLS 失败最高为 0.8522；修复加载视口预留和详情加载态宽度后重测为 0，没有放宽 0.1 门禁。

这些是受控 Chromium lab，不是 RUM 或真实设备数据。

## 7. 测试和截图

- M05A formal validator：12 artists / 44 artwork routes / 31 approved / 13 no-image / 242 derivatives，pass。
- M05A Vitest 分片及正式 release loader 回归：pass。
- Performance validator 正/负测试：13/13 pass。
- Build budget 正/负测试：4/4 pass。
- Playwright：5/5 pass，22.1 秒；覆盖 12 artist routes、44 artwork routes、focus、zoom、compare、decode failure、390/360、forced colors、reduced motion、runtime network 和 overflow。
- 六张本地截图位于 `docs/qa/museum-05a/screenshots/`，包含 artist index、artist gallery、artwork detail、desktop/mobile compare 和 forced-colors。

完整 A–F 审查见 `docs/qa/museum-05a/adversarial-review.md`。最终全仓 clean-install、Git push、Actions、Pages 和 online screenshots 属于 MUSEUM-AUTO-01 FINAL，不能由本地阶段证据替代。

## 8. Remaining P3

1. 44 个作品路由在低带宽模式全部遍历；正常带宽图像解码与 responsive candidate 对批准作品做代表性抽测而非 31/31。
2. 没有真实触摸设备或 AT session；环境可用时可补充，不阻断当前静态 release。
3. Runtime 动态 URL 不能只由源码正则证明；当前由同源 loader、正式 manifest 和浏览器零外部请求共同闭合。

已知未修复 P0/P1/P2 为 0；MUSEUM-05A 阶段门禁为 `completed/pass`。
