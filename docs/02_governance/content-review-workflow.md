# 内容审核流程

## 职责分离

| 角色 | 可做 | 不可独立做 |
|---|---|---|
| collector | 登记来源、采集 raw | 提升 Claim、决定权利 |
| normalizer | 映射字段、提出合并 | 删除冲突、确认身份 |
| discipline reviewer | 审身份/Claim/关系/说明 | 代表权利审核 |
| rights reviewer | 确认逐资产许可和范围 | 判断学科事实 |
| release manager | 运行门禁、签发/回滚 | 绕过失败或改写审核记录 |

小团队可由同一人兼任，但日志必须记录所扮演角色；高风险发布至少存在学科和权利/发布两种决策。

## 工作流

1. `candidate`：保存发现来源、原值和创建者；不得公开。
2. `sourced`：至少一个 Evidence 精确链接 Source，完成 Tier 与引用定位。
3. `reviewed`：审核身份、谓词、范围、不确定性、冲突和说明。
4. `verified`：适当 Tier 和独立交叉核验完成；不是所有低风险字段都要求第二来源，但理由要记录。
5. `publishable`：权利、引用完整性、状态、语言和敏感性门禁通过。
6. `published`：进入指定不可变 release；记录 release ID。

禁止 `candidate → published`。任何状态变化记录 actor、role、timestamp、from/to、reason 和关联 Evidence。

## 审核检查单

- 身份：stable ID、同名/别名/文字系统、时间地点、外部 ID；艺术家死亡门槛。
- 陈述：原子性、谓词、适用范围、精度、来源独立性、反证。
- 关系：类型/方向、A/B/C、四类分数、措辞、算法隔离。
- 媒体：权利状态、holder、license URL、署名、允许行为、期限、来源对象页。
- 展签：区分事实、解释、比较、假说；翻译草稿不继承审核。
- 无障碍：alt/长描述用途、非颜色编码、文本替代。

## 争议与质量事件

争议内容进入 `disputed` 并保留各方 Claim；若仍展示，必须有争议标签。严重错误、权利投诉或安全/文化敏感问题可紧急 `withdrawn`，随后由正式审查决定替代/恢复。审核者不得删除反证以得到“干净”叙事。

## 抽样与复核

每个 release 对新增/修改的高风险 Claim 和全部媒体做 100% 门禁；低风险元数据另做引用完整性自动检查与人工抽样。条款变更、来源 adapter 变化或 schema major 变化触发受影响内容复核。

自动门禁还检查记录不能自选较弱 schema、所有公开 Claim 至少有 supporting Evidence、反证触发 disputed 工作流、生卒/作品归属语义与展示值一致、关系端点的实际实体类型正确，以及 Source rule binding 与实际内容类别一致。权利和条款审核日期超过 366 天或位于未来时，不允许用人工“已看过”的口头说明绕过。
