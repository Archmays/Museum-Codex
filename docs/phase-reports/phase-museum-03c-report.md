---
phase_id: MUSEUM-03C
status: completed
validation_status: pass
runtime_model_reasoning: not_exposed_by_runtime
m03b_package_hash: sha256:1f0f00a0d7f6162fcb0d716e6b86fbcfe42a4e04a0422d7c1c0df63b70c97b86
m03b_graph_hash: sha256:58fe40930ab6f0e84019bbb0c3f378a2e73d7f3fbd4f810a66aa78f0481d1dd3
artworks_automatically_reviewed: 44
approved_self_hosted_artworks: 31
approved_external_delivery_artworks: 0
metadata_only_after_automated_review: 7
blocked_rights_conflict: 2
blocked_identity_conflict: 0
blocked_quality_failure: 0
blocked_source_unavailable: 4
original_downloads: 31
original_bytes: 75611836
derivative_files: 242
derivative_bytes: 35907176
human_review_dependency: false
bundle_content_hash: sha256:3aa84fa7df37c4823cd2cb1f92c7e1843e7dea70b7cfd683528b25698951d565
ledger_sha256: sha256:e03ef898662aa528762bd3112c9893c1f455acb65473d1e73e3da5374fbbd218
---

# MUSEUM-03C 自动媒体采集与验证阶段报告

报告日期：2026-07-15（Asia/Shanghai）。运行时没有暴露模型或 Reasoning 选择，记录为 `not_exposed_by_runtime`。

## 1. 结论

MUSEUM-03C 达到 `completed/pass`。44/44 件 MUSEUM-03B 正式作品均经过自动官方元数据复核、身份与对象级权利交叉核验、替代来源检索（适用时）和一个明确终态；31 件作品取得并验证可自托管原图，超过 28 件质量目标。所有进入 tracked bundle 的媒体均有真实字节、SHA-256、解码/质量证据、父记录、衍生记录、许可规则、署名、notice 和逐文件撤回映射。没有 `waiting for manual review`、`pending curator` 或 `unknown passed`。

## 2. 输入门禁

- Sealed package：`12 artists / 44 artworks / 31 typed contexts / 36 relations`，关系等级 `A/B/C=0/0/36`。
- Package content hash：`sha256:1f0f00a0d7f6162fcb0d716e6b86fbcfe42a4e04a0422d7c1c0df63b70c97b86`。
- Graph content hash：`sha256:58fe40930ab6f0e84019bbb0c3f378a2e73d7f3fbd4f810a66aa78f0481d1dd3`。
- M03B media baseline：31 `self_hosted_open_media_eligible`、4 `external_iiif_candidate`、9 `metadata_only`、下载字节 0。
- M03B package 内容未改写；后续 schema 注册改为 append-only 兼容验证，历史 code anchor 仍须为当前 main 祖先。

## 3. 官方来源执行

44/44 个官方对象 detail API 返回 HTTP 200；对象 ID、accession、艺术家、标题、日期语义、机构、对象 URL 和 source identity 44/44 闭合，身份冲突为 0。当前 live 状态确认：

- The Met：38/38 对象复核成功；31 件 `isPublicDomain=true` 且有官方 `primaryImage`，7 件无可批准媒体定位符。
- AIC：6/6 对象复核成功；4 件 `is_public_domain=true` 且 `image_id` 一致，2 件 Käthe Kollwitz 作品为非 public-domain 且带明确 ARS/VG Bild-Kunst 版权声明。
- 9 件原 metadata-only 对象均执行了基于精确艺术家、标题、日期、机构和 accession 的 Commons 补充检索；没有候选同时闭合 permanent revision、file-level license、官方馆藏对象 corroboration 与视觉身份，因此没有自动提升。
- Cleveland 与 Rijksmuseum 虽未出现在本批 44 件输入中，仍补齐了独立、fail-closed 的 M03C 可执行来源合同：Cleveland 绑定 numeric object ID、accession 对象页、`share_license_status=CC0`、对象署名和 accession-bound 官方 CDN；Rijksmuseum 由受控 resolver 依次请求并验证唯一 HumanMadeObject → VisualItem → DigitalObject canonical PID 链，再绑定对象记录与媒体记录的 PDM/CC0/CC BY 4.0 精确 allowlist、英文对象 credit 和 `iiif.micr.io`。三个 resolver URL 均只能由已验证的官方 numeric PID 构造，每跳独立保存 response hash、headers、event 和公网 peer/hop evidence；错 host/PID、多重或缺失链接、重定向换端点及任一跳不可用均 fail closed。Met/AIC 也补上 numeric object-ID 路径注入阻断。该增强未改变本批 ledger、媒体 bytes 或 bundle hash。

## 4. 下载、网络与恢复

流水线默认离线；真实媒体获取必须同时提供 `--live --download-media`。下载器使用 direct `http.client` HTTPS，忽略环境代理；每一跳验证 trusted host、公网 DNS、TLS hostname 和实际 peer IP，拒绝 Cookie/Auth、私网、未知重定向、HTML、MIME/magic 不一致、超限内容和覆盖写入。每来源并发为 1，AIC、Cleveland、Rijksmuseum 与 Commons 至少 1 秒间隔；Rijksmuseum 的三个 metadata resolver 请求也逐跳执行同一限速与网络门禁。支持 Retry-After、ETag/304、lock、临时文件、fsync、atomic no-overwrite、hash dedupe 和 expected-hash 幂等恢复。

结果：

- 实际 original downloads：31；总字节 `75,611,836`；全部为官方 Met JPEG。
- 4 个开放 AIC IIIF 定位符均真实尝试，但官方 `www.artic.edu` 在本运行环境返回 HTTP 403；记录为 `blocked_source_unavailable`，未降格为未经字节核验的 external approval。
- 9 件无批准定位符：7 件进入 `metadata_only_after_automated_review`，2 件进入 `blocked_rights_conflict`。
- 原图、官方 preview、raw metadata response、headers、hop evidence、请求、事件、hash、quality 和失败记录保存在 ignored `data/media-source/art/museum-03c/`；CI 不执行 live 下载。

## 5. 图像质量与衍生物

31/31 原图通过 JPEG magic/MIME、Pillow 完整解码、尺寸/像素、非空、HTML/placeholder/tracking-pixel、entropy、blur、blank/monochrome、orientation、border、watermark overlay、site chrome、duplicate、decompression-bomb 和官方 preview pHash/aspect 对照。质量状态为 `pass=31 / low_resolution=0 / fail=0`；最小图为 879×1078，最大图为 3253×4000，没有重复、preview mismatch、watermark overlay 或 site chrome。3 张边缘启发式命中的作品，其原图与官方 preview 的四边几何完全一致，记录为 `official_preview_matched_artwork_margin`，没有把画面、纸张或装裱边缘误判为站点界面。

衍生规则仅允许 EXIF orientation、ICC→sRGB（存在时）、metadata-safe strip、LANCZOS resize 和 compression；禁止 crop、upscale、AI、inpainting、generative fill、去水印或内容/颜色改变。生成 JPEG/WebP 的 320w/640w/960w/1600w 可用档，不放大缺失档：

- 衍生文件：242；总字节 `35,907,176`。
- AVIF：运行时不支持，明确记录 `not_available`，未伪称生成。
- 每个 derivative 有独立 ID、唯一物理路径、parent byte record、source SHA-256、输出 SHA-256、变换版本和自验结果；响应式聚合留给 MUSEUM-04 DTO。仅 7 个带嵌入 ICC 的原图对应 56 个 derivative 记录 `icc_normalization`，未标记 ICC 的原图准确记录为 assumed sRGB，不虚构颜色配置转换。

## 6. 44 项终态

| 终态 | 数量 | 说明 |
|---|---:|---|
| `approved_self_hosted` | 31 | identity、rights、bytes、quality 四项 mandatory closure 均 pass |
| `approved_external_delivery` | 0 | 不以 URL 可访问替代真实字节与权利闭合 |
| `metadata_only_after_automated_review` | 7 | 官方来源无可批准媒体，替代检索未闭合 |
| `blocked_rights_conflict` | 2 | AIC 对象级明确版权声明 |
| `blocked_identity_conflict` | 0 | 44/44 身份一致 |
| `blocked_quality_failure` | 0 | 31/31 获取字节通过质量门禁 |
| `blocked_source_unavailable` | 4 | AIC IIIF HTTP 403，保留 metadata 与官方来源入口 |

执行者统一记录为 `automated_cross_validation_pipeline`，`human_review_dependency=false`。

## 7. 每位艺术家媒体覆盖

| 艺术家 | 正式作品 | 自托管作品 | Metadata-only | Blocked | 衍生文件 |
|---|---:|---:|---:|---:|---:|
| Albrecht Dürer | 4 | 4 | 0 | 0 | 32 |
| Francisco de Goya | 4 | 4 | 0 | 0 | 32 |
| Henry Ossawa Tanner | 4 | 0 | 4 | 0 | 0 |
| José Guadalupe Posada | 4 | 3 | 1 | 0 | 20 |
| Julia Margaret Cameron | 4 | 4 | 0 | 0 | 30 |
| Käthe Kollwitz | 2 | 0 | 0 | 2 | 0 |
| Katsushika Hokusai | 4 | 4 | 0 | 0 | 32 |
| Kitagawa Utamaro | 4 | 4 | 0 | 0 | 32 |
| Mary Cassatt | 4 | 0 | 0 | 4 | 0 |
| Raja Ravi Varma | 2 | 0 | 2 | 0 | 0 |
| Shen Zhou | 4 | 4 | 0 | 0 | 32 |
| Vincent van Gogh | 4 | 4 | 0 | 0 | 32 |

媒体可用性不映射为艺术地位、价值或图节点权重。

## 8. Bundle 与物理闭包

- Ledger：`data/reviewed/art/museum-03c/media-source-ledger.json`，SHA-256 `sha256:e03ef898662aa528762bd3112c9893c1f455acb65473d1e73e3da5374fbbd218`。
- Bundle：`data/reviewed/art/museum-03c/media-bundle-v1/`，256 个 regular files，总物理字节 `36,923,181`。
- Bundle manifest 文件 SHA-256：`sha256:bdeab8d5d989363714345cca605c7c3427198be13c43461c29697e2968f34507`。
- Bundle content hash：`sha256:3aa84fa7df37c4823cd2cb1f92c7e1843e7dea70b7cfd683528b25698951d565`。
- `validate-bundle`：0 issues；exact M03B hash、declared schema path、exact file set、bytes/hash、request/event/byte/cross/quality/review/derivative 父链、source SHA、attribution、notice、canonical source rules、withdrawal 与 44-entry ledger/derived counts 全部闭合。
- Bundle 不含 ignored originals；只包含 approved derivatives。Blocked、unknown、development-only 媒体字节为 0。

## 9. CLI、schema 与测试

实现命令：`plan`、`discover`、`acquire --live --download-media`、`cross-check`、`assess-rights`、`build-derivatives`、`validate-bundle`、`explain`、`report-coverage`。新增 11 个 `additionalProperties=false` schema 和 canonical dispatch；终态枚举严格限制为 7 项。测试覆盖 identity、rights、bytes、SSRF/peer pinning、redirect、rate limit、Retry-After、ETag/304、atomicity、idempotency、pHash/quality、never-upscale、bundle closure、Cleveland/Rijksmuseum source-gate 正负合同和历史 M03B 回归。Rijks 三跳 resolver、来源合同、安全运输、state/schema 定向复验为 `65 passed`，覆盖成功链、逐跳持久化、错 host/PID、缺失/多重链接及 follow-up source unavailable；source registry 与当前 bundle validator 均通过；bundle content hash 保持 `sha256:3aa84fa7df37c4823cd2cb1f92c7e1843e7dea70b7cfd683528b25698951d565`。

提交前验证证据：

- `tests/pipeline`（排除已单独执行的慢速 bundle 文件）：`224 passed in 829.06s`。
- 修复 Windows 非 UTF-8 控制台 JSON 输出后，`tests/pipeline/test_media_pipeline.py` 复验：`8 passed in 4.58s`；`report-coverage` 的普通与 `--json` 输出均可在本机 GBK 环境解析，结果仍为 44 reviewed / 31 approved。
- `tests/pipeline/test_media_bundle.py`：`13 passed in 290.63s`；包含重写并重算 hash 后的 attribution、transform/ICC、processor version、M03B hash、父链、计数和 malformed-manifest 对抗用例。
- `tests/test_governance_foundation.py`：`50 passed in 1.36s`。
- `tests/test_museum_03b_fixtures.py`：`6 passed in 7.12s`。
- 当前真实 bundle 复验：`ok=true`、242 个 derivative 文件、`35,907,176` bytes；修复 validator 后无需重编码，bundle、manifest 和 ledger hash 均保持不变。
- 独立强化复核最初发现的 provenance 自信任、语义闭包、父路径逃逸、质量硬编码、stale failure、ICC 过报，以及第二轮发现的 transformation/attribution 漂移、malformed manifest 异常和 Windows junction 问题均已补测试并关闭；未解决 P0/P1/P2 为 0。

阶段中一次性 `pytest -q` 曾两次触及 20/30 分钟外部执行上限，未产生失败堆栈；分组诊断定位为当时尚待 Stage C 重构的旧 M04 zero-media fixture matrix。该历史超时未被当作 M03C 通过证据，也没有通过删测试或放宽门禁规避。MUSEUM-04-REVISED 完成后，MUSEUM-AUTO-01 最终树在进程级禁用网络的 runner 中完整执行 `373 tests in 1070.061s` 并返回 `OK`，从而关闭了该历史回归缺口。

详细 A–F 审查见 `docs/qa/museum-03c/adversarial-review.md`。MUSEUM-03C 没有公开 release、没有修改 Pages runtime，也没有进入 MUSEUM-05/06。
