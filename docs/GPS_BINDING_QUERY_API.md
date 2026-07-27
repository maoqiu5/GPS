# GPS 业务绑定与查询 API

## 1. 目标

货比特核心定位接口不返回箱号。GPS 项目通过 `device_business_bindings` 保存设备号与箱号、路线、订单、运单之间的时间段绑定关系，再用定位时间或进出区时间归属业务对象。

轻量 API 脚本：

```text
scripts/gps_query_api.py
```

VPS 默认数据库：

```text
/root/apps/gps/data/gps/gps_tracking.db
```

## 2. 启动

本地或 VPS：

```bash
python3 scripts/gps_query_api.py \
  --db-path /root/apps/gps/data/gps/gps_tracking.db \
  --schema-path /root/apps/gps/schema/HBT_SQLITE_SCHEMA.sql \
  --host 127.0.0.1 \
  --port 8015
```

健康检查：

```bash
curl -s http://127.0.0.1:8015/health
```

BrianHub 项目统一运维约定：

- SSH 登录：`ssh -i ~/.ssh/cnstock_vps root@192.236.235.229`
- GPS 项目目录：`/root/apps/gps`
- GPS SQLite：`/root/apps/gps/data/gps/gps_tracking.db`
- 查询 API 建议绑定 VPS 本机回环地址：`127.0.0.1:8015`
- 本地 `file://` 页面调试时，通过 SSH 隧道把 Mac 的 `127.0.0.1:8015` 转发到 VPS：

```bash
ssh -i ~/.ssh/cnstock_vps -f -N -L 8015:127.0.0.1:8015 root@192.236.235.229
```

说明：本地 HTML 里的 `127.0.0.1` 指的是 Mac 本机，不是 VPS。使用上述隧道后，页面无需修改 API 地址即可查询 VPS 数据库。

## 3. 新增/更新设备业务绑定

```http
POST /bindings
Content-Type: application/json
```

最小字段：

```json
{
  "device_id": "61005610",
  "container_no": "TEST-CONT-001",
  "route_id": "CN-EU-001",
  "route_name": "China-Europe Test Route",
  "bind_start_at": "2026-06-22T00:00:00+00:00",
  "bind_end_at": null,
  "source": "manual"
}
```

说明：

- `device_id`、`bind_start_at`、`source` 必填。
- `container_no`、`route_id`、`shipment_id`、`order_id`、`truck_no` 至少填一个。
- 如果传 `binding_id`，则更新已有绑定。
- 如果传 `route_id + route_name`，会自动 upsert `business_routes`。
- 如果传 `container_no`，会自动 upsert `business_containers`。

## 4. 查询接口

### 4.1 设备列表

```http
GET /devices?active_only=1&limit=50
```

返回最新状态、坐标、电量、定位时间。

### 4.2 绑定列表

```http
GET /bindings?container_no=TEST-CONT-001
GET /bindings?device_id=61005610
GET /bindings?route_id=CN-EU-001&active_at=2026-07-01T00:00:00+00:00
```

### 4.3 单设备轨迹

```http
GET /tracks/device/61005610?start=2026-06-22T00:00:00+00:00&end=2026-07-22T23:59:59+00:00&limit=2000
```

### 4.4 单设备轨迹地图数据

```http
GET /api/trajectory?device_id=61007408&limit=5000
```

用途：

- 给 `trajectory-map-interactive.html` 顶部设备号查询框使用。
- 从 SQLite `hbt_track_points` 读取指定设备轨迹点。
- 服务端按时间排序后生成页面可直接渲染的数据结构。
- 返回清洗后的展示点、剔除的 GPS 漂移点、重点口岸、自动边境穿越点、路线节点、总时效、分段运输时效和口岸等待时间。

返回结构：

```json
{
  "points": [],
  "removedPoints": [],
  "ports": [],
  "borderCrossings": [],
  "route": {
    "origin": {},
    "destination": {},
    "totalDuration": "20天13小时42分",
    "segments": []
  },
  "meta": {
    "deviceId": "61007408",
    "rawCount": 186,
    "displayCount": 185,
    "removedCount": 1
  }
}
```

页面默认请求：

```text
http://127.0.0.1:8015/api/trajectory?device_id={设备号}&limit=5000
```

如果 API 未启动或查询失败，页面保留内置样本轨迹，避免地图空白。

有轨迹设备列表：

```http
GET /api/trajectory-devices?limit=200
```

用途：

- 返回已生成 `gps_trajectory_cache` 的设备。
- 页面顶部“有轨迹设备”下拉框使用该接口，用户可直接选择可查询设备。
- 返回每台设备的展示点数、原始点数、剔除点数、总时效和预处理时间。

口岸定义列表：

```http
GET /api/port-definitions
```

用途：

- 查看当前启用的关键口岸/边境通道定义。
- 预处理和实时计算都会优先读取 `gps_port_definitions`。
- 后续新增、关闭或调整口岸，可修改数据库表后重新执行预处理，不需要修改页面代码。

缓存控制：

- 默认优先读取 `gps_trajectory_cache` 预处理结果。
- 命中缓存时，如果 `gps_port_passages` 和 `gps_route_segments` 已存在结构化结果，接口会用结构化表覆盖 `ports` 和 `route`，并返回 `meta.structuredRoute=true`。
- 命中缓存时，如果 `gps_border_crossings` 已存在结构化结果，接口会用结构化表覆盖 `borderCrossings`，并返回 `meta.borderCrossingCount`。
- 传 `use_cache=0` 时强制绕过缓存，临时实时计算。

```http
GET /api/trajectory?device_id=61007408&use_cache=0
```

### 4.4.1 自动边境穿越点

```http
GET /api/border-crossings?device_id=61007408
```

用途：

- 直接读取 `gps_border_crossings`。
- 返回设备按轨迹自动识别的国家/边境穿越点。
- 页面用该结果重点标注“自动边境”节点。

算法说明：

- 基于已剔除漂移点后的有效轨迹。
- 当相邻有效点国家归属发生变化时，取两点中点作为穿越点。
- 中欧线路按 CN→KZ→RU→BY→PL 前进方向去抖，只保留每个相邻国家边界的首次穿越，避免口岸附近 GPS 抖动生成多次来回穿越。
- 如果穿越点靠近 `gps_port_definitions` 中的口岸，会返回匹配口岸、距离和置信度。

返回核心字段：

```json
{
  "items": [
    {
      "fromCountryCode": "CN",
      "toCountryCode": "KZ",
      "crossingTime": "2026-06-25T16:42:00+00:00",
      "matchedPortShortName": "阿拉山口/多斯特克",
      "confidence": 0.85
    }
  ]
}
```

### 4.4.2 结构化路线时效

```http
GET /api/route-summary?device_id=61007408
```

用途：

- 直接读取 `gps_port_passages` 和 `gps_route_segments`。
- 返回设备经过口岸、口岸等待时长、始发站 - 口岸 - 目的站分段运输时效。
- 适合后续做报表、路线看板和时效查询，不需要解析整条轨迹 JSON。

返回核心字段：

```json
{
  "ports": [],
  "route": {
    "routeText": "始发站 → 口岸 → 目的站",
    "totalDuration": "29天19小时29分",
    "segments": []
  },
  "meta": {
    "matchedPortCount": 4,
    "segmentCount": 5,
    "algorithmVersion": "trajectory-precompute-v6"
  }
}
```

预处理脚本：

```bash
python3 scripts/gps_precompute_trajectory.py \
  --db-path /root/apps/gps/data/gps/gps_tracking.db \
  --schema-path /root/apps/gps/schema/HBT_SQLITE_SCHEMA.sql
```

预处理内容：

- 生成页面可直接渲染的轨迹 JSON。
- 预先计算 GPS 漂移点、口岸命中、始发站 - 口岸 - 目的站、总时效、分段运输时效和口岸等待时间。
- 预先计算自动边境穿越点，并写入 `gps_border_crossings`。
- 按中欧线路经纬度走廊预先判断每个轨迹点所属国家。
- 写入 `gps_trajectory_cache`。
- 同步写入 `gps_port_passages`、`gps_border_crossings` 和 `gps_route_segments`，供后续报表、查询和运营分析使用。
- 同步更新 `hbt_track_points.is_valid` 和 `hbt_track_points.is_drift_candidate`。

### 4.5 单箱号轨迹

```http
GET /tracks/container/TEST-CONT-001?limit=2000
```

逻辑：

```sql
p.device_id = b.device_id
AND p.loc_at >= b.bind_start_at
AND (b.bind_end_at IS NULL OR p.loc_at < b.bind_end_at)
```

### 4.6 进出区事件

```http
GET /site-events?device_id=61005610&limit=100
GET /site-events?container_no=TEST-CONT-001&limit=100
GET /site-events?route_id=CN-EU-001&limit=100
```

### 4.7 路线当前设备

```http
GET /routes/CN-EU-001/current-devices
```

默认按当前 UTC 时间匹配绑定，也可以指定：

```http
GET /routes/CN-EU-001/current-devices?active_at=2026-07-01T00:00:00+00:00
```

## 5. 本次验证

本地验证使用临时 SQLite：

- API 启动成功。
- `GET /health` 成功。
- `POST /bindings` 成功创建测试绑定。
- `GET /bindings` 可查回绑定。
- `GET /tracks/container/{container_no}` 可按绑定时间段返回轨迹。
- `GET /api/trajectory?device_id={device_id}` 可返回页面渲染所需的轨迹、异常点、口岸和时效数据。

VPS 验证：

- 脚本已上传至 `/root/apps/gps/scripts/gps_query_api.py`。
- 使用真实 SQLite dry-start 验证。
- `GET /health` 返回当前库摘要。
- 2026-07-22 已使用 `~/.ssh/cnstock_vps` 同步新版 API 至 VPS 并启动 `127.0.0.1:8015`。
- 本机已通过 SSH 隧道验证 `GET /api/trajectory?device_id=61005610` 返回 `496` 个轨迹点。
- 2026-07-22 已执行轨迹预处理：缓存 `48` 台有轨迹设备、`16390` 个轨迹点，识别 `2` 个漂移候选点。
