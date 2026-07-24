---
document_id: museum-relationship-kg-acceptance-matrix
status: approved
final_corpus_release: release:art-final-corpus-2.5.0
candidate_phase: MUSEUM-10A-RELATION-KG-LOCAL-01
final_phase: MUSEUM-10A-RELATION-KG-LOCAL-02
candidate_user_review_required: true
---

# 艺术关系知识图谱分阶段验收矩阵

## 1. 使用方法

本矩阵用于防止再次出现“数据和自动测试通过，但关系图谱实际不好用”的情况。

验收分为五个阶段：

- A：500/5,000最终语料；
- B：500人关系缺口与来源审计；
- C：不部署的知识图谱候选；
- D：用户人工产品体验验收；
- E：修订后的3.0.0正式发布。

任何阶段不得用后续阶段的计划代替本阶段证据。特别是：C阶段自动测试通过不等于D阶段用户通过。

## 2. 阶段总门禁

| 项目 | A Final Corpus | B Web Audit | C Candidate | D User Review | E 3.0 Release |
|---|---|---|---|---|---|
| 500 artists / 5,000 artworks | 必须 | 输入核验 | 输入hash绑定 | 抽样可访问 | 线上不变 |
| Batch 01–10 published | 必须 | 核验 | 不改写 | 不适用 | 不改写 |
| Legacy supplement 121 | 必须 | 核验 | 可作为作品节点 | 抽样 | 线上闭合 |
| 异构实体ontology | 不实现 | 审计设计 | 必须实现 | 可理解 | 正式发布 |
| A/B/C关系分层 | 不新增半成品 | 研究队列 | 必须 | 用户能区分 | 正式发布 |
| 多实体统一搜索 | 不要求KG版 | 测试样本 | 必须 | 用户验证 | 正式上线 |
| Entity explorer | 现有无回归 | 任务设计 | 候选完成 | 人工体验 | 正式上线 |
| AB路径3.0 | 现有无回归 | 路径样本 | 候选完成 | 人工体验 | 正式上线 |
| 谱系模式 | 不实现 | 数据需求 | 候选完成 | 人工体验 | 正式上线 |
| 时空联动 | 现有map无回归 | 数据需求 | 候选完成 | 人工体验 | 正式上线 |
| 用户候选批准 | 不适用 | 不适用 | 尚未批准 | 必须明确 | 绑定批准记录 |
| Pages deployment | 2.5.0一次 | 0 | 0 | 0 | 3.0.0一次 |

## 3. A阶段｜500/5,000最终语料

### A1｜数量与身份

- artist_count=500；
- artwork_count=5,000；
- Gallery=125；
- Collection=375；
- living=0；
- unknown death=0；
- non-person=0；
- duplicate artist=0；
- duplicate artwork=0；
- attribution conflict=0。

### A2｜内容与来源

- 500/500儿童友好双语介绍；
- 5,000/5,000作品详情页；
- Claim → Evidence → Source闭合；
- source drift按stable ID处理；
- 121 supplement不改写legacy身份事实；
- banned governance jargon=0；
- duplicate intros=0。

### A3｜媒体、检索与体验

- 每件作品有终态媒体决定；
- public originals=0；
- no AI artwork modification；
- artist index覆盖500；
- search覆盖5,000；
- first query分片加载；
- compare/print/source/rights/no-image等价；
- current relation explorer、paths、map/timeline无回归；
- 不提前部署3.0关系原型。

### A4｜发布

- 2.0–2.4 intermediate releases deployment=0；
- 2.5.0 accepted final-full=1；
- runtime deployment=1；
- online byte/function closure；
- historical rebuild=0。

## 4. B阶段｜500人关系缺口与来源审计

### B1｜覆盖审计

对500位艺术家逐一记录：

- 直接历史关系数量和类型；
- 事件/机构/地点/文献中介候选；
- 策展比较覆盖；
- 当前source coverage；
- 是否为关系孤立实体；
- 缺失的官方/基金会/档案来源；
- research priority；
- 不应推断的敏感或不确定关系。

### B2｜研究队列

建立：

- high-value direct relationship queue；
- event/institution queue；
- lineage queue；
- document/archive queue；
- place/time correction queue；
- conflict/withdrawal queue；
- no-evidence honest-empty queue。

不得以每位艺术家最低关系数作为目标。

### B3｜代表性验收问题

至少准备30–50个问题，覆盖：

- 直接师承；
- 合作／通信；
- 家庭／赞助；
- 同一展览；
- 学院／机构；
- 艺术运动；
- 作品／收藏事件；
- 地点和时间；
- 策展比较；
- 无足够证据；
- 跨文化、跨时期实体；
- 关系稀疏艺术家。

所有“预期答案”必须来自实际研究，不得为测试预造边。

## 5. C阶段｜不部署的KG候选

### C1｜数据包

- 支持全部规定实体类型；
- stable typed IDs；
- typed/provenanced公开候选边=100%；
- A/B/C分层=100%；
- direction/time/place/context建模；
- claims/evidence/sources；
- withdrawal/replacement；
- deterministic package；
- static shards；
- candidate leakage到正式线上=0。

### C2｜实体探索

- 初始图节点=0；
- 支持任一实体类型搜索；
- 点击节点recenter；
- expand/collapse；
- pin/unpin；
- back/forward/history；
- 分组邻居；
- 桌面默认10–15节点；
- 桌面expanded≤60；
- mobile≤30；
- label overlap=0；
- node overlap=0；
- 完整列表／表格等价。

### C3｜关系层切换

- 默认历史关系只显示A层；
- B层需显式打开；
- C层需显式进入比较模式；
- 线型／标签／图例不只靠颜色；
- 选中边显示meaning、does-not-mean和证据；
- 关系方向清晰；
- 没有关系时诚实空状态。

### C4｜AB路径

- 支持任意两个受支持实体；
- 默认3条、最多5条；
- loopless；
- relation filters；
- direct/event/institution/place/comparison modes；
- generic hub penalty；
- generic entity penalty；
- evidence penalty；
- temporal coherence；
- directionality；
- path diversity；
- 成本分解可审计；
- no-path状态；
- 取消长查询；
- URL可复现但查询历史不持久化。

### C5｜谱系与时空

- 师承谱系只使用正式方向边；
- 学院／工作室／运动投影保留中间实体；
- 共同技法不得自动形成谱系；
- 时间区间和重叠可见；
- 地点类型区分活动、事件、机构、收藏；
- map/list/timeline互跳；
- 不使用用户定位。

### C6｜双层解释

- child explanation自然可理解；
- research layer完整；
- 两层事实一致；
- 主儿童层无schema/metadata术语；
- 每条边可追到来源；
- 无证据时明确说明。

### C7｜候选证据

至少交付：

- 12组实体探索截图；
- 10组AB路径；
- 4组谱系；
- 4组时空联动；
- desktop/mobile；
- forced-colors；
- low-bandwidth；
- 无路径；
- withdrawn relation；
- high-degree hub被惩罚；
- temporal contradiction；
- C级比较opt-in；
- 交互录屏或连续截图；
- 证据抽屉。

Deployment必须为0。

## 6. D阶段｜用户人工产品体验验收

用户至少检查：

1. 是否像“探索知识关系”，而不是看一团线；
2. 是否能迅速找到一个艺术家、作品或事件；
3. 点击节点后是否自然地继续探索；
4. 是否清楚区分认识／合作、事件中介和策展比较；
5. AB路径是否解释每一步，而不是只给一条线；
6. 是否出现“巴黎→油画→现代艺术”一类无意义捷径；
7. 儿童能否理解“为什么连接”；
8. 研究者能否看到来源、时间和限制；
9. 移动端是否可操作；
10. 是否仍有标签重叠、视觉中心误导或信息密度失控；
11. 无关系实体是否诚实且仍可通过作品／机构／地点探索；
12. 哪些视觉、布局、交互和文案需要修改。

批准必须有明确记录，例如：

- `approved_for_3_0_release`
- 或带具体修改项的`revision_required`

没有明确批准不得进入E阶段部署。

## 7. E阶段｜3.0.0正式发布

### E1｜数据与功能

- 使用用户批准后的candidate revision；
- 500 artist entrypoints；
- 5,000 artwork nodes；
- unified entity search；
- typed/provenanced relations=100%；
- A/B/C分离；
- entity explorer；
- AB paths；
- lineage；
- time-space；
- child/research modes；
- text/table equivalence；
- withdrawal/rollback。

### E2｜性能、无障碍与隐私

- desktop FTI≤1.8s；
- mobile FTI≤2.5s；
- recenter interaction p95≤150ms；
- representative path query p95≤250ms；
- CLS≤0.1；
- 44px targets；
- 200% reflow；
- keyboard/focus/live regions；
- forced-colors/reduced-motion/low-bandwidth/no-script；
- serious/critical a11y=0；
- external runtime graph/image requests=0；
- analytics=false；
- query history persisted=false；
- geolocation=false。

### E3｜发布

- immutable3.0.0 release；
- historical release hash-only；
- local full=0；
- accepted GitHub final-full=1；
- deployment=1；
- online byte closure；
- online representative scenario smoke；
- closeout deployment=0；
- main/origin/remote一致；
- worktree clean。

## 8. 对抗测试场景

必须覆盖：

- A=A同实体；
- 直接A层关系；
- B层展览中介；
- B层机构中介；
- B层地点／时间中介；
- C层比较仅opt-in；
- 无路径；
- 方向不允许反转；
- 时间冲突；
- 泛化高degree hub；
- relation repetition；
- withdrawn edge；
- conflicting evidence；
- isolated artist；
- mobile expansion limit；
- no-script text path；
- forced-colors关系类型；
- URL deep link restore；
- browser back/forward；
- long query cancel。

## 9. 不设的指标

以下指标不得成为造数目标：

- 每位艺术家最低关系数；
- 全图总边数；
- 平均degree；
- AB路径必须存在；
- 每位艺术家必须进入谱系；
- 每个关系类型最低数量。

唯一硬要求是：公开边全部有真实类型、证据、来源和清晰边界。