# ADR-0009：字段级与对象级许可传播

- Status: accepted; implemented in MUSEUM-02
- Date: 2026-07-12

## Context

同一 API 内字段许可可能不同；metadata/data/媒体也不能互相继承。AIC `description` 与其他 artwork data 是直接的字段级差异，Met 图片 URL 和 IIIF 可达性都不是媒体许可。

## Decision

每个 field provenance 和 candidate Claim 必须绑定 canonical `source_id + license_rule_id + content_class`；每个 media candidate 也必须绑定 media rule，但 MUSEUM-02 强制 `rights_status=unknown`、`development_only=true`、`publish_status=blocked`、`bytes_downloaded=false`。validator 将 rule ID 回解到 canonical registry，核对来源和内容类别；AIC 进一步按 raw locator 强制 `description → CC BY 4.0`、其余批准字段 → CC0，并要求请求字段集合精确匹配批准 profile。

Getty ULAN 数据绑定 ODC-BY rule，署名模板通过 rule 闭包和 fixture notice 保留。Wikidata Commons filename、Met `primaryImage`、AIC `image_id`/IIIF 仅形成 locator/hint，不继承父记录许可。对象级公版标志只提高后续 rights review 的候选价值，不在本阶段产生 publishable media。

## Alternatives

- 只记录 source-level license：无法表达 AIC 字段差异或媒体例外。
- 把许可字符串复制到每个字段：容易漂移，无法验证 canonical rule identity。
- 根据 API/IIIF 可访问性推断许可：错误且不可审计。

## Consequences

provenance 记录更大，但字段可精确解释，规则变更可通过 snapshot hash 和稳定 rule ID 找到受影响消费者。任何未匹配、类别错配、字段 profile 绕过或署名缺失均 fail closed。

## Revisit when

引入书面授权覆盖、复杂组合许可或正式媒体导入时，追加许可决策实体；不得弱化现有 no-inheritance 规则。
