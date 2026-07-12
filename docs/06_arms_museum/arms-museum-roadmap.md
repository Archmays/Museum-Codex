# 武器博物馆路线图

## 路线原则

武器馆路线与美术馆路线分开，任何阶段都要求前一阶段完成且由用户明确授权。`MUSEUM-02A` 完成不自动授权 `MUSEUM-ARMS-00`，也不改变 `MUSEUM-03` 的目标、首批 12 位艺术家范围或美术馆数据契约。

| 阶段 | 目标 | 允许输出 | 禁止事项 | 完成门槛 |
|---|---|---|---|---|
| `MUSEUM-02A` | 登记第七分馆、公共安全边界与门户契约 | 章程、政策、模型/研究/互动 outline、路线、common enum、fail-closed dispatch、不可点击卡片 | arms 数据、adapter、live probe、媒体、正式路由、M03 工作 | 治理/前端/Pages/A–E 审查通过，七馆门户稳定 |
| `MUSEUM-ARMS-00` | 来源、分类、权利、安全与敏感内容专项研究 | 来源矩阵、条款核验、术语与分类、OD-011 决策输入、concrete schema/fixture/adapter 设计 | live adapter、正式器物、媒体下载、公开路由与原型 | 学科/安全/权利评审，年代与现代边界、schema/fixtures、静态发布方案闭合 |
| `MUSEUM-ARMS-01` | 小范围历史器物知识图谱与非操作性展陈原型 | 经审核的小样本、Claim–Evidence–Source、静态非操作性体验和文字替代 | 现代操作资料、采购/优化、伤害模拟、未审媒体、规模扩张 | 数据、权利、安全、年龄、无障碍、性能、撤回与发布门禁通过 |
| 后续待定 | 不预设 | 由新阶段提示定义 | 不从本路线自行推导 | 用户另行授权 |

## `MUSEUM-02A` 退出条件

- `arms` 成为合法 branch ID，中文/英文名称固定；
- 六份规划文件与 OD-011、总体架构、风险和路线完成；
- common entity enum 接受 `arms`，但 actual arms data 的 concrete dispatch 明确 fail-closed；
- 门户有七张卡片，武器馆可见但不可点击，只有美术馆可进入；
- 无第三方媒体、正式 arms 数据、adapter、live probe 或 route；
- 全部治理、pipeline、前端、build、安全、Pages 与线上回归通过。

## `MUSEUM-ARMS-00` 入场输入

只有用户另行授权，并能提供学科、安全、年龄适宜性和权利审核资源时才可开始。开始前应重新核验：

1. `MUSEUM-02A` 阶段报告与 fail-closed contract；
2. `OD-011` 的待决范围和决策者；
3. 来源身份、metadata/media 条款和敏感/现代内容边界；
4. 跨文化分类、年代精度、maker attribution 与 provenance 规则；
5. concrete schema、fixtures、ID 前缀、审核角色和静态发布边界。

本阶段仍不得把研究来源或 recorded fixture 当作正式馆藏，不得下载第三方媒体或开放公众 route。

## `MUSEUM-ARMS-01` 入场输入

必须先有 `MUSEUM-ARMS-00 completed/pass`、用户确认的小样本与公开边界、逐对象权利审核能力、敏感内容分级、儿童/家庭路径和可撤回的静态 release 方案。任何操作化、采购化、伤害优化或权利不明材料都会阻断原型。

## 与当前主路线的关系

美术馆 `MUSEUM-03` 仍按既定 selection framework、约 48 件作品与 50–80 条关系的目标执行，只有用户另行授权才可开始。武器馆阶段不与美术馆阶段混并，也不因门户已有筹备卡片而获得优先级或自动准入。
