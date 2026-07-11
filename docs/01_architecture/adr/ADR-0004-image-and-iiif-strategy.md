# ADR-0004：图像、IIIF 与三维策略

- Status: accepted for planning
- Date: 2026-07-11

## Context

高分辨率艺术作品既需要细节浏览，也有逐资产许可、来源服务稳定性、移动带宽和撤回要求。API/IIIF 可访问性不等于再发布授权。

## Decision

1. 优先使用来源提供且资产权利允许的 IIIF Image API / Presentation manifest；保存 canonical manifest URL、版本/level、权利和归属。
2. 对允许自托管的资产生成尺寸受控衍生物：AVIF（可用时）+ WebP + 保守回退，使用响应式 `srcset`、尺寸属性和懒加载；不默认提交原始巨幅文件。
3. 许可仅允许链接/查看时，站点不复制字节，并准备低风险占位与来源跳转；外部服务故障不影响文本和证据浏览。
4. 任何 crop、颜色处理、修复对比或科学成像层都记录变换与来源；不得让有损处理替代研究母版。
5. Three.js 不进入美术馆 MVP 基线。仅当某展项的空间学习目标、授权资产、性能和无障碍替代明确时，在独立 ADR 中启用。

## Why

IIIF 支持区域/尺寸请求和多层呈现，避免首屏下载整幅图；自托管衍生物提供撤回与缓存控制。现代格式节省带宽，但必须保留兼容路径和视觉 QA。

## Alternatives

- 直接嵌入来源大图：最简单，但性能、条款和可用性不可控。
- 全部下载自托管：离线可靠，但存储、许可、撤回和 Git 限制高。
- 自建 IIIF 服务器：控制强，GitHub Pages 无法承载动态服务；规模需要时再评估。
- 默认 Three.js 展厅：视觉强但输入、移动性能、可访问与制作成本不符合 MVP 价值排序。

## Costs and safeguards

跨源 IIIF 能力与 CORS 不一致；采集时探测并记录。AVIF 编码成本与浏览器差异需视觉回归。alt 描述与深度策展描述分开，避免把作品意义压缩成文件名。每次发布扫描 unknown/development-only/过期或禁止再发布资产。

## Revisit when

来源 IIIF 不稳定、撤回 SLA 要求完全自托管、图像流量/仓库尺寸超预算、研究需要色彩管理/测量级图像，或 3D 展项有明确学习证据。

## Current official basis

[IIIF Image API 3.0](https://iiif.io/api/image/3.0/)、[IIIF Presentation API 3.0](https://iiif.io/api/presentation/3.0/)、[IIIF 静态 Level 0 指南](https://iiif.io/guides/guide_for_implementers/)、[MDN 图片格式](https://developer.mozilla.org/en-US/docs/Web/Media/Guides/Formats/Image_types)、[`picture` 元素](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/picture)、[Three.js WebGLRenderer](https://threejs.org/docs/pages/WebGLRenderer.html)、[Three.js 资源释放](https://threejs.org/manual/en/cleanup.html)。核验日期：2026-07-11；IIIF 协议兼容性不构成版权许可。
