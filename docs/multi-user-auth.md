# 多用户认证

本 fork 将上游单管理员密码门禁扩展为多用户账号体系。分析能力与免费行情源保持不变。

## 行为

- `ADMIN_AUTH_ENABLED=true` 时保护 `/api/v1/*`。`/api/health`、`/api/v1/auth/login`、`/api/v1/auth/register`、`/api/v1/auth/status` 保持公开。
- 会话写入 httpOnly Cookie `dsa_session`（`SameSite=lax`）。
- 新用户密码使用 bcrypt；上游单管理员文件哈希（PBKDF2）仍可用于无用户名的兼容登录。
- 首次启动若设置 `ADMIN_USERNAME` 与 `ADMIN_PASSWORD`，会创建管理员。其他账号通过 `/register` 注册为普通用户。
- 登录后的自选股、分析历史、预警规则、投资组合按 `user_id` / `owner_id` 隔离。行情缓存仍全局共享。

## 配置

| 变量 | 说明 |
|------|------|
| `HOST_PORT` | Compose 发布到宿主机的唯一端口，默认 `18473` |
| `SECRET_KEY` | 会话签名密钥；未设置时回退到 `data/.session_secret` |
| `ADMIN_AUTH_ENABLED` | 是否强制登录 |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | 引导管理员 |
| `AUTH_REGISTRATION_ENABLED` | 是否允许公开注册，默认 true |
| `DATABASE_URL` | 用户库。Compose 内为 `postgresql+psycopg2://dsa:...@db:5432/dsa`；未设置时使用 `DATABASE_PATH` 对应的 SQLite |

## Docker

```bash
cp .env.example .env
docker compose up -d --build
```

浏览器访问 `http://localhost:18473`。仅该端口映射到宿主机。
