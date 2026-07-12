# ADR-0006：构建期 Python 数据管线

- Status: accepted; implemented in MUSEUM-02
- Date: 2026-07-12

## Context

内容导入必须可复放、可离线测试、可审核，并且不能把来源 API 变成公开站点的运行时依赖。仓库已使用 Python 3.12、JSON Schema 与 `jsonschema`；前端 `src/` 已表示浏览器产品代码。

## Decision

建立独立顶层包 `museum_pipeline/`，入口为 `python -m museum_pipeline`。CLI 使用标准库 `argparse`；HTTP 使用可注入的标准库 transport；事实契约仍以 Draft 2020-12 JSON Schema 为唯一跨语言规范，不引入 Pydantic、ORM、FastAPI 或数据库服务。网络默认关闭，只能由命令行显式 `--live` 开启单对象采集，环境变量不能开启网络。公开运行时只消费审核后的静态 release；本阶段 candidate/raw/review 均不进入 Pages。

## Why

独立包避免与 React `src/` 混淆；标准库实现足以覆盖当前四个无凭据 per-record adapter，并减少供应链面。注入 transport 使超时、重试、304、重定向和响应体上限可完全离线测试。

## Alternatives

- Pydantic/ORM：开发便利，但会复制并漂移 JSON Schema 事实模型。
- FastAPI + 数据库：适合远程协作审核，但扩大安全、账户、备份和运维范围，违反本阶段边界。
- Node-only pipeline：可共用前端工具链，但 Python 对现有治理验证和字节处理更直接。

## Costs and safeguards

标准库 `urllib` 只有单一 socket timeout；实现取 connect/read 两个声明上限中的更严格值，并另设总超时。固定 host、TLS 验证、公共 DNS 检查、最大 5 MiB、有限重试/重定向和无 Cookie 减小网络风险。未来新增依赖必须单独 ADR、固定版本、记录许可证并进入 CI 扫描。

## Revisit when

出现必须认证且标准库无法安全表达的协议、数据规模需要流式解析，或明确授权远程审核服务时。
