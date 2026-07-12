---
phase_id: MUSEUM-02A
status: completed
validation_status: pass
arms_branch_registered: true
arms_branch_id: arms
public_portal_updated: true
public_hall_count: 7
arms_public_route_added: false
arms_formal_data_added: false
public_third_party_media_added: false
arms_safety_policy_ready: true
arms_data_contract_status: planned
museum_03_scope_changed: false
pages_regression_status: pass
open_decisions_count: 10
museum_03_recommended: true
---

# MUSEUM-02A 阶段报告

报告日期：2026-07-12（Asia/Shanghai）
项目根目录：`D:\ChatGPT-Codex-Projects\Museum-Codex`

## 1. 起始状态

- 起始 commit：`99e427aefd8d7bbfd6c5a447ec16c96d464645d8`；开始时本地 `main`、`origin/main` 与 GitHub 默认分支 `main` 一致，工作区干净。
- `MUSEUM-02` 为 `completed/pass`；Pages 已公开且使用 workflow 部署。
- 未进入 `MUSEUM-03`，没有正式 12 人名单、arms 数据、arms adapter、arms route 或第三方媒体。
- `skill/SKILL_INDEX.md` 不存在，因此没有虚构项目 skill；执行使用全局 `codex-quality-guard`、`frontend-design` 与 `playwright`。
- 修改前重新运行基线：26/26 schemas、29/29 governance fixtures、17 sources、physical release closure、14 valid/28 expected-invalid/4 recorded pipeline fixtures、139/139 Python tests、20/20 Vitest/RTL、lint、strict typecheck、production build、repository/public/dist leakage checks均通过。

## 2. 变更原因、命名与范围

现有架构和门户基于六馆，无法只通过新增卡片安全地登记第七分馆。用户确认：

- 中文公开名称：`武器博物馆`；
- 英文公开名称：`Museum of Arms & Armor`；
- branch ID：`arms`；
- 当前状态：`planned / portal-visible / data-contract-not-yet-implemented`。

本阶段只完成跨馆治理、common contract、不可点击门户入口和 Pages 修订。没有开始 `MUSEUM-03` 或 `MUSEUM-ARMS-00`。

## 3. 文档与总体架构

新增 `docs/06_arms_museum/` 六份正式规划文件：

1. `arms-museum-branch-charter.md`；
2. `safety-ethics-and-public-content-policy.md`；
3. `knowledge-model-outline.md`；
4. `source-and-rights-research-brief.md`；
5. `interactive-experience-concepts.md`；
6. `arms-museum-roadmap.md`。

README、项目章程、分馆策略、总体架构、领域模型、无障碍/视觉语义、AI 政策、主路线、开放决定和风险登记均更新为七馆。不可导航的 `portal-visible` 筹备标记与正式分馆原型被明确分开；文明馆、科学馆和美术馆边界通过稳定实体与 Claim 连接，而非标签重叠。

主路线新增：

- `MUSEUM-ARMS-00`：来源、分类、权利、安全与敏感内容专项研究；
- `MUSEUM-ARMS-01`：小范围历史器物知识图谱与非操作性展陈原型。

两者均需用户另行授权，不与美术馆阶段混并。

## 4. 安全与伦理边界

正式政策路径：`docs/06_arms_museum/safety-ethics-and-public-content-policy.md`。

政策允许经审核的历史、馆藏身份、材料/一般工艺、高层次原理、保护、仪式、制度、来源、归还、冲突人类影响和非操作性 3D 观察；阻断制造、参数、改装、恢复功能、装填、发射、瞄准、拆装、维修启用、采购、规避监管、人体弱点、伤害优化、现实战术和暴力/极端主义娱乐化。

现代或受监管武器只允许高层次历史、政策、设计史和博物馆说明，并要求更高等级审核。儿童/家庭路径默认非图像化、非操作化、可跳过敏感内容。`public`/`dist` scanner 新增 `operational_arms_content` fail-closed 规则；扫描范围只针对公开输入与构建产物，不误报政策文档中的禁止词。

## 5. Knowledge model 与来源研究

知识模型只提供 outline，未创建 branch schema。候选实体和关系覆盖器物/甲胄、maker、材料/工艺、高层次机制、来源/收藏/保护事件、冲突/法律/仪式/人类影响及其 Claim–Evidence–Source；明确禁止 `best_target`、`lethality_score`、`optimal_range`、`penetration_optimization`、`build_steps`、`modification_instructions`、`supplier`、`market_price` 和其他现实使用/优化字段。

来源 brief 只规定未来必须核验的来源类别、官方身份、metadata/media 许可、API/IIIF/下载边界、现代操作资料、静态公开适用性、敏感内容、文化财产/provenance 风险和条款版本。没有选择来源、建立 adapter、live probe、抓取或下载媒体。

## 6. Schema、版本与 canonical dispatch

- `schemas/common/entity.schema.json` 的 `branch_id` enum 加入 `arms`；
- 这是兼容新增，`schemas/schema-manifest.json` 中 `common/entity` 从 `1.0.0` 升为 `1.1.0`；其余未受影响 schema 保持 `1.0.0`；
- canonical target dispatch 遇到任何 actual `branch_id=arms` 记录时返回 `arms_branch_schema_not_implemented`，明确禁止回退 common entity；
- 新增 `fixtures/governance/invalid/arms-branch-schema-not-implemented.json`，它是 expected-invalid contract probe，不是正式器物数据；
- unit tests 分别验证 common enum 接受 `arms`、arms concrete dispatch fail-closed、art/biology dispatch 不变、schema manifest 版本和 physical closure；pipeline canonical dispatch 回归保持通过。

本阶段 schema 总数仍为 26，没有空壳 arms entity schema，也没有 publishable/published arms 记录。

## 7. 门户七馆变更

- `HallId` 顺序扩展为 `art / biology / music / games / civilization / arms / science`；
- 中英文首页、meta 与 JS-off 文案由六馆更新为七馆；
- 武器馆使用用户确认的中英文名称、描述与筹备状态；
- 原创 motif 使用防护弧、锻造层纹、年代刻痕和馆藏编号点，不含真实枪械、准星、子弹、爆炸、血迹、击杀图标、交叉武器徽章或军事 HUD；
- 武器馆由非链接 `article` 呈现，motif 为 `aria-hidden=true`；只有美术馆仍是可导航入口；
- `src/App.tsx` 未增加 `/arms` route，`#/arms` 继续显示 NotFound。

## 8. 响应式与无障碍

宽屏七卡布局为 2/3/2；1024px 与 768px 双列布局将最后一张卡片居中；390px 与 360px 单列。Playwright 实测：

- 1440×900；
- 1024×768；
- 768×1024；
- 390×844；
- 360×800。

所有尺寸无横向溢出，中文/英文无截断，美术馆 featured 层级清楚。键盘顺序、skip link、触控、低带宽、reduced motion、forced colors、About、Accessibility 和 JS-off 回归通过；状态不只依靠颜色。

## 9. 最终本地验证

```text
schemas: 26/26 PASS
governance fixtures: 30/30 PASS (8 valid, 22 expected-invalid)
source registry: 17 sources PASS
physical release fixture: PASS
pipeline schemas/fixtures/contracts: 10 schemas, 14 valid, 28 expected-invalid, 4 recorded, 4 adapters PASS
Python tests: 143/143 PASS
network primitives during Python tests: disabled PASS
npm ci: 242 packages, 0 vulnerabilities
lint: PASS
strict typecheck: PASS
Vitest/RTL: 22/22 PASS
production build: PASS
dist: 4 files, 286,923 bytes
build/resource/public-leakage/repository-safety checks: PASS
local Playwright: 5/5 PASS
```

公开 artifact 扫描没有第三方媒体、candidate/raw/review/probe 数据或操作化武器内容。仓库安全扫描没有凭据模式或超过 5 MiB 的文件。

## 10. Pages workflow

实现 commit：`0f7760286de06008cc1901b230ae1db98c555905`（`Phase MUSEUM-02A add Arms and Armor museum branch`）。

- workflow run：`29198773759`；
- run URL：`https://github.com/Archmays/Museum-Codex/actions/runs/29198773759`；
- head SHA：`0f7760286de06008cc1901b230ae1db98c555905`；
- build job `86666375732`：success；
- deploy job `86666491736`：success；
- build 中所有 governance、pipeline、Python、frontend、build、leakage 与 repository safety steps 均 success。

Pages API：`public=true`、`build_type=workflow`、`https_enforced=true`。

## 11. 线上验证

实际公开 URL：`https://archmays.github.io/Museum-Codex/`，HTTP 200。

以该 URL 运行 Playwright 5/5：

- 首页七馆与中英文切换；
- 武器馆可见、不可点击、无 route；
- 美术馆可进入；
- About 与 Accessibility；
- 五种要求尺寸、键盘、低带宽、reduced motion、forced colors、JS-off；
- console errors 0；
- failed requests 0；
- HTTP/resource 404 0；
- 第三方 runtime/media 0；
- 横向溢出 0。

机器结果：`docs/qa/museum-02a/playwright-results.json`。

## 12. 截图

- 桌面：`docs/qa/museum-02a/desktop-home-1440x900.png`（1440×900 viewport，full-page 1440×2932）；
- 移动：`docs/qa/museum-02a/mobile-home-390x844.png`（390×844 viewport，full-page 390×4560）。

截图来自线上 Pages 回归，只包含项目原创页面、CSS/HTML 几何和内联矢量；不是第三方馆藏或军事媒体。

## 13. Reviewer A–E

完整记录：`docs/qa/museum-02a/adversarial-review.md`。

| Reviewer | 结论 |
|---|---|
| A 博物馆与信息架构 | 七馆、分馆准入、相邻分馆边界和治理契约一致；resolved |
| B 历史、来源与策展 | 仪式、象征、来源、收藏、人类代价与跨文化分类风险已覆盖；resolved |
| C 安全、伦理与年龄适宜性 | 政策、现代/家庭边界、public scanner 和安全 motif 完成；resolved |
| D 数据与治理 | enum/version/fixture/dispatch/physical closure 闭合，无 arms 正式数据；resolved |
| E 前端、无障碍与 Pages | 七卡布局、双语、不可点击、五尺寸、a11y、JS-off 和 live Pages 通过；resolved |

最终无未解决 P0、P1 或 P2；本阶段没有新增 P3。

## 14. Git 与工作区

- 起始 commit：`99e427aefd8d7bbfd6c5a447ec16c96d464645d8`；
- 实现 commit：`0f7760286de06008cc1901b230ae1db98c555905`；
- 本报告与线上 QA 证据使用后续 closeout commit 提交；其精确 hash 在最终 Git handoff 中记录，避免在提交内容中制造自引用 hash；
- 未 reset、force push 或改写历史；未回写 `MUSEUM-00/01/02` 报告伪造武器馆当时已存在。

## 15. 未决事项

当前开放决定为 10 项：OD-001、OD-002、OD-004–OD-011。OD-003 仍为已关闭的 Pages 公开决定；本阶段没有关闭许可、首批艺术家、性能、地图、媒体、搜索、隐私、投诉或 arms 内容边界决定。

`MUSEUM-02` 的两项既有 P3（应用层 append-only 非 WORM；DNS 公网预检非 cryptographic pinning）保持原 owner 与复核期限，本阶段未扩大其范围。

## 16. MUSEUM-03 与禁止事项复核

`museum_03_scope_changed: false`。本阶段没有选择首批 12 位艺术家、修改美术馆 pipeline 正式范围、建立 arms adapter/live probe、抓取器物、下载图片/3D、创建 arms route/schema/release、发布现代技术资料、操作/改装/采购/战术说明、排名或伤害模拟。

`museum_03_recommended: true` 只表示 `MUSEUM-02` 的既有技术准入在本次横向修订后仍保持通过，不是进入 `MUSEUM-03` 的授权。`MUSEUM-ARMS-00` 同样需要用户另行授权。

## 17. 验收门槛结论

`MUSEUM-02A` 标记 `completed/pass`。第七分馆命名、branch ID、总体架构、安全政策、knowledge model outline、未来路线、OD-011、common enum/semver/fail-closed dispatch、七馆不可点击门户、测试、Pages、线上 Playwright、截图与 Reviewer A–E 均完成；没有正式 arms 数据、第三方媒体或阶段越界。
