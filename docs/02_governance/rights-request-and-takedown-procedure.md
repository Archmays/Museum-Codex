# 权利、署名请求与撤回流程

生效日期：2026-07-14。决策人：Mays。

本流程适用于公开页面、metadata、策展文字、关系解释、来源、署名、release 记录及未来可能获准的媒体。MUSEUM-04 是 zero-media release，但 metadata、来源、署名和原创内容仍可成为权利或更正请求的对象。

## 公开入口与敏感证明

使用 [Rights or attribution request](https://github.com/Archmays/Museum-Codex/issues/new?template=rights-or-attribution.yml) 提交请求。公开 Issue 只记录安全公开的信息：请求类型、受影响 URL、公开对象或 release、问题描述、期望更正、可选的权利人关系、紧急/安全问题与联系偏好。

不得在公开 Issue 提交或要求身份证件、合同、授权原件、家庭地址、电话号码、未公开联系方式或其他敏感证明，也不要求文件上传。需要核验证明时，由维护者安排受控的非公开渠道；私密证明不进入 Git、公开 release、公开 Issue 或 Pages artifact。

## 响应目标

- 初步确认：目标为收到请求后 7 个自然日内。
- 一般初评：目标为收到请求后 14 个自然日内。
- 明显误授权、隐私、安全或持续高风险分发：立即开始隔离，并以 72 小时内临时下架相关公开内容或移除引用为目标。

这些是响应目标，不取代适用法律、法院命令、平台强制措施或更短的安全处置期限。

## Triage 与记录

Release manager 建立受控记录，至少包含：请求 ID、接收时间、请求类型、公开 URL、受影响 ID/release、请求范围、风险级别、联系偏好、临时措施、责任角色、证据存放类别、结论、replacement、目标 release、缓存处置与恢复条件。

初评区分：

1. 署名或来源更正；
2. 权利或授权范围争议；
3. 隐私、安全或高风险持续分发；
4. 事实错误、记录错配或重复身份；
5. 不属于本仓库控制范围的上游页面或第三方平台问题。

## 隔离与升级

- Release manager 负责公开分发隔离、release 与缓存处置。
- Rights reviewer 核对权利链、许可范围、到期/撤销状态和署名义务。
- Data/content reviewer 核对受影响记录、Claim → Evidence → Source 与 replacement。
- Privacy/safety concern 立即升级，不等待一般 14 日初评目标后才采取临时措施。
- 存在法律要求、身份争议或复杂授权链时，交由适当的人类权利/法律审核，不由自动化系统作最终法律判断。

临时隔离可以阻止构建、从当前 public projection 移除记录、停止链接或回滚到最近通过门禁的 release。临时措施必须记录范围和原因，不得借隔离删除审计历史。

## 撤回、replacement 与缓存

已发布内容不原地改写。确认撤回或更正时：

1. 创建新的 release，并以 predecessor 指向原 release；
2. 用结构化 withdrawal/deprecation 记录原因、时间、scope、replacement 与最小公开说明；
3. 从新 release 的 included 集合和公开引用中移除受影响内容；
4. 处理 Pages artifact、站点引用和可控制缓存；记录无法直接控制的第三方缓存或镜像；
5. 保留必要的最小审计记录，不继续公开分发受限正文或字节；
6. 记录 replacement ID/release，或明确没有 replacement。

历史 release 及原始快照保持可追溯，不通过改写历史伪装内容从未存在。高风险情形可先隔离、后完成完整审查。

## 恢复

恢复必须有新的权利审核记录，核对权利人、授权范围、平台、用途、地域、修改/再发布条件、署名、开始/到期日及撤销状态。恢复创建新的 release；不得仅把旧状态改回 active。新记录必须说明恢复条件、reviewer、review date、来源证据和与先前撤回的关系。

## 关闭与复核

请求关闭时记录结论、已采取措施、public notice、release/hash、缓存状态、未解决限制和下次复核条件。若请求者需要补充敏感证明，只在已安排的非公开渠道处理；公开 Issue 仅保留非敏感摘要。
