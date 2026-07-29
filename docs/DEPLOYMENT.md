# GPS 工具部署说明

更新时间：2026-07-25  
项目代号：`gps`  
生产目录：`/root/apps/gps`

## 1. 线上入口

- 页面入口：`https://brianhub.net/gps/`
- API 前缀：`https://brianhub.net/gps/api/*`
- 静态页面目录：`/root/apps/gps/web`
- 生产数据库：`/root/apps/gps/data/gps/gps_tracking.db`
- API 脚本：`/root/apps/gps/scripts/gps_query_api.py`
- API 监听：`172.19.0.1:8015`

公网入口由 `brianhub-gateway` 管理，GPS 项目不绑定 `80` 或 `443`。

## 2. 运行架构

GPS 项目不是标准 Docker 前后端双容器项目，当前生产形态为：

- 静态前端：`/root/apps/gps/web/index.html` 和相关 JS/CSS 文件。
- 轻量 API：宿主机 Python 进程 `gps_query_api.py`。
- 数据库：SQLite 轨迹库。
- 网关：Caddy 将 `/gps/` 静态文件映射到 `/root/apps/gps/web`，将 `/gps/api/*` 转发到 Python API。

当前 API 进程示例：

```text
/usr/bin/python3 /root/apps/gps/scripts/gps_query_api.py --db-path /root/apps/gps/data/gps/gps_tracking.db --schema-path /root/apps/gps/schema/HBT_SQLITE_SCHEMA.sql --host 172.19.0.1 --port 8015
```

## 3. 启动 API

进入项目目录：

```bash
cd /root/apps/gps
```

启动查询 API：

```bash
python3 scripts/gps_query_api.py \
  --db-path /root/apps/gps/data/gps/gps_tracking.db \
  --schema-path /root/apps/gps/schema/HBT_SQLITE_SCHEMA.sql \
  --host 172.19.0.1 \
  --port 8015
```

建议后续将该进程固化为 systemd 服务或 Compose 服务，避免手工进程丢失。

## 4. 发布静态页面

静态页面发布到：

```text
/root/apps/gps/web
```

更新页面或前端脚本后，需要注意：

- 不删除 `data`、`logs`、`schema`、`scripts`、`docs`。
- Service Worker 缓存版本需要随静态资源变化更新。
- 发布后用无缓存浏览器或清理旧缓存验证。

## 5. 生产数据保护

不得覆盖或删除：

- `/root/apps/gps/data`
- `/root/apps/gps/data/gps/gps_tracking.db`
- `/root/apps/gps/logs`
- `/root/apps/gps/schema`
- HBT 环境配置和任何真实接口凭据

文档中不得记录真实 HBT 账号、密码、Token 或接口签名。

## 6. 发布验证

健康检查：

```bash
curl -s http://172.19.0.1:8015/health
```

公网页面：

```bash
curl -sS --max-time 15 -o /dev/null -w 'page %{http_code} %{time_total}\n' https://brianhub.net/gps/
```

公网 API：

```bash
curl -sS --max-time 15 https://brianhub.net/gps/api/health
```

业务接口验证：

- 使用门户登录会话访问 `/gps/api/trajectory`。
- 使用已有设备号验证轨迹查询。
- 检查地图是否能加载轨迹、口岸、边境穿越点和铁路运价模块。

## 7. 回滚

如果页面或 API 异常：

1. 保留 `logs` 下当前日志。
2. 恢复上一版 `web/index.html`、`web/rail-calculator.js` 或相关脚本。
3. 如 API 异常，停止旧 Python 进程后用上一版脚本重新启动。
4. 不删除 SQLite 数据库。
5. 重新验证 `/gps/`、`/gps/api/health` 和核心轨迹查询。

## 8. 参考文档

- 产品说明：[PRD.md](./PRD.md)
- GPS 绑定查询 API：[GPS_BINDING_QUERY_API.md](./GPS_BINDING_QUERY_API.md)
- HBT 增量运行手册：[HBT_INCREMENTAL_RUNNER_RUNBOOK.md](./HBT_INCREMENTAL_RUNNER_RUNBOOK.md)
- HBT 数据接入 PRD：[HBT_DATA_INGESTION_PRD.md](./HBT_DATA_INGESTION_PRD.md)
