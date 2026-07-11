# 许可证决策备忘录

- Status: open decision
- Date: 2026-07-11

本阶段不替用户选择最终许可证。以下只比较项目有权许可的代码和原创内容；第三方元数据/媒体始终保留各自许可与署名。

## 代码选项

| 选项 | 影响 | 适合情形 |
|---|---|---|
| MIT | 允许广泛复用、修改、商业使用；保留版权与许可声明 | 希望最大化工具和前端采用，接受闭源衍生 |
| Apache-2.0 | 类似宽松许可并含明确专利条款 | 希望专利授权与贡献边界更明确 |
| GPL-3.0 | 分发衍生程序时要求同许可开放源代码 | 希望强 copyleft，接受集成限制 |
| 暂不许可（all rights reserved） | 外部用户通常无复制/修改授权 | 决策前的私有筹备；不适合开放协作 |

推荐待用户确认的优先比较：MIT vs Apache-2.0。选择前确认未来贡献模式、专利关注、是否接受闭源复用。

## 项目原创文字/策展内容选项

| 选项 | 影响 |
|---|---|
| CC BY 4.0 | 允许修改和商业复用，要求署名与改动说明 |
| CC BY-SA 4.0 | 加 ShareAlike，传播开放但组合兼容更复杂 |
| CC BY-NC 4.0 | 禁止商业使用但“商业”边界可能造成复用不确定 |
| 保留所有权利 | 控制最大，公共教育复用最低 |

推荐由用户在开放教育目标、商业合作、ShareAlike 期望和执法成本之间选择。不要给事实数据库自动套用原创文字许可；数据库权利和上游条款需单独评估。

## 决策后动作

1. 新增代码 `LICENSE` 和内容许可说明/范围文件。
2. README 精确声明哪些目录受何许可、哪些不受覆盖。
3. 建立 `THIRD_PARTY_NOTICES` 与逐资产 attribution 输出。
4. 检查依赖、字体、数据和 CC BY-SA 组合兼容性。
5. 记录决策 ID、日期和不追溯覆盖第三方内容的声明。

正式公开 Dataset Release 必须引用已关闭的代码/原创内容 decision ID（不适用也需明确），附许可证范围声明、`third_party_notices` 与逐资产 attribution manifest；OD-001/OD-002 pending 时只允许非公开/合成 fixture，不得签发 public release。

## Synthetic fixtures

`governance/license-decisions.json` 是机器可读决策注册表。`license-decision:synthetic-fixture-code` 与 `license-decision:synthetic-fixture-content` 仅把合成验证 fixture 标为 `not_applicable`，不授予任何项目代码或内容许可，也不关闭 OD-001/OD-002。物理 fixture 携带这两项的哈希快照，用来证明任意或虚构 decision ID 会被发布闸门拒绝。

每项决策包含结构化 `scope_constraint`。合成决策只匹配 release ID、build version、record IDs 和 Source registry 均明确属于 fixture 的包；在真实 release 中复用同一 decision ID 会失败。项目级 OD 决策只有在状态关闭、批准者/生效日/证据与许可证描述完整后才可用于公开构建。

## 唯一待确认项

在 MUSEUM-01 发布代码前，用户选择代码许可证；在首个原创展签公开前，用户选择原创内容许可证。没有选择不会阻塞 MUSEUM-00 的治理底座，但阻止正式公开发布相应内容。
