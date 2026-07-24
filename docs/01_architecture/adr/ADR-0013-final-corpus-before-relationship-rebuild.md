# ADR-0013｜先完成500/5,000最终语料，再重构关系知识图谱

- Status：Accepted
- Date：2026-07-24
- Decision owners：project owner + corpus/release writer + relationship KG product owner
- Scope：美术馆500位艺术家／5,000件作品总体与后续MUSEUM-10A

## Context

当前公开release为`release:art-expansion-batch-05-1.9.0`，包含258位艺术家和2,471件作品。现有关系体验已经从无意义的全体圆环改为focused relation lanes，但正式关系仍只有60条，且全部是C级策展比较。

项目仍有Batch 06–10共242位艺术家、2,408件作品，以及121件legacy supplement尚未发布。最终关系知识图谱需要基于完整500位艺术家、5,000件作品进行关系缺口、机构、事件、地点、运动、作品和文献研究。如果现在基于258人重构，实体总体、作品分布、source coverage、路径稀疏度和性能基线都会继续变化。

用户明确要求：先让500位艺术家及全部作品上线，再认真重构关系图谱；并对当前实现程度不满意，要求参考AllHistory的关系图谱思路。

## Decision

采用严格的前后里程碑顺序。

### Milestone A｜Final Corpus

先执行`MUSEUM-09G-K-FINAL-CORPUS`：

- Batch 06–10；
- 121件legacy supplement；
- 500 artists / 5,000 artworks；
- Gallery125 / Collection375；
- final release `release:art-final-corpus-2.5.0`；
- 一次final-full和一次Pages部署；
- 现有关系、paths、map和search只做无回归，不实施3.0.0重构。

### Milestone B｜Relationship KG

2.5.0在线闭合后，依次执行：

1. `MUSEUM-10A-RELATION-KG-WEB-01`：500人关系缺口、来源和验收问题审计；
2. `MUSEUM-10A-RELATION-KG-LOCAL-01`：异构KG数据包和交互候选，不部署；
3. 用户人工体验审阅；
4. `MUSEUM-10A-RELATION-KG-LOCAL-02`：根据反馈修订并发布3.0.0。

## Why

### 1. 稳定实体总体

关系、路径、谱系和时间空间索引应建立在完整稳定ID集合上。先完成总体可以避免持续迁移节点、slug、adjacency和path index。

### 2. 使用完整作品语料

作品是艺术关系图谱的重要中间实体。5,000件作品全部就绪后，才能可靠研究展览、收藏、材料、技法、题材、机构和作品流转。

### 3. 正确测量关系缺口

258人时看到的稀疏度不代表500人最终结构。关系研究队列必须基于最终每位艺术家的实际source coverage和孤立程度生成。

### 4. 分离“数据规模完成”与“产品重构”

同时扩大到500人并重写关系前端，会让失败难以判断来自内容、schema、路径算法、UI或性能。分阶段可以保持可回滚、可审查和单一done condition。

### 5. 人工产品体验门禁

自动测试可以证明无重叠、性能和可访问性，但不能证明图谱真正帮助用户理解关系。3.0.0候选必须由用户实际审阅，不能再次以自动`pass`替代产品判断。

## Consequences

### Positive

- 关系3.0基于完整语料；
- KG ontology和path算法只需面向稳定总体；
- 性能测试真实覆盖500/5,000；
- 用户可单独审阅关系产品；
- final corpus和KG均有独立rollback点；
- 不会为赶关系UI而降低语料治理门槛。

### Costs

- 关系重构不会在下一次本地任务中立即上线；
- 总体时间更长；
- 需要一次500/5,000发布和后续候选／正式两阶段；
- 在2.5.0之前，用户仍使用现有focused explorer。

## Rejected alternatives

### A. 现在以258位艺术家重构

拒绝。输入总体仍变化，关系覆盖和路径结构会失真，后续需要大规模迁移。

### B. 把500扩展和KG重构放在同一巨型提交

拒绝。风险不可定位，用户在部署前难以单独审查关系体验，也会让一次final-full同时承担两个不同产品目标。

### C. 先部署关系原型再收集意见

拒绝。用户已经明确不满意，正式线上不应再次成为试验场。候选必须不部署并提供截图／录屏／场景。

### D. 等所有关系事实都研究完再发布500语料

拒绝。500/5,000本身具有独立价值；关系研究可以在最终语料上线后持续进行，且不能为图谱密度阻塞基础语料。

## Validation

ADR落实必须证明：

- 2.5.0先于3.0.0；
- final corpus阶段不写入半成品KG runtime；
- 500/5,000在线闭合；
- MUSEUM-10A Web审计使用实际2.5.0；
- LOCAL-01 candidate deployment=0；
- 用户人工批准有可审计记录；
- 只有LOCAL-02可部署3.0.0；
- arms museum和OD-011不被顺带处理。