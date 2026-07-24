---
phase_id: MUSEUM-09D-WAVE-01
contract_id: MUSEUM-09D-WAVE-01-WEB-00
contract_status: approved_for_local_execution
web_preflight_commit: e289e4e12af33cae4cd45097e54b56102800fd38
source_remote_main_before_web_docs: 7f23d2598dce99205e7a373f3ac3bcbaf4471e1b
required_local_start: latest_origin_main_after_web_docs
batch_ids:
  - museum-09-batch-03
  - museum-09-batch-04
  - museum-09-batch-05
input_release_id: release:art-expansion-batch-02-1.6.0
planned_release_ids:
  - release:art-expansion-batch-03-1.7.0
  - release:art-expansion-batch-04-1.8.0
  - release:art-expansion-batch-05-1.9.0
planned_final_artist_count: 258
planned_final_artwork_count: 2471
planned_final_gallery_count: 71
planned_final_collection_count: 187
single_main: true
branch_worktree_pr_allowed: false
intermediate_pages_deploy_allowed: false
final_pages_deploy_count: 1
museum_09g_authorized: false
batch_06_authorized: false
arms_museum_authorized: false
---

# MUSEUM-09D-WAVE-01｜本地 Codex 执行合同

## 1. 合同地位

本文件、`docs/qa/museum-09d-wave-01/web-preflight-audit.md` 与 `docs/01_architecture/adr/ADR-0012-multi-batch-wave-release-and-single-deployment.md` 共同构成 Batch 03–05 多批次 wave 的网页端审核结果和本地执行边界。

本地 Codex 不得继续使用 `7f23d2598dce99205e7a373f3ac3bcbaf4471e1b` 作为可写 baseline。必须先同步包含三份网页端文件的最新 `origin/main`，并将同步后的实际 SHA 记录为 MUSEUM-09D-WAVE-01 baseline。

本合同授权：

- 将单批次工厂升级为 phase-agnostic、wave-aware V2；
- 顺序处理 Batch 03、04、05 的 research、media、release；
- 创建 1.7.0、1.8.0、1.9.0 三个 immutable releases；
- 只将 1.9.0 部署到 Pages；
- 对最终 258 artists / 2,471 artworks 运行完整线上闭包；
- 完成后将 Batch 03–05 标记为 published。

本合同不授权：

- Batch 06 或 MUSEUM-09G；
- Batch 07–10；
- 武器馆；
- 关闭 OD-011；
- 改写历史 release 或 Git 历史；
- 中间 1.7.0/1.8.0 Pages deployment；
- 把失败或 partial batch 标记为 published。

## 2. 本地入场协议

在 `D:\ChatGPT-Codex-Projects\Museum-Codex` 中：

1. 读取真实 `%USERPROFILE%\.codex\AGENTS.md`。
2. 执行：

```powershell
git fetch origin
git switch main
git pull --ff-only origin main
```

3. 记录并比较：
   - local HEAD
   - origin/main
   - GitHub remote main
   - branch
   - `git status --porcelain=v2 --branch`
   - `git stash list`
   - `git worktree list`
4. 三方 main 必须一致；只允许 main、一个 worktree、stash=0、worktree clean。
5. 若出现来源不明改动，不覆盖、不删除；无法归属时停止写入。
6. 核验当前 1.6.0 content/manifest/tree、ledger、Batch 01/02 published 状态及 Batch 03–05 closure。
7. 核验网页端三份文档存在，且内容与最终 main 一致。

禁止：branch、worktree、PR、force push、history rewrite、`git reset --hard`、`git clean -fd/-xdf`。

## 3. 固定 Batch 输入

### Batch 03

- ID：`museum-09-batch-03`
- artists/artworks：49/485
- Gallery/Collection：12/37
- closure：`sha256:2f401a1fbf6d8f9d7f773b11c54b6c7c388c8d3a47725c9bedd3af7f13bf528d`
- output release：`release:art-expansion-batch-03-1.7.0`
- predecessor：`release:art-expansion-batch-02-1.6.0`

### Batch 04

- ID：`museum-09-batch-04`
- artists/artworks：49/485
- Gallery/Collection：12/37
- closure：`sha256:81e07ced806a68819a6fa300cefff2f0ae9e89f8dfb95ae31ed82fde379c4ee0`
- output release：`release:art-expansion-batch-04-1.8.0`
- predecessor：`release:art-expansion-batch-03-1.7.0`

### Batch 05

- ID：`museum-09-batch-05`
- artists/artworks：49/484
- Gallery/Collection：11/38
- closure：`sha256:1983735d38fa32b3666e401ef1144ae58ce119b4fe5072d71893535e105d0527`
- output release：`release:art-expansion-batch-05-1.9.0`
- predecessor：`release:art-expansion-batch-04-1.8.0`

不得更改 assignment。只有 documented hard-gate failure 才可按 canonical ordered reserve 确定性替换；替换必须保持批次人数、作品数、tier与coverage边界，无法保持则该批次 partial/blocked，不发布 wave。

## 4. Wave 总体事务模型

一个总任务，三个顺序 batch transaction。每个 batch 独立形成：

1. formal candidate package
2. media bundle
3. immutable release
4. validation summary
5. deterministic rebuild evidence
6. registry state history

全局另形成：

- wave plan
- transaction journal
- resume cursor
- predecessor chain manifest
- cross-batch dedupe report
- final deployment binding
- online closure

只有 Batch 03、04、05 全部通过，才允许切换 current release 与部署 1.9.0。

若 Batch 04/05 失败：

- 已成功的内部 package/release 可保留为 tracked immutable evidence；
- 不部署；
- current runtime 继续 1.6.0；
- 失败批次不标记 published；
- 修复后从失败 transaction resume；
- 不重做前序已闭合 transaction。

## 5. Factory V2 硬要求

建立建议入口：

```powershell
python scripts/run_museum_expansion_wave.py `
  --phase-id MUSEUM-09D-WAVE-01 `
  --batch-ids museum-09-batch-03,museum-09-batch-04,museum-09-batch-05 `
  --release-plan docs/05_roadmap/museum-09d-wave-01/release-plan.json `
  --through release
```

必须支持：

- `--dry-run`
- `--resume`
- `--from-batch`
- `--from-stage`
- `--journal`
- `--no-deploy`
- 每批 research/media/release 独立事务
- 原子输出与临时路径隔离
- stable input hash
- per-batch checkpoint
-失败闭包与resume
- predecessor chain验证
- final-release-only deployment marker

V2不得在通用 writer 中硬编码：

- MUSEUM-09C/M09D/M09E/M09F
- Batch 03/04/05
- 49/485/484
- 1.7.0/1.8.0/1.9.0
- fixed date/time
- source-specific phase分支
- reviewer ID
- authorization scope

这些均来自 execution context、registry、release plan 或CLI。

保留 V1 与历史脚本作为兼容 wrapper；不删除、不改写 sealed evidence，不为证明兼容性而重建历史 release。

## 6. Research 事务合同

每批必须精确处理 fixed artists/works，并闭合：

- stable identity
- deceased verification
- duplicate clusters
- aliases/transliterations/Chinese label status
- official source identities
- Claim → Evidence → Source
- contexts
- place-time episodes
- artwork identity/attribution/title/date/material/institution
- correction/withdrawal
- source drift by stable ID/content hash
- hard-gate replacement ledger

Living、unknown-death、non-person、duplicate artist、duplicate artwork、attribution conflict target必须为0。

### 6.1 儿童友好叙事内建

新增147位艺术家必须直接生成：

- bilingual `public_intro`
- `look_for`
- `evidence_boundary`
- sentence-level provenance

硬门禁：

- count=147
- banned governance jargon=0
- duplicate full intro=0
- distinct signatures=147
-事实范围与source一致
-不创造影响、师承、排名、意图或敏感身份
- self-hosted/external/metadata-only提示与实际媒体状态一致

主叙事禁止使用“元数据、经审核声明、可核验范围、发布记录、本次星海、本公开档案支持、不据此断言”等治理模板。技术边界保留在 evidence层。

## 7. Media 事务合同

每件作品逐对象分类，不预设为 metadata-only：

- approved_self_hosted
- approved_external_iiif_link_only
- approved_external_iiif_manifest_only
- metadata_only_after_media_review
- blocked_rights/source/identity
- no_media_available

规则：

- availability≠permission
- metadata license≠media license
- general policy不自动覆盖object
- 无法证明时metadata-only或blocked
- originals只进入protected ignored vault
- Git/public originals=0
- 先按SHA-256对照M03C、Batch01、后续wave cache
- duplicate bytes复用
- bounded retry
- partial body不入vault
- no screenshot、no AI、no crop、no upscale、no watermark removal

Derivative recipe继续JPEG85/WebP82、320/640/960/1600、sRGB、metadata stripped。输入未变时redownload=0、reencode=0。

## 8. Relationship、place、tour与UX合同

正式关系仅允许有证据的 C-level：

- shared subject
- shared material
- shared technique

每条包含 means / does-not-mean / evidence / endpoint / source / withdrawal。不得用计算相似补边，不强制凑关系，不创造影响或师承。

Relationship explorer在258位规模仍保持：

- global default=0节点
- starter≤9
- focus initial≤13
- expanded≤20
- per lane≤4
- theme≤16
- path≤13
- DOM+SVG
- no circle layout
- no all-node label render
- label overlap=0
- node overlap=0
-完整artist list与relationship table
-完整A–B path文字等价

Place-time不得推断坐标、旅行路线或把holding当creation/activity place。Tours默认保持18；候选hook/sequence不得自动晋升。

## 9. Release 与部署合同

依次创建：

- 1.7.0：tracked immutable，不部署
- 1.8.0：tracked immutable，不部署
- 1.9.0：tracked immutable，唯一待部署release

历史与predecessor只hash-only，不重建。三release均更新ledger并验证byte-identical、manifest/content/tree、reference closure与rollback。

预期最终规模：

- artists=258
- artworks=2,471
- Gallery=71
- Collection=187

Relationship、episode、media数量由实际正式证据决定，不预造数。Tours除非正式新增且完整闭合，否则=18。

## 10. Cross-batch 完整性

最终对全部公开总体运行：

- artist/work dedupe
- stable ID与slug/alias collision
- cross-batch identity与attribution
- Claim/Evidence/Source references
- source/rule/rights closure
- media SHA reuse
- withdrawal/replacement
- relationship endpoints
- place identities
- search shards
- route inventory
- candidate leakage
- public originals=0
- predecessor chain
- registry monotonicity

## 11. CI 与测试

开发阶段：

- targeted waves
- local full=0
- historical hash-only
-失败后只重跑失败项和依赖闭包
-不连续push小修
-最多2个本地checkpoint

Push前必须本地预检此前常见漂移：

- ledger
- LF/CRLF evidence hash
- Python compatibility
- schema lifecycle
- historical successor fixtures
- frontend headings/copy
- relationship/path layout
- classifier exact docs paths
- online verifier predecessor references

三批与runtime全部闭合后，执行唯一接受的GitHub clean final-full：全Python、全frontend、全Playwright、build、source/rights/security/privacy/leakage、performance、artifact binding、Pages upload/deploy、online byte closure、functional smoke。

原则上：

- accepted final-full=1
- runtime deployment=1
- intermediate deployment=0
- closeout deployment=0

失败时记录attempt；优先failed-job rerun。需代码修复则只重跑affected closure，最后重新取得唯一clean accepted full。不得删测试、skip/xfail、降低阈值或force push。

## 12. Mobile、a11y、低带宽、性能与隐私

至少覆盖7个既有viewport及：artist index、新Gallery/Collection、三种媒体、compare、search、relationship starter/focus/expanded/theme/table、paths、map/list/timeline、dense rights/source。

硬要求：

- 44px controls
- 200% reflow
- keyboard/focus/live regions
- forced colors/reduced motion
- low bandwidth/no-script
- serious/critical=0
- no external runtime image request
- no unexpected preload
- analytics/query history/geolocation=0
- CLS≤0.1
- interaction p95≤150ms
- desktop FTI≤1.8s
- controlled mobile FTI≤2.5s

数据规模线性预算只能基于公式和证据调整，不得任意放宽。

## 13. Registry 最终状态

完成后：

- Batch01/02保持published
- Batch03=published，绑定candidate/media/1.7.0
- Batch04=published，绑定candidate/media/1.8.0
- Batch05=published，绑定candidate/media/1.9.0/runtime/deployment/online closure
- Batch06–10保持registered_not_started
- current release=1.9.0
- next authorized phase=null

状态历史必须单调。中间阶段可记录research_in_progress/formal_candidate_ready/media_bundle_ready，但未完成不得published。

## 14. Git、收口与存储

始终只用main。建议实现提交：

`Phase MUSEUM-09D-WAVE-01 publish expansion batches 03-05`

最终closeout：

`Close out Phase MUSEUM-09D-WAVE-01 online evidence [skip ci]`

closeout前后验证：

- local=origin=remote main
- worktree clean
- stash=0
- single worktree
- closeout check-runs=0
- closeout deployment=0

保留packages、releases、journal、source snapshots、protected originals、schemas/tests、screenshots、CI/online evidence。删除partial bodies、retry scratch、staging DB、temp unsharded output、dist/output/tmp、无用traces与可重建cache。受保护输入删除=0，报告文件数与bytes。

## 15. 阶段报告与验收

创建 `docs/phase-reports/phase-museum-09d-wave-01-report.md`，至少记录：

- baseline/implementation/runtime/final SHA
- Factory V2与journal/resume tests
- Batch03/04/05 assignment、closure、replacement、source drift
- candidate/media/release IDs与hashes
- 147/1,454增量和258/2,471总量
- Gallery71/Collection187
- child narratives/provenance/jargon/duplicate
- relationship/place/tour/media totals
- deterministic builds与cross-batch checks
- targeted/full/Actions attempts
- unique deployment与online closure
- screenshots/mobile/a11y/performance/privacy
- Reviewer A–H、P0/P1/P2/P3
- storage与Git clean
- Batch06–10/M09G/arms边界

只有所有硬门禁满足才可 `completed/pass`。任何批次无法保持固定数量、身份、来源或权利闭包时，必须partial/blocked且不得部署。
