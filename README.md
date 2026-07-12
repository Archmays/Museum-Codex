# Museum / 博物馆

**公开访问：<https://archmays.github.io/Museum-Codex/>**

Museum 是一个以可追溯知识图谱为骨架、以数字博物馆为界面的长期知识项目。它用展览、关系、时间、地点和可解释路径帮助用户探索，而不是复制百科条目或建立无来源图片库。

当前 `MUSEUM-02A` 公开门户包含七个分馆入口卡片、美术馆序厅、关于与权利、无障碍与低带宽页面，以及中英文切换。新增的武器博物馆（`arms` / `Museum of Arms & Armor`）仅为可见、不可点击的筹备入口，尚无正式路由或数据契约。`MUSEUM-02` 的离线导入与审核管线仍只服务获准的本地候选流程；当前公开版本**不包含正式艺术家、艺术作品、武器器物数据或第三方馆藏资产**。

## 不可妥协的规则

- 可发布事实按 `Entity → Claim → Evidence → Source` 追溯。
- 算法相似、策展比较、历史语境和直接历史关系使用不同语义与视觉编码。
- 网站消费版本化静态数据；外部 API 失败不得使已发布内容不可浏览。
- 元数据许可与媒体许可分开记录；`rights_status=unknown` 或 `development_only=true` 的媒体不能进入公开构建。
- 美术馆正式艺术家实体只接受已确认去世的个人；匿名作者、工作室、群体和传统归属使用专门归属表达。
- AI 只能产生候选、草稿或冲突提示，不能成为事实的唯一来源。

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
python scripts/scan_public_artifact_for_candidate_data.py public
python scripts/run_offline_python_tests.py
npm ci
npm run check
python scripts/scan_public_artifact_for_candidate_data.py dist
```

验证器区分 schema/fixture 自测与实际 release bundle：后者会核验 canonical schema 分派、精确文件集合、字节数、SHA-256、类型化 ID、完整引用闭包、稳定 Source rule ID/快照、许可决策、自托管媒体字节、notices 和 attribution 的实际 JSON 内容。测试通过不代表任何真实内容已经获准发布。阶段结果见 [`docs/phase-reports/phase-museum-00-report.md`](docs/phase-reports/phase-museum-00-report.md)。

## 目录

- `docs/00_project`：立项、边界和第一性原理
- `docs/01_architecture`：领域、图谱、数据发布与 ADR
- `docs/02_governance`：证据、来源、版权、AI 和审核
- `docs/03_art_museum`：美术馆 MVP 规划（不含实现）
- `docs/04_biology_museum`：生物馆研究边界
- `docs/06_arms_museum`：武器博物馆章程、安全政策、模型与未来研究路线
- `docs/06_pipeline`：MUSEUM-02 离线采集与审核管线契约
- `research/source-registry`：当前官方来源核验记录
- `schemas` / `fixtures` / `scripts` / `tests`：机器可执行治理契约
- `governance`：机器可读许可决策注册表；OD-001/OD-002 保持 pending
- `data`：本地采集、审核和版本化发布区的边界说明
