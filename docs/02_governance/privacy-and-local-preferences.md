---
title: Privacy and local preferences
phase_id: MUSEUM-08
decision: OD-009
status: accepted
effective_date: 2026-07-19
---

# 隐私与本地偏好

Museum-Codex 的公开运行时不建立访客档案，也不以行为数据换取功能完整性。

## 禁止的数据处理

站点不使用 analytics、账户、服务端 profile、telemetry SDK、Cookie、浏览器指纹、用户 geolocation 或 remote logging。不得收集或保存搜索词、访问记录、已选艺术家、作品比较、关系路径、地图筛选、导览访问或 print/share 历史。

搜索、比较、路径、地图和导览状态只存在于当前页面内；可分享 URL 是访客主动形成的当前地址，不写入 localStorage、sessionStorage、Cookie 或远程服务。

## 允许的本地偏好

仅允许保存访客明确选择、且不构成访问历史的 UI 偏好：

- `museum-locale`；
- `museum-low-bandwidth`；
- 未来如增加 appearance/contrast，必须先纳入同一 allowlist 与扫描器。

清除站点本地存储会重置这些偏好，不影响公开内容或核心任务。系统级 `prefers-reduced-motion`、`forced-colors` 与缩放只在本地读取，不记录。

## 工程门禁

候选 release 的 `privacy-snapshot.json`、仓库 privacy scanner 与浏览器 request/storage 审计共同执行 deny-by-default 门禁。任何新增网络端点、存储 key、Cookie、定位调用、tracking 名称或 query/history 持久化都会使验证失败，除非后续有新的显式决策与完整影响评估。
