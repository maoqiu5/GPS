# 货比特数据采集 PRD

## 1. 背景

GPS 项目当前已能从货比特开放接口读取设备、轨迹、站点、报警和进出区事件。为了支持轨迹可视化、口岸等待时效、设备与路线/箱号/运单匹配，需要把接口数据持续保存到 BrianHub VPS。

第一版按 BrianHub 现有生产形态使用 SQLite：

```text
/root/apps/gps/data/gps/gps_tracking.db
```

## 2. 目标

### 2.1 第一阶段目标

本阶段先完成可验证的最小采集闭环：

- 创建 GPS 独立数据目录和 SQLite 数据库。
- 执行建表脚本。
- 拉取当前账号可见的全部设备清单。
- 拉取当前账号可见的全部站点。
- 拉取样本设备 `61007408` 的一段轨迹全信息。
- 将采集过程写入结构化日志。
- 将同步结果写入任务日志表。

### 2.2 后续目标

- 对全部设备做历史轨迹全量回填。
- 定时增量拉取新轨迹点。
- 定时拉取报警事件。
- 定时拉取进区、出区事件。
- 保存设备与路线、箱号、运单、订单的时间段绑定关系。
- 通过设备号和定位时间，把轨迹点归属到对应业务对象。

## 3. 数据范围

| 数据 | 接口 | 第一阶段 | 后续增量 |
| --- | --- | --- | --- |
| 设备清单 | `device.syncDeviceInfos` | 全量拉取 | 定时刷新 |
| 站点 | `basic.getAllSites` | 全量拉取 | 定时刷新 |
| 轨迹全信息 | `device.interfaces.getPlayBackFullInfoByGpsno` | 样本设备 7 天窗口 | 全设备按 7 天窗口回填和增量 |
| 报警 | `device.searchWarningInfo` | 暂不执行 | 按 72 小时以内窗口增量 |
| 进出区 | `device.searchSiteEvents` | 暂不执行 | 按 31 天以内窗口增量 |

## 4. 运行环境

VPS：

```text
root@192.236.235.229
```

项目路径：

```text
/root/apps/gps
```

数据库：

```text
/root/apps/gps/data/gps/gps_tracking.db
```

脚本：

```text
/root/apps/gps/scripts/hbt_stage1_collect.py
```

建表 SQL：

```text
/root/apps/gps/schema/HBT_SQLITE_SCHEMA.sql
```

日志目录：

```text
/root/apps/gps/logs
```

## 5. 核心表

第一阶段会创建完整第一版 schema，但主要写入以下表：

| 表 | 用途 |
| --- | --- |
| `hbt_devices` | 设备主数据和最新状态 |
| `hbt_sites` | 站点/电子围栏 |
| `hbt_track_points` | 样本轨迹点 |
| `hbt_track_fetch_windows` | 样本轨迹窗口拉取记录 |
| `hbt_sync_cursors` | 样本设备轨迹游标 |
| `hbt_sync_jobs` | 本次采集任务记录 |

完整 schema 见 [HBT_SQLITE_SCHEMA.sql](./HBT_SQLITE_SCHEMA.sql)。

## 6. 幂等策略

设备：

- 以 `device_id` 做主键。
- 重复同步时更新最新状态、位置、电量、服务期和原始 payload。

站点：

- 以 `site_id` 做主键。
- 重复同步时更新名称、坐标、地址、机构和原始 payload。

轨迹点：

- 唯一键：`device_id, loc_at, lng, lat`。
- 重复拉取同一窗口时执行 upsert。
- 货比特接口可能返回重复点，重复点会被唯一键去重。

采集窗口：

- 唯一键：`device_id, window_start_at, window_end_at, method`。
- 同一窗口重复执行时更新状态和点数。

## 7. 日志设计

脚本输出 JSON Lines 日志，每行一个事件。

示例：

```json
{"ts":"2026-07-22T04:56:03+00:00","event":"devices_done","count":226,"online":117,"offline":109}
```

关键事件：

| event | 说明 |
| --- | --- |
| `stage1_start` | 采集开始 |
| `schema_applied` | 建表完成 |
| `devices_page` | 设备分页拉取 |
| `devices_done` | 设备同步完成 |
| `sites_done` | 站点同步完成 |
| `track_window_done` | 样本轨迹窗口同步完成 |
| `stage1_done` | 采集结束 |

日志文件建议命名：

```text
/root/apps/gps/logs/hbt_stage1_YYYYMMDD-HHMMSS.log
```

## 8. 验收标准

第一阶段执行成功后，应满足：

- SQLite 文件存在：`/root/apps/gps/data/gps/gps_tracking.db`
- Schema 建表成功：至少 `17` 张业务表。
- `hbt_devices` 有当前账号可见设备，当前实测应为 `226` 台。
- `hbt_sites` 有当前账号可见站点，当前实测应为 `12` 个。
- `hbt_track_points` 有样本设备轨迹点，当前样本约 `61` 条唯一点。
- `hbt_track_fetch_windows` 有样本窗口成功记录。
- `hbt_sync_jobs` 有 `stage1_sample_collect` 成功记录。
- 日志文件完整保存，没有打印接口密钥。

## 9. 风险和限制

- 当前为 SQLite 第一版，适合快速上线和中等规模数据；全量轨迹长期增长后可能需要迁移到 PostgreSQL/TimescaleDB。
- 历史轨迹接口单次窗口不能超过 `7` 天。
- 报警接口单次窗口不能超过 `72` 小时。
- 进出区接口单次窗口不能超过 `31` 天。
- 设备和箱号/路线/订单的绑定关系需要业务系统或人工导入，不能只靠轨迹接口自动推断。

## 10. 下一步

第一阶段成功后，进入第二阶段：

1. 建立全设备历史轨迹回填任务。
2. 为每台设备生成 7 天窗口。
3. 支持断点续跑和失败重试。
4. 增加报警和进出区事件增量任务。
5. 增加业务绑定导入接口或管理页面。

## 11. 第二阶段进展

已新增轨迹回填脚本：

```text
scripts/hbt_backfill_tracks.py
```

已完成：

- 本地 dry-run 验证。
- VPS dry-run 验证。
- VPS 单设备单窗口真实验证。

验证结果见 [HBT_TRACK_BACKFILL_RUNBOOK.md](./HBT_TRACK_BACKFILL_RUNBOOK.md)。

## 12. 第三阶段进展

已新增事件采集脚本：

```text
scripts/hbt_collect_events.py
```

支持：

- 报警事件：`device.searchWarningInfo`
- 进出区事件：`device.searchSiteEvents`

已完成本地 dry-run、VPS dry-run 和 VPS 小批量真实验证。验证结果见 [HBT_EVENT_INGESTION_RUNBOOK.md](./HBT_EVENT_INGESTION_RUNBOOK.md)。

## 13. 第四阶段进展

已新增当前状态采集脚本：

```text
scripts/hbt_collect_current.py
```

支持：

- 批量调用 `device.interfaces.getCurrentsByGpsnos`
- 每批最多 `50` 台设备
- 更新 `hbt_devices`
- 写入 `hbt_device_snapshots`
- 更新当前状态游标

已完成本地 dry-run、VPS dry-run 和 VPS 全量当前状态刷新。验证结果见 [HBT_CURRENT_STATUS_RUNBOOK.md](./HBT_CURRENT_STATUS_RUNBOOK.md)。

## 14. 第五阶段进展

已新增增量采集总控脚本：

```text
scripts/hbt_run_incremental.sh
```

支持按固定顺序执行：

- 当前状态刷新。
- 轨迹增量拉取。
- 报警事件增量拉取。
- 进出区事件增量拉取。

已完成：

- 本地 dry-run 验证。
- VPS dry-run 验证。
- VPS 上按真实库规划出 `226` 台设备、`5` 个当前状态批次、轨迹/报警/进出区增量窗口。

定时任务和环境变量配置见 [HBT_INCREMENTAL_RUNNER_RUNBOOK.md](./HBT_INCREMENTAL_RUNNER_RUNBOOK.md)。

## 15. 第六阶段进展

事件采集脚本已增强游标续跑能力：

```text
scripts/hbt_collect_events.py --use-cursors
```

行为：

- 报警使用 `alarm:all` 或 `alarm:{device_id}` 游标。
- 进出区使用 `site_event:all` 或 `site_event:{device_id}` 游标。
- 续跑起点为上次成功时间前 `5` 分钟。
- 依靠事件唯一键去重，降低边界时间漏数风险。

增量总控脚本已默认对报警和进出区任务启用 `--use-cursors`。

## 16. 第七阶段进展

已在 VPS 执行第一轮小流量正式增量采集：

```text
TRACK_MAX_WINDOWS=5
ALARM_MAX_WINDOWS=2
SITE_MAX_WINDOWS=1
SLEEP_SECONDS=0.5
```

结果：

- 当前状态刷新成功：`226` 台设备，`5` 批。
- 轨迹增量成功：`5` 个窗口，返回 `0` 个新点。
- 报警增量成功：`2` 个窗口，返回 `0` 条报警。
- 进出区增量成功：`1` 个窗口，返回并写入 `245` 条事件。

执行报告见 [HBT_INCREMENTAL_REAL_RUN_REPORT.md](./HBT_INCREMENTAL_REAL_RUN_REPORT.md)。

## 17. 第八阶段进展

已执行第二轮扩大增量：

- 轨迹窗口：`50` 个，成功 `50` 个，失败 `0` 个。
- 报警窗口：`4` 个，成功 `4` 个，失败 `0` 个。
- 进出区窗口：`1` 个，成功 `1` 个，失败 `0` 个。

第二轮按设备号排序时返回 `0` 个新轨迹点，说明前序设备存在大量空窗口。为提高历史回填效率，轨迹回填新增排序参数：

```text
--order-by online_recent
```

增量总控默认使用：

```text
TRACK_ORDER_BY=online_recent
```

活跃设备真实验证结果：

- `10` 个轨迹窗口全部成功。
- 返回 `865` 个轨迹点。
- 轨迹点累计增加到 `925` 条。
- 成功轨迹窗口累计 `67` 个，失败 `0` 个。

## 18. 第九阶段进展

已新增业务绑定与查询 API：

```text
scripts/gps_query_api.py
```

已覆盖：

- `POST /bindings`：创建/更新设备与箱号、路线、订单、运单、车辆的时间段绑定。
- `GET /bindings`：按设备号、箱号、路线、订单等查询绑定。
- `GET /devices`：查询设备最新状态。
- `GET /tracks/device/{device_id}`：查询单设备轨迹。
- `GET /tracks/container/{container_no}`：按箱号和绑定时间段查询轨迹。
- `GET /site-events`：按设备、箱号或路线查询进出区事件。
- `GET /routes/{route_id}/current-devices`：查询路线当前绑定设备。

本地使用 VPS SQLite 副本验证通过，VPS 使用真实库临时启动验证通过。使用说明见 [GPS_BINDING_QUERY_API.md](./GPS_BINDING_QUERY_API.md)。

## 19. 第十阶段进展

已继续执行 VPS 真实增量拉取：

```text
TRACK_MAX_WINDOWS=200
TRACK_ORDER_BY=online_recent
ALARM_MAX_WINDOWS=4
SITE_MAX_WINDOWS=1
SLEEP_SECONDS=0.5
```

结果：

- 轨迹窗口成功 `200` 个，失败 `0` 个。
- 本轮轨迹接口报告 `16309` 个点。
- 有轨迹设备数从 `3` 增加到 `48`。
- 轨迹点累计从 `925` 增加到 `16390`。
- 成功轨迹窗口累计 `267` 个，失败 `0` 个。
- 进出区事件累计 `247` 条。

详见 [HBT_INCREMENTAL_REAL_RUN_REPORT.md](./HBT_INCREMENTAL_REAL_RUN_REPORT.md)。
