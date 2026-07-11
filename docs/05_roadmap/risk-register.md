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

风险在每个阶段入口和 release 前复核；关闭风险需 Evidence，不因“暂未发生”删除。
