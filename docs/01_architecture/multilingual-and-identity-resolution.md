# 多语言与身份消歧

## 名称模型

实体使用稳定、非语言化 ID；`labels` 和 `aliases` 以 BCP 47 标签记录，例如 `zh-Hans`、`zh-Hant`、`en`、`fr`。每个名称记录文字、类型（preferred/alternate/historical/transliteration）、语言/文字系统、来源 Claim 和适用时间。ID 不由当前英文名生成后再随改名变化。

界面回退顺序由 locale 配置定义，例如 `zh-Hans → zh → en → source-language`，并向用户标注回退。人写策展文字按 locale 独立审核；机器翻译只生成草稿，不覆盖原文或继承已审核状态。

## 身份解析流程

1. 规范化空白、标点和 Unicode，但保存原始字符串。
2. 优先匹配权威外部 ID；名称只是候选信号。
3. 比对出生/死亡、活动地点/时间、机构、作品和来源。
4. 生成 `same / distinct / uncertain` merge proposal 及特征说明。
5. 高风险实体由学科审核者确认，记录 survivor 与 alias 映射。

同名不合并；不同文字系统名称也不自动拆分。外部来源互相复制不视为独立证据。

## 艺术家门槛

正式 `artist` 需要：确认死亡、可靠出生和死亡 Claim、至少一个可核验作品或正式艺术史记录、明确身份/别名映射。死亡不明者停留候选；在世者不进入美术馆正式发布数据。

古代匿名、工作室或群体创作采用受控 creator attribution；“Master of …”等约定称谓可有稳定非个人身份实体，但不能填入虚假的法定姓名、出生或死亡日期。

## 地点和时间身份

地点 ID 与名称、行政边界和几何版本分开；历史地点允许多个时段名称与父级关系。时间支持精度（day/month/year/decade/century/range）、约数和 open interval。多语显示不能提高底层日期精度。

## 搜索

构建期为每个 locale 生成带 preferred label、alias、transliteration、分馆、类型和受控关键词的静态索引。排名因素可解释且不改变实体权威性；搜索命中回退/别名时显示匹配原因。正式内容不依赖第三方搜索服务。
