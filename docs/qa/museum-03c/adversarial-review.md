# MUSEUM-03C A–F 对抗性审查

日期：2026-07-15。对象：M03C 自动媒体请求、live evidence、44 项终态、ledger、derivatives 与 tracked media bundle。

| Reviewer | 检查重点 | 结果 | 证据 |
|---|---|---|---|
| A — identity/data | 44 个对象 ID、accession、artist、title、date、institution、object/media ID、source snapshot；M03B hash 不漂移 | PASS | 44/44 official detail HTTP 200；identity conflict 0；package/graph hash 固定 |
| B — rights | 对象级媒体状态、精确 media rule、redistribution/derivative/commercial、attribution、revocation/expiry；不以 URL 代许可 | PASS | 31 approved 全闭合；2 明确版权 blocked；7 metadata-only；4 source unavailable；blocked bytes 未入 bundle |
| C — security/transport | direct HTTPS、public DNS、actual peer、redirect、cookie/auth、size、atomicity、idempotency、symlink/junction、CI offline | PASS | 续传必须绑定持久化 HTTP 200/公网 hop/SHA/字节/MIME 证据；父路径 symlink/junction 在 lock/temp/network 前拒绝；AIC/Commons 节流；默认 offline |
| D — image quality | magic/MIME/decode/pixels/entropy/blur/blank/monochrome/placeholder/orientation/border/watermark/site chrome/duplicate/wrong crop/preview match | PASS | 31/31 quality pass；0 duplicate、0 preview mismatch、0 watermark/site chrome、0 decompression bomb；3 个 border flag 均由官方 preview 同构解释 |
| E — accessibility/product | 本阶段不含公开 UI；不得将媒体可用性映射为艺术价值 | NOT_APPLICABLE | M04/M05A 才消费 bundle；ledger 保持相同 44 artwork records |
| F — release/physical closure | exact file set/hash/bytes、parent chain、notices/attribution/source rules/withdrawal、blocked zero | PASS | bundle 256 files；242 media files；`validate-bundle` 0 issues |

## 对抗性负例

- 私网 DNS、TLS peer mismatch、未知 redirect、HTML 伪图、超限 body、MIME/magic mismatch、Cookie/Auth、覆盖写入均 fail closed。
- `approved_self_hosted` 缺任一 identity/rights/bytes/quality closure 或 derivative ID 会被 schema 拒绝。
- 人工等待态、未知通过态、第八种终态、requested-schema 降级与错误 branch/ID prefix 会被拒绝。
- Bundle hash 漂移、遗漏衍生物、blocked media、署名/notice/withdrawal 不闭合会失败。
- 即使攻击者重算 manifest/ledger hash，错误 M03B hash、schema-valid 但错误的许可/署名、canonical source rule 漂移、review/parent/source SHA 引用漂移及派生计数漂移仍会失败。
- 即使攻击者重算受影响文件和 manifest hash，矛盾的 `changes_statement`、伪加或遗漏 `icc_normalization`、processor version 漂移仍会失败；缺少 `bytes`、`sha256` 或 `record_ids` 的 malformed manifest 返回结构化失败，不抛未处理异常。
- governed vault 祖先中的 symlink 或 Windows junction 在创建 JSON、bytes、temp 或 lock 前失败；合法 hardlink 不被误判。

## Findings

- P0/P1/P2：无未解决项。
- P3-01：4 个 AIC 官方 IIIF 定位符在本环境返回 HTTP 403；记录为 `blocked_source_unavailable`，不影响 31 个已批准资源。后续仅在官方 host/contract 仍一致时重试。
- P3-02：运行时 Pillow 不支持 AVIF；当前正式提供 JPEG/WebP，并明确声明 AVIF `not_available`。
- P3-03：watermark/site-chrome 检查由官方 full-image provenance、preview pHash/aspect、边缘几何与像素启发式组成，不等同 OCR；本批 31 项没有明显异常。3 个 artwork-margin 命中均明确保存 preview 同构解释。

结论：M03C `completed/pass`，可供 media-aware M04 消费；只有 ledger/bundle 中的 approved derivative 可进入公开 release。
