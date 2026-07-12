# 武器博物馆来源与权利研究 Brief

## 当前阶段限制

`MUSEUM-02A` 不选择正式来源，不建立 adapter，不进行 live probe，不抓取馆藏，不下载图片或 3D 模型，也不创建正式器物候选。本文只规定未来 `MUSEUM-ARMS-00` 的研究问题和核验门槛。

## 未来来源类别

`MUSEUM-ARMS-00` 至少评估：

- 正式武器、甲胄和军事史博物馆；
- 综合博物馆的 arms and armor 部门；
- 国家档案馆和历史档案；
- 考古数据库与发掘报告；
- 保护、材料分析与修复研究机构；
- 经同行评审的学术出版物和权威参考书；
- 条约、裁军、国际人道法与人道历史机构；
- 权威术语库、名称规范和馆藏身份系统。

Tier 3 或聚合来源可发现候选，但不能独立支持争议事实、直接历史影响、制造者身份、来源清白或正式发布。商业目录、论坛、社交媒体和娱乐资料不能成为高风险事实的独立证据。

## 每个来源的逐项核验

每个候选来源必须记录并复核：

1. 官方身份、canonical 名称、官方 host 与管理机构；
2. 适用记录类型、对象身份规则和稳定 ID；
3. metadata/data 许可、规则文本、版本、范围与 attribution；
4. 媒体许可、对象级 rights evidence、下载/IIIF/缓存与改编边界；
5. API、IIIF、bulk download、页面抓取和速率/访问条件；
6. 是否包含现代、仍在服役、受监管或可操作技术资料；
7. 是否适合静态公开，以及哪些字段必须隔离或只保留来源链接；
8. 暴力、死亡、殖民、掠夺、极端主义和图像化伤害等敏感内容；
9. 文化财产、战争掠夺、非法发掘、交易、归还与 provenance 风险；
10. 访问日期、条款版本、复核周期、撤销/变更触发和 reviewer。

不得因为某机构是博物馆、档案馆或公共机构，就推定其图像、3D、技术图纸或全部元数据可再发布。

## 权利分层

- 项目原创文字、代码、第三方 metadata/data、图片、音频、视频、3D、字体和授权文件分别建账；
- API 可访问性、IIIF URL、缩略图或“open access”标签不自动证明媒体可再发布；
- 每个媒体对象记录 source object URL、rights holder、canonical license、用途/地域/平台/期限、attribution、修改权、缓存方式、content hash、reviewer 和撤回状态；
- `unknown`、`restricted`、`research_or_education_only` 或 `development_only=true` 默认阻断公开 release；
- 现代操作手册、训练资料或可执行工程图即使权利允许，也受安全政策阻断。

## 来源快照与发布闭包

未来 adapter 只有在另行授权后才能使用，且必须固定 HTTPS host、对象 ID、path/query/profile、response contract、license rule 和 terms snapshot。原始响应不可变保存，规范化结果记录逐字段 provenance；public runtime 只消费经审核的静态 release，不调用上游 API。

正式 release 必须闭合到精确 Source rule、内容类别、对象级媒体结论、notice、attribution、字节 hash、schema 版本和 withdrawal。许可规则或安全结论不能由记录自报来绕过 canonical registry。

## `MUSEUM-ARMS-00` 预期交付

- 来源比较矩阵与逐来源核验笔记；
- 年代、现代武器、敏感内容和儿童/家庭边界建议，提交 `OD-011` 决策；
- 受控术语与跨文化分类风险说明；
- metadata/data/media 权利规则与复核计划；
- concrete schema、fixtures、审核角色与 fail-closed adapter 方案；
- 明确的禁止字段、隔离字段和 public projection 规则。

这些研究工件通过前，不得进入 `MUSEUM-ARMS-01`、下载媒体或发布器物数据。
