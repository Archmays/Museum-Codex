# 凭据、网络与 secrets

当前四个参考 adapter 不需要凭据。`credential_requirements=none`，snapshot 只允许记录 credential alias；不保存 value、value hash、Cookie 或 Authorization。错误输出使用稳定 code 和通用消息，不显示绝对本地路径、token 或完整敏感请求。

## 默认离线

- tests、contract fixtures、validators 与 GitHub Actions 不访问外部 API；
- 环境变量不能开启 live mode；
- 只有 `acquire ... --live` 明确授权一个 source/object request sequence；
- CI 即使存在 secret 也不运行 live fetch；workflow 只上传 `dist/`。
- CI 通过 `scripts/run_offline_python_tests.py` 在进程级封锁 DNS 与 socket connect；任何测试意外联网会立即失败。

## Transport policy

- HTTPS +系统 CA/TLS hostname validation；
- adapter 固定 host/path/query allowlist，每次 redirect 重新验证；
- DNS 解析出的 loopback/private/link-local/multicast/reserved/unspecified 地址全部拒绝；
- User-Agent 明确，无 Cookie persistence；
- connect/read 使用更严格的 5/20 秒 ceiling，total 30 秒；
- response 最大 5 MiB，redirect 最多 3，retry 最多 3；
- 429 尊重 `Retry-After`（最多 30 秒）；5xx 有界指数退避+jitter；一般 4xx 不重试；
- live probe 并发固定 1，并服从 registry 更低限制。

固定官方 host 与 TLS 减少 SSRF/DNS 风险，但标准库连接前 DNS 与实际 socket 解析不是密码学 pinning；若未来引入用户可配置 host、代理或 credential adapter，必须先做新的安全 ADR，不复用当前信任边界。

Repository safety scan 覆盖 `.body`、JSON、Python、JS/TS、Markdown 等文本，阻断常见 token/private key，并阻断大于 5 MiB 文件。`.gitignore` 排除 raw/intermediate/staging/downloads、第三方媒体和本地配置。
