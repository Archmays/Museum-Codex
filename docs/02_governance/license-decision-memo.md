# 许可证决策备忘录

- Status: decided
- Decision date: 2026-07-14
- Decision authority: Mays

OD-001 与 OD-002 已关闭：项目原创代码与项目原创策展内容均采用 `ALL-RIGHTS-RESERVED`，不新增项目级开源 `LICENSE`。公开可查看不等于授权复制、修改、再发布或商业使用。第三方元数据、媒体、依赖与其他材料始终保留各自许可、限制与署名。

## 决策前的代码选项记录

| 选项 | 影响 | 适合情形 |
|---|---|---|
| MIT | 允许广泛复用、修改、商业使用；保留版权与许可声明 | 希望最大化工具和前端采用，接受闭源衍生 |
| Apache-2.0 | 类似宽松许可并含明确专利条款 | 希望专利授权与贡献边界更明确 |
| GPL-3.0 | 分发衍生程序时要求同许可开放源代码 | 希望强 copyleft，接受集成限制 |
| 暂不许可（all rights reserved） | 外部用户通常无复制/修改授权 | 决策前的私有筹备；不适合开放协作 |

最终选择为保留所有权利。MIT、Apache-2.0 与 GPL-3.0 仅保留为决策前比较记录，不适用于当前项目代码。

## 项目原创文字/策展内容选项

| 选项 | 影响 |
|---|---|
| CC BY 4.0 | 允许修改和商业复用，要求署名与改动说明 |
| CC BY-SA 4.0 | 加 ShareAlike，传播开放但组合兼容更复杂 |
| CC BY-NC 4.0 | 禁止商业使用但“商业”边界可能造成复用不确定 |
| 保留所有权利 | 控制最大，公共教育复用最低 |

最终选择为保留所有权利。不要给事实、第三方 metadata 或媒体自动套用项目原创内容权利声明；数据库权利和上游条款继续单独评估。

## 决策实施

1. 保持无项目级 `LICENSE`，以根目录 `RIGHTS.md` 和公开 About & Rights 页面声明范围。
2. `governance/license-decisions.json` 中 `license-decision:od-001` 与 `license-decision:od-002` 记录 `decided`、`ALL-RIGHTS-RESERVED`、Mays 与 2026-07-14。
3. README 精确区分项目代码、原创内容、第三方 metadata/media、notices 与 attribution。
4. 每个正式 release 仍携带实际使用规则对应的 third-party notices 与 attribution；项目保留权利不能覆盖第三方义务。
5. 未来若重新授权，追加新决策并完成依赖、贡献、专利、内容与历史 release 影响评估，不覆写本决策。

正式公开 Dataset Release 必须引用这两项已关闭的 decision ID，附权利范围声明、`third_party_notices` 与逐资产 attribution manifest。`ALL-RIGHTS-RESERVED` 不是 SPDX/open license，也不解除 Source、metadata 或 media 的独立许可与署名门禁。

## Synthetic fixtures

`governance/license-decisions.json` 是机器可读决策注册表。`license-decision:synthetic-fixture-code` 与 `license-decision:synthetic-fixture-content` 仅把合成验证 fixture 标为 `not_applicable`，不授予任何项目代码或内容许可，也不关闭 OD-001/OD-002。物理 fixture 携带这两项的哈希快照，用来证明任意或虚构 decision ID 会被发布闸门拒绝。

每项决策包含结构化 `scope_constraint`。合成决策只匹配 release ID、build version、record IDs 和 Source registry 均明确属于 fixture 的包；在真实 release 中复用同一 decision ID 会失败。项目级 OD 决策只有在状态关闭、批准者/生效日/证据与权利描述完整后才可用于公开构建。

## 重评触发

只有用户明确重新授权，或贡献模式、专利边界、商业合作、内容复用目标或第三方组合义务发生实质变化时，才重评 OD-001/OD-002。重评前继续保留所有权利。
