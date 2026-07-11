# ADR-0005：GitHub Pages 发布方式

- Status: accepted; implemented in MUSEUM-01
- Date: 2026-07-11

## Context

项目希望低运维公开发布，同时保留审核门禁。Pages 是静态托管，不提供运行时后端；项目站点通常位于 `/<repo>/` 子路径，SPA history 深链会遇到 404。

## Decision

MUSEUM-01 才建立 GitHub Actions + Pages。Vite `base` 显式匹配仓库子路径；首版采用 hash 路由保证刷新/深链不依赖 404 hack，或对可预渲染详情生成真实静态路径。workflow 构建固定 release，依次运行测试、schema/引用/权利/敏感信息/大文件检查，再上传 Pages artifact。默认权限只给 `contents: read`、`pages: write`、`id-token: write` 的部署 job，环境使用 GitHub Pages。

第三方 Actions 固定到经核验的完整 commit SHA。当前官方 Pages 限额包括发布站点最大 1 GB、部署超时 10 分钟和每月 100 GB 软带宽；高分辨率母版与 raw 数据不能靠 Pages 承载。

MUSEUM-00 不创建 workflow、不启用 Pages、不发布站点。

## Why

Pages 与静态优先契合，成本和运维低。Actions 把发布门禁变成可复核流水线。hash 路由牺牲部分 URL 美观，换取项目站点上的确定性。

## Alternatives

- history 路由 + 404 重写：URL 更自然，但错误页复制、直链和爬虫行为脆弱。
- 预渲染全部页面：SEO/可访问首屏好；图谱与数据规模增大时构建成本高，可选择性采用。
- Cloudflare Pages/Netlify/Vercel：路由和边缘功能更强，但增加供应商配置；需要重定向、预览或函数时重评。
- 自管服务器：控制最大，不符合当前运维与静态边界。

## Costs and safeguards

公开 Pages 使获准文件可下载，不能代替访问控制。单文件与仓库规模受限制，应分片、压缩并避免原始媒体。Action 固定版本、依赖锁文件、最小权限；fork PR 不取得采集 secrets。发布后仍需撤回流程，新 release 必须能使被撤回资产不再被引用并按托管缓存策略响应。

## Revisit when

需要整洁 history 路由/大规模预渲染、构建或 artifact 超出 Pages 限制、必须访问控制/服务器函数，或撤回传播要求无法由静态托管满足。

## Current official basis

[GitHub Pages 是静态托管](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages)、[Pages 限额](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits)、[Pages 自定义 Actions 工作流](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)、[Actions 安全使用](https://docs.github.com/en/actions/reference/security/secure-use)、[React Router HashRouter](https://api.reactrouter.com/v7/functions/react-router.HashRouter.html)。核验日期：2026-07-11；正式实施前再次核验平台限额与 workflow 权限。
