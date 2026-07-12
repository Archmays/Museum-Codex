# 风险登记表

等级：Likelihood/Impact 使用 L/M/H。Owner 表示责任角色而非具体个人。

| ID | 风险 | L | I | 预防/缓解 | 触发与响应 | Owner |
|---|---|---:|---:|---|---|---|
| R-001 | 视觉/算法相似被写成历史影响 | M | H | 分语义 schema、C 级、invalid fixture、文案审查 | 命中因果措辞或类型错配即阻断 release | discipline reviewer |
| R-002 | 在世/死亡不明者进入正式 artist | L | H | publishable 条件、Tier 1/2 死亡 Claim | 门禁失败；退回 identity queue | discipline reviewer |
| R-003 | 元数据许可被套给图片 | H | H | 分字段、对象级 rights、媒体 validator | unknown/缺 rights URL 阻断并隔离字节 | rights reviewer |
| R-004 | 上游 API/字段/速率改变 | H | M | raw 快照、adapter contract、限速/重试、static runtime | contract fail；暂停 adapter，不覆盖 reviewed | data maintainer |
| R-005 | IUCN/受限数据被公开再发布 | M | H | source-specific block、书面授权字段 | 无授权即 development-only/链接模式 | rights reviewer |
| R-006 | 图规模导致移动端卡顿 | M | H | 局部子图、分片、预计算、设备预算 | 基准失败则缩可视规模/worker/预计算 | engineering |
| R-007 | WebGL 图/地图排除辅助技术 | M | H | DOM 等价列表、键盘/读屏人工 QA | 任务不可等价完成则不发布 | accessibility reviewer |
| R-008 | 第三方 API key/授权文件进入 Git | L | H | gitignore、秘密扫描、构建期 secrets | 发现即撤销轮换、清理并审计历史 | release manager |
| R-009 | 重复实体误合并或同名混淆 | M | H | 外部 ID + 多信号 proposal + 人审 + 可逆 merge | 冲突触发拆分 release 与 alias 修复 | identity reviewer |
| R-010 | 争议 Claim 被规范字段覆盖 | M | H | 冲突 Claim 并存、投影可重建 | 新反证进入 disputed，保留旧版本 | discipline reviewer |
| R-011 | Pages/仓库被大图或单 JSON 撑满 | M | M | 不提交 raw、响应式衍生物、分片/预算 | 接近平台限额即外置合规媒体/重评托管 | engineering |
| R-012 | 撤回后缓存仍分发资产 | M | H | 内容 hash、新 release、缓存策略/响应手册 | 紧急新 release、移除引用、平台缓存处置 | release manager |
| R-013 | AI 草稿混入正式展签或虚构引用 | M | H | provenance、人工审核、非 AI Evidence | 无可解析来源即拒绝并记录 | content reviewer |
| R-014 | 西方正典/开放图像可得性主导 12 人 | H | M | 组合维度、缺口说明、偏差审查 | 候选组合失衡则回到宽池，不用低质填充 | curator |
| R-015 | 生物观测被误当分布/动画普遍行为 | M | H | 分实体/Claim、原始研究与简化字段 | 范围升级无 Evidence 则阻断 | science reviewer |
| R-016 | 第三方条款或撤回要求未及时复核 | M | H | 12 月复核、release 前高风险复核 | 条款变化暂停新增发布并重评影响 | rights reviewer |
| R-017 | 输入通过基础 schema 或自报许可规则绕过分馆/来源约束 | M | H | canonical schema dispatch、稳定 rule ID、canonical 快照 hash | 任一类型/branch/ID/规则不匹配即阻断 | data + rights reviewer |
| R-018 | Manifest hash 正确但夹带未登记文件、空 notices 或缺媒体字节 | M | H | 精确文件集合、artifact schema/ID 内容闭包、自托管字节 hash | 物理包任一集合/内容不闭合即拒绝 | release manager |
| R-019 | 镜像站、同形域名或字段查询借用权威来源身份与开放许可 | M | H | hashed registry identity、HTTPS 精确 host、endpoint + query-field matcher、notice rule 并集对账 | 身份、字段集合或实际 rule coverage 任一不一致即拒绝 | data + rights reviewer |
| R-020 | duplicate/304 snapshot 引用损坏、错源或循环 body，导致表面 hash 正确但不可重放 | L | H | 引用链同源解析、物理 bytes/hash、cycle、snapshot ID suffix 和损坏 body 不复用测试 | 任一引用无法闭合即阻断 normalize/run | data maintainer |
| R-021 | Review decision 在 candidate/proposal 改变后被自动套用 | M | H | bundle exact input hashes、physical validation、stale status、不创建 merge | 任一 hash 不同即 stale，要求重新审核 | review lead |
| R-022 | raw/candidate/review/recorded fixture 或技术探针进入 Pages | L | H | Git ignore、public/dist scanner、workflow 仅上传 dist、线上标识符 smoke | 扫描命中即停止 build/deploy，撤回污染 artifact | release manager |
| R-023 | 固定 adapter 被路径/query/redirect/DNS 绕过形成 SSRF 或 secret 泄漏 | L | H | HTTPS exact allowlist、object pattern、public IP check、每跳复核、无 Cookie、脱敏与有界 transport | 任一 host/path/query/地址异常即拒绝并保留安全错误码 | security reviewer |
| R-024 | recorded projection 与当前 live response 分叉却被当作实时通过 | M | H | 双 hash、抓取日、adapter version、真实 live probe、drift fail closed、projection notice | contract/shape 不同先升级 adapter/fixture，阶段状态如实 partial/blocked | data maintainer |
| R-025 | 武器馆内容被操作化、采购化、伤害优化或暴力娱乐化 | M | H | 独立安全政策、敏感内容分级、公开 artifact 文本扫描、学科/安全/年龄审核 | 命中制造/改装/操作/采购/战术或美化表达即阻断并退回内容审查 | safety + content reviewer |
| R-026 | `branch_id=arms` 借 common entity fallback 绕过尚未实现的分馆 schema | M | H | common enum 与 concrete dispatch 分离、明确 unimplemented 错误、expected-invalid fixture、physical closure 回归 | 任一 arms 实体进入数据入口即 fail-closed；不得通过 common schema 发布 | data + release reviewer |
| R-027 | 未确认候选姓名、外部 ID、作品、leads 或 decision package 进入 Git/Pages | M | H | ignored review/raw、tracked-path scan、bundle-label public/dist scan、Pages 仅上传 dist | 任一命中即阻断提交/构建/部署并重建无污染 artifact | release manager |
| R-028 | 西方机构开放数据和高分图可得性主导合格池与 Recommended | H | H | 42+ 宽池、无 adapter 自动排除、small-quota 理由、scenario 偏差矩阵、替换规则 | 组合目标失衡则回到宽池；不以低质量来源补数、不把 media count 当价值 | curator + discipline reviewer |
| R-029 | preflight 的 PD/CC0/IIIF/metadata-only 状态被误写成发布批准 | M | H | `*_candidate` 状态、metadata/media 分离、object evidence、decision pending、无 approve CLI | 出现 publishable/approved/released 或许可继承即 schema/semantic fail | rights reviewer |
| R-030 | 权威来源记录内部生卒/身份字段冲突却被规范投影静默覆盖 | M | H | raw bytes、结构化字段与 biography/馆藏交叉核验、冲突候选退出合格池、adapter gap | 任一高风险冲突进入 hard gate 即退回 research queue，保留双方证据 | identity reviewer + data maintainer |

风险在每个阶段入口和 release 前复核；关闭风险需 Evidence，不因“暂未发生”删除。
