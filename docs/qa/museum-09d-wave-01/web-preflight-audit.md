---
phase_id: MUSEUM-09D-WAVE-01-WEB-00
document_type: web_preflight_audit
status: completed
validation_status: pass
repository: Archmays/Museum-Codex
branch: main
audited_remote_main: 7f23d2598dce99205e7a373f3ac3bcbaf4471e1b
audited_runtime_commit: a116556bb03b076e9bbf5d3357df6a55c998bea1
current_release_id: release:art-expansion-batch-02-1.6.0
current_release_hash: sha256:266d8b655182dab60ee82a472a6937c99976e28d74afee402180f1d566c0ea71
current_release_manifest_sha256: sha256:3fe1613d9c1f969cb31294132f995b3147aae648fa762c5c4b772c460e859c4f
current_release_tree_sha256: sha256:d1ed04f15eec22f241b55ab0915d6876f7788f63ea27249ace3d2ddc4028842c
batch_03_status: registered_not_started
batch_04_status: registered_not_started
batch_05_status: registered_not_started
batch_03_artist_count: 49
batch_03_artwork_count: 485
batch_04_artist_count: 49
batch_04_artwork_count: 485
batch_05_artist_count: 49
batch_05_artwork_count: 484
planned_new_artist_count: 147
planned_new_artwork_count: 1454
planned_public_artist_count: 258
planned_public_artwork_count: 2471
planned_public_gallery_count: 71
planned_public_collection_count: 187
branch_or_pr_conflict_found: false
runtime_changed: false
pages_deployed: false
museum_09d_entered: false
arms_museum_entered: false
---

# MUSEUM-09D-WAVE-01-WEB-00｜Batch 03–05 网页端预审

## 1. 结论

GitHub 远端 `main` 在本次预审开始时精确为 `7f23d2598dce99205e7a373f3ac3bcbaf4471e1b`，提交信息为 `Close out Phase MUSEUM-09C online evidence [skip ci]`。没有发现 MUSEUM-09D 命名的功能分支、开放或关闭 PR，也没有发现 Batch 03–05 已进入真实执行的代码、release 或阶段报告。

当前部署 runtime 为 `a116556bb03b076e9bbf5d3357df6a55c998bea1`。当前公开 release 为 `release:art-expansion-batch-02-1.6.0`：

- content：`sha256:266d8b655182dab60ee82a472a6937c99976e28d74afee402180f1d566c0ea71`
- manifest：`sha256:3fe1613d9c1f969cb31294132f995b3147aae648fa762c5c4b772c460e859c4f`
- physical tree：`sha256:d1ed04f15eec22f241b55ab0915d6876f7788f63ea27249ace3d2ddc4028842c`

当前公开规模为 111 artists / 1,017 artworks / 36 Gallery / 75 Collection。Batch 01 与 Batch 02 均为 `published`；Batch 03–10 均保持 `registered_not_started`。

本次网页端只创建审计、执行合同与 ADR，不修改 registry、schema、validator、workflow、runtime、release 或 Pages。

## 2. Canonical Batch 03–05 输入

以下值来自 `governance/museum-09-batch-registry.json` 的固定 assignment，不得由本地执行者重新挑选。

### 2.1 Batch 03

- ID：`museum-09-batch-03`
- planned phase：`MUSEUM-09D`
- status：`registered_not_started`
- artists：49
- artworks：485
- Gallery / Collection：12 / 37
- input closure：`sha256:2f401a1fbf6d8f9d7f773b11c54b6c7c388c8d3a47725c9bedd3af7f13bf528d`
- coverage delta：Africa 3；East Asia 6；Europe 16；Latin America and Caribbean 7；North America 6；Oceania 1；South Asia 3；Southeast Asia 4；West and Central Asia 3
- source set：AIC、Cleveland、Cooper Hewitt、Met、MoMA、National Gallery Singapore、NGA、Tate

### 2.2 Batch 04

- ID：`museum-09-batch-04`
- planned phase：`MUSEUM-09E`
- status：`registered_not_started`
- artists：49
- artworks：485
- Gallery / Collection：12 / 37
- input closure：`sha256:81e07ced806a68819a6fa300cefff2f0ae9e89f8dfb95ae31ed82fde379c4ee0`
- coverage delta：Africa 3；East Asia 6；Europe 16；Latin America and Caribbean 5；North America 7；Oceania 2；South Asia 3；Southeast Asia 3；West and Central Asia 4
- source set：AIC、Cleveland、Cooper Hewitt、Met、MIA、MoMA、National Gallery Singapore、NGA、Tate、V&A

### 2.3 Batch 05

- ID：`museum-09-batch-05`
- planned phase：`MUSEUM-09F`
- status：`registered_not_started`
- artists：49
- artworks：484
- Gallery / Collection：**11 / 38**
- input closure：`sha256:1983735d38fa32b3666e401ef1144ae58ce119b4fe5072d71893535e105d0527`
- coverage delta：Africa 4；East Asia 6；Europe 17；Latin America and Caribbean 6；North America 7；Oceania 1；South Asia 2；Southeast Asia 4；West and Central Asia 2
- source set：AIC、Cleveland、Cooper Hewitt、Met、MIA、MoMA、National Gallery Singapore、NGA、Smithsonian、Tate、V&A

### 2.4 组合闭包

三批次固定合计：

- new artists：147
- new artworks：1,454
- new Gallery：35
- new Collection：112

在无 hard-gate replacement 且全部成功发布时，公开总量应为：

- artists：258
- artworks：2,471
- Gallery：71
- Collection：187

此前规划阶段的 `72 Gallery / 186 Collection` 只是按每批 12/37 的粗略推算，已被 canonical registry 纠正；本地执行必须使用 71/187，不得沿用旧估算。

## 3. 工厂 V1 审计

M09C 已建立 `scripts/run_museum_expansion_batch.py` 与 `museum_pipeline/art/expansion_batch_factory.py`。其优点：

- research、media、release 三事务分离；
- batch assignment、计数、tier、source set 与 closure 来自 registry；
- release ID/version 由 CLI 输入；
- 单批次可 `--through release`；
- 可记录 online closeout；
- Batch 01/02 已证明 deterministic 与 predecessor overlay 可行。

但 V1 尚不适合作为三个批次的长期 wave orchestrator：

1. CLI 只有单个 `--batch-id`，没有 wave plan、resume journal、per-batch checkpoint 或多 release 链编排。
2. `BUILD_AT=2026-07-23T12:00:00+08:00`、`REVIEW_DATE=2026-07-23` 为固定值。
3. claim/evidence 的 `phase_id`、applicability scope、reviewer 与 summary 文案仍写死 `MUSEUM-09C`。
4. source binding 对 Smithsonian 与其他 source 使用特定 M09C/M09B scope 分支，不是通用 execution context。
5. source rules 的 `applies_to` 与 pattern 写死 M09C public release records。
6. V1 没有跨批次 dry-run、事务 journal、resume、rollback-before-runtime-switch 或 final-release-only deployment contract。
7. V1 需要证明 Batch 03–05 中一个失败时不会把前一批误标为 published、不会切换 runtime，也不会重做已完成批次。
8. M09C 中 Batch 02 全部媒体最终为 metadata-only；V2 不能把该结果当作后续批次的预设，必须逐对象执行权利与媒体决策。

## 4. Release 链判定

采用以下不可变 predecessor 链：

1. `release:art-expansion-batch-03-1.7.0`，predecessor `release:art-expansion-batch-02-1.6.0`
2. `release:art-expansion-batch-04-1.8.0`，predecessor `release:art-expansion-batch-03-1.7.0`
3. `release:art-expansion-batch-05-1.9.0`，predecessor `release:art-expansion-batch-04-1.8.0`

1.7.0 与 1.8.0 必须形成完整、可回滚、可 hash-only 验证的 tracked immutable releases，但不得触发 Pages deployment。只有 1.9.0 可以成为 current release，并在三批全部成功后触发唯一正式 final-full 与唯一 Pages deployment。

任何中间失败必须保持当前线上 runtime 仍为 1.6.0；不能公开半完成 wave。

## 5. 内容与体验合同

新增 147 位艺术家从 research 开始就必须生成：

- bilingual `public_intro`
- `look_for`
- `evidence_boundary`
- sentence-level Claim → Evidence → Source provenance

禁止把治理模板放进儿童主叙事；不得在发布后另开 UX 修复阶段补救。

关系探索继续继承 1.5.1/1.6.0 合同：

- default global graph node count=0
- starter≤9
- focus initial≤13
- expanded≤20
- per lane≤4
- theme≤16
- path visual≤13
- DOM+SVG；不依赖 WebGL
- no circle layout
- no all-node label rendering
- label overlap=0；node overlap=0
- 完整发现由 artist index、search、list、relationship table 与 paths 承担

正式边只能来自有证据的 C-level shared subject/material/technique；不得通过计算相似补边，不强制为艺术家凑关系。

## 6. CI、部署与阶段边界

网页端文件必须使用 `[skip ci]`；不得运行重型 CI 或部署。当前 classifier 尚未授权本次三个新文档的 exact docs-only path；本地 Codex 必须以 exact-path fixtures 增量加入，未知 descendant 继续 fail closed。

本地开发使用 targeted waves、historical hash-only、local full=0。只有三批 packages/releases 与受影响 runtime 全部闭合后，才运行唯一接受的 GitHub clean final-full 和唯一 Pages deployment。

MUSEUM-09G/Batch 06、Batch 07–10、武器馆及 OD-011 均不在本合同授权范围。

## 7. 网页端职责边界

网页端已完成：

- 当前 main/release/runtime 真源核验；
- Batch 03–05 固定输入核验；
- Gallery/Collection 总量纠错；
- 工厂 V1 非通用项审计；
-三 release 单部署方案；
-内容、UX、CI 与失败恢复合同。

网页端不执行：

- Windows 本地同步；
- registry/schema/workflow/code 修改；
- source cache/original vault 访问；
- research/media/release build；
-测试、final-full、Pages或线上验证。
