# MUSEUM-02A 对抗性审查

审查日期：2026-07-12（Asia/Shanghai）
审查范围：第七分馆治理契约、common schema/dispatch、公开门户、无障碍、安全扫描、Pages 测试与阶段边界。

## 结论

Reviewer A–E 的初审发现均已实际修订。最终无未解决 P0、P1 或 P2；本阶段没有新增 P3。`MUSEUM-02` 已登记的 append-only/WORM 与 DNS pinning 两项 P3 保持原 owner 和复核期限，本阶段没有扩大或伪装解决它们。

## Reviewer A｜博物馆与信息架构

| ID | 等级 | 初审发现 | 实际修订 | 状态 |
|---|---|---|---|---|
| A-01 | P1 | 只增加卡片会使七馆数量、分馆准入和数据契约脱节 | 更新项目章程、分馆策略、总体架构、领域模型、路线图、OD-011 和风险；登记 `planned / portal-visible / data-contract-not-yet-implemented` | resolved |
| A-02 | P2 | 既有“门户入口不能先于数据集”规则与不可点击筹备卡片存在表述冲突 | 明确区分不可导航的 `portal-visible` 筹备标记与可进入的分馆原型；后者仍要求可追溯数据集 | resolved |
| A-03 | P2 | 文明馆、科学馆和美术馆可能与武器馆边界重叠 | 在分馆章程中按社会制度、一般科学原理和艺术描绘分别划界，并要求通过稳定实体/Claim 跨馆连接 | resolved |

复核：非历史报告中的“六馆 / 六个分馆 / Six museums / 01 — 06”扫描为 0；七馆名称、顺序和状态在架构、文案和门户中一致。

## Reviewer B｜历史、来源与策展

| ID | 等级 | 初审发现 | 实际修订 | 状态 |
|---|---|---|---|---|
| B-01 | P1 | 器物容易脱离冲突、人类代价、来源和收藏史 | 章程与模型强制纳入 `provenance_event`、`human_impact_context`、来源/归还争议及 `contextualized_by_human_impact` | resolved |
| B-02 | P2 | 现代类型学可能被无条件投射到古代与跨文化器物 | 模型明确记录词表、文化/时期适用范围和争议；`derived_from_typology` 不等于直系技术影响 | resolved |
| B-03 | P2 | 仪式、象征、表演和实际使用可能被压成单一用途 | 增加 `ritual_or_symbolic_context`、`used_ceremonially_in` 和“仪式与实战”非操作性互动概念 | resolved |

复核：来源 brief 只规定未来来源类别和逐项核验，没有选择来源、建立 adapter、live probe、抓取或媒体下载。

## Reviewer C｜安全、伦理与年龄适宜性

| ID | 等级 | 初审发现 | 实际修订 | 状态 |
|---|---|---|---|---|
| C-01 | P0 | 若只靠策展文案，制造、改装、操作、采购或战术内容仍可能进入 public artifact | 建立正式安全政策；为 `public`/`dist` scanner 增加 `operational_arms_content` fail-closed 规则和单元测试 | resolved |
| C-02 | P1 | 现代/受监管武器与儿童访问边界未形成独立门禁 | 政策要求现代内容只保留高层次历史/政策/设计史说明并提高审核等级；家庭路径默认非图像化、非操作化且可跳过敏感内容 | resolved |
| C-03 | P2 | 视觉 motif 可能暗示枪械、准星或军事游戏 | 采用原创防护弧、锻造层纹、年代刻痕和馆藏编号点；未使用真实枪械、准星、子弹、爆炸、血迹、击杀图标或 HUD | resolved |

复核：public/dist 安全扫描只检查公开输入和构建产物，不因政策文档中的禁止词误报整个仓库。

## Reviewer D｜数据与治理

| ID | 等级 | 初审发现 | 实际修订 | 状态 |
|---|---|---|---|---|
| D-01 | P0 | `branch_id=arms` 若未知 entity type 默认回退 common entity，可绕过尚未实现的 branch schema | `expected_target_schema` 对 `arms` 返回无 concrete target；binding validator 发出 `arms_branch_schema_not_implemented`，明确禁止 common fallback | resolved |
| D-02 | P1 | 只改 enum 而不更新版本、fixture 和测试会破坏契约可追踪性 | `common/entity` manifest 版本兼容升级为 `1.1.0`；新增 expected-invalid fixture 与 schema/dispatch/art/biology 回归测试 | resolved |
| D-03 | P2 | 新分馆可能意外生成正式器物记录或媒体 | Git/路径审计确认只有一条明确 expected-invalid probe；`data/releases`、adapter、raw、intermediate、媒体和 route 均无新增 | resolved |

复核：26 schemas、8 valid/22 expected-invalid governance fixtures、physical release closure、14 valid/28 expected-invalid/4 recorded pipeline fixtures与 143/143 Python tests 通过。

## Reviewer E｜前端、无障碍与 Pages

| ID | 等级 | 初审发现 | 实际修订 | 状态 |
|---|---|---|---|---|
| E-01 | P1 | 七张卡片在宽屏和双列平板中会留下不平衡空位 | 宽屏改为 2/3/2；1024/768 双列布局把最后一张卡片居中；移动端单列 | resolved |
| E-02 | P1 | 武器馆可能被 motif 或 DOM 角色误认为已开放 | 使用带完整状态文字的非链接 `article`；只有美术馆为链接；motif `aria-hidden=true`；`#/arms` 继续进入 NotFound | resolved |
| E-03 | P2 | 初版线上测试把同文档 hash 导航错误地要求为新 HTTP 200 response | 删除错误的 response 对象断言，保留站点根 HTTP 200、NotFound UI、0 HTTP error 和 0 failed request 检查 | resolved |
| E-04 | P2 | 旧测试未覆盖 768×1024、resource 404、Accessibility 回归和 JS-off 七馆文案 | 扩展 Playwright：五种尺寸、键盘、中英切换、低带宽、reduced motion、forced colors、About/Accessibility、JS-off、first-party resources、404/console/request 监测 | resolved |

复核：本地 Playwright 5/5；1440×900 与 390×844 截图经视觉检查，无横向溢出、文字截断、第三方媒体或攻击性视觉语义。

## 阶段边界复核

- 未进入 `MUSEUM-03`，未选择首批 12 位艺术家，未改变美术馆 pipeline 范围；
- 未进入 `MUSEUM-ARMS-00`，未建立 arms adapter、live probe、正式 schema、器物数据、媒体、3D、route 或 dataset release；
- 未关闭 OD-001、OD-002 或 OD-004–011；
- 新增 raster 文件仅为本项目页面 QA 截图，不是第三方馆藏或军事媒体。
