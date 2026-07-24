---
product_id: museum-art-relationship-knowledge-graph
planned_phase: MUSEUM-10A
planned_release_id: release:art-relationship-knowledge-graph-3.0.0
status: approved_product_spec_after_final_corpus
requires_input_release: release:art-final-corpus-2.5.0
requires_user_candidate_review: true
current_relationship_model_replaced: false
---

# 艺术关系知识图谱3.0产品规范

## 1. 产品问题

当前关系功能以艺术家为唯一主要节点，正式边只有60条C级策展比较，类型仅为共同题材、共同材料、共同技法。它能够支持“把两件作品放在一起观察”，但不能充分回答：

- 两位艺术家是否真正认识或合作？
- 他们是否参加过同一展览？
- 一位艺术家通过哪个学院、教师、团体或出版物与另一位相连？
- 一件作品如何通过委托、收藏、展览和机构流转？
- 两个看似不相关实体之间有哪些不同且可信的路径？
- 关系发生在何时、何地？
- 哪些只是策展比较，而不是历史联系？

3.0.0的目标不是画一个更大的网络，而是建立**搜索驱动、异构实体、证据可解释、路径可比较、时间空间可联动**的艺术知识探索系统。

## 2. 核心产品承诺

1. 用户可搜索任一受支持实体，而不只艺术家。
2. 每次只展开当前问题相关的局部邻域。
3. 点击节点可重新居中，并保留探索历史。
4. 历史事实、事件语境、策展比较在数据和视觉上完全分开。
5. AB路径返回多条可解释路径，不只最短hop。
6. 每条边和每一步路径都有“意味着什么／不意味着什么／证据是什么”。
7. 没有证据时诚实显示空状态。
8. 儿童模式与研究模式共享同一事实层。
9. 500位艺术家和5,000件作品可被发现，但不一次绘制全部节点。
10. 部署前必须经过用户对候选截图和典型场景的人工体验验收。

## 3. 用户与任务

### 3.1 儿童与家庭访客

- 这位艺术家和谁一起学习、工作或展览？
- 他们真的见过面吗？
- 这两个人为什么会连在一起？
- 他们共同使用了什么材料或技法？
- 从A到B的每一步发生了什么？

### 3.2 教师与学生

- 构建某个运动、学院或展览的关系网络；
- 对比直接历史关系和策展比较；
- 追踪技法、机构或展览语境；
- 使用时间和地点检查关系是否可能成立；
- 导出或打印一条有来源的路径。

### 3.3 研究型访客

- 查看关系方向、时间有效期和来源；
- 查看冲突、缺口和撤回；
- 过滤边类型与证据等级；
- 检查路径为何被排序或排除；
- 使用完整表格和机器可读来源记录。

## 4. 异构实体本体

### 4.1 必须支持的节点类型

| 类型 | 说明 | 示例任务 |
|---|---|---|
| Artist | 艺术家 | 查找师承、合作、团体、展览 |
| Artwork | 作品 | 查看创作、委托、收藏、展览、材料 |
| Person | 非艺术家人物 | 教师、赞助人、评论家、收藏家、出版人 |
| Event | 展览、沙龙、工作坊、历史事件 | 连接共同参与者和作品 |
| MovementOrGroup | 艺术运动、团体、工作室 | 查看成员、创立、分裂、关联事件 |
| Institution | 学院、博物馆、画廊、出版社、工作室 | 学习、任教、展览、收藏、出版 |
| Place | 城市、历史地点、区域 | 活动、居住、展览、机构所在地 |
| Material | 材料 | 作品与策展比较 |
| Technique | 技法 | 作品、学习和传播语境 |
| Subject | 题材或图像主题 | 策展比较，不表示历史接触 |
| Document | 书信、档案、评论、出版物、目录 | 支持关系和事件证据 |
| TimeSpan | 必要时的显式时间节点/区间 | 时间筛选和路径一致性 |

节点必须有stable ID、type、labels、aliases、source IDs、lifecycle、public status和withdrawal状态。

## 5. 关系本体与三级分层

### 5.1 A层｜直接历史关系

只有直接来源或高质量档案证据支持时才能发布。关系可有方向：

- `studied_under` / `taught`
- `collaborated_with`
- `corresponded_with`
- `family_of`
- `partner_of`
- `patron_of` / `commissioned_by`
- `founded` / `co_founded_with`
- `member_of`
- `employed_by` / `taught_at` / `studied_at`
- `explicitly_influenced`，仅在可靠来源明确表述影响时
- `owned_or_collected_work_of`，需避免把机构收藏误作私人关系

A层不得由共同材料、共同地点或算法相似推断。

### 5.2 B层｜事件与语境连接

通过有来源的中间实体建立，不冒充直接私人关系：

- `participated_in_event`
- `artwork_exhibited_at`
- `associated_with_movement`
- `associated_with_institution`
- `active_in_place`
- `resided_in`
- `published_in`
- `reviewed_by`
- `represented_by_gallery`
- `work_held_by_institution`
- `contemporaneous_in_place`，只有时间和地点区间明确时

展示时必须保留中间实体。例如“艺术家A→参加→展览X←参加←艺术家B”，不得压缩成“艺术家A认识艺术家B”。

### 5.3 C层｜策展比较

延续现有边并扩展为明确的观察层：

- `shared_subject`
- `shared_material`
- `shared_technique`
- `shared_format`
- `shared_visual_problem`
- `curatorial_contrast`

C层必须默认关闭于“历史关系”视图；只有用户选择“比较”模式才加入路径。它永远不表示相识、师承、传播、因果或价值排序。

## 6. 边数据合同

每条公开边至少包含：

- stable relation ID；
- source entity ID / target entity ID；
- relation type与layer A/B/C；
- directionality；
- valid time interval和precision；
- place/event/institution context IDs；
- Claim IDs；
- Evidence IDs；
- Source IDs和locator；
- evidence confidence；
- review状态和reviewer；
- `what_it_means`；
- `what_it_does_not_mean`；
- uncertainty/conflict；
- withdrawal/replacement；
- child explanation；
- research explanation；
- path eligibility；
- public visibility。

不允许只存一个模糊字符串“related_to”。

## 7. 五种产品模式

### 7.1 实体探索

- 初始为空，提供统一搜索、推荐问题和coverage-balanced starter；
- 搜索支持所有实体类型；
- 当前实体居中；
- 邻居按关系组、实体类型或时间分组；
- 点击节点重新居中；
- 支持expand、collapse、pin、unpin、back、forward、breadcrumb；
- 桌面默认10–15节点，主动展开硬上限60；
- 移动端硬上限30；
- 超出部分通过分组计数、分页列表和“继续展开”访问。

### 7.2 艺术家关系

默认只展示A层历史关系。用户可显式打开：

- B层事件/机构/地点连接；
- C层策展比较。

三层使用不同线型、标签、图例和解释，不能只靠颜色区分。

### 7.3 AB路径

输入任意两个受支持实体，输出：

- 最佳历史路径；
- 其他可信且结构不同的路径；
- 仅直接历史关系；
- 经由事件；
- 经由机构；
- 经由地点/时间；
- 策展比较路径（显式opt-in）。

每一步可展开证据；路径可保存为URL状态、打印或复制文本，但不得持久化用户查询历史。

### 7.4 谱系

支持有方向且可形成层级的投影：

- 师承谱系；
- 学院/工作室谱系；
- 运动/团体成员与分支；
- 技法教学与传播，只有可靠证据时；
- 展览系列或机构沿革。

不能把共同技法自动排成“影响谱系”。

### 7.5 时间—空间联动

选择节点、边或路径后：

- 同步显示时间区间；
- 标识时间是否重叠；
- 显示相关地点和历史名称；
- 跳转map/list/timeline；
- 区分活动地点、事件地点、机构所在地和作品收藏地；
- 不使用用户定位。

## 8. AB路径算法合同

### 8.1 基本方法

- 在显式、已发布typed edges上运行；
- 支持有向多重异构图；
- 先按模式过滤，再运行有界k-shortest loopless paths；
- 可使用Yen/Eppstein等确定性实现；
- 默认k=3，可请求最多5；
- 默认max hops=5，研究模式最多7；
- candidate expansion有硬上限；
- 无路径时返回诚实空状态和可调整的过滤建议。

### 8.2 路径成本

不得只按hop count。建议成本由以下部分组成：

- relation layer：A最低，B次之，C在比较模式外不可用；
- evidence confidence penalty；
- generic hub penalty，例如与degree的对数相关；
- generic entity penalty，例如“艺术”“绘画”“巴黎”这类过宽节点；
- relation repetition penalty；
- entity-type transition penalty；
- temporal incoherence penalty；
- unsupported direction penalty或直接拒绝；
- uncertainty/conflict penalty；
- stable ID tie-breaker。

示意：

`cost = relation_base + evidence_penalty + hub_penalty + genericity_penalty + temporal_penalty + repetition_penalty`

具体权重必须由代表性路径集验证，不能为了得到预期人物而手工特判。

### 8.3 路径多样性

后续路径不能只是第一条路径换一个高连接节点。使用边/节点Jaccard或共享中间实体上限，确保返回结构不同的解释：

- direct relationship path；
- event-mediated path；
- institution-mediated path；
- place/time path；
- comparison path。

### 8.4 不允许的推断

- 共同地点不自动证明见面；
- 同时存在不证明接触；
- 共同材料不证明影响；
- 收藏某作品不自动证明艺术家知道收藏者；
- 算法相似不创建公开边；
- 最短路径不等于真实传播链。

## 9. 双层解释

### 9.1 儿童模式

首先回答：

- “他们为什么连在一起？”
- “他们真的见过面吗？”
- “中间发生了什么？”
- “可以观察什么？”

语言自然、短句、避免schema/metadata/置信度术语。证据缺失时说“我们现在没有足够证据”。

### 9.2 研究模式

展示：

- relation type/layer/direction；
- time/place；
- Claim → Evidence → Source；
- source locator；
- confidence与review；
-冲突、限制、撤回；
- 路径成本分解；
- 为什么其他路径被排除。

两种模式只改变表述和信息密度，不改变事实。

## 10. 数据与发布架构

建议建立内部正式包：

- entity shards；
- relation shards；
- claims/evidence/sources；
- adjacency by entity/type/layer；
- path eligibility index；
- lineage indexes；
- temporal index；
- place index；
- search index；
- child explanations；
- withdrawal/replacement；
- build manifest和deterministic hashes。

Public release为静态Pages可消费的sharded overlay；运行时按当前实体加载邻接分片，不下载全图，不依赖远程数据库或第三方图谱API。

## 11. 交互与视觉要求

- 不出现500节点全局图；
- 标签必须是可访问DOM，不依赖canvas文字；
- 关系类型不只靠颜色；
- 节点大小不表示艺术价值；
- 图形距离不默认表示历史强度；
- 选中边时降低无关元素而非完全消失；
- 视图切换保留当前实体和过滤器；
- 可复制当前深链；
- reduced-motion、forced-colors、low-bandwidth、no-script有等价任务；
- 文字列表和表格覆盖完整数据。

## 12. 隐私与安全

- analytics=false；
- query history不持久化；
- geolocation=false；
- 外部图像或图数据运行时请求=0；
- URL状态不得包含个人数据；
- 搜索在客户端本地分片完成；
- 来源URL通过既有安全与权利门禁。

## 13. 性能目标

500/5,000正式语料下：

- 初始关系页不加载全量关系图；
- 首次邻域仅加载所需entity、adjacency和label shards；
- click-to-recenter interaction p95≤150ms；
- 已缓存邻域≤80ms目标；
- desktop FTI≤1.8s；
- controlled mobile FTI≤2.5s；
- CLS≤0.1；
- 当前视图节点硬上限；
- 路径查询在代表性语料p95≤250ms，最坏情况可取消；
- worker或分块计算不得阻塞主线程。

## 14. 候选与人工验收

`MUSEUM-10A-RELATION-KG-LOCAL-01`只生成候选，不部署。至少提供：

- 12组实体探索截图；
- 10组AB路径；
- 4组谱系；
- 4组时空联动；
- 直接历史、事件中介、机构中介、无路径、C级比较等场景；
- desktop/mobile/forced-colors/low-bandwidth；
- 交互录屏或连续截图；
- 代表性edge evidence drawers。

用户明确批准后，才允许`LOCAL-02`修订和部署3.0.0。自动测试通过不能替代该人工产品体验门禁。

## 15. 完成定义

3.0.0必须达到：

- 500 artist entrypoints；
- 5,000 artwork nodes；
- 多实体统一搜索；
- typed/provenanced公开关系100%；
- direct/context/curatorial分离；
- click-to-recenter与progressive expand；
- 多条AB路径和过滤；
- generic hub penalty；
- 时间和空间语境；
- child/research双层；
- text/table equivalence；
- overlap=0；
- privacy门禁；
- 用户候选验收通过。

直接历史关系数量不设造数指标。