# 全球覆盖分类法

## 使用原则

覆盖分类用于发现偏斜、分配研究工作和保持批次平衡，不用于给艺术家赋予价值等级。每位目标艺术家有且只有一个有来源依据的 primary coverage bucket；可另保留有来源支持的跨区域 context tags。不得从姓名、外貌、标题或模型推断敏感身份、迁移、侨民、殖民语境或创作地点。

## Primary buckets 与 MUSEUM-09A 闭合

| Primary bucket | Guardrail | 目标数 | 占比 | 状态 |
|---|---:|---:|---:|---|
| Europe | ≤35% | 170 | 34% | pass |
| East Asia | ≥10% | 65 | 13% | pass |
| Africa | ≥8% | 40 | 8% | pass |
| Latin America and Caribbean | ≥8% | 55 | 11% | pass |
| North America | ≥8% | 75 | 15% | pass |
| South Asia | ≥6% | 30 | 6% | pass |
| Southeast Asia | ≥4% | 25 | 5% | pass |
| West and Central Asia | ≥4% | 25 | 5% | pass |
| Oceania | ≥2% | 15 | 3% | pass |
| **合计** |  | **500** | **100%** | **pass** |

这些数值是方向性 guardrails，不是配额优先于证据。未来若 hard gate 造成缺口，应保留 `coverage_gap`、搜索范围和下一轮入口，不得降低个人身份、已故状态或来源门槛。

## Primary basis

允许的 primary basis 是官方人物记录中的明确地理描述、既有已审核艺术家基线，或已记录且可解析到来源的 birthplace/activity crosswalk。多个来源冲突时保留冲突并阻止提升，不能由程序静默择一。现代国家名只是来源文字的一部分，不等同于国籍、族裔或单一文化身份。

## 时期、媒介与来源维度

目标总体同时记录 `before-1400`、`1400-1599`、`1600-1799`、`1800-1899`、`1900-1949` 和 `1950-onward`；最后一组仍只接受确认去世的个人。

媒介标签来自作品元数据，覆盖 painting、drawing、printmaking、sculpture、photography、ceramics、textile/fiber、architecture/design、decorative arts，以及来源明确支持的 mixed/installation/performance documentation。标签只描述已记录实践，不从作品标题扩写主题或艺术史意义。

来源维度同时记录每个正式来源的候选作品数、目标作品数、涉及时期、媒介和区域。任一来源在 5,000 件目标作品中的占比不得超过 30%；MUSEUM-09A 的最高单一来源占比为 16.48%。

## 当前偏斜与解释限制

既有 12 人基线集中在 Europe、East Asia、South Asia、North America 和 Latin America/Caribbean。MUSEUM-09A 的矩阵补足 Africa、Southeast Asia、West/Central Asia 与 Oceania，但不宣称已穷尽全球艺术史，也不把 500 人总体解释为艺术价值排名。

有关女性艺术家、长期被低估群体、跨文化、迁移、侨民、殖民与后殖民语境，只能在未来研究记录有明确来源时使用。本矩阵不保存模型推断的 gender、ethnicity、race 或其他敏感身份字段。
