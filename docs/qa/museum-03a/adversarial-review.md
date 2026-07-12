# MUSEUM-03A 对抗性审查

审查对象包括公开 curation contracts、synthetic fixtures/CLI/CI、ignored live raw/review bundle 和非姓名化组合统计。真实候选姓名、外部 ID、作品清单和推荐组合不写入本文件。

## Reviewer A｜艺术史与身份

- 发现：一个东亚版画候选的 Getty ULAN 同一记录中，结构化生卒与 biography/其他来源线索相差约一个世纪。若只验证字段“存在”会错误通过硬门槛。
- 修订：用现有 Getty adapter 对 24 位合格候选的 final raw bytes 重放 life observations；冲突候选退出合格池，保留 research queue、反证和 adapter/data-quality gap；由另一位有权威身份与官方对象记录的候选按明确小配额理由补位。
- 结论：Tier 3 未承担死亡/身份最终证明；特殊身份未转个人；关系措辞仍为待核验 lead。P0–P2 resolved。

## Reviewer B｜策展、公平与全球视野

- 发现：v1 的 Scenario A/B 只有 6 位达到 4 条清晰媒体路径，Scenario B 只有 3 个历史区段；部分场景差异不足。
- 修订：v5 的 A/B/C/Recommended 均为 12 个唯一合格 ID、6 个地区/传统计数、4 个历史区段、3 位女性、11 类媒介/材料、8 位有 4 条清晰路径；A/B 与 C 的候选和目标不同，Recommended 可审查地与 C 接近。
- 发现：西方机构 API 与英语发现仍影响宽池；开放图片对非西方/近现代候选不均。
- 修订：保留 42 位宽池、24 位合格池、8 个逐人小配额理由、8 个带损益的替换方案；不以图片数或 adapter 排除候选，不声称代表完整艺术史。P0–P2 resolved。

## Reviewer C｜版权、媒体与公开范围

- 发现：The Met policy page 首次 live request 返回 429；AIC/Met 的 `image_id`、IIIF、image URL 与 `is_public_domain` 单字段均可能被误读为许可。
- 修订：429 后不重试、不回退镜像；对象 record hash 绑定 2026-07-11/12 canonical source-license snapshot。Schema/semantics 强制 metadata/media 分离、object-level evidence、no inheritance、`bytes_downloaded=false` 和 `*_candidate` 状态。AIC clear path 使用 exact detail response + canonical object media rule；其余降级 metadata-only。
- 四个 OD-007 选项已比较；代理建议 mixed + metadata-first default，但 OD-007 保持 open。无媒体下载。P0–P2 resolved。

## Reviewer D｜数据、身份解析与可复现性

- 发现：最初中断的临时 survey 使用确定性 raw path，重跑会原子 replace 同一路径；尚未进入正式 bundle，但不满足 snapshot 不覆盖原则。
- 修订：中断目录保留为技术尝试；复制当前 bytes 到 final raw root 后，final root 对同路径相同 bytes 只读复用、不同 bytes fail closed；每位候选 checkpoint 原子写。正式 bundle 只引用 final root metadata/hash。
- 发现：v2 bundle 的一个 alternate 仍指向已退出 Recommended 的目标，物理 closure 正确拒绝。
- 修订：不修改失败 bundle；生成 v3，再因场景审查生成 v4；v5 修正审查日志中的小配额统计。v5 对 13 个 payload 文件验证 exact set、path/symlink、bytes/SHA-256、source/artwork/lead/scenario/alternate/decision closure 与 stale protection。
- 结论：33 schemas、5 valid/26 invalid curation fixtures、CLI 无 approve/auto-apply。P0–P2 resolved。

## Reviewer E｜发布边界、安全与产品回归

- 验证：`.gitignore` 覆盖 `data/raw/**`、`data/intermediate/**`、`data/review/**`、`data/staging/**`；`git ls-files` 私有路径为零。
- 验证：public/dist 扫描除通用 ID/目录/媒体模式外，还从 final ignored bundle 提取 labels/aliases 做泄漏比对；候选姓名、QID、ULAN、作品、leads、decision 和 media 均为零命中。
- 验证：CI 只运行 synthetic curation contract，不含 `--live`、private build、curl 或媒体下载；Pages artifact 仍只上传 `dist`。
- 验证：公开 UI 未修改；七馆、空美术馆序厅、武器馆不可点击、无第三方 runtime/media 保持不变。P0–P2 resolved。

## 保留 P3

| ID | Owner | 原因 | 影响 | 最晚复核 | 当前缓解 |
|---|---|---|---|---|---|
| P3-01 | data maintainer | 应用层 append-only 不是 WORM/管理员防篡改存储 | 本地管理员仍可能改 raw | MUSEUM-03B 正式批次前 | bytes/hash、final immutable path、stale closure、单机受控目录 |
| P3-02 | security reviewer | DNS 公网预检不是 cryptographic pinning，系统代理属信任边界 | 被破坏的本机网络环境可影响官方 HTTPS 请求 | 任一凭据/自定义 host 或 MUSEUM-03B 前 | 无凭据/cookie、精确 HTTPS host、redirect/size/timeout、response hash |
| P3-03 | data maintainer | Search/discovery utility 不是 MUSEUM-02 reference adapter | search contract drift 需人工识别，不能生产化复用 | MUSEUM-03B source plan | search 只发现对象 ID；每个采用对象回到 reference detail adapter/official object record |

最终无未解决 P0、P1 或 P2。P3 不授权进入 MUSEUM-03B。
