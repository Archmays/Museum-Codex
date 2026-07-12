# MUSEUM-03A 私有候选包与公开边界

## 私有工件

真实候选、作品、外部身份 ID、关系线索、scenario、推荐组合、备选、source snapshots、review log、handoff 与 decision template 只允许写入：

`data/review/curation/museum-03a/<bundle-id>/`

Live raw 只允许写入 `data/raw/`。两者均由 `.gitignore` 阻断，不得进入 Git、`public/`、`dist/` 或 Pages artifact。

每个 bundle 必须包含候选池、合格池、作品权利预审、关系 leads、A/B/C scenario、Recommended、备选、用户 handoff、pending decision template、source snapshots、review log 和 manifest。Manifest 对每个非 manifest 文件记录 safe POSIX path、content role、bytes 与 SHA-256；实际文件集合必须精确相等。候选/作品/lead/scenario/备选/decision 引用必须闭合，source IDs 必须解析，任何 hash/bytes 变化触发 stale。Symlink、path escape、未登记文件和媒体后缀均失败。

## 公开仓库可交付

允许提交 curation schemas、synthetic fixtures、验证器/CLI、通用方法、非姓名化统计、对抗性审查、路线拆分、风险和阶段报告。Synthetic fixture 必须显著使用虚构身份，不得冒充批准名单。

不得提交真实候选姓名清单、QID/ULAN、作品清单、relation leads、推荐 slate、用户 handoff/decision、live raw、review bundle 或任何第三方媒体。CI 不执行 live research，不读取 private bundle，只验证公开 contract 和 synthetic negative cases。

## 泄漏门禁

- `git ls-files` 检查 raw/intermediate/review/staging 零跟踪；
- `public` / `dist` 扫描 candidate/snapshot/review IDs、QID、ULAN、技术探针、候选目录和第三方媒体；
- 本地 final QA 额外从 ignored bundle 提取 preferred labels/aliases，与 `public` / `dist` 做逐词泄漏扫描；
- workflow 只上传 `dist`，不上传仓库根目录或 fixtures；
- selection bundle 出现 raster/audio/video/3D 后缀即 fail closed；
- 页面保持七馆门户、美术馆空序厅、武器馆不可点击，不新增真实艺术家/作品/媒体。

MUSEUM-03A `completed` 只说明确认包准备完毕；不等于 `MUSEUM-03 completed`、`OD-004 closed`、`OD-007 closed` 或获得进入 MUSEUM-03B 的授权。
