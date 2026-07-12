# MUSEUM-02 A–E 对抗性审查

审查日期：2026-07-12。范围：`museum_pipeline/`、pipeline schemas/fixtures、source/rights registry binding、CI workflow、public/dist artifact。初审 finding 均在本阶段实际修复并增加回归测试；复审没有未解决 P0–P2。

## Findings 与修订

| ID | Reviewer | 初始级别 | Finding | 修订与复验证据 | 状态 |
|---|---|---:|---|---|---|
| A-01 | A 数据工程 | P1 | duplicate/304 事件只信任引用 manifest，未递归核对真实 body，损坏引用可能表面通过 | 引用同源解析、cycle 检测、真实 bytes/hash、snapshot ID hash suffix；损坏 body 不再复用；新增 tamper/304 tests | resolved |
| A-02 | A | P1 | run validator 只核对 artifact hash，未验证输出 record、raw snapshot 和 adapter snapshot ID 闭包 | physical validator 现验证 canonical record、raw physical snapshot、registry/rule hash、adapter 版本、input/output ID 与完整文件集合 | resolved |
| A-03 | A | P2 | Wikidata 年精度显示仍含 `00-00`，BCE year 比较丢失负号 | display 按 year/month/day precision 输出，source raw time 单独保留；BCE hard-conflict 测试 | resolved |
| B-01 | B 身份/艺术史 | P1 | strong ID 可能让 artwork 与 individual 产生 `same` | 任意已知 candidate kind 不同均形成 hard `identity_kind_mismatch` 并强制 `distinct` | resolved |
| B-02 | B | P2 | 初版只实现 ID/name/date，缺 script/transliteration、地点/时期、机构、馆藏和复制上游 lineage | 补齐全部 signal；`upstream_lineage_id` 防止复制页面被计为独立证据 | resolved |
| B-03 | B | P1 | `approve_same` 可指向错误 proposal，且可能覆盖 hard conflict | target/role/存在性校验；distinct/hard conflict 禁止 merge；同一批次冲突 decision 阻断 | resolved |
| B-04 | B | P2 | Getty activity/分类与未映射关系可能静默丢失或把 nationality 当 role | activity place/period 与 role/category 分开；关系/notes/contributor branches 进入 quarantine，不创建历史影响 | resolved |
| C-01 | C 来源/许可 | P1 | 初版 media candidate 没有 canonical media rule binding | media candidate 新增 `license_rule_id + content_class=media`，并验证 source/rule/class closure | resolved |
| C-02 | C | P1 | Field rule 只由 adapter 写入，validator 未回解 canonical registry；AIC 请求可用同名 query 绕过 exact profile | provenance/Claim/media 全部回解规则；AIC request 与 response final URL 双向绑定 exact ordered fields；description only CC BY | resolved |
| C-03 | C | P2 | Met constituents 被排除但未保留；图片/IIIF 提示缺少对象与数据许可隔离的物理检查 | constituent assertions 单独保留并有 provenance；Met/AIC/Wikidata media hints 始终 unknown/development-only，错误权利提示有 invalid fixture | resolved |
| C-04 | C | P2 | Recorded projection 与 live raw 的 hash 容易混淆 | 每源 manifest 同时记录 projection hash 和未提交 live raw snapshot/bytes/hash，notice 明示最小化；媒体 bytes=false | resolved |
| D-01 | D 安全/网络 | P1 | AIC 基类只限制 query name，任意字段集合/重复参数/顺序变体可通过 request gate | AIC override 要求唯一 fields 参数、精确 profile 与 detail path；search/extra/missing/reordered/duplicate tests | resolved |
| D-02 | D | P1 | DNS gate 未覆盖 100.64/10 等 `is_global=false` 地址 | 改为所有 non-global IP fail closed，并增加 shared-range test | resolved |
| D-03 | D | P1 | 上游可返回与请求 ID 不同的合法形状 response | 四个 adapter 均将 final URL object ID 与 response canonical ID 精确对账 | resolved |
| D-04 | D | P2 | CI 约定离线但没有进程级网络断言 | `run_offline_python_tests.py` 封锁 DNS/socket connect；workflow 改用该 runner | resolved |
| D-05 | D | P2 | safe path 未拒绝 canonical spelling 差异与 Windows reserved names | 拒绝 `//`、`./`、尾点、CON/PRN/AUX/NUL/COM/LPT、drive、反斜杠和 symlink root/component | resolved |
| E-01 | E 发布边界 | P1 | 原 Pages workflow 没有 pipeline/recorded contract 与 candidate leakage gates | build 前加 offline registry/pipeline/public scan，build 后加 dist scan；artifact 仍只上传 `dist` | resolved |
| E-02 | E | P2 | MUSEUM-01 报告只列首次成功 run，未解释最终证据 commit 的后续成功 run | 新增 append-only postscript，API/CLI 复核两个 run 的 build/deploy 均 success | resolved |
| E-03 | E | P2 | 技术探针/fixture 可能被误读为策展或公开内容 | manifests/notices/docs 全部 `curatorial_selection=false`；raw/intermediate ignored；public/dist 标识符与媒体扫描 | resolved |

## 复审结论

- Reviewer A：raw body、304/duplicate、跨平台 SHA-256、run closure 与确定性 normalized bytes 通过。
- Reviewer B：name-only 不 merge、跨类型/hard conflict 阻断、special identity 保留、merge 可逆通过；无艺术影响关系生成。
- Reviewer C：AIC exact-field、Getty ODC-BY、Met/IIIF no-inheritance、逐字段 provenance 与 recorded notices 通过。
- Reviewer D：SSRF/path/redirect/secret/retry/response limit/TLS/离线 CI 通过；无新增依赖。
- Reviewer E：无 raw/candidate/review/recorded/media 进入 public/dist；无真实艺术家/作品、首批名单或 MUSEUM-03 功能。

## Open P3

| ID | 原因 | 当前缓解 | Owner | 最晚复核 |
|---|---|---|---|---|
| A-P3 | append-only 由应用原子写入和 validator 保证，不是 OS WORM/ACL | 单用户本地目录、已存在 ID 拒绝、bytes/hash tamper 检测、Git ignore | data maintainer | MUSEUM-03 正式批次入口；若先出现多用户执行则提前 |
| D-P3 | 标准库 DNS 公网检查与实际 TLS socket 不是地址 pinning，系统代理也可能参与连接 | 仅固定官方 host/path、每跳复核、TLS hostname/CA、无用户 URL/凭据、单对象 live | security reviewer | 任何 credential/custom-host adapter 之前；最晚 MUSEUM-03 入口复核 |

两项均不允许弱化当前 fail-closed 门禁；若运行模型从单用户本地构建改变，必须先升级设计，不沿用本阶段假设。
