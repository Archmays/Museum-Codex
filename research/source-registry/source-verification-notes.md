# 来源核验说明

## 核验范围与方法

- 核验日期：`2026-07-11`（Asia/Shanghai）。
- 只使用来源机构、标准组织或项目自身的官方页面、API 文档、条款、许可和第一方仓库；没有用搜索摘要替代结论。
- 分别记录技术访问、API key、限制/速率、元数据许可、媒体许可、再发布、修改、署名、商业使用和静态发布适配。
- `source-license-rules.json` 进一步把 metadata/data/media 的许可绑定到 endpoint、字段或对象选择器，并强制无父级继承；`minimum-source-set.json` 只定义本阶段最低覆盖，未来经审核的新来源不会被误判为错误。
- 未公开数字值写 `not stated`；文档冲突原样记录，不推断“无限制”。
- Tier 评估针对本项目用途；来源权威性与内容再发布许可是两条独立结论。

## 当前性与文档冲突

1. Wikimedia 的 2026 全局 Action/REST 限额已变化；适配器需合规 User-Agent、最多 3 并发并处理 `Retry-After`。
2. Europeana FAQ 称读取 API 无节流，但 project-key 页面暗示更高请求率；批量前联系/复核，registry 不写虚构数字。
3. Smithsonian 官方 bulk GitHub 仓库在 2026-05-21 归档并迁至 S3；不要实现指向旧更新路径的 adapter。
4. Rijksmuseum 2026-06-29 更改 canonical PID/redirect，且 OAI-PMH 有潜在 breaking change；用 contract test 和 raw snapshot 防止静默丢字段。
5. Art Institute of Chicago 的 artwork `description` 是 CC BY 4.0，其他 artwork data 才是 CC0；其他 endpoint 又可能不同。字段级许可必须可保留。
6. Catalogue of Life 当前 XR 含程序合并，不能把 XR 每条记录都等同专家逐条审校 Base。
7. IUCN 条款页面可能对自动客户端返回 403，但官方 API/help/FAQ/下载资料仍清楚表明 token、动态限流与严格再发布条件。公开使用前需要人工打开条款并保存许可决定。

## 不应作出的推断

- API 或 IIIF 可用 → 图片可再发布。
- 聚合元数据 CC0 → 数字对象/缩略图 CC0。
- 机构是 Tier 1 → 每条用户/聚合记录都是 Tier 1 Evidence。
- CC0/PD → 没有隐私、人格、商标或文化敏感风险。
- occurrence 点 → 稳定栖息地/长期分布。
- interaction 聚合记录 → 普遍行为或动画脚本。
- 未写限速 → 无限制。

## 下次复核触发

每个公开 release 前复核实际使用来源的条款与对象权利；平时至少 12 个月一次。API 版本/字段、仓库归档、许可文本、访问错误或撤回通知立即触发。保存核验页面 URL、访问时间、必要的条款快照 hash 和 reviewer；不要把网页全文或不明授权文件提交 Git。

本次 canonical 机器规则快照由 `minimum-source-set.json.license_rules_snapshot_hash` 固定；每条规则的稳定 ID 由来源、内容类别和 `applies_to` 选择器哈希派生。修改条款解释时必须同时更新核验笔记、规则文件、快照 hash、受影响 fixture，并重新运行两个治理验证器；Release 不接受自报的替代规则数组。
