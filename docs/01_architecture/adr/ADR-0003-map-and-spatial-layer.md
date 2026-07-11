# ADR-0003：地图与空间层

- Status: accepted for later phase
- Date: 2026-07-11

## Context

艺术时空地图与未来生态区地图需要矢量数据、交互过滤和静态部署。底图许可、样式与 tile 服务不能被“开源库”一词掩盖。

## Decision

MUSEUM-07/BIO 原型首选 **MapLibre GL JS** 作为渲染器，分馆数据发布为版本化 GeoJSON 或矢量分片。渲染库许可、底图/tiles、字体 glyphs、sprites 和地理数据许可分别登记。初期采用明确许可的公共服务或自托管静态资源；不得把开发 token 放进仓库。

小数据使用按时代/地区分片的 GeoJSON；超出传输/渲染预算后再生成 PMTiles/矢量 tiles。地点列表是地图的等价可访问入口。

## Why

MapLibre 是供应商中立的 WebGL 地图客户端，适合静态站点和可替换样式。GeoJSON 透明、易版本化；先保留简单数据链，再以测量结果决定分片格式。

## Alternatives

- Leaflet：轻量、DOM/栅格生态成熟；若只需少量点和简单图层可优先。
- 商业托管地图：数据与样式完善，但 token、成本、条款和离线容错风险更高。
- 自建 tile 服务：控制强，超出 Pages 和本阶段运维范围。

## Costs and safeguards

WebGL 地图需要移动 GPU/内存预算、键盘替代和减少运动；历史边界具有时间与不确定性，不能当现代精确行政事实。生态记录以记录/推定/稳定范围分层，不把点聚合为分布结论。

## Revisit when

外部 tile 条款或配额不适合公开流量、GeoJSON 首屏超过预算、需要离线完整地图、历史边界时态查询或服务端空间分析。

## Current official basis

[MapLibre GL JS 文档](https://maplibre.org/maplibre-gl-js/docs/)、[大型 GeoJSON 优化](https://maplibre.org/maplibre-gl-js/docs/guides/large-data/)、[GeoJSON RFC 7946](https://www.rfc-editor.org/info/rfc7946/)。核验日期：2026-07-11。库的开源许可不覆盖底图、tiles、glyphs、sprites 或地理数据。
