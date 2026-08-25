# GPS 项目交接说明

> 更新时间：2026-08-25
> 接手原则：VPS `/root/apps/gps` 为生产事实；本地 `D:\codex\GPS` 为开发源码。

## 1. 项目一句话

BrianHub 生产项目，提供 GPS 轨迹可视化、铁路运价查询/预测，统一入口 `/gps/`；卡车运价已移交 rates 项目。

## 2. 当前状态

- 线上：`https://brianhub.net/gps/`
- VPS 目录：`/root/apps/gps`
- 本地目录：`D:\codex\GPS`
- 技术栈：Python / SQLite / 非 Docker 部署
- VPS 无 `.git`
- 后端服务：`gps-query-api-edge.service`
- 内部 API：`172.19.0.1:8015`
- 本地已同步 VPS 最新源码：✅（2026-08-25）
- 本地 API 测试：待重新运行 `test_gps_only_api.py`；truck 接口移除已完成，静态断言应通过

## 3. 核心模块

- GPS 轨迹可视化
- 铁路运费查询/预测
- 卡车运价已移交 rates 项目，不再由 GPS API 提供
- HBT 数据接入和增量任务

## 4. 关键路径

- 前端：`web/`
- 后端 API：`scripts/gps_query_api.py`
- SQLite：`data/gps/gps_tracking.db`
- Schema：`schema/`
- 文档：`docs/README.md`、`docs/PRD.md`、`docs/DEPLOYMENT.md`


## 4.1 已知问题 / 待确认

- ~~`tools/test_gps_only_api.py` 要求 GPS API 中不再包含 `/api/truck-stations`、`/api/truck-market-references`、`/api/truck-distance`。~~
- 已按用户确认“不保留”处理：从 `scripts/gps_query_api.py` 的 `do_GET` 中移除上述三个 truck 路由。
- 这些 truck 功能由 rates 项目接管；若 rates 回退或需要 GPS 重新提供，需恢复并保持与 rates 实现一致。


## 5. 部署注意

- 不是 Docker 模板，是 systemd 服务
- 不要删除/覆盖 `data/`、`schema/`、生产 SQLite
- 后端改动后需重启 `gps-query-api-edge.service`

## 6. 安全

- 不读取/输出 HBT 凭据、API Key、数据库内容
- 不提交 `data/`、`logs/`、`runtime/`、`secrets/`

## 7. 新对话接续

```text
这是 GPS 项目对话。
请先读 D:\codex\HANDOVER_INDEX.md 和 D:\codex\GPS\docs\HANDOVER.md，
再查看 VPS /root/apps/gps 状态，然后开始工作。
```
