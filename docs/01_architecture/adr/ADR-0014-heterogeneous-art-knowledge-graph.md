# ADR-0014｜采用异构艺术知识图谱、证据分层与静态分片运行时

- Status：Accepted for MUSEUM-10A design
- Date：2026-07-24
- Decision owners：project owner + relationship research writer + KG/runtime writer
- Requires：`release:art-final-corpus-2.5.0`

## Context

当前关系模型以艺术家为主要节点，公开60条边全部为C级策展比较，只表达共同题材、材料或技法。它无法自然建模作品、展览、学院、团体、机构、地点、赞助人、评论家、文献或艺术运动，也无法回答大多数历史关系和AB路径问题。

当前AB路径在艺术家关系图上执行有界BFS/Yen，主要按hop count排序，`composite_weight=false`。在未来更丰富的图谱中，单纯最少hop会偏好“巴黎”“油画”“现代艺术”等泛化高连接节点，产生看似短、实际解释力低的路径。

GitHub Pages是静态部署环境，项目要求无外部运行时图数据、无查询历史持久化、无用户定位，并保持offline-like静态可审计性。

## Decision

### 1. 采用异构有向多重知识图谱

节点至少包括：

- Artist
- Artwork
- Person
- Event
- MovementOrGroup
- Institution
- Place
- Material
- Technique
- Subject
- Document
- 必要时的TimeSpan

边必须typed、direction-aware、time-aware、provenanced。禁止以无语义`related_to`替代正式关系类型。

### 2. 采用A/B/C三层关系

- **A｜直接历史关系**：师承、合作、通信、家庭、赞助、共同创立、明确影响等；
- **B｜事件／机构／地点／文献语境**：保留中间实体，不压缩为私人关系；
- **C｜策展比较**：共同题材、材料、技法、形式和观察问题。

三层在schema、索引、路径资格、UI、图例和文案中分离。C层不得默认出现在历史关系视图或路径中。

### 3. 每条边绑定Claim → Evidence → Source

公开边必须包含：

- stable ID；
- endpoint IDs和types；
- direction；
- layer和relation type；
- valid time和precision；
- context IDs；
- claim/evidence/source IDs；
- source locator；
- confidence/review；
- child/research explanation；
- `what_it_means`与`what_it_does_not_mean`；
- conflict、withdrawal和replacement；
- path eligibility。

算法候选可以存入内部研究包，但未经正式证据闭合不得成为公开边。

### 4. 采用静态、不可变、分片发布

内部formal KG package至少包含：

- entity shards；
- relation shards；
- claims/evidence/sources；
- adjacency by entity/type/layer；
- path eligibility index；
- lineage indexes；
- temporal index；
- place index；
- unified search index；
- child explanations；
- withdrawal/replacement；
- deterministic manifest和hashes。

Public 3.0.0是immutable static overlay。运行时根据当前实体加载小型entity/adjacency shards，不下载全图，不依赖远程图数据库或第三方知识图谱API。

### 5. 采用加权、多样化AB路径

路径在已发布typed edges上运行有界k-shortest loopless算法。成本至少考虑：

- relation layer；
- evidence confidence；
- high-degree hub penalty；
- generic entity penalty；
- relation repetition；
- entity-type transition；
- temporal coherence；
- direction；
- uncertainty/conflict；
- stable ID tie-breaker。

默认返回3条、最多5条结构不同的路径。后续路径需满足节点／边重叠上限，避免只更换一个高连接枢纽。

### 6. 采用局部渐进探索，不提供全局500节点图

- 默认0节点；
- 搜索后局部展开；
- click-to-recenter；
- expand/collapse/pin/history；
- 桌面默认10–15节点，主动展开最多60；
- 移动端最多30；
- 完整数据由search、list、table和path访问；
- 节点大小不表示艺术价值；
- 距离不默认表示历史强度；
- 标签使用可访问DOM。

### 7. 采用儿童／研究双层表达

事实和边只有一套；儿童模式提供自然解释，研究模式提供类型、时间、来源、冲突和路径成本。不得生成两套互相矛盾的数据。

### 8. 部署前设置用户人工体验门禁

LOCAL-01只生成候选包、原型、截图和录屏，deployment=0。自动测试通过后仍需用户明确批准，LOCAL-02才可创建和部署3.0.0。

## Consequences

### Positive

- 能表达真实艺术史关系和中间语境；
- AB路径更有解释力；
- 当前C级比较可被保留但不再冒充全部关系；
- 静态Pages仍可离线式审计；
- 逐实体分片适应500/5,000规模；
- 关系、路径、谱系和时空联动共享统一本体；
- 用户可在部署前判断产品是否真正好用。

### Costs

- schema、研究和前端复杂度显著增加；
- 需要新增事件、机构、人物和文献研究；
- 路径算法需代表性语料调参；
- 需要更多candidate evidence和人工产品审阅；
- 部分艺术家会诚实保持历史关系稀疏。

## Rejected alternatives

### A. 继续使用艺术家单一节点图

拒绝。无法表达事件、机构、作品和文献中介，关系覆盖会长期稀疏。

### B. 绘制全体500艺术家的力导向图

拒绝。视觉拥挤、误导距离语义、移动端和无障碍不可用，也无法解释边。

### C. 用AI或相似度自动补边

拒绝。可以作为内部候选发现，但不能代替历史证据或直接公开。

### D. 把A/B/C边混合为一种“相关”

拒绝。会让共同材料与师承在视觉上等价，重复当前根本问题。

### E. 使用远程图数据库作为运行时真源

拒绝。破坏静态release、可重现、隐私、离线和Pages部署边界。

### F. 仅以hop count排序AB路径

拒绝。高连接泛化节点会主导结果，路径短但没有解释价值。

## Risks and mitigations

- **关系研究量过大**：按500人缺口和代表性问题分批，先高价值直接关系和事件中介。
- **图谱变得稠密**：局部加载、硬节点上限、分组和文字等价。
- **路径权重人为偏置**：固定代表性测试集、成本分解、稳定tie-breaker、对抗审查。
- **时间地点误推断**：只使用明确source interval/place；unknown保持unknown。
- **儿童语言简化过度**：与同一claim/evidence绑定，研究层可追溯。
- **候选通过自动测试但体验仍差**：用户人工候选验收为硬门禁。

## Validation

MUSEUM-10A必须证明：

- 所有公开边typed/provenanced；
- A/B/C数据和视觉分离；
- 支持多实体搜索和recenter；
- AB路径含hub/genericity/time penalties；
- 路径解释和证据可展开；
- 谱系与时空模式使用同一正式边；
- 无全局大图；
- text/table/keyboard等价；
- static shard和deterministic release；
- analytics/query history/geolocation/external runtime graph requests均为0；
- LOCAL-01 deployment=0；
- 用户批准后才允许LOCAL-02发布。