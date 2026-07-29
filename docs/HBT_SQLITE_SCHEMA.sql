-- GPS / HBT first-stage SQLite schema.
-- Target path on BrianHub VPS:
-- /root/apps/gps/data/gps/gps_tracking.db

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS hbt_devices (
  device_id TEXT PRIMARY KEY,
  org_root_id TEXT,
  org_id TEXT,
  status INTEGER,
  last_loc_at TEXT,
  last_upload_at TEXT,
  last_lng REAL,
  last_lat REAL,
  soc REAL,
  upload_frequency INTEGER,
  service_start_at TEXT,
  service_expire_at TEXT,
  raw_payload TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_hbt_devices_status
  ON hbt_devices(status);

CREATE INDEX IF NOT EXISTS idx_hbt_devices_last_loc_at
  ON hbt_devices(last_loc_at);

CREATE INDEX IF NOT EXISTS idx_hbt_devices_org_root_id
  ON hbt_devices(org_root_id);

CREATE TABLE IF NOT EXISTS hbt_device_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  device_id TEXT NOT NULL,
  snapshot_at TEXT NOT NULL,
  last_loc_at TEXT,
  last_upload_at TEXT,
  lng REAL,
  lat REAL,
  status INTEGER,
  soc REAL,
  speed REAL,
  direction REAL,
  temperature REAL,
  humidity REAL,
  vibration REAL,
  tilt_y REAL,
  light REAL,
  elock_status INTEGER,
  raw_payload TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (device_id) REFERENCES hbt_devices(device_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS uk_hbt_device_snapshots_device_snapshot
  ON hbt_device_snapshots(device_id, snapshot_at);

CREATE INDEX IF NOT EXISTS idx_hbt_device_snapshots_device_time
  ON hbt_device_snapshots(device_id, snapshot_at);

CREATE TABLE IF NOT EXISTS hbt_track_points (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  device_id TEXT NOT NULL,
  loc_at TEXT NOT NULL,
  source_timestamp_ms INTEGER,
  lng REAL NOT NULL,
  lat REAL NOT NULL,
  speed REAL,
  direction REAL,
  temperature REAL,
  humidity REAL,
  vbx REAL,
  vby REAL,
  vbz REAL,
  vibration REAL,
  tilt_x REAL,
  tilt_y REAL,
  tilt_z REAL,
  light REAL,
  elock_status INTEGER,
  distance_m_from_prev REAL,
  is_valid INTEGER NOT NULL DEFAULT 1,
  is_drift_candidate INTEGER NOT NULL DEFAULT 0,
  source_method TEXT NOT NULL,
  raw_payload TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (device_id) REFERENCES hbt_devices(device_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS uk_hbt_track_points_device_time_lng_lat
  ON hbt_track_points(device_id, loc_at, lng, lat);

CREATE INDEX IF NOT EXISTS idx_hbt_track_points_device_time
  ON hbt_track_points(device_id, loc_at);

CREATE INDEX IF NOT EXISTS idx_hbt_track_points_time
  ON hbt_track_points(loc_at);

CREATE TABLE IF NOT EXISTS gps_trajectory_cache (
  device_id TEXT PRIMARY KEY,
  raw_count INTEGER NOT NULL,
  display_count INTEGER NOT NULL,
  removed_count INTEGER NOT NULL,
  start_at TEXT,
  end_at TEXT,
  total_duration_text TEXT,
  payload_json TEXT NOT NULL,
  source_max_loc_at TEXT,
  source_point_count INTEGER NOT NULL DEFAULT 0,
  precomputed_at TEXT NOT NULL,
  algorithm_version TEXT NOT NULL,
  FOREIGN KEY (device_id) REFERENCES hbt_devices(device_id)
);

CREATE INDEX IF NOT EXISTS idx_gps_trajectory_cache_precomputed_at
  ON gps_trajectory_cache(precomputed_at);

CREATE TABLE IF NOT EXISTS gps_port_definitions (
  port_id TEXT PRIMARY KEY,
  port_name TEXT NOT NULL,
  port_short_name TEXT NOT NULL,
  countries TEXT,
  lat REAL NOT NULL,
  lng REAL NOT NULL,
  radius_km REAL NOT NULL,
  note TEXT,
  route_corridor TEXT NOT NULL DEFAULT 'china-europe',
  sort_order INTEGER NOT NULL DEFAULT 0,
  active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_gps_port_definitions_active_order
  ON gps_port_definitions(active, route_corridor, sort_order);

INSERT INTO gps_port_definitions (
  port_id, port_name, port_short_name, countries, lat, lng, radius_km,
  note, route_corridor, sort_order, active
)
VALUES
  (
    'alashankou-dostyk',
    '阿拉山口 / 多斯特克口岸',
    '阿拉山口/多斯特克',
    '中国 - 哈萨克斯坦',
    45.167,
    82.575,
    60,
    '中哈铁路口岸，按口岸中心点半径自动匹配。',
    'china-europe',
    10,
    1
  ),
  (
    'orenburg-kz-ru',
    '奥伦堡方向哈俄口岸',
    '奥伦堡方向哈俄口岸',
    '哈萨克斯坦 - 俄罗斯',
    51.46,
    56.37,
    180,
    '按轨迹从哈萨克斯坦西北部进入俄罗斯推定，接近奥伦堡方向通道。',
    'china-europe',
    20,
    1
  ),
  (
    'krasnoe-osinovka',
    '克拉斯诺耶 / 奥西诺夫卡口岸',
    '克拉斯诺耶/奥西诺夫卡',
    '俄罗斯 - 白俄罗斯',
    54.73,
    31.72,
    130,
    '俄白铁路边境口岸，按口岸中心点半径自动匹配。',
    'china-europe',
    30,
    1
  ),
  (
    'brest-terespol',
    '布列斯特 / 特雷斯波尔口岸',
    '布列斯特/特雷斯波尔',
    '白俄罗斯 - 波兰',
    52.083,
    23.66,
    80,
    '白波边境铁路/公路口岸，按口岸中心点半径自动匹配。',
    'china-europe',
    40,
    1
  )
ON CONFLICT(port_id) DO UPDATE SET
  port_name=excluded.port_name,
  port_short_name=excluded.port_short_name,
  countries=excluded.countries,
  lat=excluded.lat,
  lng=excluded.lng,
  radius_km=excluded.radius_km,
  note=excluded.note,
  route_corridor=excluded.route_corridor,
  sort_order=excluded.sort_order,
  active=excluded.active,
  updated_at=CURRENT_TIMESTAMP;

CREATE TABLE IF NOT EXISTS truck_stations (
  slug TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  city TEXT NOT NULL,
  country_code TEXT NOT NULL,
  station_group TEXT NOT NULL DEFAULT 'europe',
  terminal TEXT NOT NULL,
  address TEXT NOT NULL,
  lat REAL NOT NULL,
  lng REAL NOT NULL,
  source_note TEXT,
  sort_order INTEGER NOT NULL DEFAULT 0,
  active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_truck_stations_active_order
  ON truck_stations(active, sort_order);

INSERT INTO truck_stations (
  slug, name, city, country_code, station_group, terminal, address, lat, lng, source_note, sort_order, active
)
VALUES
  ('duisburg', 'Duisburg / 杜伊斯堡', 'Duisburg, Germany', 'DE', 'europe', 'DIT (Duisburg Intermodal Terminal) / DUSS Terminal', 'Gaterweg 201, 47229 Duisburg, Germany', 51.4019, 6.7214, '用户提供的中欧班列常用目的站资料', 10, 1),
  ('malaszewicze', 'Małaszewicze / 马拉舍维奇', 'Małaszewicze, Poland', 'PL', 'europe', 'PKP Cargo Terminal / Europort Terminal', 'Station Małaszewicze, 21-540 Małaszewicze, Poland', 52.0264, 23.5298, '用户提供的中欧班列常用目的站资料', 20, 1),
  ('hamburg', 'Hamburg / 汉堡', 'Hamburg, Germany', 'DE', 'europe', 'DUSS Terminal Hamburg-Billiwerder', 'Wöhlerstraße 42, 22113 Hamburg, Germany', 53.5186, 10.1065, '用户提供的中欧班列常用目的站资料', 30, 1),
  ('tilburg', 'Tilburg / 蒂尔堡', 'Tilburg, Netherlands', 'NL', 'europe', 'Railport Brabant / GVT Terminal', 'Ringbaan-West 300, 5038 NX Tilburg, Netherlands', 51.5811, 5.0483, '用户提供的中欧班列常用目的站资料', 40, 1),
  ('belgrade', 'Belgrade / 贝尔格莱德', 'Belgrade, Serbia', 'RS', 'europe', 'Belgrade Ranžirna / Batajnica Logistics Center', 'Batajnički drum b.b., 11080 Belgrade, Serbia', 44.9081, 20.2858, '用户提供的中欧班列常用目的站资料', 50, 1),
  ('budapest', 'Budapest / 布达佩斯', 'Budapest, Hungary', 'HU', 'europe', 'BILK Logistics Terminal', 'Európa út 6, 1239 Budapest, Hungary', 47.3912, 19.1235, '用户提供的中欧班列常用目的站资料', 60, 1),
  ('krems', 'Krems / 克雷姆斯', 'Krems an der Donau, Austria', 'AT', 'europe', 'Hafen Krems / Metrans Krems Terminal', 'Karl-Mierka-Straße 102, 3500 Krems an der Donau, Austria', 48.4067, 15.6289, '用户提供的中欧班列常用目的站资料', 70, 1),
  ('london', 'London / 伦敦', 'London / Barking, United Kingdom', 'GB', 'europe', 'DB Cargo Barking Eurohub', 'Ripple Road, Barking IG11 0RH, United Kingdom', 51.5278, 0.1389, '用户提供的中欧班列常用目的站资料', 80, 1),
  ('katowice', 'Katowice / 卡托维兹', 'Katowice / Sławków, Poland', 'PL', 'europe', 'Sławków Euroterminal', 'ul. Groniec 1, 41-260 Sławków, Poland', 50.2925, 19.3408, '用户提供的中欧班列常用目的站资料', 90, 1),
  ('prague', 'Prague / 布拉格', 'Praha-Uhříněves, Czechia', 'CZ', 'europe', 'Metrans Terminal Praha-Uhříněves', 'Přátelství 681/81, 104 00 Praha 22-Uhříněves, Czechia', 50.0264, 14.5956, '用户提供的中欧班列常用目的站资料', 100, 1),
  ('warsaw', 'Warsaw / 华沙', 'Warszawa, Poland', 'PL', 'europe', 'PKP Cargo Terminal Warszawa-Praga', 'ul. Jagiellońska 88, 03-215 Warszawa, Poland', 52.2801, 21.0028, '用户提供的中欧班列常用目的站资料', 110, 1),
  ('munich', 'Munich / 慕尼黑', 'München, Germany', 'DE', 'europe', 'DUSS Terminal München-Riem', 'Landshuter Allee 38, 81829 München, Germany', 48.1392, 11.6881, '用户提供的中欧班列常用目的站资料', 120, 1),
  ('milan', 'Milan / 米兰', 'Milano, Italy', 'IT', 'europe', 'Terminal Italia - Milano Smistamento', 'Via Chiese, 20126 Milano MI, Italy', 45.5183, 9.2205, '用户提供的中欧班列常用目的站资料', 130, 1),
  ('liege', 'Liège / 列日', 'Liège / Grâce-Hollogne, Belgium', 'BE', 'europe', 'Liège Logistics Intermodal (LLI)', 'Rue de l''Aéroport, 4460 Grâce-Hollogne, Belgium', 50.6381, 5.4489, '用户提供的中欧班列常用目的站资料', 140, 1),
  ('ceska-trebova', 'Česká Třebová / 切斯卡特拉波瓦', 'Česká Třebová, Czechia', 'CZ', 'europe', 'Metrans Terminal Česká Třebová', 'Semanínská 2110, 560 02 Česká Třebová, Czechia', 49.8928, 16.4422, '用户提供的中欧班列常用目的站资料', 150, 1),
  ('barcelona', 'Barcelona / 巴塞罗那', 'Barcelona, Spain', 'ES', 'europe', 'Terminal Can Tunis (Barcelona Port Rail)', 'Carrer 3, Parc Logístic, 08040 Barcelona, Spain', 41.3325, 2.1281, '用户提供的中欧班列常用目的站资料', 160, 1),
  ('vorsino', 'Vorsino / 沃尔西诺', 'Vorsino, Russia', 'RU', 'russia', 'Freight Village Vorsino', 'North Industrial Area, bld. 6, Vorsino village, Kaluga Region, Russia', 55.2403, 36.6675, '用户提供的中欧班列常用目的站资料', 170, 1),
  ('selyatino', 'Selyatino / 谢利亚季诺', 'Selyatino, Russia', 'RU', 'russia', 'Terminal Selyatino', 'Selyatino, Naro-Fominsky District, Moscow Oblast, Russia', 55.5147, 36.9753, '用户提供的中欧班列常用目的站资料', 180, 1),
  ('bely-rast', 'Bely Rast / 别雷拉斯特', 'Bely Rast, Russia', 'RU', 'russia', 'TLK Bely Rast', 'Bely Rast Village, Dmitrovsky District, Moscow Oblast, Russia', 56.1628, 37.3828, '用户提供的中欧班列常用目的站资料', 190, 1),
  ('elektrougli', 'Elektrougli / 电煤站', 'Elektrougli, Russia', 'RU', 'russia', 'TLC Vostok (Elektrougli)', 'ul. Tsentralnaya 59, Elektrougli, Noginsky District, Moscow Oblast, Russia', 55.7289, 38.2106, '用户提供的中欧班列常用目的站资料', 200, 1),
  ('khovrino', 'Khovrino / 霍夫季诺', 'Moscow, Russia', 'RU', 'russia', 'Khovrino Railway Station / TLC Khovrino', 'ul. Pushteyskaya 5, Moscow, Russia', 55.8672, 37.4939, '用户提供的中欧班列常用目的站资料', 210, 1),
  ('kolyadichi', 'Kolyadichi / 科里亚季奇', 'Minsk, Belarus', 'BY', 'belarus', 'Kolyadichi Railway Terminal', 'ul. Babushkina 39, Minsk, Belarus', 53.7915, 27.5681, '用户提供的中欧班列常用目的站资料', 220, 1),
  ('yekaterinburg', 'Yekaterinburg / 叶卡捷琳堡', 'Yekaterinburg, Russia', 'RU', 'russia', 'Ekaterinburg-Tovarnyy / Logistics Center Ural', 'ul. Armavirskaya 20, Yekaterinburg, Sverdlovsk Oblast, Russia', 56.8625, 60.5892, '用户提供的中欧班列常用目的站资料', 230, 1),
  ('shushary', 'Shushary / 舒沙雷', 'Saint Petersburg, Russia', 'RU', 'russia', 'Shushary Railway Station / Container Terminal Shushary', 'Shushary Settlement, Pushkinsky District, Saint Petersburg, Russia', 59.8114, 30.3808, '用户提供的中欧班列常用目的站资料', 240, 1),
  ('kleshchikha', 'Kleshchikha / 克列西哈', 'Novosibirsk, Russia', 'RU', 'russia', 'Kleshchikha Terminal', 'ul. Stantsionnaya 60, Novosibirsk, Novosibirsk Oblast, Russia', 54.9912, 82.8051, '用户提供的中欧班列常用目的站资料', 250, 1),
  ('kazan', 'Kazan / 喀山', 'Kazan, Russia', 'RU', 'russia', 'Kazan-Kirovsky / Tikhoretskaya Terminal', 'ul. Tikhoretskaya 19, Kazan, Republic of Tatarstan, Russia', 55.7481, 49.1214, '用户提供的中欧班列常用目的站资料', 260, 1),
  ('almaty', 'Almaty / 阿拉木图', 'Almaty, Kazakhstan', 'KZ', 'central_asia', 'Almaty-1 Freight Yard', 'Turksib District, Almaty, Kazakhstan', 43.3422, 76.9497, '用户提供的中欧班列常用目的站资料', 270, 1),
  ('poti', 'Poti / 波季', 'Poti, Georgia', 'GE', 'central_asia', 'APM Terminals Poti', '52 Demetre Tavdadebuli St, Poti 4400, Georgia', 42.1462, 41.6669, '用户提供的中欧班列常用目的站资料', 280, 1),
  ('baku', 'Baku / 巴库', 'Alyat / Baku, Azerbaijan', 'AZ', 'central_asia', 'Baku International Sea Trade Port (Alyat Terminal)', 'Baku International Sea Trade Port, Alyat, Baku, Azerbaijan', 40.0169, 49.4042, '用户提供的中欧班列常用目的站资料', 290, 1),
  ('tbilisi', 'Tbilisi / 第比利斯', 'Tbilisi, Georgia', 'GE', 'central_asia', 'Tbilisi Dry Port', 'Tbilisi Dry Port, Tbilisi, Georgia', 41.6634026, 44.9137714, 'Tbilisi Dry Port public location reference', 300, 1),
  ('minsk-kolodishchi', 'Minsk Kolodishchi / 明斯克科洛迪希', 'Minsk District, Belarus', 'BY', 'belarus', 'Kolodishchi Terminal', 'Kolodishchi Railway Station, Minsk District, Belarus', 53.9483, 27.7812, '用户提供的中欧班列常用目的站资料', 310, 1)
ON CONFLICT(slug) DO UPDATE SET
  name=excluded.name,
  city=excluded.city,
  country_code=excluded.country_code,
  station_group=excluded.station_group,
  terminal=excluded.terminal,
  address=excluded.address,
  lat=excluded.lat,
  lng=excluded.lng,
  source_note=excluded.source_note,
  sort_order=excluded.sort_order,
  active=excluded.active,
  updated_at=CURRENT_TIMESTAMP;

CREATE TABLE IF NOT EXISTS truck_freight_rules (
  rule_key TEXT PRIMARY KEY,
  rule_type TEXT NOT NULL,
  country_code TEXT,
  city_pattern TEXT,
  distance_limit_km REAL,
  amount_eur REAL,
  multiplier REAL,
  note TEXT,
  sort_order INTEGER NOT NULL DEFAULT 0,
  active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_truck_freight_rules_type_order
  ON truck_freight_rules(active, rule_type, sort_order);

INSERT INTO truck_freight_rules (
  rule_key, rule_type, country_code, city_pattern, distance_limit_km, amount_eur, multiplier, note, sort_order, active
)
VALUES
  ('base-eur', 'base', NULL, NULL, NULL, 120, NULL, '1x40HQ 20-23t 基础调度费估算', 10, 1),
  ('minimum-eur', 'minimum', NULL, NULL, NULL, 450, NULL, '1x40HQ 20-23t 最低起步费估算', 20, 1),
  ('empty-return-multiplier', 'empty_return_multiplier', NULL, NULL, NULL, NULL, 0.65, '还空段按重柜公里费的 65% 估算', 25, 1),
  ('cross-border-surcharge', 'cross_border_surcharge', NULL, NULL, NULL, 120, NULL, '跨国家代码路线固定操作成本估算', 26, 1),
  ('fuel-europe', 'fuel_surcharge_rate', 'EUROPE', NULL, NULL, NULL, 0.13, 'DHL Freight Netherlands 2026-07 Europe Fuel Surcharge 公开比例', 27, 1),
  ('fuel-nl', 'fuel_surcharge_rate', 'NL', NULL, NULL, NULL, 0.25, 'DHL Freight Netherlands 2026-07 Netherlands Fuel Surcharge 公开比例', 28, 1),
  ('city-milan-area-c', 'city_access_fee', 'IT', 'MILAN|MILANO', NULL, 7.5, NULL, 'Comune di Milano Area C standard ticket 7.5 EUR；按门点文本命中 Milan/Milano 时计入', 29, 1),
  ('city-london-congestion-advisory', 'city_access_advisory', 'GB', 'LONDON', NULL, NULL, NULL, 'TfL Congestion Charge 18 GBP from 2026-01-02；未换算为 EUR，询价初期仅提示不计入总价', 30, 1),
  ('city-paris-lez-advisory', 'city_access_advisory', 'FR', 'PARIS', NULL, NULL, NULL, 'Paris ZFE/low emission compliance depends on vehicle CritAir class；询价初期仅提示不计入总价', 31, 1),
  ('band-250', 'distance_band', NULL, NULL, 250, 2.05, NULL, '短途提派单价估算 EUR/km', 40, 1),
  ('band-600', 'distance_band', NULL, NULL, 600, 1.72, NULL, '中短途提派单价估算 EUR/km', 50, 1),
  ('band-1200', 'distance_band', NULL, NULL, 1200, 1.48, NULL, '中长途提派单价估算 EUR/km', 60, 1),
  ('band-long', 'distance_band', NULL, NULL, 999999, 1.42, NULL, '长途提派单价估算 EUR/km', 70, 1),
  ('factor-gb', 'country_factor', 'GB', NULL, NULL, NULL, 1.18, '英国跨境/岛内综合系数', 100, 1),
  ('factor-ie', 'country_factor', 'IE', NULL, NULL, NULL, 1.22, '爱尔兰综合系数', 110, 1),
  ('factor-ch', 'country_factor', 'CH', NULL, NULL, NULL, 1.16, '瑞士清关及运营系数', 120, 1),
  ('factor-no', 'country_factor', 'NO', NULL, NULL, NULL, 1.18, '挪威综合系数', 130, 1),
  ('factor-se', 'country_factor', 'SE', NULL, NULL, NULL, 1.10, '瑞典综合系数', 140, 1),
  ('factor-fi', 'country_factor', 'FI', NULL, NULL, NULL, 1.12, '芬兰综合系数', 150, 1),
  ('factor-dk', 'country_factor', 'DK', NULL, NULL, NULL, 1.08, '丹麦综合系数', 160, 1),
  ('factor-it', 'country_factor', 'IT', NULL, NULL, NULL, 1.07, '意大利综合系数', 170, 1),
  ('factor-es', 'country_factor', 'ES', NULL, NULL, NULL, 1.06, '西班牙综合系数', 180, 1),
  ('factor-pt', 'country_factor', 'PT', NULL, NULL, NULL, 1.08, '葡萄牙综合系数', 190, 1),
  ('factor-ro', 'country_factor', 'RO', NULL, NULL, NULL, 1.05, '罗马尼亚综合系数', 200, 1),
  ('factor-bg', 'country_factor', 'BG', NULL, NULL, NULL, 1.06, '保加利亚综合系数', 210, 1),
  ('factor-rs', 'country_factor', 'RS', NULL, NULL, NULL, 1.08, '塞尔维亚综合系数', 220, 1),
  ('factor-ee', 'country_factor', 'EE', NULL, NULL, NULL, 1.10, '爱沙尼亚综合系数', 230, 1),
  ('factor-lv', 'country_factor', 'LV', NULL, NULL, NULL, 1.09, '拉脱维亚综合系数', 240, 1),
  ('factor-lt', 'country_factor', 'LT', NULL, NULL, NULL, 1.08, '立陶宛综合系数', 250, 1),
  ('surcharge-gb', 'country_surcharge', 'GB', NULL, NULL, 380, NULL, '英国附加费估算', 300, 1),
  ('surcharge-ie', 'country_surcharge', 'IE', NULL, NULL, 520, NULL, '爱尔兰附加费估算', 310, 1),
  ('surcharge-no', 'country_surcharge', 'NO', NULL, NULL, 220, NULL, '挪威附加费估算', 320, 1),
  ('surcharge-ch', 'country_surcharge', 'CH', NULL, NULL, 180, NULL, '瑞士附加费估算', 330, 1)
ON CONFLICT(rule_key) DO UPDATE SET
  rule_type=excluded.rule_type,
  country_code=excluded.country_code,
  city_pattern=excluded.city_pattern,
  distance_limit_km=excluded.distance_limit_km,
  amount_eur=excluded.amount_eur,
  multiplier=excluded.multiplier,
  note=excluded.note,
  sort_order=excluded.sort_order,
  active=excluded.active,
  updated_at=CURRENT_TIMESTAMP;

CREATE TABLE IF NOT EXISTS truck_supplier_quote_observations (
  quote_id TEXT PRIMARY KEY,
  observed_at TEXT NOT NULL,
  supplier_name TEXT,
  origin_station_slug TEXT NOT NULL,
  origin_station_label TEXT,
  delivery_address TEXT NOT NULL,
  destination_country_code TEXT,
  return_station_slug TEXT,
  return_station_label TEXT,
  container_type TEXT NOT NULL,
  gross_weight_tons REAL,
  supplier_rate_eur REAL NOT NULL,
  supplier_currency TEXT NOT NULL DEFAULT 'EUR',
  supplier_rate_basis TEXT,
  model_estimate_eur REAL,
  model_distance_km REAL,
  model_loaded_km REAL,
  model_empty_return_km REAL,
  model_billable_km REAL,
  delta_eur REAL,
  delta_pct REAL,
  supplier_terms TEXT,
  extra_charges_note TEXT,
  inquiry_text TEXT,
  supplier_response_text TEXT,
  analysis_note TEXT,
  calibration_status TEXT NOT NULL DEFAULT 'record_only',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_truck_supplier_quote_observations_lane
  ON truck_supplier_quote_observations(origin_station_slug, destination_country_code, return_station_slug);

CREATE INDEX IF NOT EXISTS idx_truck_supplier_quote_observations_observed
  ON truck_supplier_quote_observations(observed_at);

INSERT INTO truck_supplier_quote_observations (
  quote_id, observed_at, supplier_name, origin_station_slug, origin_station_label,
  delivery_address, destination_country_code, return_station_slug, return_station_label,
  container_type, gross_weight_tons, supplier_rate_eur, supplier_currency,
  supplier_rate_basis, model_estimate_eur, model_distance_km, model_loaded_km,
  model_empty_return_km, model_billable_km, delta_eur, delta_pct,
  supplier_terms, extra_charges_note, inquiry_text, supplier_response_text,
  analysis_note, calibration_status
)
VALUES (
  'mala-tallinn-kesk-sojamae-20260723',
  '2026-07-23',
  NULL,
  'malaszewicze',
  'MALA Railterminal / Małaszewicze',
  'KESK-SÕJAMÄE 7, 11415, TALLINN, ESTONIA',
  'EE',
  'malaszewicze',
  'Mala Depot / Małaszewicze',
  '40HC',
  20,
  2495,
  'EUR',
  '40'' HC COC upto 20 tons max payload; 1 delivery address by container chassis',
  3160,
  2008.7,
  1001.2,
  1007.5,
  1656.1,
  -665,
  -21.04,
  '1 delivery address by container chassis; 2 hour free unloading time included',
  'T-1 = EUR 125 / 1 Set, 1 HS Code, max EUR 200,000 cargo value; Each additional HS Code = EUR 7.40 per item; Customs guarantee costs if cargo value >= EUR 200,000 = 0.05% of invoice value; Overtime if 2 hours free time exceeded; Additional costs if T-1 is not directly closed during unloading = at cost; Additional costs if arrival terminal and/or empty container depot is within Mala = at full costs apply; TRB Handling Fee USD 100 / Cntr',
  'Pls kindly check and advise on-carriage from Mala station to KESK-SÕJAMÄE 7, 11415, TALLINN, ESTONIA, and empty container return in Mala. 1X40HC, Gross weight 20 Tons.',
  'Pickup full from MALA Railterminal; Delivery to EE - KESK-SÕJAMÄE 7, 11415, TALLINN, ESTONIA Door; Empty container return to Mala Depot; EUR 2.495,- / 40'' HC COC upto 20 tons max payload; 1 delivery address by container chassis, 2 hour free unloading time included.',
  'Record only. Do not change pricing parameters yet. Observed supplier base truck rate is lower than current model; likely because lane price includes fuel/cross-border costs, mature Mala-Tallinn-Mala lane economics, supplier margin, and live market capacity factors.',
  'record_only'
)
ON CONFLICT(quote_id) DO UPDATE SET
  observed_at=excluded.observed_at,
  supplier_name=excluded.supplier_name,
  origin_station_slug=excluded.origin_station_slug,
  origin_station_label=excluded.origin_station_label,
  delivery_address=excluded.delivery_address,
  destination_country_code=excluded.destination_country_code,
  return_station_slug=excluded.return_station_slug,
  return_station_label=excluded.return_station_label,
  container_type=excluded.container_type,
  gross_weight_tons=excluded.gross_weight_tons,
  supplier_rate_eur=excluded.supplier_rate_eur,
  supplier_currency=excluded.supplier_currency,
  supplier_rate_basis=excluded.supplier_rate_basis,
  model_estimate_eur=excluded.model_estimate_eur,
  model_distance_km=excluded.model_distance_km,
  model_loaded_km=excluded.model_loaded_km,
  model_empty_return_km=excluded.model_empty_return_km,
  model_billable_km=excluded.model_billable_km,
  delta_eur=excluded.delta_eur,
  delta_pct=excluded.delta_pct,
  supplier_terms=excluded.supplier_terms,
  extra_charges_note=excluded.extra_charges_note,
  inquiry_text=excluded.inquiry_text,
  supplier_response_text=excluded.supplier_response_text,
  analysis_note=excluded.analysis_note,
  calibration_status=excluded.calibration_status,
  updated_at=CURRENT_TIMESTAMP;

INSERT INTO truck_supplier_quote_observations (
  quote_id, observed_at, supplier_name, origin_station_slug, origin_station_label,
  delivery_address, destination_country_code, return_station_slug, return_station_label,
  container_type, gross_weight_tons, supplier_rate_eur, supplier_currency,
  supplier_rate_basis, model_estimate_eur, model_distance_km, model_loaded_km,
  model_empty_return_km, model_billable_km, delta_eur, delta_pct,
  supplier_terms, extra_charges_note, inquiry_text, supplier_response_text,
  analysis_note, calibration_status
)
VALUES (
  'hamburg-suderholz-pommerndreieck-20260723',
  '2026-07-23',
  NULL,
  'hamburg',
  'Hamburg / DUSS Terminal Hamburg-Billwerder',
  'Pommerndreieck 2a, 18516 Süderholz, Germany',
  'DE',
  'hamburg',
  'Hamburg / DUSS Terminal Hamburg-Billwerder',
  '40HC',
  NULL,
  1300,
  'EUR',
  'Supplier on-carriage and empty return quote for Hamburg -> Süderholz -> Hamburg',
  890,
  482.4,
  241.4,
  241.0,
  398.0,
  410,
  46.07,
  'Supplier quote assumed as base truck on-carriage with empty return; detailed waiting/customs terms not provided in sample.',
  'No separate accessorial charge details provided in sample.',
  'Example discussed: Pommerndreieck 2a, 18516 Süderholz door; pickup full from Hamburg station, empty return Hamburg.',
  'Supplier quoted EUR 1300; model estimate at the time was EUR 890.',
  'Record only. Do not change pricing parameters yet. Observed supplier base truck rate is higher than current model; may reflect short round-trip chassis/day resource minimum, supplier margin, and live market capacity factors.',
  'record_only'
)
ON CONFLICT(quote_id) DO UPDATE SET
  observed_at=excluded.observed_at,
  supplier_name=excluded.supplier_name,
  origin_station_slug=excluded.origin_station_slug,
  origin_station_label=excluded.origin_station_label,
  delivery_address=excluded.delivery_address,
  destination_country_code=excluded.destination_country_code,
  return_station_slug=excluded.return_station_slug,
  return_station_label=excluded.return_station_label,
  container_type=excluded.container_type,
  gross_weight_tons=excluded.gross_weight_tons,
  supplier_rate_eur=excluded.supplier_rate_eur,
  supplier_currency=excluded.supplier_currency,
  supplier_rate_basis=excluded.supplier_rate_basis,
  model_estimate_eur=excluded.model_estimate_eur,
  model_distance_km=excluded.model_distance_km,
  model_loaded_km=excluded.model_loaded_km,
  model_empty_return_km=excluded.model_empty_return_km,
  model_billable_km=excluded.model_billable_km,
  delta_eur=excluded.delta_eur,
  delta_pct=excluded.delta_pct,
  supplier_terms=excluded.supplier_terms,
  extra_charges_note=excluded.extra_charges_note,
  inquiry_text=excluded.inquiry_text,
  supplier_response_text=excluded.supplier_response_text,
  analysis_note=excluded.analysis_note,
  calibration_status=excluded.calibration_status,
  updated_at=CURRENT_TIMESTAMP;

INSERT INTO truck_supplier_quote_observations (
  quote_id, observed_at, supplier_name, origin_station_slug, origin_station_label,
  delivery_address, destination_country_code, return_station_slug, return_station_label,
  container_type, gross_weight_tons, supplier_rate_eur, supplier_currency,
  supplier_rate_basis, model_estimate_eur, model_distance_km, model_loaded_km,
  model_empty_return_km, model_billable_km, delta_eur, delta_pct,
  supplier_terms, extra_charges_note, inquiry_text, supplier_response_text,
  analysis_note, calibration_status
)
VALUES (
  'duisburg-im-freihafen-20260723',
  '2026-07-23',
  NULL,
  'duisburg',
  'Duisburg / DIT-DUSS Terminal',
  'Im Freihafen 4, 47138 Duisburg, Germany',
  'DE',
  'duisburg',
  'Duisburg / DIT-DUSS Terminal',
  '40HC',
  NULL,
  625,
  'EUR',
  'Supplier local on-carriage and empty return quote for Duisburg -> Im Freihafen -> Duisburg',
  450,
  25.5,
  12.9,
  12.7,
  21.1,
  175,
  38.89,
  'Supplier quote assumed as base local drayage with empty return; detailed waiting/customs terms not provided in sample.',
  'No separate accessorial charge details provided in sample.',
  'Example discussed: Im Freihafen 4, 47138 Duisburg door; pickup full from Duisburg station, empty return Duisburg.',
  'Supplier quoted EUR 625; model estimate at the time was EUR 450.',
  'Record only. Do not change pricing parameters yet. Observed supplier base truck rate is higher than current model minimum; may reflect local drayage minimum, terminal/chassis handling floor, supplier margin, and live market capacity factors.',
  'record_only'
)
ON CONFLICT(quote_id) DO UPDATE SET
  observed_at=excluded.observed_at,
  supplier_name=excluded.supplier_name,
  origin_station_slug=excluded.origin_station_slug,
  origin_station_label=excluded.origin_station_label,
  delivery_address=excluded.delivery_address,
  destination_country_code=excluded.destination_country_code,
  return_station_slug=excluded.return_station_slug,
  return_station_label=excluded.return_station_label,
  container_type=excluded.container_type,
  gross_weight_tons=excluded.gross_weight_tons,
  supplier_rate_eur=excluded.supplier_rate_eur,
  supplier_currency=excluded.supplier_currency,
  supplier_rate_basis=excluded.supplier_rate_basis,
  model_estimate_eur=excluded.model_estimate_eur,
  model_distance_km=excluded.model_distance_km,
  model_loaded_km=excluded.model_loaded_km,
  model_empty_return_km=excluded.model_empty_return_km,
  model_billable_km=excluded.model_billable_km,
  delta_eur=excluded.delta_eur,
  delta_pct=excluded.delta_pct,
  supplier_terms=excluded.supplier_terms,
  extra_charges_note=excluded.extra_charges_note,
  inquiry_text=excluded.inquiry_text,
  supplier_response_text=excluded.supplier_response_text,
  analysis_note=excluded.analysis_note,
  calibration_status=excluded.calibration_status,
  updated_at=CURRENT_TIMESTAMP;

CREATE TABLE IF NOT EXISTS gps_precompute_runs (
  run_id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_type TEXT NOT NULL,
  device_id TEXT,
  status TEXT NOT NULL,
  processed_devices INTEGER NOT NULL DEFAULT 0,
  processed_points INTEGER NOT NULL DEFAULT 0,
  error_message TEXT,
  started_at TEXT NOT NULL,
  finished_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_gps_precompute_runs_type_time
  ON gps_precompute_runs(run_type, started_at);

CREATE TABLE IF NOT EXISTS gps_port_passages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  device_id TEXT NOT NULL,
  port_name TEXT NOT NULL,
  port_short_name TEXT,
  countries TEXT,
  lat REAL,
  lng REAL,
  radius_km REAL,
  arrival_point_idx INTEGER,
  departure_point_idx INTEGER,
  arrival_at TEXT,
  departure_at TEXT,
  wait_hours REAL NOT NULL DEFAULT 0,
  wait_duration_text TEXT,
  matched INTEGER NOT NULL DEFAULT 0,
  algorithm_version TEXT NOT NULL,
  precomputed_at TEXT NOT NULL,
  FOREIGN KEY (device_id) REFERENCES hbt_devices(device_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS uk_gps_port_passages_device_port
  ON gps_port_passages(device_id, port_name);

CREATE INDEX IF NOT EXISTS idx_gps_port_passages_port_time
  ON gps_port_passages(port_name, arrival_at, departure_at);

CREATE TABLE IF NOT EXISTS gps_border_crossings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  device_id TEXT NOT NULL,
  seq_no INTEGER NOT NULL,
  from_country TEXT,
  from_country_code TEXT,
  to_country TEXT,
  to_country_code TEXT,
  from_point_idx INTEGER,
  to_point_idx INTEGER,
  crossing_at TEXT,
  lat REAL,
  lng REAL,
  matched_port_name TEXT,
  matched_port_short_name TEXT,
  matched_distance_km REAL,
  confidence REAL NOT NULL DEFAULT 0,
  note TEXT,
  algorithm_version TEXT NOT NULL,
  precomputed_at TEXT NOT NULL,
  FOREIGN KEY (device_id) REFERENCES hbt_devices(device_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS uk_gps_border_crossings_device_seq
  ON gps_border_crossings(device_id, seq_no);

CREATE INDEX IF NOT EXISTS idx_gps_border_crossings_device_time
  ON gps_border_crossings(device_id, crossing_at);

CREATE TABLE IF NOT EXISTS gps_route_segments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  device_id TEXT NOT NULL,
  seq_no INTEGER NOT NULL,
  segment_name TEXT NOT NULL,
  from_node TEXT,
  to_node TEXT,
  depart_at TEXT,
  arrival_at TEXT,
  transport_hours REAL NOT NULL DEFAULT 0,
  transport_duration_text TEXT,
  port_name TEXT,
  port_wait_text TEXT,
  algorithm_version TEXT NOT NULL,
  precomputed_at TEXT NOT NULL,
  FOREIGN KEY (device_id) REFERENCES hbt_devices(device_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS uk_gps_route_segments_device_seq
  ON gps_route_segments(device_id, seq_no);

CREATE INDEX IF NOT EXISTS idx_gps_route_segments_device_time
  ON gps_route_segments(device_id, depart_at, arrival_at);

CREATE TABLE IF NOT EXISTS hbt_track_fetch_windows (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  device_id TEXT NOT NULL,
  window_start_at TEXT NOT NULL,
  window_end_at TEXT NOT NULL,
  method TEXT NOT NULL,
  status TEXT NOT NULL,
  point_count INTEGER NOT NULL DEFAULT 0,
  distance_m REAL,
  error_code TEXT,
  error_message TEXT,
  started_at TEXT,
  finished_at TEXT,
  raw_response TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (device_id) REFERENCES hbt_devices(device_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS uk_hbt_track_fetch_window
  ON hbt_track_fetch_windows(device_id, window_start_at, window_end_at, method);

CREATE INDEX IF NOT EXISTS idx_hbt_track_fetch_windows_status
  ON hbt_track_fetch_windows(status);

CREATE TABLE IF NOT EXISTS hbt_alarm_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  event_key TEXT NOT NULL UNIQUE,
  device_id TEXT NOT NULL,
  org_id TEXT,
  org_root_id TEXT,
  warning_type TEXT,
  warning_desc TEXT,
  start_at TEXT NOT NULL,
  end_at TEXT,
  is_open INTEGER NOT NULL DEFAULT 0,
  raw_payload TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (device_id) REFERENCES hbt_devices(device_id)
);

CREATE INDEX IF NOT EXISTS idx_hbt_alarm_events_device_time
  ON hbt_alarm_events(device_id, start_at);

CREATE INDEX IF NOT EXISTS idx_hbt_alarm_events_type_time
  ON hbt_alarm_events(warning_type, start_at);

CREATE INDEX IF NOT EXISTS idx_hbt_alarm_events_open
  ON hbt_alarm_events(is_open);

CREATE TABLE IF NOT EXISTS hbt_sites (
  site_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  address TEXT,
  center_lng REAL,
  center_lat REAL,
  org_id TEXT,
  org_root_id TEXT,
  source_created_at TEXT,
  source_updated_at TEXT,
  raw_payload TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_hbt_sites_org_root_id
  ON hbt_sites(org_root_id);

CREATE INDEX IF NOT EXISTS idx_hbt_sites_name
  ON hbt_sites(name);

CREATE TABLE IF NOT EXISTS hbt_site_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  event_key TEXT NOT NULL UNIQUE,
  device_id TEXT NOT NULL,
  site_id TEXT,
  site_name TEXT,
  org_root_id TEXT,
  device_org_id TEXT,
  site_org_id TEXT,
  in_at TEXT NOT NULL,
  out_at TEXT,
  is_inside INTEGER NOT NULL DEFAULT 0,
  duration_seconds INTEGER,
  raw_payload TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (device_id) REFERENCES hbt_devices(device_id),
  FOREIGN KEY (site_id) REFERENCES hbt_sites(site_id)
);

CREATE INDEX IF NOT EXISTS idx_hbt_site_events_device_time
  ON hbt_site_events(device_id, in_at);

CREATE INDEX IF NOT EXISTS idx_hbt_site_events_site_time
  ON hbt_site_events(site_id, in_at);

CREATE INDEX IF NOT EXISTS idx_hbt_site_events_inside
  ON hbt_site_events(is_inside);

CREATE TABLE IF NOT EXISTS business_routes (
  route_id TEXT PRIMARY KEY,
  route_code TEXT,
  route_name TEXT NOT NULL,
  origin_site_id TEXT,
  destination_site_id TEXT,
  raw_payload TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS business_containers (
  container_id INTEGER PRIMARY KEY AUTOINCREMENT,
  container_no TEXT NOT NULL UNIQUE,
  container_type TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS business_shipments (
  shipment_id INTEGER PRIMARY KEY AUTOINCREMENT,
  waybill_no TEXT,
  demand_no TEXT,
  container_no TEXT,
  shipper_name TEXT,
  receiver_name TEXT,
  origin_name TEXT,
  destination_name TEXT,
  depart_at TEXT,
  arrive_at TEXT,
  estimated_arrive_at TEXT,
  raw_payload TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS uk_business_shipments_waybill_no
  ON business_shipments(waybill_no)
  WHERE waybill_no IS NOT NULL AND waybill_no != '';

CREATE UNIQUE INDEX IF NOT EXISTS uk_business_shipments_demand_no
  ON business_shipments(demand_no)
  WHERE demand_no IS NOT NULL AND demand_no != '';

CREATE INDEX IF NOT EXISTS idx_business_shipments_container_no
  ON business_shipments(container_no);

CREATE TABLE IF NOT EXISTS business_orders (
  order_id TEXT PRIMARY KEY,
  order_code TEXT,
  shipment_id INTEGER,
  route_id TEXT,
  container_no TEXT,
  raw_payload TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (shipment_id) REFERENCES business_shipments(shipment_id),
  FOREIGN KEY (route_id) REFERENCES business_routes(route_id)
);

CREATE TABLE IF NOT EXISTS device_business_bindings (
  binding_id INTEGER PRIMARY KEY AUTOINCREMENT,
  device_id TEXT NOT NULL,
  route_id TEXT,
  container_no TEXT,
  shipment_id INTEGER,
  order_id TEXT,
  truck_no TEXT,
  bind_start_at TEXT NOT NULL,
  bind_end_at TEXT,
  source TEXT NOT NULL,
  confidence REAL,
  raw_payload TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (device_id) REFERENCES hbt_devices(device_id),
  FOREIGN KEY (route_id) REFERENCES business_routes(route_id),
  FOREIGN KEY (shipment_id) REFERENCES business_shipments(shipment_id),
  FOREIGN KEY (order_id) REFERENCES business_orders(order_id),
  CHECK (bind_end_at IS NULL OR bind_end_at > bind_start_at)
);

CREATE INDEX IF NOT EXISTS idx_device_business_bindings_device_time
  ON device_business_bindings(device_id, bind_start_at, bind_end_at);

CREATE INDEX IF NOT EXISTS idx_device_business_bindings_container
  ON device_business_bindings(container_no, bind_start_at, bind_end_at);

CREATE INDEX IF NOT EXISTS idx_device_business_bindings_route
  ON device_business_bindings(route_id, bind_start_at, bind_end_at);

CREATE TABLE IF NOT EXISTS hbt_order_node_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  event_key TEXT NOT NULL UNIQUE,
  device_id TEXT,
  order_id TEXT,
  order_code TEXT,
  site_id TEXT,
  site_name TEXT,
  arrival_at TEXT,
  leaving_at TEXT,
  raw_payload TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_hbt_order_node_events_device
  ON hbt_order_node_events(device_id, arrival_at);

CREATE INDEX IF NOT EXISTS idx_hbt_order_node_events_order
  ON hbt_order_node_events(order_id, arrival_at);

CREATE TABLE IF NOT EXISTS hbt_train_nodes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  shipment_id INTEGER,
  waybill_no TEXT,
  station_name TEXT,
  in_at TEXT,
  out_at TEXT,
  lng REAL,
  lat REAL,
  raw_payload TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (shipment_id) REFERENCES business_shipments(shipment_id)
);

CREATE INDEX IF NOT EXISTS idx_hbt_train_nodes_waybill_time
  ON hbt_train_nodes(waybill_no, in_at);

CREATE TABLE IF NOT EXISTS hbt_truck_track_points (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  truck_no TEXT NOT NULL,
  loc_at TEXT NOT NULL,
  lng REAL,
  lat REAL,
  speed REAL,
  address TEXT,
  raw_payload TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS uk_hbt_truck_track_points_truck_time_lng_lat
  ON hbt_truck_track_points(truck_no, loc_at, lng, lat);

CREATE INDEX IF NOT EXISTS idx_hbt_truck_track_points_truck_time
  ON hbt_truck_track_points(truck_no, loc_at);

CREATE TABLE IF NOT EXISTS hbt_sync_cursors (
  cursor_key TEXT PRIMARY KEY,
  cursor_type TEXT NOT NULL,
  device_id TEXT,
  last_success_at TEXT,
  last_run_at TEXT,
  next_run_at TEXT,
  status TEXT NOT NULL DEFAULT 'idle',
  error_message TEXT,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_hbt_sync_cursors_type_status
  ON hbt_sync_cursors(cursor_type, status);

CREATE TABLE IF NOT EXISTS hbt_sync_jobs (
  job_id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_type TEXT NOT NULL,
  device_id TEXT,
  window_start_at TEXT,
  window_end_at TEXT,
  status TEXT NOT NULL,
  request_count INTEGER NOT NULL DEFAULT 0,
  insert_count INTEGER NOT NULL DEFAULT 0,
  update_count INTEGER NOT NULL DEFAULT 0,
  skip_count INTEGER NOT NULL DEFAULT 0,
  error_code TEXT,
  error_message TEXT,
  started_at TEXT NOT NULL,
  finished_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_hbt_sync_jobs_type_time
  ON hbt_sync_jobs(job_type, started_at);

CREATE INDEX IF NOT EXISTS idx_hbt_sync_jobs_status
  ON hbt_sync_jobs(status);
