---
phase_id: MUSEUM-00
status: completed
validation_status: pass
governance_foundation_ready: true
museum_01_recommended: true
github_push_status: pushed
open_decisions_count: 10
---

# MUSEUM-00 阶段报告

报告日期：2026-07-11（Asia/Shanghai）
项目根目录：`D:\ChatGPT-Codex-Projects\Museum-Codex`

## 1. 阶段目标

从第一性原理建立可扩展到美术、生物、音乐、游戏、文明和科学分馆的数字博物馆治理底座：用可追溯知识图谱承载事实，用数字展陈支持时空、关系和路径探索，并让来源、证据、权利、版本、撤回和静态发布均可被机器验证。本阶段只建设约束后续工作的架构、治理、schema、fixtures、验证器和路线，不实现正式产品功能。

## 2. 环境审计与实际完成内容

- 目标目录在开始时已经存在，但没有项目文件、Git 历史、项目 `AGENTS.md` 或 `skill/SKILL_INDEX.md`；发现并遵守了全局 `AGENTS.md`。没有覆盖、删除或重写任何既有有效内容。
- 初始化 Git，默认分支为 `main`；创建 `.gitignore`，排除密钥、缓存、虚拟环境、临时下载、原始大数据和未审媒体。
- 完成立项、第一性原理、分馆策略、五层系统架构、领域/图谱/Claim–Evidence–Source 模型、身份与多语言、无障碍与视觉语义、五份 ADR。
- 完成来源分层、A/B/C 证据等级、艺术家关系、内容审核、权利许可、版本撤回和 AI 内容治理。
- 实际核验并登记 17 个官方来源：美术 10 个、生物 7 个；把元数据和媒体许可拆开，并生成字段/对象级机器许可规则。
- 完成美术馆 MVP、艺术家选择、星海、AB 路径、数字展厅和互动候选规划；只定义接口和边界，没有确定 12 位艺术家。
- 完成生物馆研究、生态网络和行为动画证据框架；没有制作动画或正式分馆。
- 实现 16 个可运行 JSON Schema、29 个治理 fixture、1 个真实字节闭包 release fixture、3 个 CLI 验证器和 44 个自动化测试。
- 完成 Reviewer A–E 多角度对抗审查，修复全部 substantive findings 后复审通过。
- 没有创建 React/Vite 前端、正式首页、星海、地图、AB 交互、展厅、3D、批量采集或 GitHub Pages。

## 3. 创建和修改的文件

本阶段创建 112 个受控文件（含本报告）；开始时没有项目文件，因此不存在对既有项目文件的修改。

| 范围 | 文件 |
|---|---|
| 根与数据边界 | `README.md`、`AGENTS.md`、`.gitignore`、`.gitattributes`、`requirements-dev.txt`、`data/README.md` |
| 立项 | `docs/00_project/{project-charter,product-vision-and-boundaries,first-principles-analysis,museum-branch-strategy,decision-log}.md` |
| 架构 | `docs/01_architecture/{overall-system-architecture,domain-model,knowledge-graph-model,claim-evidence-source-model,data-pipeline-and-release-model,multilingual-and-identity-resolution,accessibility-and-visual-semantics}.md` |
| ADR | `docs/01_architecture/adr/ADR-0001` 至 `ADR-0005`：静态优先、图引擎、空间层、IIIF、Pages |
| 治理 | `docs/02_governance/{source-quality-policy,evidence-level-policy,artist-relationship-policy,content-review-workflow,rights-and-licensing-policy,license-decision-memo,data-versioning-and-withdrawal-policy,ai-generated-content-policy}.md`；`governance/license-decisions.json` |
| 来源研究 | `research/source-registry/{art-source-registry,biology-source-registry,source-verification-notes}.md`、`source-comparison-matrix.csv`、`source-license-rules.json`、`minimum-source-set.json` |
| 美术馆规划 | `docs/03_art_museum/{art-museum-mvp-scope,artist-selection-framework,artist-star-map-interaction-spec,relationship-graph-visual-rules,artist-ab-path-spec,digital-gallery-spec,artwork-interaction-catalog}.md` |
| 生物馆规划 | `docs/04_biology_museum/{biology-museum-research-brief,ecosystem-knowledge-model-outline,behavior-animation-evidence-policy}.md` |
| 路线与风险 | `docs/05_roadmap/{phased-roadmap,museum-01-entry-criteria,risk-register,open-decisions}.md` |
| Schema | `schemas/schema-manifest.json`、`schemas/README.md`；common 11 个、art 3 个、biology 2 个 schema，共 16 个 |
| 治理 fixtures | `fixtures/governance/valid/` 8 个、`fixtures/governance/invalid/` 21 个 |
| 物理 release fixture | `fixtures/release-bundles/valid/minimal/` 下 manifest、records、source rules、license decisions、notices、attributions 和真实 40-byte 媒体文件 |
| 验证与测试 | `scripts/{__init__,validate_governance_foundation,validate_source_registry,validate_publishable_media_rights}.py`、`tests/test_governance_foundation.py` |
| 阶段报告 | `docs/phase-reports/phase-museum-00-report.md` |

完整文件集合由本阶段 Git commit 固定；fixture 文件名和 schema 依赖由测试逐项枚举，不能静默增删。

## 4. 核心架构决策

1. **博物馆不是百科或图片库。** 藏品是具有身份、语境、来源和权利边界的可展陈对象；关系是有方向、类型、时空和证据的解释结构；事实是可争议、可撤回的 Claim，而非覆盖式文本。
2. **静态优先。** 外部 API 只在构建期采集；运行时使用版本化 JSON/GeoJSON、分片索引和审核后的媒体引用。Pages 在上游离线时仍可浏览，回滚以不可变 dataset release 完成。
3. **共享小核心、分馆扩展。** common schema 提供 Entity、Relationship、Claim、Evidence、Source、Media 与 Release；art/biology 用独立 schema 表达学科语义，不建立单一巨型 schema。
4. **Claim–Evidence–Source 是事实规范层。** 发布级 Claim 必须有双向闭合的 Evidence 与 Source；候选不能跳到 published；反证强制进入 disputed 流程。
5. **相似性与历史事实隔离。** `historical_relationship_strength`、`evidence_confidence`、`computational_similarity`、`curatorial_relevance` 分列；计算相似不能变成 `influenced_by`。
6. **具体 schema 强制分派。** 记录按实体类型、分馆和 ID 前缀绑定 concrete schema，不能借 common schema 降级绕过艺术家、生物或关系约束。
7. **来源与许可按实际 scope 绑定。** Source 的 canonical 身份、官方 host、规则数组和快照 hash 闭合；消费记录绑定稳定 rule ID、scope locator、字段集合和权限解析方式。
8. **物理发布而非自报 manifest。** Release 精确核对文件集合、规范路径、字节数、SHA-256、记录 ID、schema 版本、引用闭包、来源规则、许可决定、notices 和 attribution；空媒体也会阻断。
9. **技术只做 ADR，不提前实现。** 未来基线建议 React + TypeScript + Vite；Graphology + Sigma.js 负责探索图，Cytoscape.js 保留为复杂复合图替代；MapLibre 用于后续空间层；IIIF 优先承载高分图；IndexedDB 不作为 MVP 必需；后端只在协作编辑、私有授权、服务端搜索或规模触发时重评。

## 5. 来源研究结果

### 美术来源（10）

Wikidata、Wikimedia Commons、Getty ULAN、The Met、Europeana、Smithsonian、Rijksmuseum、National Gallery of Art、Art Institute of Chicago、Cleveland Museum of Art。

### 生物来源（7）

Catalogue of Life、GBIF、Encyclopedia of Life、GloBI、IUCN Red List、RESOLVE Ecoregions 2017、Natural History Museum London。

每行记录官方 URL、数据类型、接口/下载、key、访问/速率、元数据许可、媒体许可、再发布、修改、署名、商业使用、静态发布适配、Tier、风险和核验日期。重要结论包括：

- 开放 API、IIIF 或图片 URL 不等于媒体可再发布。
- Wikidata/Wikipedia/Commons/Europeana 默认作为 Tier 3 发现层；高风险事实须回到 Tier 1/2。
- AIC artwork `description` 为 CC BY 4.0，而其他 artwork data 可为 CC0；验证器按真实 endpoint 与 `fields` 查询分流。
- GBIF occurrence 不自动证明稳定分布；GloBI/EOL 聚合关系不能单独批准行为动画。
- IUCN 具有 Tier 1 评估价值，但在单独许可前阻止静态再发布数据、文本和范围资产。

核验记录和所有官方链接见 `research/source-registry/`；canonical 来源矩阵和许可规则分别由 SHA-256 固定。

## 6. 证据治理规则

- 艺术家正式收录只允许确认已故的个人；生卒、身份和至少一件作品/正式艺术史记录均须有 Tier 1/2 支持。死亡不明、同名未消歧、算法猜测不得发布。
- 匿名作者、工作室、群体创作和不确定归属使用专门实体/归属类型，不伪造成确定个人。
- 艺术关系采用 A（直接事实）、B（历史语境）、C（策展比较/计算相似）三级；C 级禁止使用直接影响措辞。
- Claim 状态按 `candidate → sourced → reviewed → verified → publishable → published` 受控推进，并保留 disputed/deprecated/withdrawn 分支；候选不能直达 published。
- 计算 Claim 必须含计算证据、算法/模型版本和输入说明；AI 永远不能成为历史事实唯一来源。
- 生物行为动画必须绑定 Evidence 并记录机制、观察范围、简化和不确定性；不能先生成动画再补证据。

## 7. 版权与许可治理规则

- 代码、原创文字、第三方元数据、图片、音视频和用户取得授权分别记账；项目许可证不覆盖第三方内容。
- Media 必须记录对象级权利状态、canonical license、rights holder、来源 URL、署名、允许再发布/修改/商业使用、审查和授权期限。
- `rights_status=unknown`、`development_only=true`、许可撤销/过期、范围不覆盖 GitHub Pages 或自托管媒体无实际字节，均阻断公开 release。
- `third-party-notices.json` 按 Source 实际使用规则的精确并集和逐 Media 许可生成；多报、漏报、错误 holder/URL/署名均失败。
- 代码和原创内容最终许可证仍为用户决定；机器决策注册表保持 pending，合成 fixture 的 `not_applicable` 不能覆盖生产 release。

## 8. Schema 和验证结果

最终受控结果：

```text
validate_governance_foundation.py: PASS
  schemas=16, registries=1, fixtures=29, valid=8, invalid=21, release_bundles=1
validate_source_registry.py: PASS
  sources=17 (art=10, biology=7)
validate_publishable_media_rights.py fixtures/governance/valid: PASS
  media_records=2
explicit physical release validation: PASS
python -m unittest discover -s tests -q: PASS (44/44)
clean temporary virtual environment: PASS
```

验证器覆盖艺术家稳定 ID/死亡状态、在世阻断、关系类型与 A/B/C、历史/算法隔离、Claim–Evidence–Source 闭包、来源 URL/日期/Tier、Media 权利、unknown/development-only 阻断、schema/data/build 版本、withdrawn/deprecated 阻断、计算相似不转影响以及生物动画证据与简化说明。

## 9. Fixtures 结果

- **8 个 valid fixture 全部通过：** 可发布艺术家、直接关系、成员关系、Claim–Evidence–Source、完整 release 闭包、CC BY 媒体、生物动画证据等。
- **21 个 invalid fixture 全部按预期错误码失败：** 在世艺术家、算法伪影响、关系端点错误、无证据 Claim、无来源 Evidence、候选跳级、争议状态冲突、Tier 3 高风险计算、unknown/development-only 媒体、许可 scope 错配、ShareAlike 错配、IUCN 未授权、撤回内容、缺记录、Windows/逃逸路径和 schema 降级等。
- **物理 release fixture 通过：** 实际 40-byte 媒体、records、Source rules、license decisions、notices 和 attribution 与 manifest 精确闭合。
- **篡改测试通过：** 未登记文件、被改字节、缺媒体、空 attribution、缺 ID、错误 notices、伪来源 origin、字段许可绕过、多规则 notice 漏报及同步更新所有 hash 的 0-byte 媒体均被阻断。

## 10. 对抗性审查发现

| Reviewer | 初审发现 | 严重度 | 处理 |
|---|---|---:|---|
| A 知识图谱与数据架构 | common schema 可降级、引用/证据与 release 集合闭包不足、版本自报 | P1/P2 | 强制 concrete schema、ID/端点类型、双向证据、精确 included/manifest/schema versions 闭包 |
| B 艺术史与证据治理 | 生卒 Claim 语义/时间、作品归属、计算证据、Tier 与反证状态仍可能弱约束 | P1/P2 | 加入生卒语义和 chronology、作品与归属端点、Tier 1/2、计算证据、counter-evidence 状态规则 |
| C 版权与公开发布 | 字段级许可可被 detail/search、编码或外域绕过；来源身份可伪装；notices 不能表达多规则；0-byte 媒体可同步 hash | P1/P2 | endpoint + query fields、HTTPS 精确 host、hashed canonical identity、rule 并集 notices、media bytes≥1 与回归探针 |
| D 产品与学习体验 | 重点核对是否退化为百科、信息过载、儿童/公众/深度用户和无障碍 | — | 现有渐进披露、局部图、证据解释、角色化路径、非颜色通道和 DOM 等价视图满足本阶段；无 substantive finding |
| E 工程、性能与安全 | 物理文件集合、路径、字节、回滚、静态离线和密钥边界需要机器闭包 | P2 | 精确文件集、安全 POSIX 路径、hash/bytes、不可变 release、撤回、无运行时 API、gitignore/密钥扫描 |

## 11. 根据审查进行的修订

修订不只停留在意见：新增 4 个发布 artifact schema、canonical schema dispatch、Source identity/规则双快照、scope matcher、许可权限解析、物理 release closure、精确 notices、44 个回归测试和多组无效 fixture。Reviewer C 额外独立执行 52/52 条许可规则探针；A–E 最终均为 PASS，本阶段范围内无未解决 P0–P3 审查问题。

## 12. Git 和 GitHub 状态

- 初始状态：目录存在但为空、未初始化 Git、无历史可重写。
- 当前分支：`main`。
- Remote：`https://github.com/Archmays/Museum-Codex.git`。
- 仓库可见性：`private`；依据用户同类 `*-Codex` 仓库的既有可见性选择安全默认，最终公开/私有决定仍为 OD-003。
- GitHub Pages：未启用。
- 提交信息：`Phase MUSEUM-00 project architecture and governance foundation`。
- 推送：成功推送 `main` 至 `origin`。
- Commit hash：本报告属于该 commit，自身 hash 无法在同一不可变 commit 内自指；准确 hash 在任务最终回复中报告。
- 提交后工作区：无未提交文件。
- 敏感信息：未发现；未提交 API key、授权原件或密钥。
- 大文件：未发现超过 5 MiB 的文件；没有来源不明或许可不清媒体。

## 13. 未解决决定

共 10 项，完整责任人和最晚决策点见 `docs/05_roadmap/open-decisions.md`：

1. 代码许可证；
2. 原创文字许可证与第三方范围声明；
3. 仓库和 Pages 最终可见性；
4. 首批 12 位艺术家；
5. 目标设备和量化性能预算；
6. 底图/tile 提供者与许可；
7. IIIF/自托管高分图策略比例；
8. 中文搜索分词和索引方案；
9. 分析、收藏历史与隐私模式；
10. 权利投诉联系、SLA 和授权证明保管流程。

其中 OD-001/002/003 是进入公开发布链前的用户决策；它们不阻止 MUSEUM-00 治理底座完成，也不授权启用 Pages。

## 14. 主要风险

风险登记表保留 19 项。最高关注面是：相似性伪历史、在世/身份不明艺术家、元数据许可外溢到图片、IUCN/受限数据再发布、图谱与高分图性能、WebGL 无障碍、密钥/授权文件入 Git、实体误合并、撤回后缓存、AI 虚构、观测误作分布，以及伪来源域名/字段许可绕过。每项都有 owner、触发和阻断/缓解动作。

## 15. 验收门槛

| 门槛 | 结果 |
|---|---|
| 愿景、产品边界、分馆架构、通用/美术模型、生物扩展 | PASS |
| Claim–Evidence–Source、A/B/C、关系解释和视觉语义 | PASS |
| 17 个实际核验来源，元数据/媒体许可分离 | PASS |
| 可执行权利、版本、撤回和静态快照治理 | PASS |
| 16 schemas、29 fixtures、3 validators、44 tests | PASS |
| unknown/development-only/withdrawn/算法伪影响阻断 | PASS |
| A–E 对抗审查修复并复审 | PASS |
| Git 状态、敏感信息和大文件检查 | PASS |
| 未实现禁止的正式产品功能、未发布未核验数据 | PASS |

结论：`MUSEUM-00` 满足全部验收门槛，状态为 `completed`。

## 16. 是否建议进入 MUSEUM-01

**建议，但不自动开始。** `museum_01_recommended=true` 表示治理和技术底座已经具备；仍须用户明确授权进入 `MUSEUM-01`。本次任务到此终止，没有创建其前端骨架或 Pages 工作流。

## 17. MUSEUM-01 明确输入条件

1. 本报告保持 `completed/pass/ready=true`，本阶段 commit 可定位；
2. 干净 checkout/新虚拟环境中 3 个验证器、物理 release 和 44 个测试继续通过；
3. 用户明确授权开始 `MUSEUM-01`；
4. 启用公开 Pages 前，用户决定 OD-001、OD-002、OD-003；
5. 仅输入本阶段架构、治理、schema、fixtures、验证器、来源 registry、open decisions 和 risk register；
6. 不把首批 12 人、批量作品、未知权利媒体或未经审核关系提前作为输入。
