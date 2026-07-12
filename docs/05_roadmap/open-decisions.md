# 未决事项

这些事项没有被静默决定。当前共 **10** 项未决。

| ID | 决定 | 最晚时间 | 默认安全状态 | 决策者 |
|---|---|---|---|---|
| OD-001 | 代码许可证：MIT、Apache-2.0、GPL 或保留权利 | MUSEUM-01 公开代码前 | 不新增 LICENSE，不宣称开放许可 | 用户 |
| OD-002 | 项目原创文字许可及第三方范围声明 | 首个展签公开前 | 保留权利、逐项第三方许可 | 用户 |
| OD-004 | 首批 12 位艺术家组合 | MUSEUM-03B 前 | MUSEUM-03A 已生成私有 decision package；不把 Recommended 当批准名单、不采集正式批次 | 用户 + curator |
| OD-005 | MVP 目标设备与量化性能预算 | MUSEUM-01/M04 | 先建立基准，不作性能保证 | product + engineering |
| OD-006 | 底图/tile 提供者与许可/归属方案 | MUSEUM-07 | 不安装地图、不配置 token | user + rights |
| OD-007 | 高分图像以来源 IIIF、自托管衍生物或混合方案的比例 | MUSEUM-03B/05 | MUSEUM-03A 已比较 metadata-first / external / self-hosted-open / mixed；仍逐资产决定，不复制未知字节 | rights + engineering |
| OD-008 | 中文搜索分词、索引库与可接受包体 | MUSEUM-01/08 | aliases 精确搜索；不加依赖 | product + engineering |
| OD-009 | 分析/收藏历史是否收集及隐私模式 | 对应功能设计前 | 不收集、不建账户 | 用户 |
| OD-010 | 权利投诉联系、SLA、授权证明保管与删除流程 | 首次公开第三方资产前 | 不公开高风险资产 | user + rights |
| OD-011 | 武器博物馆正式内容的年代范围、现代武器边界、年龄适宜性和敏感内容分级 | MUSEUM-ARMS-00 | 仅显示不可点击门户入口；不采集器物、不下载媒体、不展示现代操作资料或图像化伤害，不改变美术馆计划 | user + curator + safety + rights |

每项关闭时更新 decision log，记录选择、理由、影响、日期和重评触发。`open_decisions_count` 以本表未关闭项计算。

MUSEUM-03A 只生成用户 decision package；`OD-004` 与 `OD-007` 均保持 open，没有关闭日期。当前未决数量仍为 **10**。

## 已关闭事项

| ID | 关闭日期 | 决定 | 影响 |
|---|---|---|---|
| OD-003 | 2026-07-11 | `repository=public`、`pages=public` | MUSEUM-01 获准正式启用 GitHub Pages；OD-001、OD-002 仍保持未决和保留权利状态 |
