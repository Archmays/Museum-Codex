# Museum / 博物馆

**公开访问：<https://archmays.github.io/Museum-Codex/>**

Museum 是一个以可追溯知识图谱为骨架、以数字博物馆为界面的长期知识项目。它用展览、关系、时间、地点和可解释路径帮助用户探索，而不是复制百科条目或建立无来源图片库。

当前线上门户仍保持 `MUSEUM-03B` 基线；`MUSEUM-04` 尚未正式发布。仓库当前包含本地、非公开的艺术星海 `0.1.0` reviewed candidate：12 位艺术家、44 件作品 metadata、31 个共享语境与 36 条 C 级策展比较，并实现图形、艺术家列表和关系表三种等价任务路径。该 candidate 不含作品图片或其他媒体字节，不含 A/B 关系、历史因果边或算法相似；在 12 份双语艺术家简介获得具名人工编辑审核前，formal public release、main push 与 Pages 部署均由硬门禁阻止。武器博物馆（`arms` / `Museum of Arms & Armor`）仍仅为可见、不可点击的筹备入口，没有正式路由或数据契约；离线导入、候选和审核原始资料不进入公开构建。

## 不可妥协的规则

- 可发布事实按 `Entity → Claim → Evidence → Source` 追溯。
- 算法相似、策展比较、历史语境和直接历史关系使用不同语义与视觉编码。
- 网站消费版本化静态数据；外部 API 失败不得使已发布内容不可浏览。
- 元数据许可与媒体许可分开记录；`rights_status=unknown` 或 `development_only=true` 的媒体不能进入公开构建。
- 美术馆正式艺术家实体只接受已确认去世的个人；匿名作者、工作室、群体和传统归属使用专门归属表达。
- AI 只能产生候选、草稿或冲突提示，不能成为事实的唯一来源。

## 权利与署名

自 2026-07-14 起，项目原创代码以及原创策展文字、翻译、关系解释、UI 文案和原创设计均为 `ALL-RIGHTS-RESERVED`。公开仓库/source visibility 不构成开源或开放内容授权；本仓库保持无项目级 `LICENSE`。第三方依赖、metadata 与 media 继续适用各自独立许可、限制、notices 和 attribution，项目权利声明不覆盖这些义务。完整范围见 [`RIGHTS.md`](RIGHTS.md) 与公开 [About & Rights](https://archmays.github.io/Museum-Codex/#/about) 页面。

权利、署名、更正或撤回问题可提交 [Rights or attribution request](https://github.com/Archmays/Museum-Codex/issues/new?template=rights-or-attribution.yml)。请勿在公开 Issue 提交身份证件、合同、授权原件、地址、电话或其他敏感证明；需要时由维护者安排非公开渠道。响应、隔离、new-release withdrawal、缓存、replacement 与恢复流程见 [`docs/02_governance/rights-request-and-takedown-procedure.md`](docs/02_governance/rights-request-and-takedown-procedure.md)。MUSEUM-04 candidate 的限定范围为 metadata-only，不包含作品媒体字节；这不表示 formal public release 已获人工批准。

## 验证

支持 Python `3.11–3.13`；本阶段在 Python `3.12.7` 验证。干净 checkout 先建立虚拟环境并安装固定治理依赖：

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
```

```powershell
python scripts/validate_governance_foundation.py
python scripts/validate_source_registry.py
python scripts/validate_publishable_media_rights.py fixtures/governance/valid
python scripts/validate_governance_foundation.py --release-root fixtures/release-bundles/valid/minimal
python -m museum_pipeline verify-sources --json
python scripts/validate_pipeline_foundation.py
python scripts/validate_museum_03b_batch.py data/reviewed/art/museum-03b/museum-03b-first-slate-v1/package-v1
python scripts/validate_museum_04_issue_form.py
python scripts/build_museum_04_release.py
python scripts/validate_museum_04_release.py
python scripts/validate_museum_04_fixtures.py
python scripts/scan_public_artifact_for_candidate_data.py public --label-set data/reviewed/art/museum-03b/museum-03b-first-slate-v1/package-v1/public-leakage-label-set.json
python scripts/run_offline_python_tests.py
npm ci
npm run check
node scripts/verify-museum-04-budgets.mjs
python scripts/validate_museum_04_performance_evidence.py
npm run test:e2e
python scripts/scan_public_artifact_for_candidate_data.py dist --label-set data/reviewed/art/museum-03b/museum-03b-first-slate-v1/package-v1/public-leakage-label-set.json
```

正式提升与 Pages workflow 另行执行 `python scripts/validate_museum_04_release.py --require-public`；当前 reviewed candidate 会按设计以 `m04_human_editorial_review_required` 失败，直至具名人工审核被绑定并重新验证。

验证器区分 schema/fixture 自测与实际 release bundle：后者会核验 canonical schema 分派、精确文件集合、字节数、SHA-256、类型化 ID、完整引用闭包、稳定 Source rule ID/快照、许可决策、zero-media 边界、notices 和 attribution 的实际 JSON 内容。阶段结果见 [`docs/phase-reports/phase-museum-04-report.md`](docs/phase-reports/phase-museum-04-report.md)。

## 目录

- `docs/00_project`：立项、边界和第一性原理
- `docs/01_architecture`：领域、图谱、数据发布与 ADR
- `docs/02_governance`：证据、来源、版权、AI 和审核
- `docs/03_art_museum`：美术馆产品、关系语义与交互规则
- `docs/04_biology_museum`：生物馆研究边界
- `docs/06_arms_museum`：武器博物馆章程、安全政策、模型与未来研究路线
- `docs/06_pipeline`：MUSEUM-02 离线采集与审核管线契约
- `research/source-registry`：当前官方来源核验记录
- `schemas` / `fixtures` / `scripts` / `tests`：机器可执行治理契约
- `governance`：机器可读许可决策注册表；OD-001/OD-002 为 `decided / ALL-RIGHTS-RESERVED`
- `data`：本地采集、审核和版本化发布区的边界说明
