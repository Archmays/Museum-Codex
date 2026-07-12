# MUSEUM-03A 艺术家选择与权利预审方法

本方法只生成用户确认前的私有候选包，不批准艺术家、不创建正式作品或关系，也不关闭 `OD-004` / `OD-007`。

## 决策流程

`宽池 → 个人/死亡/身份硬门槛 → Tier 1/2 来源与对象记录 → 约 4 件作品权利路径或小配额理由 → 关系研究线索 → 组合情景 → 偏差审查 → 用户确认`

宽池先追求发现广度，不按当前 adapter、开放图片数量、知名度或市场价值过滤。合格池必须是明确个人、确认去世、身份已解析，有可靠生卒 Claim、权威身份来源、馆藏/学术来源和至少一件正式对象记录。匿名、工作室、群体、死亡不明、同名未消歧、Tier 3-only 或全部无合理对象/metadata 路径者留在研究队列。

每个候选约预审 4 件作品。小于 4 件时必须逐人记录具体原因；这不会被 readiness 分数抵消。作品预审分离 metadata 与 media 许可，图片 URL、`image_id`、IIIF 可访问性和 `is_public_domain` 单个字段都不是发布批准。所有状态使用 `*_candidate`、`review_required` 或 `blocked_*`，不使用 `publishable`、`approved` 或 `released`。

## 来源策略

- Tier 1：Getty ULAN、正式博物馆对象记录/馆藏目录/档案/catalogue raisonné；
- Tier 2：大学项目、学术出版社、策展研究与同行评审研究；
- Tier 3：Wikidata、Wikipedia、Commons、Europeana 等，只用于发现、多语名、外部 ID 和待核验线索；
- Tier 4：不支撑正式事实或权利结论。

GitHub repository 按实际发布者而不是平台名称分级。博物馆、档案馆、大学或正式研究机构账号下的 official repository/release，可在核对组织身份、license、commit/tag/hash、上游链和撤回状态后成为 Tier 1/2 来源。个人整理、fork、镜像和不明组织仓库只用于发现。已登记的 NGA official open-data repository 属于这一模式；已归档并迁移的仓库必须跟随当前官方迁移路径，不能把旧镜像当现行来源。

缺 adapter 不自动排除非西方候选。每个来源记录 `adapter_ready`、`manual_preflight_only`、`adapter_extension_needed` 或 `source_not_yet_registered`。MUSEUM-03A 不把 discovery/search utility 登记为 MUSEUM-02 reference adapter。

## Live research 边界

Live research 必须显式、单线程、固定 HTTPS 官方 host、无凭据/cookie、有限响应大小、无媒体下载。每个响应保存原 bytes、request/final URL、UTC 时间、status/content type、bytes、SHA-256、User-Agent 和无凭据/无媒体声明；raw 与 review 工件只写 ignored 数据区。HTTP 429/499、timeout、contract drift 或来源内部矛盾均 fail closed，不回退镜像或搜索摘要。

本地应用层 append-only 仍不是 WORM；DNS 公网预检也不是 cryptographic pinning，系统代理仍属信任边界。当前单机、无凭据、固定 host、无媒体字节的预审风险可接受；MUSEUM-03B 前必须重新确认 raw 存储防篡改、代理/DNS 边界和任何新 host/凭据。

## 准备度评分与偏差

0–3 仅记录 identity、death evidence、source quality、artwork record、object-level rights、multilingual identity、relationship research、region/tradition、period、medium/material、public learning、interaction 和 adapter/pipeline 准备度。每个分数必须有 rationale、source IDs、limitations、reviewer 和时间。禁止 greatness、importance、influence、canonical、popularity 或 market-value 排名。

组合审查覆盖地区/传统、历史区段、女性及长期被忽视群体、媒介/材料、对象权利、关系学习和工程准备度。性别/被忽视群体标签只发现选择偏差，不评价艺术价值。公开数据和高分图可得性是结构性偏差，不得成为纳入理由。

## 关系线索

`relationship-lead` 只保存 MUSEUM-03B 待核验问题。A 级需指出直接证据类别；B 级需具体地点、时期、机构、团体或展览；C 级明确为策展比较。所有 lead 均为 `formal_relationship_created=false`、`public_display=false`、`exact_evidence_reviewed=false`。不生成图像嵌入，不创建 `computationally_similar_to`，不从共同标签自动推出影响或接触。

## 四种 OD-007 选项

| 选项 | 权利风险 | 访问/性能 | 撤回、缓存、署名 | Pages 与 MUSEUM-05 |
|---|---|---|---|---|
| A Metadata-first | 最低 | 视觉有限、文本最稳 | 无媒体缓存，撤回最简单 | 包体最小，后续补媒体 |
| B External IIIF/source | 中；逐对象许可 | 可缩放但依赖上游 | 不缓存字节，仍需署名/撤回链接 | 工程中等，需可用性策略 |
| C Self-hosted open only | 低至中；仅 PD/CC0 闭合对象 | 稳定且性能可控 | 项目承担缓存、署名、撤回 | 包体增加，需衍生物管线 |
| D Mixed | 逐对象降级，审查复杂 | 体验与稳健性较平衡 | 三类路径并存 | 工程最复杂，适合渐进交付 |

代理建议 D，但首轮默认 metadata-first；只有对象级权利闭合后才升级 external IIIF 或 self-hosted。该建议不关闭 `OD-007`。

## 组合声明

三套 scenario 分别优化全球/跨文化平衡、关系/学习路径、数据/权利准备度；Recommended 可与某一 scenario 相同，但必须说明约束。每套恰好 12 个唯一合格 ID，`user_approved=false`。任何组合都只是受范围、证据、权利和学习目标约束的试点建议，不代表完整或普世艺术史。
