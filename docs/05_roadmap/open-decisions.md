# 未决事项

这些事项没有被静默决定。当前共 **4** 项未决。

| ID | 决定 | 最晚时间 | 默认安全状态 | 决策者 |
|---|---|---|---|---|
| OD-006 | 底图/tile 提供者与许可/归属方案 | MUSEUM-07 | 不安装地图、不配置 token | user + rights |
| OD-008 | 中文搜索分词、索引库与可接受包体 | MUSEUM-01/08 | aliases 精确搜索；不加依赖 | product + engineering |
| OD-009 | 分析/收藏历史是否收集及隐私模式 | 对应功能设计前 | 不收集、不建账户 | 用户 |
| OD-011 | 武器博物馆正式内容的年代范围、现代武器边界、年龄适宜性和敏感内容分级 | MUSEUM-ARMS-00 | 仅显示不可点击门户入口；不采集器物、不下载媒体、不展示现代操作资料或图像化伤害，不改变美术馆计划 | user + curator + safety + rights |

每项关闭时更新 decision log，记录选择、理由、影响、日期和重评触发。`open_decisions_count` 以本表未关闭项计算。

`OD-001`、`OD-002`、`OD-005` 与 `OD-010` 已由用户 Mays 在 MUSEUM-04 入口关闭。当前未决数量为 **4**：OD-006、OD-008、OD-009、OD-011。

## 已关闭事项

| ID | 关闭日期 | 决定 | 影响 |
|---|---|---|---|
| OD-003 | 2026-07-11 | `repository=public`、`pages=public` | MUSEUM-01 获准正式启用 GitHub Pages；OD-001、OD-002 仍保持未决和保留权利状态 |
| OD-004 | 2026-07-13 | 批准 MUSEUM-03A Recommended Slate 的 12 位艺术家；决策人 Mays；输入 bundle `sha256:ba7640dbfe554c938fc9bf65ac5fa1eb42514ced015e0b4e56598870428072c7` | 允许进入 MUSEUM-03B 正式批次；不得自动替换，任一硬门槛失败时阻断并回报 |
| OD-007 | 2026-07-13 | 采用 Option D `Mixed`，默认执行顺序为 `metadata-first` | 逐对象权利闭合后才可成为 external IIIF 或未来 self-hosted 候选；MUSEUM-03B 不下载媒体，数量不得覆盖权利门槛 |
| OD-001 | 2026-07-14 | 项目原创代码 `ALL-RIGHTS-RESERVED`；不新增开源 `LICENSE`，不宣称 open source | public repository/source visibility 不授予复制、修改、再发布或商业使用许可；第三方组件许可独立 |
| OD-002 | 2026-07-14 | 项目原创策展文字、翻译、关系解释、UI 文案与原创设计 `ALL-RIGHTS-RESERVED` | 第三方事实、metadata、media、来源许可与署名不受项目权利声明覆盖 |
| OD-005 | 2026-07-14 | 采用 MUSEUM-04 批准的设备、交互、内存、gzip 与 1k/10k/50k 性能预算 | 当前图和合成规模均有硬门禁；实验室代理不表述为真实用户 p75，无实机时记录 `not_available` |
| OD-010 | 2026-07-14 | 建立 Rights or attribution Issue Form 与撤回流程；7/14 日响应目标，高风险立即隔离并以 72 小时内临时下架为目标 | 不在公开 Issue 要求敏感证明；撤回、replacement 与恢复均创建新 release 和审核记录，不改写历史 |
