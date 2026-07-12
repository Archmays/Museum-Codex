---
phase_id: MUSEUM-02
status: completed
validation_status: pass
adapter_contracts_ready: true
reference_adapters:
  - wikidata
  - getty_ulan
  - met_open_access
  - aic_api
live_probe_status: pass
raw_snapshot_contract_ready: true
normalization_provenance_ready: true
identity_resolution_ready: true
review_workbench_contract_ready: true
candidate_data_publicly_exposed: false
public_media_added: false
pages_regression_status: pass
open_decisions_count: 9
museum_03_recommended: true
---

# MUSEUM-02 阶段报告

报告日期：2026-07-12（Asia/Shanghai）
项目根目录：`D:\ChatGPT-Codex-Projects\Museum-Codex`

## 1. 阶段目标

本阶段建立构建期、离线优先、fail-closed 的美术馆数据导入底座。交付范围包括四个参考 adapter、不可变原始快照、确定性规范化与逐字段 provenance、候选 Claim–Evidence–Source、可审核身份建议、可逆合并、本地 review bundle、字段级许可传播、录制契约样本、离线 CI 与 Pages 防泄漏门禁。

本阶段没有选择首批艺术家，没有批量采集，没有下载第三方媒体，没有创建正式 dataset release，也没有进入 MUSEUM-03。技术探针仅用于验证协议、字段、许可和漂移。

## 2. 起始 commit、Pages 与测试状态

- 起始 commit：`9a7f80b691ae95db7ba35150ed35af2abb138b2a`；开始时 `main`、`origin/main` 与远端 `main` 一致，工作区干净。
- Remote：`https://github.com/Archmays/Museum-Codex.git`。
- GitHub Pages 开始时与完成时均为 public、`build_type=workflow`、HTTPS enforced，公开地址为 `https://archmays.github.io/Museum-Codex/`。
- 在临时 worktree、新 Python 3.12 虚拟环境与全新 `npm ci` 环境中复核起始基线：16 个 schema、29 个治理 fixture（8 valid、21 expected-invalid）、44/44 Python 测试、20/20 前端测试均通过；production build 与线上四路由 smoke test 通过。
- 未删除、跳过或改写既有测试来推进本阶段。
- `skill/SKILL_INDEX.md` 不存在，因此没有虚构项目 skill；执行采用全局 `codex-quality-guard`，线上浏览器回归采用 `playwright`。

## 3. MUSEUM-01 postscript

追加式证据文件为 `docs/phase-reports/phase-museum-01-postscript.md`。GitHub API/CLI 复核结果：

- run `29155093901` 是首次成功部署证据，对应 commit `10ca328...`，build 与 deploy 均成功；
- run `29155301910` 是最终证据 commit `9a7f80b...` 后的成功部署，build 与 deploy 均成功；
- postscript 只补充两次成功 run 的时间关系，没有把 MUSEUM-01 当时未发生的能力写回旧报告，没有改变其 `completed/pass` 结论，也没有修改 MUSEUM-00 阶段报告。

## 4. 四个来源的当前官方复核

编码前重新检查官方接口、条款、许可、字段语义、限速和当前响应形状；没有用训练记忆替代当前接口核验。

| 来源 | 当前官方复核与实现结论 | Adapter 状态 |
|---|---|---|
| Wikidata | 使用官方 Special:EntityData JSON 读取显式 QID；保持 Tier 3 候选发现地位，保存 statement rank、qualifier 与 reference-presence；Commons 引用只形成 blocked media candidate。官方资料：`https://www.wikidata.org/wiki/Wikidata:Data_access`、`https://www.wikidata.org/wiki/Wikidata:Licensing`、`https://www.mediawiki.org/wiki/Wikimedia_APIs/Rate_limits`。 | `0.1.0`, contract/live PASS |
| Getty ULAN | 使用 `https://vocab.getty.edu/ulan/<id>.json` 的当前 Linked Art JSON；ODC Attribution 规则和 notice 进入逐字段 provenance。真实探针发现当前 compacted JSON 使用 `id` 而非旧 expanded `@id`，旧 raw 保留，adapter fail-closed 修订为 `0.1.1` 后重新探针通过；没有旧 XML/Web Service 静默 fallback。官方资料：`https://www.getty.edu/research/tools/vocabularies/obtain/`、`https://www.getty.edu/research/tools/vocabularies/lod/index.html`。 | `0.1.1`, contract/live PASS |
| The Met | 使用官方 object endpoint；分别保存 object 与 creator display 字段，不用显示名建立身份。OA/public-domain 标志只形成元数据/权利候选，图片 URL 不作为可发布媒体证明。官方资料：`https://metmuseum.github.io/`、`https://www.metmuseum.org/hubs/open-access`。 | `0.1.0`, contract/live PASS |
| Art Institute of Chicago | 使用 artwork detail endpoint 并强制显式、精确、有序的 `fields` profile；默认 CC0 profile 排除 `description`，需要 `description` 时绑定 CC BY 4.0 规则与 attribution；IIIF/image ID 不继承媒体许可。官方资料：`https://api.artic.edu/docs/`、`https://www.artic.edu/open-access/open-access-images`、`https://www.artic.edu/terms`。 | `0.1.0`, contract/live PASS |

MUSEUM-00 的许可结论没有因本次技术复核而发生语义变化。新增的是 MUSEUM-02 endpoint registry、精确 query/profile 约束和复核记录；对应 source registry/rule snapshot hash 已进入快照与测试。

## 5. Adapter 架构

`museum_pipeline.adapters.base.SourceAdapter` 规定并验证：`source_id`、adapter/contract version、allowlisted hosts、record types、credential requirements，以及 request/redaction/response contract/object IDs/normalize/license/media/drift 方法。四个 adapter 均为真实实现，不存在标记 ready 的空壳 adapter。

所有 endpoint 都由固定 adapter 和 `research/source-registry/pipeline-endpoint-registry.json` 派生。object ID 经过来源特定正则，最终 URL 的 host/path/query/profile 与 response object ID 都需闭合。Adapter 不能直接写 publishable 数据、自动 merge、下载媒体、创建历史关系或接受任意 URL。

## 6. 原始快照格式

`data/raw/<source>/<YYYY>/<MM>/<DD>/<timestamp>-<hash-prefix>/` 采用临时目录写入后原子 rename；目标已存在即失败。raw body 保持原始 bytes，不做 JSON 重排、Unicode 或换行转换；解析产物与 body 分离。

快照清单包含脱敏请求、canonical endpoint/query profile、credential alias、UTC 时间、adapter/version、registry/rule hashes、status/allowlisted headers/redirect chain/content type、bytes/SHA-256、body path、source object IDs、retry count、warnings/errors、terms verified date 与 run ID。路径验证阻断绝对路径、`..`、Windows drive/reserved name 和 symlink escape。

304 生成引用既有 body 的新 check event；相同 body 可形成新的 acquisition event，但通过 content hash 引用旧 body，不伪造成不同内容。递归 body-reference closure、循环、损坏被引用 body、snapshot ID hash 后缀和未来时间均 fail-closed。

## 7. Normalization 与逐字段 provenance

响应先成为 source record，再产生 `normalized_candidate`；不会直接成为确认艺术家。规范化输出使用 canonical JSON 和稳定排序，同输入、同版本产生相同 bytes。

重要字段记录 source/object/snapshot、JSON Pointer 或 RDF locator、raw/normalized value、transform ID/version/warnings、tier、license rule/content class、language/script、observed time、inferred 与 review state。未知字段进入 drift/quarantine；必需字段缺失或类型变化阻断候选写入，空值不会静默覆盖既有观察。

名称保留原文并做 Unicode 规范化，区分 preferred/alternate/historical/transliteration 和 BCP 47；日期保留 display、precision/range/circa/uncertain/calendar。年份不伪装为日精度，生晚于死及 living/deceased 冲突是 hard conflict；MUSEUM-02 不把候选 death date 自动提升为 `confirmed_deceased`。

## 8. Candidate Claim–Evidence–Source

规范化结果可产生 candidate Claim 与 Evidence；Evidence 精确指向 raw snapshot 和 source locator，Source 使用 canonical registry identity。Tier 3 高风险事实保持 candidate，复制自同一上游的记录保留共享 lineage，不计为独立证据。

冲突与反证以并列候选保存，不覆盖原观察。来源中的关系字段只作为 source assertion，不创建 `artist-relationship`；所有规则推断均标记 `inferred=true` 并保留规则版本。候选状态无通往 `published` 的自动路径。

## 9. Identity 与可逆 merge

ADR-0007 选择稳定随机内部 ID 用于真实运行、确定性 UUIDv5 用于 fixture；ID 与显示名称分离。source mapping、survivor 和 loser alias 持久化，loser ID 永不删除，merge record 支持逆向恢复。

匹配信号覆盖权威外部 ID、same-as、名称/别名、文字系统/转写、出生死亡范围、地点/时期、机构与作品/馆藏线索；跨 entity kind、日期矛盾和 living/deceased 矛盾生成 hard conflict。名称相同只是弱信号；name-only 永不自动产生 `same`，共享外部 ID 也只生成可审核 proposal，不执行无痕 merge。

Proposal 支持 `same`、`distinct`、`uncertain`，记录 signals、hard conflicts、source independence/lineage、rationale、输入 hashes、proposal version、generated_at 和 review status。anonymous、workshop、collective、traditional attribution、Master-of 与 uncertain attribution 保持原类型或进入人工队列，不强行转换为 publishable person artist。

## 10. Review workbench contract

本地 review bundle 包含候选记录、字段 provenance、冲突、身份 proposal、rights warnings、adapter drift、reviewer roles、精确输入 hashes 与 stale protection。它只写 ignored 本地数据区，不是 Pages 管理后台。

Decision 支持 `approve_same`、`approve_distinct`、`defer_uncertain`、`reject_bad_source_record`、`request_more_evidence`、`approve_field_mapping` 和 `reject_field_mapping`；记录 reviewer/role/time/rationale/input hashes/schema version/supersedes/status history。应用时重新计算 bundle、candidate、proposal 与 target hashes；任何变化都将旧 decision 标为 stale 并拒绝套用。hard conflict proposal 不可 `approve_same`，reviewer role 与 decision target 类型必须匹配。

本地 AIC 技术探针成功生成、验证 review bundle，`explain-field` 将候选 title 精确解析到 `/data/title` 与对应 license rule；测试 decision 应用未产生 publishable record，最终 run manifest physical closure 通过。

## 11. Source/rights mapping

- 每个 normalized field、candidate Claim 和 media candidate 绑定存在于 canonical registry snapshot 的 source rule、content class 与 source identity；snapshot 和 run 同时绑定 endpoint registry 与 license-rules content hash。
- AIC request/final URL/response 按 exact ordered fields profile 复核；缺字段、多字段、重排、重复、search endpoint、query 变体和错误 rule 均阻断。`description` 不能混入 CC0 profile。
- Getty ODC Attribution 与 AIC CC BY 内容必须有 notice/attribution；缺失即阻断 fixture 或字段映射。
- Met image URL、AIC IIIF/image ID、Wikidata Commons locator 都只产生 `rights_status=unknown`、`development_only=true`、`publishable=false` 的无字节 media candidate。
- API/元数据许可不继承到媒体，source-level CC0 不覆盖对象限制；revoked/denied/reverify overdue、scope mismatch、伪造 registry hash 或不存在 rule 均 fail-closed。
- OD-001 与 OD-002 保持未决，本阶段没有新增项目开放许可证。

## 12. Schemas 与 fixtures

新增 10 个 Draft 2020-12 pipeline schema：adapter contract、acquisition request、raw snapshot manifest、field provenance、normalized candidate、identity proposal、merge record、review decision、pipeline run、review bundle。全部具有稳定 `$id`，已登记到 `schemas/schema-manifest.json`，并由 entity type、branch 与 ID prefix 进行 concrete canonical dispatch，不能靠输入自报 schema 绕过。

Fixture 统计：

- recorded：4 组来源响应、12 个文件（每组 body、manifest、第三方 notice）；
- valid：14；
- expected-invalid：28；
- 原有 governance fixtures：29（8 valid、21 expected-invalid）。

四组 recorded response 均为最小、脱敏、可离线复现的官方 endpoint 响应投影，记录抓取日、许可 rule、projection body hash、对应 live raw hash/bytes 与第三方 notice；不含媒体字节，也不表达策展选择。

## 13. 测试结果

最终在新 Python 3.12 虚拟环境、重新安装固定依赖后执行：

```text
schemas: 26/26 PASS
governance fixtures: 29/29 PASS (8 valid, 21 expected-invalid)
source registry: 17 sources PASS
pipeline schemas/fixtures/contracts: 10 schemas, 14 valid, 28 expected-invalid, 4 recorded, 4 adapters PASS
Python tests: 139/139 PASS
network primitives during Python tests: disabled PASS
npm ci: 242 packages, 0 vulnerabilities
lint: PASS
typecheck: PASS
Vitest/RTL: 20/20 PASS
production build: PASS
dist: 4 files, 284,783 bytes
build/resource/public-leakage checks: PASS
```

覆盖的主要风险：adapter contracts、fake transport、timeout/retry/Retry-After/304、不可变写入、canonical JSON/raw bytes、Windows/Linux hash、Unicode/BCP 47、日期精度、provenance/source/license closure、身份信号/hard conflicts、可逆 merge、stale decision、CLI exit codes、secret redaction、response-size/redirect/SSRF 边界、offline CI 和 Pages 泄漏。

未用空洞的 coverage 百分比替代上述行为门禁。剩余 P3 限制见第 18 节。

## 14. Live probe 结果

所有 live probe 均由显式 `--live` 开启、并发 1、无凭据、无媒体下载，raw 写入被忽略的 `data/raw/`。Recorded fixture 没有被冒充为 live pass。

| Adapter / 技术对象 | HTTP / content type / bytes | Raw SHA-256 | 最终快照与结论 |
|---|---|---|---|
| Wikidata `Q42` | 200 / `application/json` / 309251 | `sha256:83e0be1eea4f43a9577d06d9845a25596814d1ea269ff24ac65d44b966d15fe6` | 最终 registry hash 绑定快照 `snapshot:wikidata:20260712t110948.631212z:83e0be1eea4f`；normalize/drift/run PASS |
| Getty ULAN `500115493` | 200 / JSON / 170122 | `sha256:6a6d7dedc0b40ebc8b7e888d618a25258348413a707a1b4ff5c7892604c05dd3` | 初次 contract drift 被阻断并保留；adapter `0.1.1` 修复后快照 `snapshot:getty_ulan:20260712t110303.846350z:6a6d7dedc0b4`；PASS |
| Met object `1` | 200 / `application/json` / 1665 | `sha256:a3fb36ebf2149f568cb8fe74f4feb439dc9519fcb6e8ab8c4d2cadeea249354d` | `snapshot:met_open_access:20260712t110309.278264z:a3fb36ebf214`；normalize/drift/run PASS |
| AIC object `27992` | 200 / `application/json` / 1077 | `sha256:bf1b7aaf1e9ddc33a860f35ae88c377d055d15342d102b1776b5dbb7624722f6` | `snapshot:aic_api:20260712t110315.181314z:bf1b7aaf1e9d`；exact-field rights、normalize/drift/run PASS |

技术对象只是探针，不是首批艺术家或作品候选。Getty 的真实漂移先被 contract 阻断，再按当前官方序列化修复并重新 live 验证，证明 fail-closed 路径有效。

## 15. CI 离线证明

`.github/workflows/deploy-pages.yml` 在 build 前依次执行 source/adapter registry、pipeline schema/fixture/recorded contract、public input scan 与 process-level offline Python tests；测试 runner 封锁 socket/DNS，并且 workflow 不包含 `--live`、不读取 API key。

build 后扫描 `dist` 的 candidate/raw/intermediate/review/source-record/QID/ULAN/probe/media 泄漏。Pages artifact 只上传 `dist`，不上传 raw snapshot、review bundle 或 recorded fixtures。

- run `29191794988`（commit `36f4ac6...`）失败：一个单元测试在 workflow build 前假定 `dist` 已存在。失败前所有 governance/pipeline/public-input 门禁均通过；deploy 被正确跳过。该失败没有隐藏或改写。
- commit `38f3ddae1d722d7e0eef4cde57d0c0140e21f6aa` 将 pre-build 单元测试限定到 `public`，仍由独立 post-build step 扫描 `dist`；删除本地 `dist` 后按 Actions 顺序重放，139/139、build 与 post-build scan 全部通过。
- run `29191872048`：head SHA `38f3ddae...`，build job `86647791345` 成功，deploy job `86647907206` 成功；所有离线 pipeline、Python、前端和泄漏步骤通过。

## 16. Pages 防泄漏与线上回归

成功部署后使用真实浏览器复核 `#/`、`#/art`、`#/about`、`#/accessibility` 四条路由；根 HTML、JS、CSS 与 favicon 均 HTTP 200，console 0 error/0 warning。DOM 与已加载资源扫描结果：

- candidate/source record/review/probe 标记：0；
- 技术探针名称、QID、ULAN ID：0；
- 第三方 raster/audio/video：0；
- JS/CSS 404：0；
- 现有门户占位、无正式艺术家/作品说明保持不变。

本阶段没有改动公开 UI，也没有把本地 pipeline 数据复制到 Pages。

## 17. 对抗性审查 findings

Reviewer A–E 的完整记录在 `docs/qa/museum-02/adversarial-review.md`。

| Reviewer | 主要发现 | 实际修订与结论 |
|---|---|---|
| A 数据工程 | body reference、重复内容、损坏引用、run closure 需要更强闭合 | 增加递归 reference/cycle/body-hash 校验、snapshot suffix、physical run validator；P0–P2 resolved |
| B 身份/艺术史 | name-only、source lineage、跨 kind 与 hard conflict 可能误合并 | 加入弱信号、lineage independence、entity-kind/date conflicts、无 auto merge、可逆 loser alias；P0–P2 resolved |
| C 来源/许可 | AIC 字段/profile、Getty attribution、Met/IIIF 媒体继承可绕过 | 精确 final URL/profile 与 rule closure、notice、blocked media candidate；P0–P2 resolved |
| D 安全/供应链 | SSRF、redirect、retry、response bomb、secret、CI 意外联网 | 固定 HTTPS allowlist、公网 DNS、受限 redirect/retry/size/timeouts、credential header 拒绝、offline runner；P0–P2 resolved |
| E 发布边界 | candidate/raw/review/fixture 或技术探针可能进入 artifact | pre/post-build 扫描、仅上传 dist、探针标记、线上资源/DOM 回归；P0–P2 resolved |

最终无未解决 P0、P1 或 P2。

## 18. 实际修订与剩余 P3

审查和真实探针触发的主要修订：Getty compacted Linked Art contract 更新并 bump adapter version；response ID 与 final URL 闭合；AIC exact ordered field profile；raw snapshot 递归引用闭合；run manifest physical closure；review target/role/stale/hard-conflict 门禁；process-level offline tests；更严格 public artifact scanner；Actions build 顺序修复。

保留两个已登记 P3：

1. 应用层 append-only 不是 WORM/防管理员篡改存储。Owner：data maintainer；原因：本阶段为单机构建工具。最晚在 MUSEUM-03 正式批次或多用户写入前复核。
2. DNS 公网预检不是 cryptographic IP pinning，系统代理仍属于部署环境信任边界。Owner：security reviewer；原因：四个固定无凭据官方 host 风险可控。最晚在引入凭据、自定义 host 或 MUSEUM-03 entry 前复核。

## 19. Git commits

- `36f4ac6145d5e442259151f28578083e3a3e82cc` — `Phase MUSEUM-02 art data ingestion pipeline foundation`：管线、schemas、fixtures、测试、CI、文档、ADRs、postscript 与 A–E 审查。
- `38f3ddae1d722d7e0eef4cde57d0c0140e21f6aa` — `Fix offline test ordering before Pages build`：修正 pre-build 测试对尚未生成 `dist` 的错误假设，保留独立 post-build dist scan。
- `5c630a50d9eecf6aa960dfb5fb5a2f51aa3db915` — `Close out Phase MUSEUM-02 evidence report`：阶段证据与 closeout 报告。
- 本文件的最终格式修订提交 — 去除 `git diff --check` 报告的 Markdown 行尾空格并补记报告提交；精确 hash 由最终 Git handoff 记录，避免在提交内容中制造自引用 hash。

未重写 `main` 历史，未覆盖已发布数据。

## 20. Remote 与工作区状态

报告撰写前：本地 `main`、`origin/main` 与 GitHub remote main 均为 `38f3ddae1d722d7e0eef4cde57d0c0140e21f6aa`，工作区干净。最终报告提交推送后需再次核对三方 hash、Actions、Pages 与工作区；最终回复记录该 closeout 证据。

`git ls-files` 确认 `data/raw/`、`data/intermediate/`、本地 review 数据与 `data/releases/` 均无本阶段新增 tracked 文件。只有脱敏、最小、带 notice 的 recorded fixtures 进入 Git；没有第三方媒体、token、cookie、授权原件或本地凭据。

## 21. 未决事项

开放决策共 9 项；MUSEUM-02 没有关闭 OD-001 或 OD-002，也没有以实现细节替代人工许可决定。两个 P3 是已知工程限制，不影响本阶段单机、固定 host、无凭据、无正式发布数据的验收，但必须在第 18 节期限前重新评估。

## 22. 风险

本阶段更新风险登记：upstream contract drift、raw snapshot immutability/closure、identity false merge、field/media rights inheritance、network/secret/public leakage。所有高风险路径均有 expected-invalid fixture 或单元测试；上游服务未来变化仍可能触发 fail-closed，需要通过新的显式 live probe 和 adapter version 修订处理，不能放宽 contract 以追求采集量。

## 23. 验收门槛结论

MUSEUM-02 标记 `completed/pass`。四个真实 adapter、离线 contract tests、至少一次真实 live response、不可变 raw bytes/hash/path、确定性 normalize、逐字段 provenance、identity same/distinct/uncertain、hard conflict、可逆 merge、stale review、AIC/Getty/Met/IIIF 许可边界、CI/Pages 防泄漏、A–E 审查与线上回归均通过。

没有正式 12 人名单、正式艺术家/作品 release、第三方媒体、候选数据公开、后端服务或 MUSEUM-03 功能。

## 24. MUSEUM-03 建议与明确输入条件

`museum_03_recommended: true` 只表示 MUSEUM-02 工具底座已达到可供下一阶段使用的条件，不等于授权进入 MUSEUM-03。只有用户另行明确授权且至少满足以下输入条件时，才可开始：

1. 明确的首批艺术家 selection framework、策展 reviewer 与人工确认流程；
2. 逐来源、逐字段、逐对象的权利审核能力和公开范围决定；
3. 使用本阶段 pipeline 重新采集，不把技术探针或 recorded fixture 当策展候选；
4. 对身份、死亡状态、作品归属、历史关系与 source independence 做 Claim–Evidence–Source 审核；
5. 在引入正式批次、凭据、自定义 host 或多用户写入前复核两个 P3；
6. 用户明确确认首批 12 人与可公开数据/媒体范围。
