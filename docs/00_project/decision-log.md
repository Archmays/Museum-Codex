# 决策日志

| ID | 日期 | 状态 | 决策 | 理由 | 重评触发 |
|---|---|---|---|---|---|
| D-0001 | 2026-07-11 | accepted | 采用静态优先发布，API 仅用于离线采集 | Pages 可用性、可复现与权利门禁优先 | 数据规模或个性化需求使静态分片不可维持 |
| D-0002 | 2026-07-11 | accepted | 事实以 Claim–Evidence–Source 为规范层 | 允许争议、反证、审核和撤回 | 无 |
| D-0003 | 2026-07-11 | accepted | common 小 schema + 分馆扩展 | 共享治理而不抹平学科语义 | 第三个分馆证明公共抽象错误 |
| D-0004 | 2026-07-11 | accepted | 算法相似与历史关系在 schema、状态和视觉上隔离 | 防止相关性被误读为历史因果 | 仅可加强隔离，不可弱化 |
| D-0005 | 2026-07-11 | accepted | 美术馆正式 artist 只含确认去世个人 | 明确首馆伦理与范围门槛 | 用户明确修改产品政策并完成影响评估 |
| D-0006 | 2026-07-11 | accepted | 元数据许可与媒体许可逐项记录 | API 开放性不等于媒体可发布 | 无 |
| D-0007 | 2026-07-11 | proposed | 代码与原创内容的最终许可证 | 本阶段不得代用户决定 | 用户选择许可证组合 |
| D-0008 | 2026-07-11 | accepted | MUSEUM-00 不建立前端或 Pages 工作流 | 保持阶段边界 | 用户授权 MUSEUM-01 |
| D-0009 | 2026-07-11 | accepted | 首批 12 位艺术家在 MUSEUM-03 才确定 | 需要来源、权利与代表性评分 | MUSEUM-03 入场门槛满足 |
| D-0010 | 2026-07-11 | accepted | 发布记录按类型、分馆与 ID 前缀强制分派 concrete schema | 阻止输入通过 common schema 降级绕过分馆约束 | schema major 版本重构时 |
| D-0011 | 2026-07-11 | accepted | Source 许可采用稳定 rule ID、canonical 快照 hash 与逐记录 binding | 防止 metadata/data/media 许可错配和来源自报条款 | 引入受控书面许可覆盖模型时 |
| D-0012 | 2026-07-11 | accepted | 物理 release 对文件、媒体字节、notices、attribution 与许可决策做精确闭包 | GitHub Pages 分发的是实际字节，不能只验证自报 manifest 字段 | 后端签名 release 服务替代静态包时 |
| D-0013 | 2026-07-11 | accepted | 许可 binding 同时记录实际 scope locator，且决策 scope 可执行 | 仅有 rule/decision ID 仍可能选择错误字段或越权复用 fixture 决策 | 引入通用规则表达式引擎时 |
| D-0014 | 2026-07-11 | accepted | Release schema_versions 从实际消费 schema 反算并精确对账 | 自报版本不能支持回滚、兼容性或审计 | schema manifest 格式升级时 |
| D-0015 | 2026-07-11 | accepted | Canonical Source 同时锁定来源矩阵身份、官方 host 与规则快照 | 仅锁许可规则仍允许镜像站或伪域名借用权威来源身份 | 来源迁移官方域名或合并机构身份时 |
| D-0016 | 2026-07-11 | accepted | 第三方 notices 按 release 内实际使用的 rule 集合精确生成 | 单一代表性许可不能表达字段、对象和媒体之间的差异 | notices 迁移到外部签名清单时 |
| D-0017 | 2026-07-11 | accepted | GitHub 仓库与 Pages 均公开，MUSEUM-01 正式启用 Pages workflow 发布 | 用户明确选择 `repository=public`、`pages=public` 并要求本阶段完成真实公开部署 | 用户重新决定站点可见性或托管方式 |
| D-0018 | 2026-07-12 | accepted | MUSEUM-02 使用独立、离线优先的构建期 Python 包与 CLI，不建立后端 | 保持静态运行时、复现性与最小供应链 | 明确授权远程审核或标准库无法安全覆盖新协议 |
| D-0019 | 2026-07-12 | accepted | Candidate 使用 source namespace UUIDv5，跨来源只生成人审 proposal，merge 保留全部 loser alias 且可逆 | 名称无关、fixture 可复现、错误身份可撤销 | MUSEUM-03 真实审核证明 signal/alias 模型不足 |
| D-0020 | 2026-07-12 | accepted | CI 使用带双 hash/notice 的最小 recorded projections；真实 probe 仅显式 live 且 raw 不提交 | 同时满足离线稳定与当前接口证据 | 来源提供签名测试 endpoint 或 fixture 需独立仓库 |
| D-0021 | 2026-07-12 | accepted | Normalized field、Claim 和 media candidate 均绑定 canonical source rule/content class；AIC 使用 exact-field selector | 阻断 metadata/media 继承和字段级许可绕过 | 引入书面授权覆盖或复杂组合许可 |

状态使用 `proposed / accepted / superseded / rejected`。被替代决策保留原行并链接后继 ID，不覆写历史。
