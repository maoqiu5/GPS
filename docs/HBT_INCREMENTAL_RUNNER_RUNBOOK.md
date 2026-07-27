# HBT 增量采集总控运行手册

## 1. 目的

`scripts/hbt_run_incremental.sh` 是 GPS 项目的增量采集总控脚本，用于按固定顺序执行：

1. 设备当前状态刷新。
2. 轨迹增量窗口拉取。
3. 报警事件增量拉取。
4. 进出区事件增量拉取。

脚本适合手动执行，也适合后续接入 `cron` 或 systemd timer。

轨迹、报警和进出区任务默认使用 `hbt_sync_cursors` 续跑。事件类游标会从上次成功时间前 `5` 分钟重新扫描，借助事件唯一键去重，避免接口边界时间漏数。

## 2. VPS 路径

```text
/root/apps/gps
/root/apps/gps/data/gps/gps_tracking.db
/root/apps/gps/schema/HBT_SQLITE_SCHEMA.sql
/root/apps/gps/scripts/hbt_run_incremental.sh
/root/apps/gps/logs
```

## 3. 环境变量

模板文件：

```text
scripts/hbt_gps_env.example
```

VPS 上建议保存为：

```text
/root/apps/gps/.env.production
```

权限建议：

```bash
chmod 600 /root/apps/gps/.env.production
```

必填：

| 变量 | 说明 |
| --- | --- |
| `HBT_APP_KEY` | 货比特开放平台 app key |
| `HBT_APP_SECRET` | 货比特开放平台 app secret |

常用可调参数：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `GPS_ROOT_DIR` | `/root/apps/gps` | 项目根目录 |
| `GPS_DB_PATH` | `/root/apps/gps/data/gps/gps_tracking.db` | SQLite 数据库路径 |
| `GPS_SCHEMA_PATH` | `/root/apps/gps/schema/HBT_SQLITE_SCHEMA.sql` | 建表脚本路径 |
| `GPS_LOG_DIR` | `/root/apps/gps/logs` | 日志目录 |
| `START_AT` | `2026-06-23 00:00:00` | 首次回填起点 |
| `END_AT` | 当前北京时间 | 本轮截止时间 |
| `TRACK_MAX_WINDOWS` | `20` | 单次最多轨迹窗口数 |
| `TRACK_ORDER_BY` | `online_recent` | 轨迹设备排序，默认优先在线和最近定位设备 |
| `ALARM_MAX_WINDOWS` | `8` | 单次最多报警窗口数 |
| `SITE_MAX_WINDOWS` | `2` | 单次最多进出区窗口数 |
| `SLEEP_SECONDS` | `0.5` | 接口请求间隔 |
| `DRY_RUN` | `0` | `1` 表示只规划、不请求接口 |

## 4. 手动执行

先做无密钥 dry-run：

```bash
DRY_RUN=1 TRACK_MAX_WINDOWS=1 ALARM_MAX_WINDOWS=1 SITE_MAX_WINDOWS=1 SLEEP_SECONDS=0 /root/apps/gps/scripts/hbt_run_incremental.sh
```

正式执行：

```bash
set -a
. /root/apps/gps/.env.production
set +a
/root/apps/gps/scripts/hbt_run_incremental.sh
```

小流量正式执行：

```bash
set -a
. /root/apps/gps/.env.production
set +a
TRACK_MAX_WINDOWS=5 ALARM_MAX_WINDOWS=2 SITE_MAX_WINDOWS=1 /root/apps/gps/scripts/hbt_run_incremental.sh
```

单设备验证事件游标：

```bash
python3 /root/apps/gps/scripts/hbt_collect_events.py alarm \
  --db-path /root/apps/gps/data/gps/gps_tracking.db \
  --schema-path /root/apps/gps/schema/HBT_SQLITE_SCHEMA.sql \
  --log-path /root/apps/gps/logs/hbt_alarm_cursor_dry.log \
  --start "2026-06-23 00:00:00" \
  --end "2026-07-22 13:42:00" \
  --device-id 61007408 \
  --use-cursors \
  --max-windows 1 \
  --dry-run
```

## 5. 定时任务建议

早期建议每小时执行一次，并限制单次轨迹窗口数量，避免首次历史回填过猛：

```cron
15 * * * * set -a; . /root/apps/gps/.env.production; set +a; TRACK_MAX_WINDOWS=20 ALARM_MAX_WINDOWS=8 SITE_MAX_WINDOWS=2 /root/apps/gps/scripts/hbt_run_incremental.sh >> /root/apps/gps/logs/cron_hbt_incremental.log 2>&1
```

当历史轨迹回填追平后，可以降低 `TRACK_MAX_WINDOWS`，例如每小时 `5` 个窗口；如果设备数量增长明显，再迁移到独立 worker 或队列表。

轨迹设备排序可选值：

| 值 | 说明 |
| --- | --- |
| `online_recent` | 优先在线设备，再按最新定位时间倒序 |
| `last_loc_at_desc` | 按最新定位时间倒序 |
| `device_id` | 按设备号排序 |

## 6. 日志

每轮总控日志：

```text
/root/apps/gps/logs/hbt_incremental_YYYYMMDD-HHMMSS.log
```

每个子任务会额外写独立日志：

```text
hbt_current_status_YYYYMMDD-HHMMSS.log
hbt_track_incremental_YYYYMMDD-HHMMSS.log
hbt_alarm_incremental_YYYYMMDD-HHMMSS.log
hbt_site_events_incremental_YYYYMMDD-HHMMSS.log
```

关键成功标志：

| event | 说明 |
| --- | --- |
| `incremental_start` | 总控开始 |
| `current_status_done` | 当前状态刷新完成 |
| `track_incremental_done` | 轨迹增量完成 |
| `alarm_incremental_done` | 报警增量完成 |
| `site_events_incremental_done` | 进出区增量完成 |
| `incremental_done` | 总控完成 |

## 7. 本次验证

本地 dry-run：

- 时间：`2026-07-22 13:36:48` 北京时间。
- 结果：通过。
- 汇总日志：`/tmp/gps_stage5_local/logs/hbt_incremental_20260722-053648.log`。

VPS dry-run：

- 时间：`2026-07-22 13:37:19` 北京时间。
- 结果：通过。
- 汇总日志：`/root/apps/gps/logs/hbt_incremental_20260722-053719.log`。
- 真实库设备规划：`226` 台。
- 当前状态规划：`5` 批。
- 轨迹规划：按 `7` 天窗口。
- 报警规划：按 `72` 小时窗口。
- 进出区规划：按 `31` 天窗口。

事件游标专项 dry-run：

- 报警样本设备 `61007408` 从游标 `2026-06-25T15:59:59+00:00` 前 `5` 分钟续跑，规划起点为 `2026-06-25 23:54:59` 北京时间。
- 进出区样本设备 `61007408` 的游标晚于本次截止时间，正确返回 `cursor_after_end`，未规划重复窗口。

活跃设备排序专项验证：

- VPS dry-run 已确认 `TRACK_ORDER_BY=online_recent` 生效，优先规划设备 `61005610`。
- VPS 真实小批量验证成功：`10` 个轨迹窗口全部成功，返回 `865` 个轨迹点，失败 `0` 个窗口。

## 8. 当前注意事项

- 不要把真实 `.env.production` 提交到仓库。
- 首次大规模历史轨迹回填建议保守设置 `TRACK_MAX_WINDOWS`，观察接口稳定性和数据库增长速度。
- 全局事件游标 `alarm:all`、`site_event:all` 需要首次全局真实执行成功后才会生成；首次全局任务仍会从 `START_AT` 开始规划。
