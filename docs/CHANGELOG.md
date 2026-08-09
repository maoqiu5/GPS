# GPS 轨迹可视化项目更新记录

本文档用于记录 GPS 轨迹可视化项目每次功能更新、修复和算法调整。


## v0.31.0 - 2026-08-08

### Added

- GPS trajectory page now follows the BrianHub unified bilingual standard for UI text, supporting only `zh-CN` and `en-US`.
- Added Chinese / English switcher that immediately updates UI text and writes the shared `brianhub_locale` cookie with `Path=/`, `Max-Age=31536000`, and `SameSite=Lax`.
- Added `tools/test_gps_i18n.js` regression coverage for locale priority, cookie behavior, fallback handling and Chinese dictionary encoding.

### Notes

- Translation is limited to UI chrome. Business data from API responses, device IDs, route text, port/country names and reports remain unchanged.

### Verification

- `node tools/test_gps_i18n.js` passed.
- `node tools/test_gps_only_html_smoke.js` passed.

## v0.30.0 - 2026-07-25

- 铁路运价结果区移除无直接改价意义的“供应商/市场参考”名单，改为“定价策略”面板：预测模式展示公里模型价、市场系数后价格、公共报价锚点、TC 执行价调整、锚点权重和暂未纳入自动改价的外部来源。
- 新增铁路供应商/市场参考源 `rail-supplier-sources-2026-07.json`，记录 TransContainer、UTLC ERA、FESCO、RZD Logistics、TransSinergia、Sinotrans、DB Cargo Eurasia、ERAI Index、RZD-Partner 等来源；这些来源作为后台采集与后续校准清单，前台只在定价策略备注中提示暂未纳入自动改价。

### 修复

- TransContainer 满洲里/后贝加尔 `40HQ` 当前执行价规则：公共报价锚点按 `-200 USD/柜` 校准，仅作用于 `40HQ`，用于降低 Vorsino、KLESHCHIHA 等 TC 满洲里预测偏差。
- GPS 左侧目录栏折叠优化：折叠后保留模块图标、按钮 title 和折叠状态记忆；进入项目后安装浏览器返回 guard，减少 Back 直接回到门户登录页的问题。
- 数据来源记录：今天导入的公共报价单和散点报价均标记为 `TransContainer`，写入铁路报价 JSON 的 `meta.operatorName/operatorCode`。
- 路线公里预测新增正式报价锚点校准：报价单已有站点优先贴近当前报价，常用莫斯科枢纽站点加入高频/拼班列规模折扣，修正 Vorsino 等站点被散点公里模型高估的问题。
- 路线公里预测新增市场系数模型 `rail-market-factors-2026-07.json`，接入方向、COC/SOC、换装口岸、区域和 UTLC 哈俄白过境平台/车板系数；模型来源记录 Delo/Global Ports、FESCO、TransContainer、UTLC ERA 公开信息。
- 修复路线公里预测中报价单站点运输类型为空的问题；`predictionOnly` 站点现在会使用合并数据里的 `ownerships` 填充 `COC/SOC` 下拉。
- 路线公里预测模式新增正式报价单站点候选：将报价单中带路线坐标的目的站按换装口岸合并进预测数据，散点模型仍只使用有价格样本训练。
- 铁路运价模块口岸文案调整：`接驳口岸` 改为 `换装口岸`；口岸下拉、结果摘要和路线图中 `Dostyk/Altynkol` 统一显示为中文 `多斯特克/阿腾科里`。
- 铁路运价模块加载优化：正式报价和散点预测数据并行加载，历史运踪路径改为后台懒加载；移除基础铁路 JSON 的 `no-store`，减少每次打开模块的阻塞请求。
- Service Worker 静态缓存升级到 `gps-static-v4`，激活时清理旧 `gps-static-*` 缓存；HTML 页面改为网络优先，避免线上已更新但浏览器继续显示旧 GPS 页面。

### 新增

- GPS 前端新增“铁路运价”模块，支持俄线铁路运价内部查价和路线公里预测。
- 新增公共报价单结构化数据、散点报价样本数据和历史运踪路线样本数据。
- 铁路运价预测模式支持按目的站、站编、箱型、COC/SOC、柜量和 COC 箱使费计算估算运费。
- 目的站和站编改为独立输入框，均支持自动提示；输入中文站名、英文站名或站编均可匹配目的站。
- 结果面板和地图联动显示估算线路公里、预测 USD/km、置信度、样本报价和历史运踪样本站序。
- 卡车距离新增市场参考层：`truck_market_sources`、`truck_market_rate_snapshots`，记录 DHL surcharge、Cargoboard API、Upply Benchmark、TIMOCOM Barometer、Trans.eu API 等来源；页面展示来源/快照和燃油参考，不自动调价。
- 卡车页面新增“市场参考”模块和路线运费拆解面板；点击任一站点路线后可查看当前估价的重柜/还空公里、计费公里、公里单价、燃油、跨境和区域系数。
- 市场参考模块新增指标类型筛选；卡车路线运费拆解新增“复制内部说明”按钮，复制站点、场站、公里、模型价和费用拆解。

### 说明

- 路线公里预测不调用正式公共报价单价格，仅基于散点报价样本和估算线路公里做内部参考。
- 散点报价样本有效期为 `2026/05/31`，不作为当前正式客户报价。
- 卡车市场参考层只作为外部锚点和后续接入准备；需要具体 lane benchmark 或账号 API 后，才进入自动运费校准。

### 验证

- `node tools/test_rail_calculator.js` 通过。
- `node tools/test_rail_html_smoke.js` 通过。

## v0.29.0 - 2026-07-23

### 新增

- 新增 `truck_stations` SQLite 表，用于存储中欧班列常用目的站、场站地址、经纬度、来源说明和启用状态。
- 新增 `truck_freight_rules` SQLite 表，用于存储 `1x40HQ`、`20-23` 吨卡车运费估算规则，包括基础费、最低费、距离分段单价、国家系数和附加费。
- 按用户提供的《中欧班列常用目的站地址及坐标汇总（完整版）》初始化 30 个站点，站点资料以该表为准。
- `truck_stations` 新增 `station_group` 字段，支持按门点国家自动匹配欧洲、中亚/跨里海、俄罗斯、白俄罗斯站点组。
- 卡车距离页面新增“站点区域”切换按钮：自动、欧洲、中亚、俄罗斯、白罗斯；手动选择时通过 `station_group` 参数覆盖自动门点国家匹配。
- 新增 `Tbilisi / 第比利斯` 站点，归入 `central_asia`，场站按 Tbilisi Dry Port 记录。
- 复核 `站点明细整理.xlsx` 后，新增 6 个高置信站点：Rotterdam RSC、Dunajská Streda、East-West Gate Fényeslitke、Altynkol、Tashkent Chukursay、Aktau Port；仅采用可追溯到官方场站 GPS/官方地址加明确坐标来源的记录。
- 第二批新增 6 个欧洲高频节点：Łódź Spedcont、Mannheim DUSS、Nürnberg TriCon、Neuss Contargo、Bremerhaven NTB、Wilhelmshaven JadeWeserPort；保留 `source_note` 标明为官网地址加 Nominatim 门牌/公司/港区级地理编码，未用 Excel 城市中心坐标覆盖。

### 调整

- `GET /api/truck-stations` 改为优先读取数据库 `truck_stations`，数据库不可用或为空时才使用代码兜底站点。
- `GET /api/truck-distance` 改为使用数据库站点和数据库运费规则计算距离、还空路线和卡车运费。
- `GET /api/truck-distance` 现在会先判断门点国家：欧洲门点只计算欧洲站点，中亚/跨里海门点只计算 Almaty、Poti、Baku，俄罗斯门点只计算俄罗斯站点，白俄罗斯门点只计算白俄罗斯站点；无法判断时保留全站点兜底。
- `GET /api/truck-distance` 新增 `station_group` 参数，支持 `auto/europe/central_asia/russia/belarus`，并在 `meta.stationGroupMode` 返回当前为自动还是手动模式。
- 在暂无供应商报价表的情况下，卡车运费估算模型升级为重柜段/还空段分开计费：还空段按 `65%` 公里费估算，跨国家代码路线新增 `120 EUR` 固定跨境操作成本，并在 `freightModel` 返回重柜公里、还空公里、计费公里和跨境附加费明细。
- 基于公开资料新增燃油附加费和城市访问规则：欧洲燃油默认 `13%`、荷兰 `25%`，按线路基础运费计算；米兰 Area C 命中 `Milan/Milano` 时计入 `7.5 EUR`。伦敦拥堵费和巴黎 ZFE/低排放区因币种、区域边界和车辆合规条件不确定，仅返回提示，不自动计入总价。
- 按业务要求，询价初期不自动加入等待费；供应商报价中的 `2小时免费等待` 和超时等待费后续在报价条款中单独写明。
- 新增 `truck_supplier_quote_observations` 表，仅用于记录供应商反馈报价样本，不参与当前自动调价；已记录 Mala -> Tallinn -> Mala、Hamburg -> Süderholz -> Hamburg、Duisburg local drayage 三条样本，状态均为 `record_only`。样本备注中记录供应商利润、短期市场容量、车架/场站窗口等可能影响因素，避免用单个供应商报价直接反推全局参数。
- 修正列日、伦敦、米兰、华沙等站点为用户资料中的具体场站坐标；新增蒂尔堡、Česká Třebová、俄罗斯/白俄罗斯、中亚和跨里海通道常用站点。

## v0.28.0 - 2026-07-23

### 优化

- 页面布局改为地图优先：左侧控制栏收窄，右侧地图占比扩大，卡车距离结果表更紧凑。
- 卡车站点标记改为醒目的圆形 `S` 图标，门点显示 `D`，还空地显示 `R`，选中路线时站点图标放大并高亮。
- 将站点坐标从城市中心升级为具体铁路/多式联运终端坐标，并为站点增加 `terminal`、`countryCode`、`sourceNote` 字段。
- 新增 `London / 伦敦` 和 `Milan / 米兰` 两个站点，分别采用 London Gateway rail terminal 和 Milano Segrate intermodal terminal 区域坐标。
- 卡车运费从固定线性单价升级为分段估算模型，新增距离分段单价、区域系数、特殊区域附加费，并在 API 返回 `freightModel` 明细。
- 新增 `web/sw.js` Service Worker 和“缓存当前地图”按钮，对已浏览或手动缓存的地图瓦片进行本地缓存；单次缓存限制为 `90` 张，避免批量抓取公开地图服务瓦片。

### 修复

- 修复英国门点地址解析失败问题。带完整 UK postcode 的地址会优先使用 `postcodes.io` 解析邮编坐标，避免 Nominatim 将 `B98 9FL` 等邮编错配或解析失败。
- 已验证 `Avon Freight Group Limited Unit 2, Redditch Gateway South, Coventry Highway, Redditch, B98 9FL` 可成功解析为 `52.307591, -1.876526`，并返回卡车距离与 `freightEur`。
- 修复荷兰地址中公司/仓库名前缀和国家名拼写错误导致的解析失败；已验证 `Edelman Central Warehouse, Tasveld 1 3417 XS Montfoort,The Netherlad` 可解析到 `Tasveld 1, Montfoort`。
- 修复地址尾部 `VAT ...` 噪声导致的解析失败；已验证 `KESK-SÕJAMÄE 7, 11415, TALLINN, ESTONIA,VAT EE100596760` 可解析到 `Kesk-Sõjamäe 7, Tallinn`。
- 修复换行断词导致 `GHIMBAV` 被拆成 `GHIMB AV` 后无法触发罗马尼亚地址候选的问题；已验证断行版 `BRASOV, ORS.GHIMBAV, Str. Hermann Oberth, Nr23, Bl.Hala5, locatia 1` 可解析到 `Strada Hermann Oberth 23, Ghimbav`。
- 将欧洲门点地址解析升级为通用候选生成流程，新增国家别名修正、公司名前缀剥离、VAT/联系人/电话噪声清理，以及 UK、NL、DE、FR、ES、IT、PL、CZ、SK、EE、BE、AT、HU、RO、北欧、波罗的海和巴尔干常见邮编格式候选。

### 新增

- 卡车派送距离模块新增“还空地”下拉选项，站点列表复用 `TRUCK_STATIONS`。
- `GET /api/truck-distance` 新增 `return_station` 参数；选择还空地时，全程距离按“铁路站点 -> 门点 -> 还空地”计算，不选择时仍按“铁路站点 -> 门点”结束。
- 卡车距离结果表移除“来源”列，新增“卡车运费”列，按 `1x40HQ`、`20-23` 吨货重的全程公里数估算欧元费用。

### 上线

- 前端静态文件已发布至 VPS：`/root/apps/gps/web/index.html`。
- 查询 API 已发布至 VPS：`/root/apps/gps/scripts/gps_query_api.py`。
- BrianHub 网关访问的 API 实例继续由 `gps-query-api-edge.service` 托管，不使用手动后台进程长期承载线上流量。

### 验证

- `https://www.brianhub.net/gps/` 已包含 `truck-return-station` 前端下拉逻辑。
- `https://www.brianhub.net/gps/api/truck-distance?address=45.6877%2C25.51944&return_station=duisburg` 返回 HTTP `200`。
- 线上返回 JSON 已包含 `returnStation` 和 `freightEur` 字段。
- `gps-query-api-edge.service` 状态为 `active (running)`，主进程监听 `172.19.0.1:8015`。

## v0.27.0 - 2026-07-22

### 新增

- 新增 `gps_border_crossings` 表，结构化保存设备自动识别出的国家/边境穿越点。
- 新增 `GET /api/border-crossings?device_id={设备号}`，可单独查看设备边境穿越点。
- `GET /api/trajectory` 返回 `borderCrossings`，页面用蓝色菱形重点标注自动边境节点。
- 页面图例新增“自动边境”，点击边境节点可查看穿越国家、轨迹点范围、匹配口岸、距离和置信度。

### 优化

- 边境穿越算法根据相邻有效轨迹点的国家归属变化自动生成边境节点。
- 对阿拉山口附近的国境阈值抖动做去抖：中欧线路只保留 CN→KZ→RU→BY→PL 前进方向的首次穿越，避免 GPS 抖动生成多次来回穿越。
- 预处理算法版本升级为 `trajectory-precompute-v6`。

### 验证

- VPS 已重新预处理 `48` 台有轨迹设备、`16390` 个轨迹点。
- `https://www.brianhub.net/gps/api/border-crossings?device_id=61007408` 返回 `4` 个主边境节点：CN→KZ、KZ→RU、RU→BY、BY→PL。
- `https://www.brianhub.net/gps/api/trajectory?device_id=61007408&limit=5000` 返回 `trajectory-precompute-v6`、边境节点 `4` 个、口岸 `4` 个、路线分段 `5` 段。
- `https://www.brianhub.net/gps/api/health` 返回 `border_crossings=87`。
- `https://www.brianhub.net/gps/` 已包含 `borderCrossings`、`自动边境` 和 `border-label` 前端渲染逻辑。

## v0.26.0 - 2026-07-22

### 优化

- 新增 `gps_port_definitions` 表，将关键口岸/边境通道定义从代码常量迁移为数据库配置。
- 预处理脚本改为优先读取 `gps_port_definitions`，未建表或无数据时才使用代码默认口岸兜底。
- `GET /api/trajectory?use_cache=0` 的实时计算路径也改为读取数据库口岸定义。
- 新增 `GET /api/port-definitions`，用于查看当前启用的口岸定义。
- 预处理算法版本升级为 `trajectory-precompute-v4`。

### 验证

- VPS 已应用新版 schema，`gps_port_definitions` 已生成 `4` 条默认中欧线路口岸定义。
- VPS 已重新预处理 `48` 台有轨迹设备、`16390` 个轨迹点。
- `https://www.brianhub.net/gps/api/port-definitions` 返回 `4` 条启用口岸。
- `https://www.brianhub.net/gps/api/trajectory?device_id=61007408&limit=5000` 返回 `trajectory-precompute-v4`、命中口岸 `4` 个、路线分段 `5` 段。

## v0.25.0 - 2026-07-22

### 新增

- 新增 `GET /api/trajectory-devices?limit=...`，返回已有预处理轨迹缓存的设备清单。
- 页面顶部新增“有轨迹设备”下拉选择，可直接选择数据库中已有轨迹的设备并自动查询。

### 验证

- `https://www.brianhub.net/gps/api/trajectory-devices?limit=5` 返回 `5` 台有轨迹设备样本。
- `https://www.brianhub.net/gps/` 已包含 `device-quick-select` 和 `/api/trajectory-devices` 前端加载逻辑。
- `https://www.brianhub.net/gps/api/trajectory?device_id=61007408&limit=5000` 仍返回 `precomputed=True`、`structuredRoute=True`、展示点 `329` 个。

## v0.24.0 - 2026-07-22

### 新增

- 新增 `GET /api/route-summary?device_id={设备号}`，直接从 `gps_port_passages` 和 `gps_route_segments` 读取结构化口岸/路线时效结果。
- `GET /api/trajectory?device_id=...` 命中缓存时，自动使用结构化表覆盖返回的 `ports` 和 `route`，并在 `meta.structuredRoute` 标记是否使用结构化路线。

### 验证

- `https://www.brianhub.net/gps/api/route-summary?device_id=61007408` 返回命中口岸 `4` 个、路线分段 `5` 段。
- `https://www.brianhub.net/gps/api/trajectory?device_id=61007408&limit=5000` 返回 `precomputed=True`、`structuredRoute=True`、口岸 `4` 个、路线分段 `5` 段。
- VPS 本机 `127.0.0.1:8015` 调试 API 与 BrianHub 网关 `172.19.0.1:8015` API 均已更新到新版。

## v0.23.0 - 2026-07-22

### 上线

- GPS 轨迹页面上线到 BrianHub 网关：`https://www.brianhub.net/gps/`。
- 页面静态文件发布到 VPS：`/root/apps/gps/web/index.html`。
- BrianHub Caddy 网关新增 `/gps` 静态页面路由和 `/gps/api/*` API 反代。
- 页面 API 地址改为生产环境自动使用 `/gps/api`，本地调试仍使用 `http://127.0.0.1:8015`。
- 新增 `gps-query-api-edge.service`，由 systemd 托管 Caddy 网关访问的 GPS API 实例，并设置开机自启。

### 验证

- `https://www.brianhub.net/gps/` 返回 HTTP `200`。
- `https://www.brianhub.net/gps/api/health` 返回健康 JSON。
- `https://www.brianhub.net/gps/api/trajectory?device_id=61007408&limit=5000` 返回 `precomputed=True`、`trajectory-precompute-v3`、展示点 `329` 个。
- `gps-query-api-edge.service` 状态为 `active`、`enabled`。

## v0.22.0 - 2026-07-22

### 新增

- SQLite 新增 `gps_port_passages`，结构化保存设备经过口岸/边境通道、到达/离开时间和等待时长。
- SQLite 新增 `gps_route_segments`，结构化保存始发站 - 口岸 - 目的站的每一段运输时效。
- 预处理脚本在生成轨迹缓存时同步写入口岸通道和路线分段表。

### 调整

- 预处理算法版本升级为 `trajectory-precompute-v3`。
- `GET /health` 增加 `port_passages` 和 `route_segments` 统计。

### 执行结果

- VPS 已完成 `trajectory-precompute-v3` 正式预处理：`48` 台有轨迹设备、`16390` 个轨迹点。
- `gps_trajectory_cache` 生成 `48` 条设备缓存。
- `gps_port_passages` 生成 `192` 条口岸通道记录，其中 `91` 条命中经过。
- `gps_route_segments` 生成 `139` 条始发站 - 口岸 - 目的站分段记录。
- 本机隧道验证 `GET /api/trajectory?device_id=61007408` 返回 `precomputed=True`，算法版本 `trajectory-precompute-v3`，展示点 `329` 个。

## v0.21.0 - 2026-07-22

### 优化

- 将国家归属从“按点序号推断”改为“按中欧线路经纬度走廊判断”。
- 预处理算法版本升级为 `trajectory-precompute-v2`。
- 国家分段、国家点数和轨迹颜色将随预处理缓存统一生成。

### 说明

- 当前采用中欧线路走廊阈值，适用于中国 - 哈萨克斯坦 - 俄罗斯 - 白俄罗斯 - 波兰方向。
- 后续可替换为国家边界 GeoJSON 点面匹配，不影响页面 API 结构。

### 执行结果

- VPS 已重新预处理 `48` 台设备、`16390` 个轨迹点。
- `gps_trajectory_cache` 全部升级为 `trajectory-precompute-v2`。
- 样本设备 `61007408` 缓存命中 `precomputed=True`，国家统计为：中国 `46`、哈萨克斯坦 `58`、俄罗斯 `17`、白俄罗斯 `32`、波兰 `176`、未知 `0`。

## v0.20.0 - 2026-07-22

### 新增

- 新增轨迹预处理脚本：`scripts/gps_precompute_trajectory.py`。
- SQLite 新增 `gps_trajectory_cache`，用于缓存页面可直接渲染的轨迹 JSON。
- SQLite 新增 `gps_precompute_runs`，记录每次预处理运行结果。

### 调整

- `GET /api/trajectory?device_id=...` 默认优先读取预处理缓存。
- 如果缓存不存在，可自动回退到实时计算；传 `use_cache=0` 可强制实时计算。
- 预处理时同步更新 `hbt_track_points.is_valid` 和 `is_drift_candidate`。

### 目标

- 将 GPS 漂移点识别、口岸命中、路线节点和时效计算从页面查询链路前移到 VPS 预处理层。
- 降低页面查询延迟，并让不同入口使用同一份计算结果。

### 执行结果

- VPS dry-run 设备 `61005610` 成功：原始 `502` 点，展示 `502` 点，漂移 `0` 点。
- VPS 正式预处理成功：`48` 台有轨迹设备，`16390` 个轨迹点。
- `gps_trajectory_cache` 生成 `48` 条设备缓存。
- `hbt_track_points.is_drift_candidate=1` 共 `2` 个点。
- 查询 API 重启后，`GET /health` 返回 `trajectory_cache=48`。
- 本机隧道验证 `GET /api/trajectory?device_id=61007408` 返回 `precomputed=True`，算法版本 `trajectory-precompute-v1`。

## v0.19.0 - 2026-07-22

### 执行结果

- 继续执行 VPS 真实增量拉取，轨迹窗口扩大到 `200`。
- 本轮轨迹窗口成功 `200` 个，失败 `0` 个，接口报告 `16309` 个点。
- 当前有轨迹设备数增加到 `48` 个。
- 轨迹点累计增加到 `16390` 条。
- 成功轨迹窗口累计 `267` 个，失败窗口 `0` 个。
- 当前状态快照累计 `904` 条。
- 进出区事件累计 `247` 条。

### 日志

- `logs/hbt_incremental_20260722-124336.log`
- `logs/hbt_current_status_20260722-124336.log`
- `logs/hbt_track_incremental_20260722-124336.log`
- `logs/hbt_alarm_incremental_20260722-124336.log`
- `logs/hbt_site_events_incremental_20260722-124336.log`

## v0.18.0 - 2026-07-22

### 修复

- 修复页面顶部设备号查询按钮未绑定提交事件的问题。
- 现在输入设备号并点击“查询”会实际调用 `GET /api/trajectory?device_id=...`。

### 验证

- 本地 HTTP 页面重新加载后，查询 `61005610` 成功刷新为 `496` 个轨迹点。
- API 健康检查和 SSH 隧道保持正常。

## v0.17.0 - 2026-07-22

### 新增

- 记录 BrianHub 统一部署约定：使用 `~/.ssh/cnstock_vps` 登录 `root@192.236.235.229`。
- 补充 GPS 项目目录、SQLite 路径和本地页面调试隧道方式。

### 发布

- 已将新版 `scripts/gps_query_api.py` 同步至 VPS `/root/apps/gps/scripts/gps_query_api.py`。
- VPS 已启动查询 API：`127.0.0.1:8015`。
- 本机已建立 SSH 隧道：`127.0.0.1:8015 -> VPS 127.0.0.1:8015`。

### 验证

- VPS `/health` 返回：设备 `226`、轨迹点 `925`、进出区事件 `245`、报警 `0`。
- 本机通过隧道查询 `61005610` 成功，返回 `496` 个轨迹点。
- 可测试设备号：`61005610`、`61006245`、`61007408`。

## v0.16.0 - 2026-07-22

### 新增

- `trajectory-map-interactive.html` 顶部新增按设备号查询功能。
- `scripts/gps_query_api.py` 新增 `GET /api/trajectory?device_id={device_id}` 页面聚合接口。
- 接口返回地图渲染所需的轨迹点、剔除漂移点、重点口岸、始发站、目的站、总时效、分段运输时效和口岸等待时间。

### 调整

- 页面默认连接 `http://127.0.0.1:8015` 的本地查询 API。
- 查询失败或 API 未启动时，页面继续显示内置样本轨迹，避免地图空白。
- 更新 `docs/GPS_BINDING_QUERY_API.md` 和 `docs/PRD.md`，记录数据库接入与设备号查询能力。

### 验证

- `scripts/gps_query_api.py` Python 编译检查通过。
- `trajectory-map-interactive.html` 内联 JavaScript 语法检查通过。
- 使用临时 SQLite 和测试轨迹点启动本地 API，`GET /api/trajectory?device_id=61007408` 返回 HTTP 200。

## v0.15.0 - 2026-07-22

### 新增

- 新增业务绑定与查询 API：`scripts/gps_query_api.py`。
- 新增 API 使用文档：`docs/GPS_BINDING_QUERY_API.md`。

### 接口

- `GET /health`
- `GET /devices`
- `GET /bindings`
- `POST /bindings`
- `GET /tracks/device/{device_id}`
- `GET /tracks/container/{container_no}`
- `GET /site-events`
- `GET /routes/{route_id}/current-devices`

### 验证

- 本地使用 VPS SQLite 副本验证通过。
- 本地创建测试绑定后，按箱号查询轨迹、按箱号查询进出区、按路线查询当前设备均通过。
- VPS 临时启动验证通过，真实库健康检查返回：设备 `226`、轨迹点 `925`、进出区事件 `245`、报警 `0`、绑定 `0`。

## v0.14.0 - 2026-07-22

### 新增

- `scripts/hbt_backfill_tracks.py` 新增 `--order-by` 参数。
- `scripts/hbt_run_incremental.sh` 新增 `TRACK_ORDER_BY`，默认 `online_recent`。
- `scripts/hbt_gps_env.example` 增加 `TRACK_ORDER_BY=online_recent`。

### 执行结果

- 第二轮 VPS 扩大增量成功：轨迹 `50` 窗口、报警 `4` 窗口、进出区 `1` 窗口全部成功。
- 第二轮按设备号排序返回 `0` 个新轨迹点，确认前序设备存在大量空窗口。
- 活跃设备优先排序真实验证成功：`10` 个轨迹窗口返回 `865` 个轨迹点，失败 `0`。
- 执行后轨迹点累计 `925` 条，成功轨迹窗口累计 `67` 个，失败窗口 `0` 个。

## v0.13.0 - 2026-07-22

### 新增

- 新增小流量正式增量采集执行报告：`docs/HBT_INCREMENTAL_REAL_RUN_REPORT.md`。
- 新增本轮正式执行日志副本：
  - `logs/hbt_incremental_20260722-054906.log`
  - `logs/hbt_current_status_20260722-054906.log`
  - `logs/hbt_track_incremental_20260722-054906.log`
  - `logs/hbt_alarm_incremental_20260722-054906.log`
  - `logs/hbt_site_events_incremental_20260722-054906.log`

### 执行结果

- VPS 小流量正式增量采集成功。
- 当前状态刷新 `226` 台设备，新增一轮 `226` 条快照。
- 轨迹增量执行 `5` 个窗口，成功 `5` 个，返回 `0` 个新点。
- 报警增量执行 `2` 个窗口，返回 `0` 条报警。
- 进出区增量执行 `1` 个窗口，返回并写入 `245` 条事件。
- 执行后 `hbt_site_events` 累计 `245` 条，`hbt_device_snapshots` 累计 `452` 条。

## v0.12.0 - 2026-07-22

### 新增

- `scripts/hbt_collect_events.py` 新增 `--use-cursors`。
- `scripts/hbt_run_incremental.sh` 默认对报警和进出区增量启用事件游标。

### 验证

- 本地编译验证通过。
- 本地总控 dry-run 验证通过。
- VPS 总控 dry-run 验证通过。
- VPS 样本设备事件游标 dry-run 验证通过：报警从上次成功时间前 `5` 分钟续跑，进出区游标晚于截止时间时正确跳过。

## v0.11.0 - 2026-07-22

### 新增

- 新增增量采集总控脚本：`scripts/hbt_run_incremental.sh`。
- 新增 VPS 环境变量模板：`scripts/hbt_gps_env.example`。
- 新增增量采集总控运行手册：`docs/HBT_INCREMENTAL_RUNNER_RUNBOOK.md`。

### 验证

- 本地 dry-run 验证通过。
- VPS dry-run 验证通过。
- VPS 真实库规划到 `226` 台设备。
- 当前状态刷新规划为 `5` 批。
- 轨迹增量按 `7` 天窗口规划。
- 报警增量按 `72` 小时窗口规划。
- 进出区增量按 `31` 天窗口规划。

## v0.10.0 - 2026-07-22

### 新增

- 新增设备当前状态采集脚本：`scripts/hbt_collect_current.py`。
- 新增当前状态采集运行手册：`docs/HBT_CURRENT_STATUS_RUNBOOK.md`。
- 新增当前状态刷新日志：`logs/hbt_current_status_20260722-053053.log`。

### 验证

- 本地 dry-run 验证通过。
- VPS dry-run 验证通过。
- VPS 全量当前状态刷新成功：`226` 台设备，按 `5` 批完成。
- 写入设备状态快照：`226` 条。
- 刷新后在线设备 `118` 台，离线设备 `108` 台。

## v0.9.0 - 2026-07-22

### 新增

- 新增报警与进出区事件采集脚本：`scripts/hbt_collect_events.py`。
- 新增事件采集运行手册：`docs/HBT_EVENT_INGESTION_RUNBOOK.md`。
- 新增报警样本日志：`logs/hbt_alarm_sample_20260722-052423.log`。
- 新增进出区样本日志：`logs/hbt_site_events_sample_20260722-052423.log`。

### 验证

- 本地 dry-run 验证通过。
- VPS dry-run 验证通过。
- 报警样本窗口真实采集成功：`2026-06-23 00:00:00` 至 `2026-06-25 23:59:59`，返回 `0` 条报警。
- 进出区样本窗口真实采集成功：`2026-06-23 00:00:00` 至 `2026-07-23 23:59:59`，返回并入库 `3` 条事件。
- 入库站点事件包括：成都、阿拉山口、Mala。

## v0.8.0 - 2026-07-22

### 新增

- 新增轨迹回填脚本：`scripts/hbt_backfill_tracks.py`。
- 新增轨迹回填运行手册：`docs/HBT_TRACK_BACKFILL_RUNBOOK.md`。
- 新增回填样本日志：`logs/hbt_backfill_sample_20260722-050803.log`。

### 验证

- 本地 dry-run 验证通过。
- VPS dry-run 验证通过。
- VPS 单设备单窗口真实回填通过：设备 `61007408`，窗口 `2026-06-30 00:00:00` 至 `2026-07-06 23:59:59`。
- 该窗口接口返回 `56` 点。
- 样本设备累计唯一轨迹点增加到 `117` 条。
- 成功轨迹窗口累计 `2` 个。

## v0.7.0 - 2026-07-22

### 新增

- 新增货比特数据采集 PRD：`docs/HBT_DATA_INGESTION_PRD.md`。
- 新增第一阶段采集脚本：`scripts/hbt_stage1_collect.py`。
- 新增第一阶段采集执行报告：`docs/HBT_STAGE1_RUN_REPORT.md`。
- 新增本地日志副本：`logs/hbt_stage1_20260722-045755.log`。
- 在 BrianHub VPS 创建 GPS 项目数据目录：`/root/apps/gps/data/gps`。
- 在 BrianHub VPS 创建 SQLite 数据库：`/root/apps/gps/data/gps/gps_tracking.db`。

### 执行结果

- 建表成功：`17` 张业务表，`41` 个索引。
- 拉取设备清单：`226` 台，其中在线 `117` 台、离线 `109` 台。
- 拉取站点：`12` 个。
- 拉取样本设备 `61007408` 的轨迹全信息窗口：接口返回 `62` 点，唯一入库 `61` 点。
- 写入成功同步任务日志：`1` 条。

## v0.6.0 - 2026-07-22

### 新增

- 整理货比特平台接口接入笔记：`docs/HBT_API_INTEGRATION.md`。
- 明确接口通用参数、签名规则、生产地址、通用错误码和推荐环境变量。
- 梳理后续优先接入接口：设备同步、单设备实时状态、批量实时状态、历史轨迹、历史轨迹全信息。
- 记录接口实测前需要确认的问题，包括经纬度顺序、字段大小写和时间戳格式。
- 增加接口连通性测试记录，确认签名算法与文档样例一致，但文档生产地址 `/intf/` 当前返回 404。
- 确认当前可用开放接口地址为 `https://openapi.51hbt.com/`，轨迹回放接口测试成功。
- 补充货比特只读接口测试结果，确认设备同步、实时状态、全信息轨迹、站点事件、站点查询等接口可用。
- 新增货比特接口字段与数据维度目录：`docs/HBT_API_FIELD_CATALOG.md`。
- 新增货比特数据落库模型设计：`docs/HBT_DATA_MODEL.md`，覆盖轨迹、增量任务、报警、进出区事件和设备业务绑定。
- 新增 SQLite 第一版建表脚本：`docs/HBT_SQLITE_SCHEMA.sql`，目标路径为 `/root/apps/gps/data/gps/gps_tracking.db`。

## v0.5.0 - 2026-07-21

### 新增

- 自动形成 `始发站 - 口岸 - 目的站` 路线。
- 页面顶部显示路线总时效。
- 增加分段时效表，展示每一段口岸/边境之间的运输时效。
- 增加每个口岸/边境通道的等待时间。
- 口岸弹窗增加到达时间、离开时间和等待时间。

### 当前路线

- 始发站（中国四川绵阳附近）
- 阿拉山口/多斯特克
- 奥伦堡方向哈俄口岸
- 克拉斯诺耶/奥西诺夫卡
- 布列斯特/特雷斯波尔
- 目的站（波兰华沙附近）

### 时效结果

- 总时效：`20天13小时42分`
- 始发站 → 阿拉山口/多斯特克：运输 `2天17小时57分`，等待 `5天21小时53分`
- 阿拉山口/多斯特克 → 奥伦堡方向哈俄口岸：运输 `3天11小时57分`，等待 `9小时59分`
- 奥伦堡方向哈俄口岸 → 克拉斯诺耶/奥西诺夫卡：运输 `2天0小时0分`，等待 `9小时59分`
- 克拉斯诺耶/奥西诺夫卡 → 布列斯特/特雷斯波尔：运输 `9小时58分`，等待 `5天1小时55分`
- 布列斯特/特雷斯波尔 → 目的站：运输 `2小时0分`

## v0.4.0 - 2026-07-21

### 新增

- 形成项目 PRD 文档。
- 新增独立更新记录文档。

### 当前状态

- 主交付物：`trajectory-map-interactive.html`
- 原始轨迹点：`186`
- 展示轨迹点：`185`
- 已剔除异常点：`1`

## v0.3.0 - 2026-07-21

### 新增

- 增加 GPS 漂移点识别算法。
- 自动剔除明显尖刺式异常点。
- 页面顶部显示原始点位数、展示点位数和剔除数量。
- 地图上显示异常点剔除说明。

### 算法结果

- 剔除原始第 `110` 点。
- 时间：`2026-07-05 22:31:42`
- 坐标：`37.537915, 55.865669`
- 前段速度：`275.4 km/h`
- 后段速度：`142.4 km/h`
- 跳过该点后速度：`24.7 km/h`
- 绕行比例：`7.9x`

## v0.2.0 - 2026-07-21

### 新增

- 增加点位所属国家信息。
- 增加点位点击后的具体地理位置查询。
- 增加经过国家统计。
- 增加重点口岸/边境通道标注。

### 口岸标注

- 阿拉山口 / 多斯特克口岸
- 奥伦堡方向哈俄口岸
- 克拉斯诺耶 / 奥西诺夫卡口岸
- 布列斯特 / 特雷斯波尔口岸

## v0.1.0 - 2026-07-21

### 新增

- 从 Excel 轨迹点数据生成互动 HTML 地图。
- 支持地图缩放、拖拽和平移。
- 支持点击点位查看采集时间、经纬度、电量和速度。
- 按时间顺序连接 GPS 轨迹点。
- 标注起点和终点。
