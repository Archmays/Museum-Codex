# ADR-0001：静态优先应用与数据架构

- Status: accepted
- Date: 2026-07-11
- Decision owners: project governance

## Context

公开站点计划部署到 GitHub Pages，上游 API 的可用性、字段、速率和许可不同。应用必须在上游不可用时浏览已发布数据，并让发布内容可复现、可回滚。

## Decision

MUSEUM-01 起建议使用 React + TypeScript + Vite 构建纯静态客户端；正式数据在构建前生成版本化 JSON/GeoJSON、分片图数据和各 locale 搜索索引。浏览器不实时拼接上游 API，不持有 API key。当前阶段不安装依赖。

Vite 负责转译而不执行 TypeScript 类型检查，因此未来 CI 必须单独运行 `tsc --noEmit`，并启用 TypeScript `strict`。Sigma、MapLibre、Three 等重依赖按路由懒加载，不进入门户首屏。

- 内容：静态 release manifest 固定 schema/data/build 版本与 hash。
- 搜索：构建时生成小型倒排索引；首版评估 MiniSearch 等纯客户端库，不调用 SaaS。
- 缓存：依赖 HTTP/Pages 缓存和内容 hash；首版不默认引入 service worker。
- IndexedDB：MVP 不需要。只有收藏/历史跨会话、离线大索引或分片缓存证明超出内存/Cache Storage 时再引入。
- 多语言：BCP 47 labels + locale 独立策展文本 + 明确回退链，不复制事实实体。

## Why

React 适合状态丰富的图/地图/详情组合；TypeScript 约束发布数据契约；Vite 的静态构建和可配置 base 适配 Pages。静态 release 把采集失败从运行时故障变成维护延迟，并允许审核、权利检查和回滚发生在发布前。

## Alternatives

- Astro/静态 HTML：文本与 SEO 更强；若未来多数页面可预渲染可重评，但复杂同步探索状态需 islands/客户端层。
- Next.js/服务端框架：路由和预渲染强，但 Pages 纯静态限制与部署复杂度在 MVP 无收益。
- 实时后端/图数据库：更新及时、查询灵活，但引入运维、隐私、成本和上游故障耦合。
- 单一巨大 JSON：实现简单，但首屏、移动内存和撤回粒度不可接受。

## Costs and mitigations

静态数据更新需构建；用自动化采集/验证和不可变 release 降低成本。大型图需预分片与局部加载。纯 SPA 的 SEO/深链有限；用 hash 路由、站点地图和后续选择性预渲染缓解。客户端索引可能占内存；按语言和分馆分片。

“静态”只保证不依赖上游运行时 API，不自动等于客户端断网可用。完整断网浏览必须另行实现并验证应用壳/数据/媒体预缓存、配额与驱逐、版本迁移，以及紧急撤回如何使旧缓存失效。

## Revisit when

需要账户同步/协同写入/受控媒体、数据或索引无法在目标移动设备预算内运行、更新 SLA 低于静态构建周期，或大量公开详情页需要可索引的预渲染。

## Current official basis

[React 从零构建应用](https://react.dev/learn/build-a-react-app-from-scratch)、[React 与 TypeScript](https://react.dev/learn/typescript)、[Vite TypeScript 功能说明](https://vite.dev/guide/features.html)、[Vite 静态部署](https://vite.dev/guide/static-deploy)、[MiniSearch 官方项目](https://github.com/lucaong/minisearch)、[BCP 47](https://www.rfc-editor.org/info/rfc5646/)、[IndexedDB](https://developer.mozilla.org/en-US/docs/Web/API/IndexedDB_API)。核验日期：2026-07-11；具体依赖版本在 MUSEUM-01 建立锁文件时重新核验。
