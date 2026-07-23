---
phase_id: MUSEUM-09C
contract_id: MUSEUM-09C-WEB-00
contract_status: approved_for_local_execution
web_preflight_commit: e63557dd6addaf33bc639de9b5ce5e23bfb60d24
source_remote_main_before_web_docs: 73a9d397e9154271f478dceab7b058007a88a086
required_local_start: latest_origin_main_after_web_docs
batch_id: museum-09-batch-02
batch_input_closure_hash: sha256:02b962ad03917cac733f8be584c0f710f624f3039c04c869b92772bb31b2681d
input_release_id: release:art-expansion-batch-01-1.5.1
input_release_hash: sha256:1f9853b514ccc2312ce00a493d47a16acc72c95f6f5aff580b954ef530dff21b
planned_output_release_id: release:art-expansion-batch-02-1.6.0
single_main: true
branch_worktree_pr_allowed: false
pages_deploy_in_web_phase: false
museum_09d_authorized: false
arms_museum_authorized: false
---

# MUSEUM-09C｜本地Codex执行合同

## 1. 合同地位

本文件与`docs/qa/museum-09c/web-preflight-audit.md`共同构成MUSEUM-09C的网页端审计结果和本地执行边界。

本地Codex不得继续使用网页端审计前的`73a9d397e9154271f478dceab7b058007a88a086`作为可写baseline。它必须先同步包含本文件和web-preflight audit的最新`origin/main`，并把同步后的实际SHA记录为MUSEUM-09C baseline。

本文件授权：

- 修复Batch 01治理真源；
- 建立可复用的扩展批次工厂；
- 对Batch 02执行research、media、release和online closure；
- 创建并部署`release:art-expansion-batch-02-1.6.0`。

本文件不授权：

- MUSEUM-09D或Batch 03；
- Batch 03–10任何真实采集、审核或发布；
- 武器馆；
- 关闭OD-011；
- 重写历史release或Git历史。

## 2. 本地入场步骤

在`D:\ChatGPT-Codex-Projects\Museum-Codex`中：

```powershell
git fetch origin
git switch main
git pull --ff-only origin main
git status --porcelain=v2 --branch
```

随后读取并记录：

- `%USERPROFILE%\.codex\AGENTS.md`及SHA-256；
- `docs/qa/museum-09c/web-preflight-audit.md`；
- 本执行合同；
- local HEAD、origin/main、GitHub remote main；
- branch、worktree、stash；
- 当前1.5.1 release hashes；
- release integrity ledger；
- batch registry；
- M09A universe与Batch 02 closure；
- source cache/vault manifest。

只有以下条件均成立才允许写入：

- branch=`main`；
- local HEAD=origin/main=GitHub remote main；
- worktree安全；
- 没有来源不明待覆盖改动；
- Batch 02 closure可重算闭合；
- 1.5.1 hashes与ledger一致。

禁止：

- branch、worktree、PR；
- force push；
- history rewrite；
- `git reset --hard`；
- `git clean -fd/-xdf`；
- 删除来源不明文件。

## 3. Wave 0｜网页端证据回读与分类修复

### 3.1 回读网页端提交

确认两份文件存在于最新main：

- `docs/qa/museum-09c/web-preflight-audit.md`
- `docs/05_roadmap/museum-09c-execution-contract.md`

验证它们只包含执行证据，没有runtime或release bytes。

### 3.2 docs-only classifier缺口

当前CI contract只把`docs/qa/`、`docs/phase-reports/`和一个exact governance doc识别为docs-only。本合同路径尚未被classifier认可。

本地Codex必须：

1. 为本合同路径新增安全、最小的docs-only分类；
2. 首选`docs_only_exact`加入本文件，而不是无条件放行整个`docs/05_roadmap/`；
3. 新增classifier fixture；
4. 断言heavy jobs=0、browser=0、release rebuild=0、deploy=0；
5. 不把任意未知Markdown自动判为docs-only。

该修复属于CI治理影响闭包，必须targeted验证；不得因本文件已使用`[skip ci]`而忽略分类契约缺陷。

## 4. Wave 1｜Batch 01治理真源修复

### 4.1 正确终态

将`museum-09-batch-01`从错误的`media_bundle_ready`单向晋升为`published`，并绑定：

- formal candidate package；
- media bundle；
- initial public release 1.5.0；
- current UX successor 1.5.1；
- content/manifest/tree hashes；
- runtime commits `4097e5ffaaf7237777ee8b9d20dc682c317f5f44`与`51ca3ea9ffbd300e879336ca4322ec3a63bef72e`；
- deployments `5550987880`与`5559246553`；
- Batch contribution 50 artists / 488 artworks；
- current public total 62 / 532；
- current media、relationship、episode、tour与UX状态；
- online closure；
- `public_release_created=true`；
- `museum_09b_media_entered=true`；
- `museum_09b_release_entered=true`；
- `next_authorized_phase=null`或等价终态；
- `museum_09c_entered=false`，直到Batch 02事务正式开始。

### 4.2 状态机

增量扩展schema和validator以支持：

- `registered_not_started`
- `research_in_progress`
- `formal_candidate_ready`
- `media_bundle_ready`
- `published`
- `blocked`
- `withdrawn`

验证：

- 状态单向晋升；
- published必须绑定release/runtime/deployment/online closure；
- initial release与current successor可以不同；
- completed phase不得仍指向旧next phase；
- Batch 02–10 assignment与closure不变；
- Batch 01 sealed inputs和历史release bytes不变。

只运行governance targeted tests，不部署。

## 5. Wave 2｜参数化扩展批次工厂

建立通用入口，建议：

```powershell
python scripts/run_museum_expansion_batch.py --batch-id museum-09-batch-02 --stage research
python scripts/run_museum_expansion_batch.py --batch-id museum-09-batch-02 --stage media
python scripts/run_museum_expansion_batch.py --batch-id museum-09-batch-02 --stage release --release-id release:art-expansion-batch-02-1.6.0 --predecessor release:art-expansion-batch-01-1.5.1
```

允许`--through release`作为编排入口，但research、media、release必须保持独立事务manifest和可恢复边界。

### 5.1 工厂输入

从registry与M09A universe读取：

- batch ID；
- artist/work stable IDs；
- counts；
- Gallery/Collection tier；
- coverage delta；
- source set；
- input closure；
- reserve顺序；
- phase；
- predecessor；
- output version。

禁止在核心writer中硬编码Batch 01/02、50/488、49/485或1.5.x/1.6.0。

### 5.2 提取边界

可抽取通用能力：

- `global_expansion.py`的assignment/coverage/identity基础；
- M09B formal candidate的artist/artwork/source-drift/Claim→Evidence→Source；
- M09B-MEDIA的rights、download、content-address、derivatives、attribution/withdrawal；
- M09B-RELEASE的immutable overlay、slug、search、route、media materialization与ledger；
- M09B-UX-01的child narrative与relationship explorer合同。

必须保留：

- 旧脚本作为兼容wrapper或封存历史实现；
- 历史packages与release hashes；
- historical hash-only策略。

禁止复制一套新的Batch 02专用writer。

## 6. Wave 3｜Batch 02正式研究

规范输入：

- Batch ID：`museum-09-batch-02`
- artists：49
- artworks：485
- Gallery：12
- Collection：37
- closure：`sha256:02b962ad03917cac733f8be584c0f710f624f3039c04c869b92772bb31b2681d`
- coverage：Africa 3、East Asia 7、Europe 17、LAC 5、North America 7、Oceania 1、South Asia 4、Southeast Asia 3、West/Central Asia 2
- sources：AIC、Cleveland、Met、MIA、MoMA、NGS、NGA、Smithsonian、Tate

创建immutable candidate package，建议：

`data/reviewed/art/museum-09c/batch-02-formal-candidate-v1/`

### 6.1 Artist门禁

49位必须全部闭合：

- 真实个人；
- 确认已故；
- identity、duplicates、authority；
- source drift；
- names/aliases/transliterations/Chinese label status；
- dates/precision；
- coverage；
- practices；
- contexts；
- place-time；
- selected works；
- Claim→Evidence→Source；
- uncertainty、correction、withdrawal；
- status history。

living、unknown-death、non-person、duplicate、Wikidata-only formal target必须为0。

### 6.2 从研究源头生成儿童友好叙事

49/49直接生成：

- `public_intro`
- `look_for`
- `evidence_boundary`
- sentence-level provenance

主叙事要求：

- 中文2–3句，主要为55–120字；
- 英文2–4句，45–90 words；
- 回答人物、时间/地点、材料/实践和观察入口；
- 与媒体状态一致；
- 不幼儿化、不空泛赞美。

主叙事禁止：

- 元数据；
- 经审核声明；
- 可核验范围；
- source record；
- reviewed claim；
- 本次星海；
- 本公开档案支持；
- 价值排序式治理模板。

硬门禁：intro=49、provenance=49、banned jargon=0、duplicate intro=0、distinct signatures=49。

### 6.3 Tier门禁

Gallery 12：

- 8–15 works；
- 3–5 contexts；
- 至少3 episodes；
- 有证据才生成relationship candidates；
- gallery sequence与observation seeds；
- 不自动创建tour。

Collection 37：

- 至少3 works；
- 至少1 context；
- 至少1 episode；
- 允许0 relationship；
- 诚实Collection profile。

### 6.4 Artwork门禁

485件闭合：

- stable identity；
- artist attribution；
- title/language；
- date/precision；
- medium/material；
- dimensions；
- institution/accession；
- source URL/identity/license；
- duplicates；
- uncertainty；
- Claim→Evidence→Source；
- media feasibility input。

不从title、holding institution或模型常识推断creation place、主题意义或历史关系。

## 7. Wave 4｜Batch 02媒体

对485件逐对象分类：

- approved self-hosted；
- approved external IIIF link-only；
- approved external IIIF manifest-only；
- metadata-only after review；
- blocked source/rights/identity；
- no media available。

规则：availability≠permission，metadata license≠media license，general policy不自动覆盖object。

仅对self-hosted下载：

- original进入protected ignored vault；
- Git/public originals=0；
- 先与M03C和Batch 01进行SHA-256复用；
- partial/failed body不入vault；
- 单对象≤100MiB。

Derivatives复用canonical recipe：JPEG85、WebP82、320/640/960/1600、no crop、no upscale、sRGB、metadata stripped、no AI/content alteration。

创建immutable media package，建议：

`data/reviewed/art/museum-09c-media/batch-02-media-bundle-v1/`

必须有rights、quality、download、derivative、attribution、notice、withdrawal、content-address与build manifests。

## 8. Wave 5｜关系、地点与公共体验

### 8.1 关系语义

只允许正式C-level：shared subject/material/technique。

不得用计算相似创建边，不创造影响、师承或接触，不为每人凑关系。

每条关系记录means、does-not-mean、confidence、context、sources、endpoints与withdrawal。

### 8.2 Relationship explorer

必须原样继承1.5.1任务合同：

- default global nodes=0；
- starter≤9；
- focus≤13；
- expanded≤20；
- per lane≤4；
- theme≤16；
- path visual≤13；
- no circle；
- no all-node labels；
- DOM+SVG；
- label overlap=0；
- node overlap=0；
- 完整artist list、relationship table和Paths文字等价。

扩展到111 artists后也不得提高图形上限来承担“全部展示”。

### 8.3 Place-time与Tours

Episodes必须有来源，unknown保持null/list-only，不推断旅行路线，holding institution不等于creation/activity place。

Tours默认保持18。Gallery sequencing或hook不得自动晋升为tour。

## 9. Wave 6｜公开release 1.6.0

创建：

`release:art-expansion-batch-02-1.6.0`

predecessor：

`release:art-expansion-batch-01-1.5.1`

预期总量：

- artists=111；
- artworks=1,017；
- Gallery=36；
- Collection=75；
- tours=18；
- relationship、episode与media按实际正式结果记录。

必须：

- immutable overlay；
- predecessor byte-identical；
- historical rebuild=0；
- protected originals不入Git/public；
- derivatives按manifest materialize而不在release tree重复保存；
- search、index、profiles、1,017 artwork details、compare、relationship explorer、paths、map/timeline/list、rights/source、unknown/withdrawn、print/no-script完整闭合；
- current release只在全部门禁通过后切换。

## 10. 测试、CI与部署

### 10.1 开发期

只运行targeted waves：

- classifier与registry；
- generic factory；
- Batch 02 research/media/release；
- narratives；
- relationship explorer；
- search/routes/map/paths；
- rights/security/privacy/leakage；
- historical hash-only。

local full=0。

### 10.2 防止重复历史失败

在首次push前本地覆盖：

- ledger；
- Windows/Linux newline hashes；
- Python版本；
- historical hash-only；
-旧frontend headings/copy；
- path layout不依赖全局circle；
- browser route expectations；
- online verifier path/resolved_path兼容。

不得把可在本地targeted发现的旧断言漂移推给多次远端full。

### 10.3 Final-full

因为本阶段改变factory、registry、public runtime、release、media、search和Pages，最终运行一次GitHub clean final-full作为source of truth：

- clean install；
- full Python/frontend；
- all validators；
- production build；
- complete E2E；
- performance；
- Pages artifact/deploy；
- online byte closure；
- online functional smoke。

原则上accepted `github_final_full_gate_count=1`、runtime deployment=1。

失败后优先failed job rerun；代码修复时只跑影响闭包。禁止删测试、skip/xfail、放宽阈值或无差别重启完整流程。

Closeout必须docs-only并使用`[skip ci]`，deployment=0。

## 11. Mobile、a11y、低带宽、隐私与性能

覆盖7 viewports及新增Gallery/Collection、三类媒体、compare、search、relationship states、paths、map/list/timeline和dense rights/source。

要求：

- 44px targets；
- 200% reflow；
- no horizontal overflow；
- keyboard/visible focus/live regions；
- forced colors/reduced motion；
- low bandwidth/no script；
- automated serious/critical=0；
- real AT/device不可用时如实记录；
- no external runtime image；
- no unexpected preload；
- no analytics/query history/geolocation；
- CLS≤0.1；
- interaction p95≤150ms；
- desktop FTI≤1.8s；
- mobile FTI≤2.5s。

与数据量线性相关预算如需调整，必须提供公式、基线和无回归证据；不得任意放宽。

## 12. Registry推进

### Batch 01

保持`published`，current successor=1.5.1，不得倒退。

### Batch 02

形成可审计状态历史：

- research_in_progress；
- formal_candidate_ready；
- media_bundle_ready；
- published。

最终绑定candidate/media/release hashes、counts、media/relationship/episode、runtime、deployment与online closure；`next_authorized_phase=null`。

### Batch 03–10

保持`registered_not_started`，不得进入或改变assignment。

## 13. 验收门槛

`completed/pass`必须同时满足：

- Batch 01 truth repaired；
- classifier contract repaired；
- generic factory ready；
- Batch 02 closure匹配；
- 49 artists / 485 artworks；
- Gallery12 / Collection37；
- public totals111 / 1,017 / 36 / 75；
- living/unknown/non-person/duplicates/attribution conflicts=0；
- 49 child-facing intros；
- banned jargon=0；
- duplicate intro=0；
- provenance pass；
- media decisions485/485；
- public originals=0；
- relationship semantics pass；
- global graph nodes=0；
- overlap=0；
- search/routes/map/paths pass；
- tours保持18，除非新增tour有独立正式门禁；
- deterministic packages/release；
- candidate leakage=0；
- historical rebuild=0；
- accepted final-full=1；
- runtime deployment=1；
- closeout deployment=0；
- online byte/function closure；
- P0/P1/P2=0；
- local/origin/remote一致；
- worktree clean；
- Batch03–10未进入；
- M09D未进入；
- arms未进入；
- OD-011 open。

无法保持49/485或关键来源/权利无法闭合时，必须partial/blocked，不得伪造通过。

## 14. 提交与收口

建议实现提交：

`Phase MUSEUM-09C publish expansion batch 02 with reusable factory`

建议closeout：

`Close out Phase MUSEUM-09C online evidence [skip ci]`

最终报告：

`docs/phase-reports/phase-museum-09c-report.md`

最终验证：

- local HEAD=origin/main=GitHub remote main；
- branch=main；
- worktree clean；
- stash=0；
- single worktree；
- deployment exactly 1；
- closeout无Actions/deploy；
- M09D=false；
- arms=false；
- OD-011 open。

## 15. 本地Codex最终回复字段

至少列出：

1. 状态与耗时；
2. baseline/implementation/runtime/final commits；
3. Batch 01 registry修复；
4. classifier修复；
5. generic factory；
6. Batch 02 closure；
7. candidate/media/release hashes；
8. 49/485与111/1,017；
9. 36/75 profiles；
10. coverage/replacements/source drift；
11. child narratives、jargon、duplicates、provenance；
12. relationships/explorer/overlap；
13. episodes/map/tours；
14. media distribution、originals、derivatives、reuse；
15. deterministic builds；
16. targeted/full与所有Actions attempts；
17. deployment、Pages、online closure；
18. screenshots；
19. mobile/a11y/low-bandwidth/performance/privacy；
20. Reviewer A–H与P3；
21. storage cleanup；
22. main/origin/remote/worktree；
23. Batch03–10、M09D、arms、OD-011；
24. report path。
