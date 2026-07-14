# ADR-0002：关系图引擎与路径计算

- Status: accepted; MUSEUM-04 implementation profile recorded
- Date: 2026-07-14

## Context

美术馆预计从 12 位试点扩展到更大图谱，需要 WebGL 渲染、可解释过滤、局部展开和 AB 路径。无障碍不能依赖 canvas 图本身。

## Decision

首选 **Graphology** 作为内存图与算法/数据结构，**Sigma.js** 作为艺术星海的 WebGL 渲染层。Graphology 负责邻域、最短路径、连通性、过滤视图和序列化；Sigma 只负责渲染与交互。所有可见关系同步提供 DOM 列表/详情。

MUSEUM-04 精确锁定 `graphology@0.26.0` 与 `sigma@3.0.3`；两者均为核验时的稳定版本，依赖许可与来源写入 third-party notices。Sigma v4 仍为 alpha，不进入生产依赖。依赖从本地构建产物加载，不使用 CDN 或 remote worker。

Graphology 只负责数据与邻域，Sigma 只负责 WebGL 图形交互。所有正式可见状态由同一 reducer 驱动，并在 DOM 艺术家列表与关系表中提供等价操作、解释、来源和权利入口；canvas 不是唯一的信息或操作通道。MUSEUM-04 的 36 条公开边全部是 C 级策展比较，由本地 Sigma custom edge program 绘制点线；不实现 AB 路径、历史因果边或算法相似度。

布局在构建期以固定 seed、版本和 hash 预计算；坐标不是 Claim，也不暗示艺术家重要性。运行时禁止随机布局与持续力导向模拟。`#/art/constellation` 路由懒加载 renderer、Graphology、Sigma 与 feature styles；这些资源不得进入门户首屏，低带宽模式不得预取或初始化 Sigma。

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

本阶段以可复现的受控 lab proxy 作为硬门禁，不把它描述为真实用户 p75。主要移动代理为 `390×844`、4× CPU slowdown、Fast 4G；低资源回退为 `360×800`、6× CPU slowdown、受限网络；桌面为 `1366×768` 与 `1440×900`。页面设计目标为 LCP ≤2.5 s、INP/脚本交互代理 ≤200 ms、CLS ≤0.1，且不加入 analytics、Cookie 或账户。

当前 `12 V / 36 E` 图的目标：移动 first interactive ≤2.5 s、桌面 ≤1.5 s、节点选择 p95 ≤100 ms、筛选或关系详情 p95 ≤200 ms、键盘焦点 p95 ≤100 ms、移动 FPS p95 ≥30、桌面 FPS p95 ≥45、移动 JS heap ≤150 MB，且无持续物理布局。门户初始 JS+CSS 相对 MUSEUM-03B 基线增长 ≤15%；星海路由新增 JS+CSS+初始数据 gzip ≤450 KB；graph summary gzip ≤100 KB。Evidence、Source、作品详情按需加载，不得为性能删除证据、权利、等级或争议字段。

合成基准固定三档：`1k V / 5k E`、`10k V / 60k E`、`50k V / 300k E`，含中英 labels 与代表性的完整治理字段。移动可见子图上限 `150 V / 600 E`，桌面 `300 V / 1,200 E`。1k 移动 lab first interactive ≤5 s；10k 不作全图首屏；50k 移动全量渲染请求必须安全拒绝或切换到分区/列表，禁止一次显示 300k 条边。若约 4 GB Android 实机不可用，结果必须记录为 `not_available`，不得把模拟节流称为实机验收。

## Revisit when

真实 release 超过移动端内存/帧率预算；需要复杂图编辑/复合节点；路径计算超过交互预算；或无障碍替代与 Sigma 状态同步成本不可接受。届时用同一基准数据比较 Cytoscape、预计算和后端查询。

## Current official basis

[Sigma 官方文档](https://www.sigmajs.org/docs/)、[Sigma 与 Graphology](https://www.sigmajs.org/)、[Graphology shortest path](https://graphology.github.io/standard-library/shortest-path.html)、[Graphology ForceAtlas2 worker](https://graphology.github.io/standard-library/layout-forceatlas2.html)、[Cytoscape.js API/性能与算法](https://js.cytoscape.org/)、[Cytoscape WebGL preview](https://blog.js.cytoscape.org/2025/01/13/webgl-preview/)。核验日期：2026-07-11。
