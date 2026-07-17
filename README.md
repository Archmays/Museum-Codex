# Museum / 博物馆

**公开访问：<https://archmays.github.io/Museum-Codex/>**

Museum 是一个以可追溯知识图谱为骨架、以数字博物馆为界面的长期知识项目。它用展览、关系、时间、地点和可解释路径帮助用户探索，而不是复制百科条目或建立无来源图片库。

当前正式 overlay 为 `release:art-time-place-1.3.0`，继承 `release:art-pathways-1.2.0`：12 位艺术家、44 件作品、23 个 verified place identities、36 条 artist place-time episodes、2 个独立 current-holding records，以及完全自托管的 Natural Earth 1:110m land/coastline/lakes GeoJSON。`#/art/map` 提供共享状态的地图、时间线和地点表；不使用外部 tile、token、在线 geocoder、用户位置、analytics、访问历史、现代政治边界或推断旅行路线。31 件作品继续使用 MUSEUM-03C 已批准的 242 个本地响应式衍生文件，其余 13 件保持明确无图状态；本阶段不重新生成媒体。

## 不可妥协的规则

- 可发布事实按 `Entity → Claim → Evidence → Source` 追溯。
- 算法相似、策展比较、历史语境和直接历史关系使用不同语义与视觉编码。
- 网站消费版本化静态数据；外部 API 失败不得使已发布内容不可浏览。
- 元数据许可与媒体许可分开记录；`rights_status=unknown` 或 `development_only=true` 的媒体不能进入公开构建。
- 美术馆正式艺术家实体只接受已确认去世的个人；匿名作者、工作室、群体和传统归属使用专门归属表达。
- AI 只能产生候选、草稿或冲突提示，不能成为事实的唯一来源。

## 权利与署名

自 2026-07-14 起，项目原创代码以及原创策展文字、翻译、关系解释、UI 文案和原创设计均为 `ALL-RIGHTS-RESERVED`。公开仓库/source visibility 不构成开源或开放内容授权；本仓库保持无项目级 `LICENSE`。第三方依赖、metadata 与 media 继续适用各自独立许可、限制、notices 和 attribution，项目权利声明不覆盖这些义务。完整范围见 [`RIGHTS.md`](RIGHTS.md) 与公开 [About & Rights](https://archmays.github.io/Museum-Codex/#/about) 页面。

权利、署名、更正或撤回问题可提交 [Rights or attribution request](https://github.com/Archmays/Museum-Codex/issues/new?template=rights-or-attribution.yml)。请勿在公开 Issue 提交身份证件、合同、授权原件、地址、电话或其他敏感证明；需要时由维护者安排非公开渠道。响应、隔离、new-release withdrawal、缓存、replacement 与恢复流程见 [`docs/02_governance/rights-request-and-takedown-procedure.md`](docs/02_governance/rights-request-and-takedown-procedure.md)。每个公开媒体文件都绑定 MUSEUM-03C parent hash、衍生 hash、许可规则、署名、notice 与 withdrawal 行；metadata-only 或 blocked 作品的媒体集合必须为空。

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
python scripts/validate_museum_07_release.py public/releases/art-time-place-1.3.0
npm run test:e2e
node scripts/verify-museum-07-budgets.mjs
python scripts/scan_public_artifact_for_candidate_data.py dist --label-set data/reviewed/art/museum-03b/museum-03b-first-slate-v1/package-v1/public-leakage-label-set.json
```

`release:art-time-place-1.3.0` 由 automated release validation pipeline 完成来源、权利、引用、字节与 hash 交叉验证，`human_review_dependency=false`，不伪造或等待逐项人工审核。底图只包含自然地理轮廓；现代地图轮廓不等于历史政治边界，时间顺序不等于旅行路线，current holding institution 不等于作品创作地。

验证器区分 schema/fixture 自测与实际 release bundle：后者会核验 canonical schema 分派、精确文件集合、字节数、SHA-256、类型化 ID、完整引用闭包、MUSEUM-03C exact projection、父子媒体链、稳定 Source rule ID/快照、许可决策、blocked/no-image 边界、notices、attribution 与 withdrawal 的实际 JSON 内容。阶段结果见 [`docs/phase-reports/phase-museum-04-report.md`](docs/phase-reports/phase-museum-04-report.md)。

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
