# ADR-0002：关系图引擎与路径计算

- Status: accepted for MVP planning
- Date: 2026-07-11

## Context

美术馆预计从 12 位试点扩展到更大图谱，需要 WebGL 渲染、可解释过滤、局部展开和 AB 路径。无障碍不能依赖 canvas 图本身。

## Decision

首选 **Graphology** 作为内存图与算法/数据结构，**Sigma.js** 作为艺术星海的 WebGL 渲染层。Graphology 负责邻域、最短路径、连通性、过滤视图和序列化；Sigma 只负责渲染与交互。所有可见关系同步提供 DOM 列表/详情。

实施时选择当时的稳定 Sigma 主线并锁定版本；截至核验日，官方明确 Sigma v4 仍为 alpha，不作为默认生产依赖。布局优先在发布构建中预计算并固定版本；可选 ForceAtlas2 运行时探索放入 Web Worker。

AB 路径不采用含混的综合分数。MVP 先按公开/审核状态、时间、方向、关系类型和 A/B/C 开关过滤，再对单位 hop 运行 Graphology 双向 BFS；最多 3 条无环替代路径由有界 Yen 枚举产生，`K≤3`、`max_hops≤6`、候选扩展上限 `10,000`。A/B/C 只作过滤与同 hop 的确定性排序（A 边数量优先，最终按稳定 ID），四类度量不合成边权。比较模式显式允许 C，历史模式不允许。若上限命中则返回“搜索预算已达”，不伪装为无路径。更大规模可在构建期预计算常用路径；算法与上限写入 release。

## Why

Graphology 与 Sigma 职责分离，适合静态 JSON 和局部子图；WebGL 比 DOM/SVG 更能承受大量点边。数据层不绑定渲染器，未来可更换视觉层。

## Alternatives

- Cytoscape.js：图分析、布局和复合图能力完整，扩展生态成熟；若编辑、复杂复合网络或内置算法成为重点，可能更合适。大规模视觉性能和包体需基准测试。
- D3/SVG：高度可定制且 DOM 语义更直接，但大量边的性能和交互维护成本较高。
- 服务端图数据库：适合超大动态图与协作查询，本阶段增加不必要运维。

## Costs and safeguards

WebGL 不天然可访问，必须维护文本列表、焦点模型、图例和状态公告。布局可能让距离看似有意义，因此 UI 明示“距离不代表价值或关系强度”。移动端默认局部子图、减少标签和边；建立 1k/10k/50k 节点的设备基准后再确定上限。

### MUSEUM-04 性能合同

基准图固定三档：`1k V / 5k E`、`10k V / 60k E`、`50k V / 300k E`，每节点至少中英 2 个 labels、每边含完整治理字段。移动可见子图上限 `150 V / 600 E`，桌面 `300 V / 1,200 E`。在用户确认的中端 4 GB Android 实机和一台主流桌面浏览器上，冷启动到可交互目标分别 ≤2.5 s/1.5 s，节点选择反馈 ≤100 ms，筛选或 AB 路径 ≤500 ms，交互期间 JS heap ≤200 MB，平移/缩放 p95 ≥30 FPS。50k 档可分片/worker 加载，但不得一次显示全边。模拟节流只能预检，不能替代实机验收；任何未达标都触发分片/预计算或技术重评。

## Revisit when

真实 release 超过移动端内存/帧率预算；需要复杂图编辑/复合节点；路径计算超过交互预算；或无障碍替代与 Sigma 状态同步成本不可接受。届时用同一基准数据比较 Cytoscape、预计算和后端查询。

## Current official basis

[Sigma 官方文档](https://www.sigmajs.org/docs/)、[Sigma 与 Graphology](https://www.sigmajs.org/)、[Graphology shortest path](https://graphology.github.io/standard-library/shortest-path.html)、[Graphology ForceAtlas2 worker](https://graphology.github.io/standard-library/layout-forceatlas2.html)、[Cytoscape.js API/性能与算法](https://js.cytoscape.org/)、[Cytoscape WebGL preview](https://blog.js.cytoscape.org/2025/01/13/webgl-preview/)。核验日期：2026-07-11。
