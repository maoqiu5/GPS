# GPS 轨迹可视化项目 PRD

## 1. 项目概述

GPS 轨迹可视化项目用于读取设备导出的 GPS 轨迹点数据和服务端 SQLite 轨迹库，并生成可交互地图页面。用户可以按设备号查询完整运输轨迹、缩放和平移地图、点击每个点查看采集时间和地理信息，并识别经过国家、重点口岸以及明显 GPS 漂移点。

当前交付物：

- 生产入口：`https://www.brianhub.net/gps/`
- `trajectory-map-interactive.html`
- `docs/HBT_API_INTEGRATION.md`
- `docs/HBT_API_FIELD_CATALOG.md`
- `docs/HBT_DATA_MODEL.md`
- `docs/HBT_DATA_INGESTION_PRD.md`
- `docs/HBT_STAGE1_RUN_REPORT.md`
- `docs/GPS_BINDING_QUERY_API.md`
- `scripts/gps_query_api.py`

## 2. 背景与目标

原始数据来自设备轨迹点表格，包含设备号、采集时间、经度、纬度、电量等字段。用户希望将这些点转换为直观地图，并能用于路线核验、口岸经过判断和异常点排查。

核心目标：

- 将 GPS 点按时间顺序绘制成轨迹。
- 支持地图放大、缩小、拖拽平移。
- 点击点位查看详细信息。
- 显示点位所属国家和具体地理位置。
- 标注经过国家和关键口岸。
- 通过数据库维护关键口岸/边境通道定义，避免页面写死口岸清单。
- 自动识别并剔除明显 GPS 漂移点。
- 自动形成始发站 - 口岸 - 目的站路线，并计算总时效、分段运输时效和口岸等待时间。
- 接入服务端 SQLite 轨迹库，支持页面顶部按设备号查询并刷新轨迹。
- 为后续每次功能变更保留更新记录。

## 3. 用户与场景

目标用户：

- 需要查看设备运输轨迹的业务人员。
- 需要核验跨境路径和口岸节点的运营人员。
- 需要排查 GPS 数据质量问题的数据或技术人员。

典型场景：

- 查看设备从起点到终点的完整路线。
- 判断轨迹经过哪些国家。
- 确认是否经过主要口岸或边境通道。
- 点击轨迹点查看时间、经纬度、电量和具体位置。
- 发现路线中异常跳点并从展示轨迹中去除。

## 4. 数据来源

当前输入数据为 Excel `.xls` 文件，工作表名为 `轨迹点`。

关键字段：

- `设备号`
- `采集时间`
- `通讯时间`
- `电量`
- `速度`
- `经度`
- `纬度`

当前样本数据：

- 设备号：`61007408`
- 原始点位数：`186`
- 展示点位数：`185`
- 已剔除异常点：`1`
- 时间范围：`2026-06-23 00:44:54` 至 `2026-07-13 14:27:02`

后续服务端数据来源为货比特开放接口：

- 接口地址：`https://openapi.51hbt.com/`
- 设备清单：`device.syncDeviceInfos`
- 当前状态：`device.interfaces.getCurrentByGpsno` / `device.interfaces.getCurrentsByGpsnos`
- 历史轨迹：`device.interfaces.getPlayBackByGpsno`
- 历史轨迹全信息：`device.interfaces.getPlayBackFullInfoByGpsno`
- 站点：`basic.getAllSites`
- 进出区事件：`device.searchSiteEvents`
- 报警：`device.searchWarningInfo`

第一阶段服务端采集已在 BrianHub VPS 落地：

- 数据库：`/root/apps/gps/data/gps/gps_tracking.db`
- 设备：`226` 台
- 站点：`12` 个
- 样本设备：`61007408`
- 样本轨迹唯一入库点：`61` 条
- 执行报告：[HBT_STAGE1_RUN_REPORT.md](./HBT_STAGE1_RUN_REPORT.md)

页面当前已支持通过轻量 API 查询服务端 SQLite：

- API 脚本：`scripts/gps_query_api.py`
- 查询接口：`GET /api/trajectory?device_id={设备号}&limit=5000`
- 有轨迹设备列表：`GET /api/trajectory-devices?limit=200`
- 结构化路线接口：`GET /api/route-summary?device_id={设备号}`
- 口岸定义接口：`GET /api/port-definitions`
- 自动边境接口：`GET /api/border-crossings?device_id={设备号}`
- 生产地址：`https://www.brianhub.net/gps/api/trajectory?device_id={设备号}&limit=5000`
- 本地调试默认地址：`http://127.0.0.1:8015`
- 数据表：`hbt_track_points`
- 页面查询框：位于 `trajectory-map-interactive.html` 顶部，按设备号刷新轨迹。

## 5. 功能需求

### 5.1 轨迹地图

- 地图基于 OpenStreetMap 底图。
- GPS 点按 `采集时间` 升序连接。
- 支持滚轮缩放、按钮缩放和拖拽平移。
- 轨迹按国家分段着色。
- 起点和终点使用特殊样式区分。
- 页面顶部支持输入设备号，调用本地 API 从 SQLite 读取对应轨迹并重新渲染。
- 页面顶部支持选择已有预处理轨迹的设备，避免用户手动猜测可查询设备号。
- 当 API 未启动、设备无数据或查询失败时，页面保留内置样本轨迹并显示错误提示。
- 页面重点标注数据库口岸定义和算法自动识别的边境穿越点。
- 自动边境点根据有效轨迹国家变化生成，中欧线路按 CN→KZ→RU→BY→PL 前进方向去抖，避免口岸附近 GPS 抖动显示多次来回穿越。

### 5.2 点位详情

点击每个轨迹点后显示：

- 原始点位序号
- 所属国家
- 采集时间
- 经度、纬度
- 电量
- 速度
- 具体地理位置查询结果

具体地理位置通过 OpenStreetMap Nominatim 反向地理编码查询。若网络不可用或查询失败，页面保留基础点位信息，并提示可放大地图查看附近地名。

### 5.3 国家分段

当前轨迹经过国家：

- 中国
- 哈萨克斯坦
- 俄罗斯
- 白俄罗斯
- 波兰

页面顶部展示每个国家的点位数量。当前过滤后点位数量：

- 中国：`35`
- 哈萨克斯坦：`71`
- 俄罗斯：`16`
- 白俄罗斯：`31`
- 波兰：`32`

### 5.4 重点口岸标注

当前标注的重点口岸/边境通道：

- 阿拉山口 / 多斯特克口岸：中国 - 哈萨克斯坦
- 奥伦堡方向哈俄口岸：哈萨克斯坦 - 俄罗斯
- 克拉斯诺耶 / 奥西诺夫卡口岸：俄罗斯 - 白俄罗斯
- 布列斯特 / 特雷斯波尔口岸：白俄罗斯 - 波兰

口岸在地图上使用橙色方形标记，并显示口岸名称标签。点击口岸标记后显示国家、关联轨迹点范围、说明和坐标。

### 5.5 GPS 漂移点识别与剔除

当前采用尖刺点检测算法：

- 计算相邻点之间的球面距离。
- 计算相邻点之间的时间差和平均速度。
- 对每个中间点 `B`，比较 `A -> B -> C` 与直接 `A -> C`。
- 若 `A -> B` 和 `B -> C` 都速度异常，且绕行比例明显过高，同时跳过 `B` 后速度恢复合理，则判定 `B` 为 GPS 漂移点。

当前阈值：

- `A -> B` 距离大于 `150 km`
- `B -> C` 距离大于 `150 km`
- `A -> B` 速度大于 `120 km/h`
- `B -> C` 速度大于 `120 km/h`
- 绕行比例大于 `3x`
- 跳过异常点后的 `A -> C` 速度小于 `80 km/h`

当前剔除点：

- 原始第 `110` 点
- 时间：`2026-07-05 22:31:42`
- 坐标：`37.537915, 55.865669`
- 判定原因：前段速度 `275.4 km/h`，后段速度 `142.4 km/h`，跳过该点后速度 `24.7 km/h`，绕行比例 `7.9x`

### 5.6 路线节点与运输时效

系统根据清洗后的轨迹点和重点口岸通道，自动形成路线：

`始发站（中国四川绵阳附近） → 阿拉山口/多斯特克 → 奥伦堡方向哈俄口岸 → 克拉斯诺耶/奥西诺夫卡 → 布列斯特/特雷斯波尔 → 目的站（波兰华沙附近）`

当前总时效：

- `20天13小时42分`

当前分段运输时效和口岸/边境等待时间：

| 区间 | 离开时间 | 到达时间 | 运输时效 | 口岸/边境等待 |
| --- | --- | --- | --- | --- |
| 始发站（中国四川绵阳附近） → 阿拉山口/多斯特克 | 2026-06-23 00:44:54 | 2026-06-25 18:42:02 | 2天17小时57分 | 5天21小时53分 |
| 阿拉山口/多斯特克 → 奥伦堡方向哈俄口岸 | 2026-07-01 16:35:03 | 2026-07-05 04:32:25 | 3天11小时57分 | 9小时59分 |
| 奥伦堡方向哈俄口岸 → 克拉斯诺耶/奥西诺夫卡 | 2026-07-05 14:32:13 | 2026-07-07 14:32:49 | 2天0小时0分 | 9小时59分 |
| 克拉斯诺耶/奥西诺夫卡 → 布列斯特/特雷斯波尔 | 2026-07-08 00:32:22 | 2026-07-08 10:31:21 | 9小时58分 | 5天1小时55分 |
| 布列斯特/特雷斯波尔 → 目的站（波兰华沙附近） | 2026-07-13 12:27:01 | 2026-07-13 14:27:02 | 2小时0分 | - |

等待时间计算规则：

- 为每个口岸配置中心点和判定半径。
- 轨迹首次进入口岸半径视为到达口岸。
- 轨迹最后一次离开口岸半径前的点视为离开口岸。
- 两者时间差视为该口岸/边境通道等待时间。
- 相邻节点之间的离开到到达时间差视为运输时效。

## 6. 非功能需求

- 页面应作为单个 HTML 文件独立交付。
- 在有网络时加载地图底图和反向地理编码。
- 即使具体位置查询失败，也必须显示基础轨迹和点位信息。
- 轨迹线应清晰可见，避免被底图或图层遮挡。
- 页面应支持本地 HTTP 服务访问，例如 `http://localhost:8765/trajectory-map-interactive.html`。


### 6.1 BrianHub bilingual UI standard

- GPS trajectory page supports only `zh-CN` and `en-US`.
- Initial locale priority follows BrianHub Portal: `X-BrianHub-Locale`, then shared `brianhub_locale` cookie, then default `en-US`.
- Unknown locale values fall back to `en-US`.
- The page provides a Chinese / English switcher; switching updates the current page immediately and writes `brianhub_locale` with `Path=/; Max-Age=31536000; SameSite=Lax`.
- Only UI chrome is translated: navigation, titles, buttons, forms, validation/error/empty messages, filters and table headers.
- Business data is not auto-translated, including device IDs, API route text, country/port names returned by backend, user input, reports and document bodies.
- Regression coverage: `node tools/test_gps_i18n.js` plus `node tools/test_gps_only_html_smoke.js`.

## 7. 已知限制

- 直接使用 `file://` 打开时，部分浏览器可能限制脚本、缓存或网络请求；推荐通过本地 HTTP 服务打开。
- 国家归属和口岸标注目前基于轨迹走向和点位区间判断，后续可接入国家边界 GeoJSON 做自动空间判断。
- 反向地理编码依赖 OpenStreetMap Nominatim，受网络和服务限制影响。
- 当前异常点算法主要识别明显尖刺式 GPS 漂移，对缓慢偏移或连续异常段需要后续增强。

## 8. 后续规划

- 接入国家边界数据，自动判断每个点所属国家。
- 支持上传或替换新的 Excel 轨迹文件。
- 支持更多查询维度，例如箱号、路线、订单号和运单号直接驱动地图。
- 支持全设备历史轨迹回填和增量采集。
- 支持报警、进出区事件和设备业务绑定查询。
- 增加异常点列表开关，可选择显示或隐藏剔除点。
- 支持导出清洗后的轨迹数据。
- 增加里程、停留时长、分国家里程统计。
- 将口岸点维护为可配置数据。
- 支持人工调整口岸等待半径和口岸节点匹配结果。

## 9. 版本与更新记录

详细更新记录维护在 [CHANGELOG.md](./CHANGELOG.md)。

当前版本：`v0.22.0`
## v0.28.0 补充 PRD - 卡车派送距离与还空运费模块

### 1. 模块目标

在 BrianHub GPS 页面中，将原 GPS 轨迹查询与卡车派送距离查询拆分为两个左侧导航模块。卡车派送距离模块用于按门点地址实时计算欧洲铁路站点到门点的卡车派送距离，并可选计算门点到还空地的回程距离，为业务报价提供快速参考。

### 2. 用户场景

- 业务人员输入欧洲门点地址，快速比较列日、杜伊斯堡、汉堡、华沙、马拉舍维奇、卡托维兹、巴塞罗那、布达佩斯、慕尼黑、克雷姆斯、布拉格、贝尔格莱德等站点到门点的卡车距离。
- 业务人员选择“还空地”后，系统按“铁路站点 -> 门点 -> 还空地”计算全程公里数。
- 如果不选择“还空地”，系统按“铁路站点 -> 门点”结束。
- 页面展示全程距离、预计时长和卡车运费，辅助 `1x40HQ`、`20-23` 吨货重场景下的报价判断。

### 3. 功能需求

- 左侧模块导航包含“卡车距离”和“GPS轨迹”，并支持折叠菜单。
- 卡车距离模块提供门点地址输入框，支持普通地址和坐标输入。
- 门点地址可能遍布欧洲，后端需要先进行地址清洗和多候选生成，再调用地理编码服务：
  - 去除 VAT、联系人、电话等非地址噪声。
  - 修正常见国家名拼写和别名，例如 `Netherlad`、`Nederland`、`Deutschland`、`Czechia`。
  - 修复换行断词和常见缩写，例如 `GHIMB AV`、`Str.`、`Nr23`、`Bl.Hala5`。
  - 支持按欧洲邮编规则生成候选，包括 UK、NL、DE、FR、ES、IT、PL、CZ、SK、EE、BE、AT、HU、RO、北欧、波罗的海和巴尔干常见格式。
  - 查询候选顺序为：清洗后原地址、单独邮编或邮编城市、去公司名前缀地址、街道+邮编+城市+国家、城市+国家兜底。
- 卡车距离模块提供“还空地”下拉框，下拉选项来自后端 `truck_stations` 数据库表。
- 欧洲及中欧班列常用站点坐标以用户提供的《中欧班列常用目的站地址及坐标汇总（完整版）》为准；代码内置站点仅作为数据库不可用时的兜底。
- `truck_stations` 表需保存 `slug`、`name`、`city`、`country_code`、`station_group`、`terminal`、`address`、`lat`、`lng`、`source_note`、`sort_order`、`active`，便于复核和后续维护。
- `station_group` 用于按门点国家自动筛选候选铁路站点：
  - 欧洲门点匹配 `europe` 站点。
  - 中亚/跨里海门点匹配 `central_asia` 站点。
  - 俄罗斯门点匹配 `russia` 站点。
  - 白俄罗斯门点匹配 `belarus` 站点。
  - 无法判断国家时保留全站点兜底。
- 站点范围包含 30 个常用目的站：杜伊斯堡、马拉舍维奇、汉堡、蒂尔堡、贝尔格莱德、布达佩斯、克雷姆斯、伦敦 Barking、Sławków/Katowice、布拉格、华沙、慕尼黑、米兰、列日、Česká Třebová、巴塞罗那、Vorsino、Selyatino、Bely Rast、Elektrougli、Khovrino、Kolyadichi、Yekaterinburg、Shushary、Kleshchikha、Kazan、Almaty、Poti、Baku、Minsk Kolodishchi。
- 查询接口为 `GET /api/truck-distance`：
  - 必填：`address` 或 `lat/lon`
  - 可选：`return_station`
- 不传 `return_station` 时，返回距离为站点到门点的距离。
- 传入 `return_station` 时，返回距离为站点到门点再到还空地的距离之和。
- API `meta` 返回 `stationGroup`、`stationCount` 和 `totalStationCount`，用于确认当前按哪个区域组匹配。
- 结果表展示列为：序号、站点、公里、时间、卡车运费。
- “来源”列不再展示给业务用户。
- 地图显示所有站点到门点的路线；选择还空地时，路线包含门点到还空地段。
- 点击任一站点行、站点标记或路线时，地图聚焦并高亮该路线。
- 底图支持免注册切换：Esri 街道、Esri 卫星、OpenStreetMap 备用。

### 4. 运费计算

当前版本按估算模型展示卡车全程运费，单位为欧元：

- 适用箱型：`1x40HQ`
- 参考货重：`20-23` 吨
- 运费规则存储在 `truck_freight_rules` 数据库表，代码内置规则仅作为数据库不可用时的兜底。
- 运费模型：
  - 起步基础费用：`120 EUR`
  - 最低费用：`450 EUR`
  - 距离分段单价：`0-250 km`、`251-600 km`、`601-1200 km`、`1200+ km` 分别使用不同 EUR/km。
  - 选还空地时，模型拆分为重柜段和还空段；重柜段按 100% 公里费计算，还空段按 `empty_return_multiplier=0.65` 计算。
  - 起运站、门点、还空地涉及多个国家代码时，叠加 `cross_border_surcharge=120 EUR` 固定跨境操作成本。
  - 燃油附加费按 `linehaulEur * fuel_surcharge_rate` 计算；当前数据库 seed 仅启用公开可核对的欧洲燃油规则：欧洲默认 `13%`，荷兰 `25%`。
  - 城市/低排放区费用仅在有明确欧元票价且可通过门点文本判断时计入总价；当前仅米兰 Area C 命中 `Milan/Milano` 时计入 `7.5 EUR`。
  - 伦敦拥堵费、巴黎 ZFE/低排放区等因币种、区域边界、车辆合规条件或罚款口径不适合在询价初期自动计入，仅作为 `cityAccessNotes` 提示。
  - 等待费不在询价初期模型中自动计算；如供应商报价有 `2小时免费等待` 和超时费，应在最终报价条款中单独写清。
  - 按目的地、起运站和还空地国家代码叠加区域系数；英国、爱尔兰、瑞士、北欧、南欧、东南欧、波罗的海等区域有不同成本系数。
  - 对英国、爱尔兰、挪威、瑞士等特殊区域叠加固定附加费。
- API 返回 `freightEur` 和 `freightModel`，其中 `freightModel` 包含重柜公里、还空公里、计费公里、线路基础运费、燃油附加费、城市访问费、分段单价、区域系数、国家附加费、跨境附加费、最低费用和估算说明。

该公式用于没有供应商报价表时的快速业务参考，不等同于最终供应商报价。后续如有实际承运商分区价、最低消费、跨境附加费、旺季附加费，可新增供应商报价表并优先匹配真实报价，匹配不到时再使用本估算模型兜底。

### 4.1 供应商报价观察样本

- `truck_supplier_quote_observations` 表用于记录供应商反馈报价与系统当时估算结果。
- 该表只做样本沉淀和后续校准依据，不参与当前 `freightEur` 自动计算。
- 当前已记录三条供应商反馈样本，均为 `record_only`：
  - 门点：`KESK-SÕJAMÄE 7, 11415, TALLINN, ESTONIA`
  - 箱型/重量：`1x40HC`，`20 tons`
  - 供应商基础卡车报价：`2495 EUR`
  - 当时系统估算：`3160 EUR`
- Hamburg -> Süderholz -> Hamburg 还空样本：
  - 门点：`Pommerndreieck 2a, 18516 Süderholz, Germany`
  - 供应商基础卡车报价：`1300 EUR`
  - 当时系统估算：`890 EUR`
- Duisburg -> Duisburg local drayage 还空样本：
  - 门点：`Im Freihafen 4, 47138 Duisburg, Germany`
  - 供应商基础卡车报价：`625 EUR`
  - 当时系统估算：`450 EUR`
- 供应商报价可能包含供应商利润、短期车队资源、当天市场供需、车架/场站窗口等因素；单条样本不得直接反推全局参数。
- 供应商报价中的 T-1、额外 HS Code、保证金、TRB Handling Fee、超时等待等条件费用记录在 `extra_charges_note`，不并入基础卡车价。

### 4.2 地图瓦片缓存

- 页面注册 `sw.js` Service Worker，对已浏览和用户手动缓存的地图瓦片进行本地缓存。
- 地图区域提供“缓存当前地图”按钮，缓存当前视野在相邻缩放层级的有限瓦片。
- 单次缓存数量限制为 `90` 张瓦片，避免对公开地图服务造成批量下载压力。
- 当前实现不是全欧洲离线地图包；仅用于弱网或重复查看同一区域时加速加载。

### 5. 部署要求

- 前端静态页面部署路径：`/root/apps/gps/web/index.html`。
- 后端 API 部署路径：`/root/apps/gps/scripts/gps_query_api.py`。
- BrianHub 网关访问的 API 必须由 systemd 服务 `gps-query-api-edge.service` 托管，监听 `172.19.0.1:8015`。
- 不允许用手动 `nohup` 后台进程长期承载线上网关 API，避免端口占用导致 systemd 服务重启失败。
- 每次上线后需要更新 `docs/CHANGELOG.md`，并同步到 VPS `/root/apps/gps/docs/CHANGELOG.md`。

### 6. 验证标准

- `https://www.brianhub.net/gps/` 返回 HTTP `200`，页面包含 `truck-return-station`。
- `https://www.brianhub.net/gps/api/truck-stations` 返回站点列表。
- `GET /gps/api/truck-distance?address=...` 返回 `distanceKm`、`durationHours`、`freightEur`。
- 带 `return_station=duisburg` 查询时，返回 JSON 包含 `returnStation.slug=duisburg`。
- `gps-query-api-edge.service` 状态为 `active` 且 `enabled`。
