# 艺术家关系政策

## 准入

关系必须使用受控类型，不得用 `related_to` 作为正式边。记录包含端点、方向、时间/地点范围、Claim/Evidence/Source、A/B/C、四类独立度量、策展说明、`public_display`、算法标记、审核状态和数据版本。

## 类型规则

- `student_of` / `teacher_of` 是互为显示方向的同一事实语义；规范存储只选一条并由 UI 派生反向标签。
- `worked_in_studio_of` 不等同师生；`collaborated_with` 要有共同工作证据。
- `associated_with_movement` 区分正式成员、自我认同和后世归类，并在 Claim 中说明。
- `participated_in_same_exhibition` 需要具体展览实体；不因同馆藏而推断相识。
- `worked_in_same_place_period` 需要地点和时间重叠计算及来源，属于 B，不推出接触。
- `explicitly_influenced_by` / `explicitly_influenced` 仅接受 A 级、非算法、具方向的直接证据。
- `shared_*`、`scholarly_compared_with` 和 `computationally_similar_to` 为 C；前者需策展范围，后者需方法版本。

端点不是一律 artist–artist：`member_of` 指向 `art_group/organization`，`associated_with_movement` 指向 `art_movement`。`participated_in_same_exhibition`、`shared_patron`、`shared_institution`、`shared_subject/technique/material` 保持 artist–artist 展示边，但相应 exhibition/person-or-organization/institution/subject/technique/material 必须作为类型化 `context_entity_ids` 存在；缺 context 不发布。

## 计算相似

记录特征空间、输入作品/衍生图、模型/参数、数据 release、归一化、相似度、已知限制和生成时间。它只生成 `computationally_similar_to` candidate，由人工决定是否具有展示价值；审核也不能把它变为历史影响。

## 公开显示

`public_display=true` 需要：底层 Claim 至少 reviewed 且达到对应门槛、来源和说明可公开、无撤回记录、措辞匹配等级。争议边可展示，但必须显式显示争议与反证；不能以视觉弱化代替说明。

## 视觉规则

颜色=类型；实线/虚线/点线=A/B/C；透明度=evidence confidence；线宽只映射明确的 relationship strength。所有信息有文本/图标冗余。节点大小和空间距离不表示艺术地位或价值。

## QA 例

- 算法边具有 `explicitly_influenced_by` → 必须失败。
- `worked_in_same_place_period` 缺 time/place scope → 失败。
- C 级文案使用“直接影响” → 文案审核失败。
- `public_display=true` 但 Claim 未 reviewed → 发布失败。
