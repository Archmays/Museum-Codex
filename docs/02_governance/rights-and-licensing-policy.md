# 权利与许可政策

## 权利对象必须分开

代码、项目原创文字、第三方元数据、图片、视频、音频、模型/字体、用户取得的授权分别建账。一个页面可以同时包含多种权利；项目许可证只覆盖项目有权许可的部分。

## 逐媒体资产字段

稳定 ID、source/source object URL、`delivery_mode=self_hosted/external_link/iiif_external`、是否缓存字节、content hash、rights holder、`rights_status`、结构化 metadata/media license identifier/URL/version、对象级 rights evidence 与快照 hash、署名、再发布/修改/商业使用允许值、地域/用途/平台限制、授权状态/文档引用、开始/到期/撤销日、下架计划、`development_only`、审核者/日期和撤回信息。

状态包括 `public_domain / cc0 / cc_by / cc_by_sa / licensed / research_or_education_only / restricted / unknown`。元数据许可使用独立字段，不能从 API 或父数据集复制给媒体。

## 发布矩阵

| 状态 | 公开构建默认 | 条件 |
|---|---|---|
| public_domain / cc0 | 可 | 核验对象级声明；仍检查人格、隐私、商标、文化敏感 |
| cc_by | 可 | 完整署名、许可链接、改动说明 |
| cc_by_sa | 条件可 | 上述条件 + 衍生物相同许可；与项目组合兼容性审查 |
| licensed | 条件可 | 授权覆盖 Pages、地域、期限、用途和衍生物 |
| research_or_education_only | 默认阻断 | 只有发布用途明确符合且法律/权利审核书面批准 |
| restricted | 阻断 | 只保留非公开记录/来源链接 |
| unknown | 阻断 | 不得进入 release |

`development_only=true` 永远阻断，无论其他字段。`allow_redistribution=false` 或授权过期也阻断。

发布还要求 `review_status=verified`、publish/lifecycle 正向一致；自托管字节必须有 SHA-256，外链/外部 IIIF 必须 `cache_bytes=false`。有限授权须覆盖 `github_pages + public_education + worldwide` 且已生效，release 的 `public_until` 不得晚于授权到期。占位授权引用无效。

## 特别规则

- IIIF、图片 URL、缩略图或“Open API”只描述技术访问，不证明再发布权。
- Wikipedia/Commons 文件逐文件核验；馆藏来源应回到馆方对象页。
- IUCN 等具有专门再发布条款的数据，在取得书面许可前只保留来源链接和开发记录。
- 用户未来取得授权时保存授权方、权利链、覆盖资产、平台/用途/地域、是否可修改/转授权、署名、到期和证明文件的受控引用；证明文件不一定进入公开 Git。
- 不提交来源不明或权利不清的大文件；Git 删除不能替代发布撤回响应。
- `reuse_mode` 区分 verbatim/adaptation/collection。adaptation 保存原资产 ID/hash、transform recipe/version、输出 hash/许可和 ShareAlike compatibility；CC BY-SA 改编缺兼容输出许可即失败。

## 构建门禁

发布构建验证所有引用资产存在、状态允许、非开发、可再发布、字节 hash/外链模式、对象级权利证据、署名、许可范围/时效/衍生兼容、Source 再发布条款和 withdrawal。Dataset Release 必带代码/原创内容许可 decision ID 与范围声明、第三方 notices manifest、逐资产 attribution manifest。公开 release 的相关 decision 仍 pending 时失败。失败列 ID/原因并非零退出；空目录、缺路径或零媒体的发布扫描同样失败。

## 权利投诉与撤回

接收后立即隔离资产和衍生物，记录请求、作用范围与时间；必要时发布新 release 移除字节/引用并处理缓存。事实记录可以保留最小审计信息，但不继续分发受限内容。恢复需要新的权利审核记录。

## 机器可执行的发布闭包

- 每条 Source 使用稳定 `registry_source_id`，其许可规则使用稳定 `rule_id`；`license_rules_snapshot_hash` 必须与规则数组一致，并与已核验 canonical registry 匹配。Evidence、实体、关系和 Media 通过 `source_license_bindings` 绑定实际 `rule_id` 与内容类别，不能借开放 metadata 规则发布受限 data/media。
- Tier 4 永不进入公开 release。IUCN canonical 规则保持禁止再发布；不得通过在 release 中自报 CC 许可绕过。未来书面许可须作为独立、可核验且有起始日、范围、到期与撤销状态的治理记录扩展后才能放行。
- `self_hosted` Media 必须声明 `storage_path`，且恰好对应一个 `record_type=media` 的真实文件；文件 SHA-256 必须等于资产 `content_hash`。外链与外部 IIIF 不得声明本地路径或缓存字节。
- CC0、CC BY、CC BY-SA 与 PDM 使用 canonical identifier/version/URL 组合；前缀相似但不存在的许可证（如 `*-FAKE`）失败。改编必须闭合到父资产、父 hash 与可修改权利，并拒绝衍生循环。
- 代码与原创内容决策解析到 `governance/license-decisions.json`；物理 release 携带其哈希快照。OD-001/OD-002 仍 pending，所以真实公开 release 失败；合成 fixture 的 `not_applicable` 决策不代表项目许可证。
- `third-party-notices.json` 与 `attributions.json` 按独立 schema 解析，逐 ID 与 Source/Media、来源 URL、许可标识、署名及改动说明核对；只同步文件 hash 而内容为空或非 JSON 仍失败。
- Rule binding 还记录实际 `scope_locator` 并执行每条规则的通用 `scope_match`；绝对 URL 同时校验 HTTPS 与精确官方 host。AIC `/description` 必须绑定专用 CC BY 规则，不能借外域同路径、伪 host 后缀、scheme-relative、其他 endpoint、URL 编码或明确排除该字段的 CC0 规则。Media 的对象许可必须与绑定的具体 Source media rule 一致。
- Binding 的 `permission_resolution` 区分 `rule_direct` 与 `object_level`：直接规则下，媒体不得超过 rule 的 redistribution/modification/commercial_use；`conditional` 或 `prohibited` 不能自报为 allowed。只有明确 `mixed + conditional` 的对象规则才能走 object-level，并仍需对象级权利证据与 canonical Media license。
- CC BY-SA 改编默认保留父资产已核验的同一版本，不能把 4.0 降为 1.0 并自报 `compatible`。合成 fixture 的 `not_applicable` 决策由结构化 scope constraint 限制，不能用于非 fixture release；notice 的 rights holder 也必须与记录一致。

### 通知与实际规则使用的精确对应

- Source notice 的 `license_rule_ids`、`license_identifiers` 和 `attribution_texts` 必须等于该 release 内所有消费记录实际绑定规则的并集；多用一条、少报一条或用一个代表性许可概括多个规则都失败。
- Media notice 逐资产核对其实际绑定 rule、对象级 canonical license、source object URL、署名文本与 rights holder；Source notice 不能代替 Media notice，反之亦然。
- 通知文件只覆盖该 release 的 Source 与 Media 精确集合；未使用的规则不能被写入 notice 来暗示更宽授权，新增实际规则也不能依赖旧 notice。
- `record_type=media` 的自托管文件必须至少包含 1 byte；即使空文件与 manifest、记录和 content hash 完全同步，也会被 schema 与物理验证器共同阻断。MIME 嗅探与解码有效性在 `MUSEUM-01` 构建管线中继续实现。
