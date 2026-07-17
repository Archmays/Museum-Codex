# ADR-0010：艺术时空地图的完全本地空间运行时

- Status: accepted
- Date: 2026-07-17
- Phase: MUSEUM-07
- Closes: OD-006

## Context

艺术时空地图必须在 GitHub Pages 上静态运行，并区分来源支持的历史地点、现代名称、艺术家活动、作品创作地点和当前馆藏机构。公开运行时不得依赖 tile provider、token、在线 geocoder、用户位置、remote style/glyph/sprite 或现代政治边界；WebGL 不可用时仍须完成筛选、选择、证据阅读、分享和打印。

## Decision

1. 底图使用 Natural Earth 官方 `1:110m` physical vectors，仅纳入 land、coastline、lakes。原始 ZIP 保存在 ignored source vault，公开 release 保存确定性 WGS84 GeoJSON、parent/output SHA-256、转换工具和配方。底图按 public domain 处理，页面显示 `Made with Natural Earth`。
2. 渲染器使用 MapLibre GL JS `5.24.0`，在 `package.json` 与 lockfile exact pin。2026-07-16 对官方 npm 与 GitHub release 重新核验：该版本为 stable、非 alpha/beta/RC/prerelease，许可证为 BSD-3-Clause；`6.0.0-*` 为 prerelease，不采用。
3. MapLibre 只在 `#/art/map` 的 map view 懒加载。style 为同源 release 内联/local JSON，sources 只接受已核验的同源 GeoJSON；不配置 tiles、glyphs、sprite、image URL、worker URL、geocoder、telemetry、geolocation 或外部请求。
4. 地图固定 2D Mercator、pitch/bearing 0、禁用旋转、有限缩放、cooperative gestures、无连续动画。图层只含 background、land、coastline、lakes、地点 marker、不确定性与选择状态；不绘制现代国界、道路、商业 POI、排名填色或推断路线。
5. map、timeline 和 place table 使用同一 URL/state contract。低带宽、forced colors、无 WebGL、context lost 或 renderer error 自动回退到 timeline/list，并保留筛选、选择和 URL。地图另有 DOM marker navigator；timeline/list 是完整等价体验，不是错误页。

## Evidence and provenance

- Natural Earth official 1:110m physical vectors: <https://www.naturalearthdata.com/downloads/110m-physical-vectors/>
- MapLibre npm package: <https://www.npmjs.com/package/maplibre-gl>
- MapLibre stable release: <https://github.com/maplibre/maplibre-gl-js/releases/tag/v5.24.0>
- Getty LOD and licensing: <https://www.getty.edu/research/tools/vocabularies/lod/>
- Physical release bindings: `public/releases/art-time-place-1.3.0/basemap-manifest.json`, `map-style.json`, `map-source-attributions.json`, `od-006-snapshot.json`

## Consequences and safeguards

- 不使用现代行政边界作为历史事实；自然地理轮廓也明确声明不等于历史政治边界。
- city centroid 不表示具体建筑；regional centroid 显示明显不确定性；unknown 坐标只进入 timeline/list。
- 时间排序不构成 movement claim，不生成艺术家旅行路线。
- current holding institution 与 artwork creation place 永久分层；缺少明确创作地来源时保持 `not_asserted`。
- renderer、底图和地点数据分别执行 gzip 预算、同源请求扫描、hash 校验与 deterministic rebuild。若 MapLibre 不能继续满足 stable/security/bundle/a11y 门禁，自动改用共享 contract 的确定性 SVG/Canvas 2D renderer，而不等待逐项人工选择。

## Revisit when

MapLibre 稳定版本或安全状态改变、Natural Earth 来源/许可改变、同源静态 GeoJSON 超过预算、Pages 不再适用，或未来经用户授权需要有时间语义的历史边界模型。
