---
phase_id: MUSEUM-01
status: completed
validation_status: pass
portal_shell_ready: true
pages_enabled: true
pages_build_type: workflow
pages_https_enforced: true
pages_deployment_status: success
pages_url: https://archmays.github.io/Museum-Codex/
online_http_status: 200
online_playwright_status: pass
repository_visibility: public
open_decisions_count: 9
museum_02_recommended: true
---

# MUSEUM-01 阶段报告

报告日期：2026-07-11（Asia/Shanghai）  
项目根目录：`D:\ChatGPT-Codex-Projects\Museum-Codex`

## 1. 开始时的仓库与 Pages 状态

- 分支：`main`；工作区干净；本地与 `origin/main` 均为 MUSEUM-00 基线 `2b8fe19a1af37f02720fe40640690f6b87db4819`，基线后没有其他提交需要兼容。
- Remote：`https://github.com/Archmays/Museum-Codex.git`。
- `gh auth status`：账户 `Archmays`，具备 `repo` 与 `workflow` scope；仓库 API 确认为 `PUBLIC`。
- 初始 `GET /repos/Archmays/Museum-Codex/pages`：HTTP 404；无既有 Pages workflow 或冲突发布配置。
- `skill/SKILL_INDEX.md` 不存在，因此没有项目技能可用；执行使用全局 `codex-quality-guard`、`frontend-design`、`make-interfaces-feel-better` 与 `playwright`。
- 用户决定 OD-003：`repository=public`、`pages=public`；OD-001/OD-002 保持未决和保留权利状态。

## 2. MUSEUM-00 回归结果

在全新临时 Python 虚拟环境安装 `requirements-dev.txt` 后通过：

```text
schemas: 16
governance fixtures: 29 (8 valid, 21 expected-invalid)
physical release bundles: 1
sources: 17 (art 10, biology 7)
publishable media records: 2
Python tests: 44/44 PASS
```

MUSEUM-00 报告未回改。真实 Linux Actions 暴露两处原基线的 CRLF/LF 字节快照不一致；修复仅将受控 JSON 规范化到 `.gitattributes` 已声明的 LF，并同步真实 bytes、SHA-256 与 release content hash，没有更改 schema、规则语义、fixture 记录或验证器。

## 3. 前端技术选择

- React 19.2.7、TypeScript 6.0.3、Vite 8.1.4、React Router 7.18.1。
- Node.js 官方 Active LTS 线固定为 v24；`.node-version` 与 Actions 固定 `24.18.0`，`engines` 限定 `24.x`。
- ESLint 10.7.0、Vitest 4.1.10、React Testing Library、Playwright 1.61.1。
- TypeScript 采用 `strict`，Vite production `base=/Museum-Codex/`，路由采用 `HashRouter`。
- 运行时无后端、外部 API、CDN、远程字体、远程图片、分析、Cookie 或账户。

## 4. 页面结构

公开路由：

- `#/`：博物馆首页与六个分馆入口；
- `#/art`：美术馆序厅与未来探索方式；
- `#/about`：博物馆方法、知识可信度与当前权利状态；
- `#/accessibility`：无障碍与低带宽说明和控制；
- 未知 hash 路由进入自然的未开放说明。

只有美术馆入口可导航；生物馆、音乐馆、游戏馆、文明馆、科学馆均以自然参观语言说明筹备状态，不链接到虚假内容。

## 5. 视觉设计

原创方向为“夜间知识中庭”：深色但不压抑，使用克制金色、铜绿、细点阵与知识轨道。六馆不用通用图标，而分别使用构图框/颜料层、生态环/细胞、声波、规则路径、城市时间层、观察透镜。全部由 CSS、HTML 与原创 SVG/程序化几何实现，没有第三方媒体或生成式仿画。

## 6. 多语言实现

- 中文默认，英文可切换；导航、标题、分馆、状态、说明、序厅、关于、无障碍和错误文案均覆盖。
- 文案集中在 `src/i18n/translations.ts`，没有散落于大量组件。
- 语言仅保存在浏览器 `localStorage`，不上传服务器；页面 `lang` 与标题同步更新。

## 7. 无障碍实现

- 语义化 `header/nav/main/footer`、合理 heading、可见 focus、44px 主要触控目标、键盘全路径。
- Skip link 通过程序化聚焦主内容，避免占用 HashRouter fragment；激活后路由保持不变。
- 展馆状态使用文字与符号，不依赖颜色；SVG/程序化装饰标记为 `aria-hidden`。
- 支持 `prefers-reduced-motion`、forced colors、显式低带宽模式与本地偏好。
- 低带宽模式停止环境轨道/星图等非必要运动；核心文字与导航保持完整。
- JavaScript 禁用时显示中英基本说明，实测对比度 16.39:1。
- 小辅助文字 token 对已知最暗表面对比度为 5.67:1 以上。

## 8. 静态 release loader

`src/data/release-loader.ts` 支持 manifest 缺失、空馆、schema major 不兼容、网络/解析失败、正常加载与自然访客文案。它只接受完整 canonical `dataset_release`、`public_release=true`、`publishable/published` 状态，并精确核对：

- 全部 `included_*_ids` 与 data manifest record IDs；
- source registry、media、notices、attributions、license decisions typed record closure；
- schema versions、content hash 形状、artifact path/hash、许可决策与 attribution/media 集合。

成功测试使用已通过 Python physical-bundle validator 的真实 fixture；伪 ID、非公开状态、缺 rights/files/hash/license/source/media record 均 fail-closed。浏览器形状检查不替代构建期真实字节/hash 验证。

## 9. 测试结果

最终本地门禁：

```text
npm ci: PASS (242 packages)
lint: PASS, 0 warnings
typecheck: PASS, strict
Vitest/RTL: 20/20 PASS
production build: PASS
dist: 4 files, 284,783 bytes
base/resource closure: PASS
external runtime dependency scan: PASS
secret scan: PASS
large-file scan: PASS (no file > 5 MiB)
Python governance/source/media/physical release: PASS
Python tests: 44/44 PASS
```

## 10. Pages workflow

`.github/workflows/deploy-pages.yml`：

- 触发：push `main`、`workflow_dispatch`；
- concurrency：`group=pages`、`cancel-in-progress=false`，保留正在部署的 run，同时由 GitHub concurrency 只保留最新 pending run；
- build job：仅 `contents: read`；
- deploy job：仅 `pages: write`、`id-token: write`；
- environment：`github-pages`；
- gate 顺序：Python 治理/来源/权利/物理 fixture/测试 → `npm ci` → lint → typecheck → 前端测试 → build → 外部依赖/secret/大文件扫描 → artifact；
- 六个官方 Actions 均固定到完整 SHA，并在注释记录 release tag。

## 11. Pages API 配置过程

1. 初始 GET：404。
2. POST `{"build_type":"workflow"}`：成功创建。
3. 后续 GET：`html_url=https://archmays.github.io/Museum-Codex/`、`build_type=workflow`、`https_enforced=true`、`cname=null`、`public=true`。
4. 未使用 legacy `main` 根目录或 `/docs` 发布源；未写入 PAT 或长期 secret。

## 12. 实际 workflow runs

| Run | Commit | 结果 | 实际问题与修复 |
|---|---|---|---|
| 29154793176 | `dfe3db9` | failure | setup-python pip cache 未找到非默认文件名；增加 `cache-dependency-path: requirements-dev.txt` |
| 29154850734 | `048938b` | failure | 物理 fixture manifest 按 CRLF 记录 bytes/hash，而 Linux checkout 为 LF；规范化 LF 并同步闭包 |
| 29154986803 | `7ab3bfa` | failure | source license rules snapshot 同类 LF hash 不一致；同步 canonical LF snapshot hash |
| 29155093901 | `10ca328` | **success** | build 与 deploy 全部成功 |

成功 run：<https://github.com/Archmays/Museum-Codex/actions/runs/29155093901>。这是部署证据链接，不是博物馆访问链接。

## 13. 实际 Pages URL

**<https://archmays.github.io/Museum-Codex/>**

该地址来自 GitHub Pages API 实际返回值，不是按规则猜测。

## 14. HTTP 验证

- 首页：HTTP 200，HTTPS；
- favicon：HTTP 200；
- `assets/index-DX2fTG7b.js`：HTTP 200；
- `assets/index-rapYWxPC.css`：HTTP 200；
- 无错误 `/assets/...` 域名根路径；
- 无混合内容、远程字体、远程图片、运行时外部 API 或失败网络请求；
- 页面标题为“博物馆 · Museum”。

## 15. Playwright 线上验证

直接针对公开 Pages URL 执行，5/5 PASS：

1. 1440×900 首页、HTTP/标题、中英切换、Skip、完整主要 Tab 顺序、控制台与网络；
2. 390×844 移动首页、低带宽实际降级与无横向溢出；
3. 1024×768 美术馆序厅、hash 刷新与无横向溢出；
4. 360×800 关于与权利、reduced motion、forced colors 与无横向溢出；
5. JavaScript 禁用、HTTP 200、基本说明可见与对比度门槛。

结果：`5 expected / 0 unexpected / 0 flaky`，控制台错误 0，失败请求 0，404 资源 0。

## 16. 截图路径

- `docs/qa/museum-01/desktop-home-1440x900.png`（1440×2932）
- `docs/qa/museum-01/mobile-home-390x844.png`（390×4192）
- `docs/qa/museum-01/art-foyer-1024x768.png`（1024×2008）
- `docs/qa/museum-01/about-rights-360x800.png`（360×2468）
- `docs/qa/museum-01/playwright-results.json`

最终文件由线上 Playwright run 生成。

## 17. 对抗性审查结果

| Reviewer | 初审 | Finding | 修复与复审 |
|---|---|---|---|
| A 产品与博物馆体验 | PASS | 无 substantive finding | PASS |
| B 前端与视觉 | P2 | 1024px 序厅装饰向右溢出 41px | 约束装饰宽度/右边界，增加全尺寸 scrollWidth 断言；PASS |
| C 无障碍与低带宽 | P1/P2 | JS-off 对比度、小字对比度、E2E 证据不足 | 对比度 16.39/≥5.67，补 Skip/键盘/reduced/forced/低带宽/JS-off；PASS |
| D Pages 与安全 | PASS | 无 substantive finding | PASS |
| E 治理与版权 | P1 | loader 未完整核对 physical record closure | typed exact record closure + 篡改测试；PASS |

## 18. 修订内容

审查后实际修复：响应式溢出、Skip 与 hash 路由冲突、JS-off 和小字对比度、低带宽/高对比/动画 QA、release loader 完整闭包。线上 CI 后继续修复 Python cache dependency path 与两处跨平台 LF 字节快照。所有修复均重新运行对应门禁。

## 19. Git commit

- 实现提交：`dfe3db9fda0cafd1ed73b42364ff6e457a39be2d`；
- workflow cache 修复：`048938be9b97f7896f0b28ce33f857b5ef40115a`；
- physical fixture LF 闭包：`7ab3bfa07f2d0deb414ab85291366e11f8211300`；
- 成功部署提交：`10ca32802650211f5b449a3b492dd51dcb6e820f`；
- 本报告与最终线上截图属于后续证据提交；该提交的完整 hash 在最终任务回复中报告，避免在 commit 内伪造自指 hash。

## 20. Remote 状态

- Remote：`origin=https://github.com/Archmays/Museum-Codex.git`；
- 默认分支：`main`；
- 成功部署时本地与远端 commit 一致；
- repository homepage 已更新为真实 Pages URL。

## 21. 未决事项

OD-003 已关闭。当前 **9** 项未决：OD-001、OD-002、OD-004 至 OD-010。代码和原创内容未新增开放许可证；页面保留权利声明。未确定首批 12 位艺术家、目标设备量化预算、地图/IIIF/搜索/分析/投诉流程等后续决定。

## 22. 退出门槛

全部 MUSEUM-01 退出门槛已满足：治理回归、门户页面、六馆、空序厅、i18n、a11y、低带宽、loader、测试、build、安全扫描、Pages API、workflow success、HTTPS、HTTP 200、线上 Playwright、README/homepage、截图与 A–E 复审均为 PASS。没有进入艺术家数据、艺术星海、AB 路径、时空地图或数字展厅开发。

结论：`MUSEUM-01 completed`。

## 23. 是否建议进入 MUSEUM-02

`museum_02_recommended=true`：建议在用户另行明确授权后进入 MUSEUM-02；本阶段不会自动开始下一阶段。
