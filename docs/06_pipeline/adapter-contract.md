# Adapter contract

`museum_pipeline.adapters.base.SourceAdapter` 定义最小协议：

- identity：`source_id`、`adapter_name`、`adapter_version`、`contract_version`；
- boundary：`allowed_hosts`、source-specific object ID pattern、`supported_record_types`、`credential_requirements`；
- behavior：`build_request()`、`redact_request()`、`validate_response_contract()`、`extract_source_object_ids()`、`normalize()`、`map_license_rules()`、`extract_media_candidates()`、`detect_contract_drift()`。

Adapter 只接受 registry 固定 endpoint template 与显式 object ID，不接受用户 URL。它不能写 reviewed/release、下载媒体、自动 merge、创建艺术影响或绕过 canonical source/license registry。

## 请求门禁

1. 仅 `GET` 和 HTTPS；host、path、query name、port、fragment 均精确限制。
2. object ID 在插值前执行 source-specific full match。
3. AIC `fields` 只有一个，顺序与集合都必须精确等于 `default` 或 `description` profile；search/detail/query 变体不能复用错误 rule。
4. User-Agent 明确；无 Cookie persistence；当前四源无需凭据。
5. 每次 redirect 重新执行同一 adapter 的完整 request validation。

## 响应门禁

状态、content type、必需字段和已知字段类型先验证；只有 contract pass 才 normalize。未知字段进入 drift/quarantine，类型变化、缺失字段或 extra AIC field 失败。normalize 若仍产生 `contract_drift`，CLI 在写 candidate 前阻断。

`contract_version` 表示共享协议形状；`adapter_version` 在上游响应形态或映射逻辑改变时升级。2026-07-12 Getty live response 证明当前 per-record JSON 是 compacted Linked Art object，故 adapter 升为 0.1.1；旧 expanded JSON-LD 仅保持 fixture compatibility，不作为无声 XML/Web Service fallback。

## 扩展新来源

后续来源必须先进入 source comparison、endpoint registry、canonical license rules 和官方复核，再实现 adapter、valid/invalid/recorded fixtures 与离线 contract tests。空壳 adapter 不得标记 ready。
