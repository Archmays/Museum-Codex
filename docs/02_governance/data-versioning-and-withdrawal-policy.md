# 数据版本与撤回政策

## 不可变与可追溯

原始快照和已发布 release 不原地修改。任何修正创建新版本，manifest 记录 predecessor、输入 hash、schema/build 版本、变更摘要和 withdrawals。公开引用使用确定版本，不使用不可复现的 `latest` 作为学术定位。

## 版本规则

- Schema：SemVer；语义/必填或类型不兼容提升 major。
- Dataset：修正且契约兼容为 patch，新增实体/字段投影为 minor，消费者契约或语义破坏为 major。
- Source snapshot：`source-id/fetched-at/hash`，保存请求与许可核验的非敏感元数据。
- Derived asset：原资产 hash + transform recipe/version + output hash。

## 废弃与撤回

`deprecated`：内容仍可在历史版本解释，但已有更准确替代；使用结构化 deprecation 记录 `superseded_by/effective_at/reason`。`withdrawn`：当前发布不得继续展示/分发；使用结构化 withdrawal 记录原因类别、`effective_at`、`scope`、replacement 和公开说明。两者与 included 集合必须互斥。

撤回原因可为 factual_error、rights_request、privacy/safety、cultural_sensitivity、source_retraction、duplicate_identity 或 legal_hold。公开说明最小化敏感细节。

## 权利请求响应

权利、署名或撤回请求通过公开 Rights or attribution Issue Form 进入，但公开 Issue 不要求身份证件、合同、授权原件、地址、电话、文件上传或其他敏感证明。初步确认目标为 7 个自然日，一般初评目标为 14 个自然日；明显误授权、隐私、安全或持续高风险分发立即隔离，并以 72 小时内临时下架或移除引用为目标。需要证明时转入受控非公开渠道。

确认撤回时创建新 release，在结构化 withdrawal 中记录 request、scope、临时措施、结论、replacement、release、缓存处置与恢复条件；不改写旧 release 或原始快照。缓存无法直接控制时记录平台、请求和剩余风险。恢复必须有新的权利审核记录并产生新的 release。详细职责与升级流程见 `rights-request-and-takedown-procedure.md`。

## 回滚

发布失败或回归时将站点构建固定到上一通过门禁的 release；不把 main 强制重写。随后创建修正 release。回滚记录 actor、时间、from/to、原因、受影响范围和后续动作。

## 上游变化

- 字段/接口变化：adapter contract fail，隔离快照，不用空值覆盖。
- URL/许可变化：保留旧访问事实，新采集暂停媒体发布直至核验。
- 来源过时/撤回：标记相关 Evidence，重评 Claim；不自动删除其他独立证据。
- 重复实体：保存 merge record 和旧 ID alias；若误合并，按记录拆分并发布新版本。

## 保留

raw、review、release 和审计日志的保留期在首次真实采集前另行决定。任何保留策略必须兼顾来源条款、撤回义务、可复现性和敏感数据最小化；不能默认无限保存未获许可的媒体字节。
