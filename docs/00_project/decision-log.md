# 决策日志

| ID | 日期 | 状态 | 决策 | 理由 | 重评触发 |
|---|---|---|---|---|---|
| D-0001 | 2026-07-11 | accepted | 采用静态优先发布，API 仅用于离线采集 | Pages 可用性、可复现与权利门禁优先 | 数据规模或个性化需求使静态分片不可维持 |
| D-0002 | 2026-07-11 | accepted | 事实以 Claim–Evidence–Source 为规范层 | 允许争议、反证、审核和撤回 | 无 |
| D-0003 | 2026-07-11 | accepted | common 小 schema + 分馆扩展 | 共享治理而不抹平学科语义 | 第三个分馆证明公共抽象错误 |
| D-0004 | 2026-07-11 | accepted | 算法相似与历史关系在 schema、状态和视觉上隔离 | 防止相关性被误读为历史因果 | 仅可加强隔离，不可弱化 |
| D-0005 | 2026-07-11 | accepted | 美术馆正式 artist 只含确认去世个人 | 明确首馆伦理与范围门槛 | 用户明确修改产品政策并完成影响评估 |
| D-0006 | 2026-07-11 | accepted | 元数据许可与媒体许可逐项记录 | API 开放性不等于媒体可发布 | 无 |
| D-0007 | 2026-07-11 | superseded | 代码与原创内容的最终许可证 | 已由 D-0026 与 D-0027 分别记录用户对代码和原创内容的 `ALL-RIGHTS-RESERVED` 决定 | 见 D-0026、D-0027 的重评触发条件 |
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
| D-0022 | 2026-07-13 | accepted | MUSEUM-03B 首批 12 人采用用户批准的 MUSEUM-03A Recommended Slate | 该组合用于验证首个正式试点批次，不构成艺术价值、重要性或影响力排名 | 任一成员硬门槛失败时阻断并提交替换建议，不自动改名单 |
| D-0023 | 2026-07-13 | accepted | 媒体采用 Option D `Mixed`，首轮默认 `metadata-first` | 先闭合知识、证据与权利；external IIIF 和未来 self-hosted 必须逐对象决定 | 对象级许可、技术交付或撤回条件变化时 |
| D-0024 | 2026-07-13 | accepted | MUSEUM-03B 不下载媒体字节、不创建 public release、不向 Pages 添加正式艺术内容 | OD-001/002 未关闭，MUSEUM-04 体验与发布闭包尚未完成 | 后续获授权的媒体或公开发布阶段 |
| D-0025 | 2026-07-13 | accepted | 正式批次任一艺术家失败时不得自动替换或降低门槛 | 保持用户批准名单、审计与失败语义真实 | 用户审阅 replacement request 并明确批准新名单 |
| D-0026 | 2026-07-14 | accepted | OD-001：项目原创代码保留所有权利，不新增开源 `LICENSE`，公开可查看不构成复制、修改、再发布或商业使用授权 | 用户 Mays 明确选择 `ALL-RIGHTS-RESERVED`；第三方组件继续按各自许可证与 notices 管理 | 用户明确重新授权代码，且完成依赖、贡献、专利与发布范围影响评估 |
| D-0027 | 2026-07-14 | accepted | OD-002：项目原创策展文字、翻译、关系解释、UI 文案与原创设计保留所有权利；第三方 metadata/media 按自身条款分别管理 | 防止项目权利声明覆盖第三方事实、元数据、媒体许可或署名义务 | 用户明确重新授权原创内容，或第三方范围/上游条款发生变化 |
| D-0028 | 2026-07-14 | accepted | OD-005：采用 MUSEUM-04 已批准的目标设备、实验室性能预算、gzip 预算与 1k/10k/50k 合成规模边界 | 为当前图、低资源回退和大规模安全拒绝提供可验证门槛；不得把实验室代理称为真实用户 p75 | 正式图规模、渲染架构、目标设备或可复现实验结果发生实质变化 |
| D-0029 | 2026-07-14 | accepted | OD-010：使用 Rights or attribution Issue Form；7 日内初步确认、14 日内一般初评，高风险立即隔离并以 72 小时内临时下架/移除引用为目标；撤回和恢复均通过新 release | 建立不要求公开敏感证明、保持历史可追溯且可快速隔离的权利响应流程 | 法律义务、托管平台能力、联系渠道或缓存机制发生实质变化 |
| D-0030 | 2026-07-17 | accepted | OD-006：使用 Natural Earth 1:110m land/coastline/lakes 构建完全自托管、无现代政治边界的静态 GeoJSON 底图；使用 exact-pinned MapLibre GL JS 5.24.0 渲染本地数据，并保留等价 timeline/list 回退 | 该方案同时闭合 public-domain 底图、Getty 地点身份、无 token/外部 tile、静态 Pages、可复现字节、无障碍等价与历史语义门禁 | Natural Earth 来源/许可、MapLibre stable/security、Pages 能力或 550 KB route / 400 KB renderer 预算发生实质变化 |
| D-0031 | 2026-07-19 | accepted | OD-008：中文与多语搜索不引入分词第三方依赖；以 Unicode normalization、exact/prefix/substring、approved alias、transliteration 和 source-language label 为完整 fallback，`Intl.Segmenter` 只作可选 token 增强；索引采用可局部重建的确定性分片 | 保持静态、可解释、低供应链、无远程依赖；Segmenter 缺失仍完成核心任务，排序不混入流行度、重要性或艺术价值 | 浏览器 Unicode/Segmenter 能力、20k synthetic 查询预算或分片规模契约发生实质变化 |
| D-0032 | 2026-07-19 | accepted | OD-009：站点不使用 analytics、账户、服务端画像、查询/访问/路径/地图/导览历史、telemetry SDK、Cookie、指纹、用户定位或远程日志；仅允许 locale、low-bandwidth 等明确本地 UI 偏好 | 站点无需收集个人行为即可完成浏览、搜索、比较、路径、地图和导览；最小本地偏好兼顾可访问性且不建立访问档案 | 用户明确要求新增数据处理，且先完成独立隐私、数据最小化、保留期、安全与同意评估 |
| D-0033 | 2026-07-19 | accepted | 未来跨 release 媒体以 SHA-256 内容身份复用，共享字节但逐引用绑定对象、用途、权利、署名与 withdrawal；M08 只交付 synthetic prototype，不迁移或删除 M04–M07 字节 | 避免数十批次重复下载、转码和物理复制，同时保持历史 URL、不可变 release 与撤回边界 | MUSEUM-09 首批真实内容前完成共享 namespace staging、Pages 缓存/回滚和逐引用权利闭包复核 |

状态使用 `proposed / accepted / superseded / rejected`。被替代决策保留原行并链接后继 ID，不覆写历史。
