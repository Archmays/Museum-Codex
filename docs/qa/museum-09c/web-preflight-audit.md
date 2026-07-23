---
phase_id: MUSEUM-09C-WEB-00
document_type: web_preflight_audit
status: completed
validation_status: pass
repository: Archmays/Museum-Codex
branch: main
audited_remote_main: 73a9d397e9154271f478dceab7b058007a88a086
audited_runtime_commit: 51ca3ea9ffbd300e879336ca4322ec3a63bef72e
current_release_id: release:art-expansion-batch-01-1.5.1
current_release_hash: sha256:1f9853b514ccc2312ce00a493d47a16acc72c95f6f5aff580b954ef530dff21b
current_release_manifest_sha256: sha256:5030b164d198260c588b1321881d8aa8c6467888d8f055cc0ba87ef67c9472f5
current_release_tree_sha256: sha256:88d09842e10d4d5b011e3b6cab8b979086983eb48e661779378b2b4a21b57fdc
batch_01_registry_drift_confirmed: true
batch_02_registered_not_started: true
branch_or_pr_conflict_found: false
runtime_changed: false
pages_deployed: false
museum_09c_entered: false
arms_museum_entered: false
---

# MUSEUM-09C-WEB-00｜网页端仓库预审

## 1. 结论

GitHub远端`main`在本次预审开始时精确为`73a9d397e9154271f478dceab7b058007a88a086`，提交信息为`Close out Phase MUSEUM-09B-UX-01 online evidence [skip ci]`。没有发现MUSEUM-09C提交、开放PR或以MUSEUM-09C命名的功能分支。

当前部署runtime为`51ca3ea9ffbd300e879336ca4322ec3a63bef72e`。当前公开release为`release:art-expansion-batch-01-1.5.1`，其封存身份为：

- content：`sha256:1f9853b514ccc2312ce00a493d47a16acc72c95f6f5aff580b954ef530dff21b`
- manifest：`sha256:5030b164d198260c588b1321881d8aa8c6467888d8f055cc0ba87ef67c9472f5`
- physical tree：`sha256:88d09842e10d4d5b011e3b6cab8b979086983eb48e661779378b2b4a21b57fdc`

本次网页端只创建审计和执行合同，不修改registry、schema、validator、workflow、runtime、release或Pages。

## 2. 已核验的公开真源

### 2.1 Batch 01初始公开release

`release:art-expansion-batch-01-1.5.0`由MUSEUM-09B-RELEASE发布，predecessor为`release:art-v1-candidate-1.4.0`：

- content：`sha256:364dffe96d35b16ba2ffdc6395cb28793411bd8be3bd3e89fad8cdc85036b6c9`
- manifest：`sha256:7b03506242135a885ddf2c5b00bf284155e6d6b673c63440c001d56a008f60f9`
- tree：`sha256:9dd52292a39a72fd5cec81bd4833fb55dbfe182443a86da431dfc64fe0ed948f`
- deployed runtime：`4097e5ffaaf7237777ee8b9d20dc682c317f5f44`
- Pages deployment：`5550987880`
- public scope：62 artists / 532 artworks / 24 Gallery / 38 Collection

### 2.2 当前UX successor

MUSEUM-09B-UX-01创建并部署`release:art-expansion-batch-01-1.5.1`：

- predecessor：`release:art-expansion-batch-01-1.5.0`
- content：`sha256:1f9853b514ccc2312ce00a493d47a16acc72c95f6f5aff580b954ef530dff21b`
- manifest：`sha256:5030b164d198260c588b1321881d8aa8c6467888d8f055cc0ba87ef67c9472f5`
- tree：`sha256:88d09842e10d4d5b011e3b6cab8b979086983eb48e661779378b2b4a21b57fdc`
- deployed runtime：`51ca3ea9ffbd300e879336ca4322ec3a63bef72e`
- Pages deployment：`5559246553`
- public scope保持：62 artists / 532 artworks / 60 relationships / 110 place-time episodes / 18 tours
- 关系探索合同：默认全局图0节点，starter≤9，focus≤13，expanded≤20，每lane≤4，theme≤16，path≤13
- 62/62艺术家已有中英文`public_intro`、`look_for`、`evidence_boundary`和逐句provenance

release integrity ledger以1.5.1为`current_release_id`，历史release默认`hash_only`，且只在builder、validator、input、schema、source/rights或release bytes改变时局部重建。

## 3. Batch 01治理漂移

`governance/museum-09-batch-registry.json`目前仍记录：

- `status=media_bundle_ready`
- `public_release_created=false`
- `museum_09b_release_entered=false`
- `next_authorized_phase=MUSEUM-09B-RELEASE`
- `deployment_count=0`

这些字段与MUSEUM-09B-RELEASE、MUSEUM-09B-UX-01、release ledger、1.5.0/1.5.1 manifests、Pages和online closure相冲突。

### 3.1 正确终态判定

本地Codex必须把Batch 01的canonical状态单向晋升为`published`，并至少绑定：

- formal candidate package ID/content/tree；
- media bundle ID/content/tree；
- initial public release 1.5.0的ID/content/manifest/tree；
- current public successor 1.5.1的ID/content/manifest/tree；
- initial runtime与current runtime；
- deployment IDs `5550987880`与`5559246553`；
- Batch 01贡献50 artists / 488 artworks；
- 当前公开总量62 / 532；
- 40件新增self-hosted、25件external-link-only、423件新增metadata-only；
- Batch 01 relationship、episode与UX successor状态；
- `public_release_created=true`；
- `museum_09b_media_entered=true`；
- `museum_09b_release_entered=true`；
- `next_authorized_phase=null`或等价终态；
- `museum_09c_entered=false`，直到Batch 02正式开始。

Batch 01的stable assignment、sealed candidate/media packages、1.5.0和1.5.1 bytes不得改写。

## 4. Batch 02规范输入

Batch 02目前仍为`registered_not_started`，未发现提前执行痕迹。规范输入为：

- ID：`museum-09-batch-02`
- planned phase：`MUSEUM-09C`
- sequence：2
- artist count：49
- artwork count：485
- Gallery：12
- Collection：37
- input closure：`sha256:02b962ad03917cac733f8be584c0f710f624f3039c04c869b92772bb31b2681d`
- coverage delta：Africa 3、East Asia 7、Europe 17、Latin America and Caribbean 5、North America 7、Oceania 1、South Asia 4、Southeast Asia 3、West and Central Asia 2
- source set：AIC、Cleveland、Met、MIA、MoMA、National Gallery Singapore、NGA、Smithsonian、Tate
- replacement：仅在hard-gate失败时按M09A ordered reserve确定性执行

Batch 03–10必须保持`registered_not_started`，其stable IDs、works、coverage、source set和closure hashes不得因M09C改变。

## 5. 可复用能力与缺口

### 5.1 可直接复用

- M09A universe、stable assignment、coverage、reserve和source cache；
- M09B identity/deceased/dedupe、artist/artwork、Claim→Evidence→Source与source-drift能力；
- M09B-MEDIA对象级权利、protected originals、content addressing、responsive derivatives、attribution/withdrawal能力；
- M09B-RELEASE immutable overlay、slug、search、routes、media materialization、ledger与online verifier能力；
- M09B-UX-01任务导向relationship explorer和儿童友好叙事硬门禁；
- M08 changed-path classifier、四级CI、historical hash-only和single-writer规则。

### 5.2 必须增量扩展

- batch registry状态机及published证据字段；
- 通用、参数化的batch runner/factory；
- research/media/release三个独立事务manifest；
- 通用release版本、predecessor、counts、source set与batch identity输入；
- 从研究阶段直接生成儿童友好叙事，而不是发布后补救；
- 111/1,017规模下的search、routes、relationship explorer、paths、map和性能验证；
- Batch 02 candidate/media/release/online evidence。

### 5.3 不应在M09C修改

- M03C媒体；
- M09A reviewed universe与Batch assignments；
- Batch 01 sealed candidate/media packages；
- 1.5.0与1.5.1历史release bytes；
- Batch 03–10 assignments；
- 18条既有tours，除非新tour另有完整正式证据；
- 武器馆与OD-011。

### 5.4 留给后续批次

- Batch 03–10真实研究、媒体和发布；
- M09D及以后阶段；
- 武器馆范围。

## 6. Changed-path与CI审计

当前`governance/ci-impact-contract.json`把以下路径识别为docs-only：

- `docs/phase-reports/`
- `docs/qa/`
- exact `docs/00_project/ci-execution-governance.md`

`docs/05_roadmap/museum-09c-execution-contract.md`目前不在docs-only allowlist。因本次提交使用`[skip ci]`，网页端不会触发Actions或Pages；但本地Codex必须在M09C开始时评估并用targeted classifier fixtures修复这项分类缺口。推荐只把本执行合同的exact path加入docs-only exact list，或建立经测试的安全roadmap-doc规则，避免把可能影响运行时的未知文档路径一概放行。

本次两份文档均为纯文本执行证据，不修改runtime/public/release/schema/tests/workflow。

## 7. 网页端与本地Codex边界

网页端已完成：

- GitHub main核验；
- commit与阶段证据对照；
- release/ledger核验；
- Batch 01 drift判定；
- Batch 02输入固定；
- affected-scope与factory边界设计；
- 执行合同固化。

本地Codex负责：

- 同步本网页端提交后的最新main；
- 读取Windows全局AGENTS.md与本地ignored source vault；
- 修复registry/schema/validator/classifier；
- 提取并测试batch factory；
- 执行Batch 02 research/media/release；
- 运行targeted gates、唯一最终full gate、Pages与online closure；
- 完成storage cleanup和Git clean。

## 8. 禁止事项

- 不在网页版修改registry、schema、runtime或release；
- 不创建branch、worktree或PR；
- 不重建历史release；
- 不提前进入Batch 02；
- 不进入M09D或武器馆；
- 不把Batch 01 registry旧状态当作真实发布状态；
- 不把release/phase证据静默改写去迎合旧registry；
- 不因本次纯文档提交部署Pages。
