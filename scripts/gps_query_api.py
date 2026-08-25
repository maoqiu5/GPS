#!/usr/bin/env python3
"""Lightweight GPS query API for HBT data and business bindings.

This intentionally uses only the Python standard library so it can run on the
current BrianHub VPS before the GPS backend container exists.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sqlite3
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen


DEFAULT_DB_PATH = "/root/apps/gps/data/gps/gps_tracking.db"
DEFAULT_SCHEMA_PATH = "/root/apps/gps/schema/HBT_SQLITE_SCHEMA.sql"
MAX_LIMIT = 5000
COUNTRY_ROUTE_RANK = {"CN": 1, "KZ": 2, "RU": 3, "BY": 4, "PL": 5}
TRUCK_AVERAGE_KMH = 75.0
TRUCK_FREIGHT_BASE_EUR = 120.0
TRUCK_FREIGHT_EUR_PER_KM = 1.42
TRUCK_FREIGHT_MIN_EUR = 450.0
HTTP_USER_AGENT = "BrianhubGPS/1.0 (trajectory; https://brianhub.net/gps)"
TRUCK_FREIGHT_DISTANCE_BANDS = [
    (100, 3.20),
    (250, 2.35),
    (500, 1.85),
    (1000, 1.55),
    (999999, TRUCK_FREIGHT_EUR_PER_KM),
]
TRUCK_FREIGHT_COUNTRY_FACTORS = {
    "GB": 1.18,
    "IE": 1.28,
    "CH": 1.22,
    "NO": 1.30,
    "SE": 1.16,
    "FI": 1.18,
    "DK": 1.12,
    "IT": 1.10,
    "ES": 1.12,
    "PT": 1.18,
    "RO": 1.12,
    "BG": 1.16,
    "RS": 1.15,
    "EE": 1.12,
    "LV": 1.12,
    "LT": 1.10,
}
TRUCK_FREIGHT_COUNTRY_SURCHARGES = {"GB": 380, "IE": 520, "NO": 220, "CH": 180}
UK_POSTCODE_PATTERN = re.compile(r"\b([A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2})\b", re.IGNORECASE)
COUNTRY_ALIASES = {
    "The Netherlad": "Netherlands",
    "Netherlad": "Netherlands",
    "The Netherlands": "Netherlands",
    "Nederland": "Netherlands",
    "Deutschland": "Germany",
    "Czechia": "Czech Republic",
    "Eesti": "Estonia",
}
EUROPEAN_POSTCODE_RULES = [
    ("Netherlands", r"\d{4}\s*[A-Z]{2}"),
    ("Poland", r"\d{2}-\d{3}"),
    ("Czech Republic", r"\d{3}\s*\d{2}"),
    ("Slovakia", r"\d{3}\s*\d{2}"),
    ("Germany", r"\d{5}"),
    ("France", r"\d{5}"),
    ("Spain", r"\d{5}"),
    ("Italy", r"\d{5}"),
    ("Estonia", r"\d{5}"),
    ("Belgium", r"\d{4}"),
    ("Austria", r"\d{4}"),
    ("Hungary", r"\d{4}"),
    ("Romania", r"\d{6}"),
    ("Denmark", r"\d{4}"),
    ("Sweden", r"\d{3}\s*\d{2}"),
    ("Finland", r"\d{5}"),
    ("Norway", r"\d{4}"),
    ("Portugal", r"\d{4}-\d{3}"),
    ("Lithuania", r"(?:LT-)?\d{5}"),
    ("Latvia", r"LV-\d{4}"),
    ("Slovenia", r"\d{4}"),
    ("Croatia", r"\d{5}"),
    ("Bulgaria", r"\d{4}"),
    ("Serbia", r"\d{5}"),
]

TRUCK_STATIONS = [
    {"slug": "liege", "name": "Liège / 列日", "city": "Liège-Guillemins, Belgium", "lat": 50.6240, "lon": 5.5660},
    {"slug": "duisburg", "name": "Duisburg / 杜伊斯堡", "city": "Duisburg, Germany", "lat": 51.4344, "lon": 6.7623},
    {"slug": "hamburg", "name": "Hamburg / 汉堡", "city": "Hamburg, Germany", "lat": 53.5511, "lon": 9.9937},
    {"slug": "warsaw", "name": "Warsaw / 华沙", "city": "Warsaw, Poland", "lat": 52.2298, "lon": 21.0118},
    {"slug": "malaszewicze", "name": "Małaszewicze / 马拉舍维奇", "city": "Małaszewicze, Poland", "lat": 52.0250, "lon": 23.5400},
    {"slug": "katowice", "name": "Katowice / 卡托维兹", "city": "Katowice, Poland", "lat": 50.2649, "lon": 19.0238},
    {"slug": "barcelona", "name": "Barcelona / 巴塞罗那", "city": "Barcelona, Spain", "lat": 41.3851, "lon": 2.1734},
    {"slug": "budapest", "name": "Budapest / 布达佩斯", "city": "Budapest, Hungary", "lat": 47.4979, "lon": 19.0402},
    {"slug": "munich", "name": "Munich / 慕尼黑", "city": "Munich, Germany", "lat": 48.1351, "lon": 11.5820},
    {"slug": "krems", "name": "Krems / 克雷姆斯", "city": "Krems an der Donau, Austria", "lat": 48.4092, "lon": 15.6142},
    {"slug": "prague", "name": "Prague / 布拉格", "city": "Prague, Czech Republic", "lat": 50.0755, "lon": 14.4378},
    {"slug": "belgrade", "name": "Belgrade / 贝尔格莱德", "city": "Belgrade, Serbia", "lat": 44.7866, "lon": 20.4489},
]

TRUCK_STATIONS = [
    {"slug": "liege", "name": "Liège / 列日", "city": "Liège Trilogiport, Belgium", "countryCode": "BE", "terminal": "DP World Liège / Trilogiport", "lat": 50.7157, "lon": 5.6813, "sourceNote": "terminal area, operator/OSM cross-check"},
    {"slug": "duisburg", "name": "Duisburg / 杜伊斯堡", "city": "Duisburg Intermodal Terminal, Germany", "countryCode": "DE", "terminal": "DIT Duisburg Intermodal Terminal", "lat": 51.3937, "lon": 6.7307, "sourceNote": "terminal area, public terminal map cross-check"},
    {"slug": "hamburg", "name": "Hamburg / 汉堡", "city": "Hamburg-Billwerder, Germany", "countryCode": "DE", "terminal": "DUSS Terminal Hamburg-Billwerder", "lat": 53.5192, "lon": 10.0951, "sourceNote": "DUSS terminal address/OSM cross-check"},
    {"slug": "warsaw", "name": "Warsaw / 华沙", "city": "Warszawa Praga, Poland", "countryCode": "PL", "terminal": "Warszawa Praga rail freight terminal", "lat": 52.2580, "lon": 21.1040, "sourceNote": "Warsaw rail freight terminal area"},
    {"slug": "malaszewicze", "name": "Małaszewicze / 马拉舍维奇", "city": "Małaszewicze, Poland", "countryCode": "PL", "terminal": "Małaszewicze rail terminal", "lat": 52.0250, "lon": 23.5400, "sourceNote": "rail terminal area"},
    {"slug": "katowice", "name": "Sławków-Katowice / 卡托维兹", "city": "Sławków Euroterminal, Poland", "countryCode": "PL", "terminal": "Sławków Euroterminal", "lat": 50.2817921, "lon": 19.3091219, "sourceNote": "Nominatim/Euroterminal cross-check"},
    {"slug": "barcelona", "name": "Barcelona / 巴塞罗那", "city": "Barcelona Morrot / Can Tunis, Spain", "countryCode": "ES", "terminal": "Barcelona Morrot intermodal terminal", "lat": 41.3520, "lon": 2.1480, "sourceNote": "port rail terminal area"},
    {"slug": "budapest", "name": "Budapest / 布达佩斯", "city": "BILK, Budapest, Hungary", "countryCode": "HU", "terminal": "Rail Cargo Terminal BILK", "lat": 47.4077, "lon": 19.1746, "sourceNote": "BILK/Rail Cargo terminal address cross-check"},
    {"slug": "munich", "name": "Munich / 慕尼黑", "city": "München-Riem, Germany", "countryCode": "DE", "terminal": "DUSS Terminal München-Riem", "lat": 48.1420, "lon": 11.6860, "sourceNote": "DUSS terminal area"},
    {"slug": "krems", "name": "Krems / 克雷姆斯", "city": "Krems an der Donau, Austria", "countryCode": "AT", "terminal": "Donauhafen Krems / rail terminal area", "lat": 48.4104, "lon": 15.6156, "sourceNote": "port/rail terminal area"},
    {"slug": "prague", "name": "Prague / 布拉格", "city": "Praha-Uhříněves, Czech Republic", "countryCode": "CZ", "terminal": "METRANS Praha-Uhříněves", "lat": 50.0326, "lon": 14.5975, "sourceNote": "METRANS terminal area"},
    {"slug": "belgrade", "name": "Belgrade / 贝尔格莱德", "city": "Batajnica, Belgrade, Serbia", "countryCode": "RS", "terminal": "Batajnica intermodal terminal", "lat": 44.9070, "lon": 20.2680, "sourceNote": "Belgrade intermodal terminal area"},
    {"slug": "london", "name": "London / 伦敦", "city": "London Gateway, United Kingdom", "countryCode": "GB", "terminal": "London Gateway rail terminal", "lat": 51.5067, "lon": 0.4946, "sourceNote": "London Gateway rail terminal area"},
    {"slug": "milan", "name": "Milan / 米兰", "city": "Milano Segrate, Italy", "countryCode": "IT", "terminal": "Milano Segrate intermodal terminal", "lat": 45.4866, "lon": 9.2863, "sourceNote": "Segrate rail terminal area"},
    {"slug": "rotterdam-rsc", "name": "Rotterdam RSC / 鹿特丹", "city": "Rotterdam, Netherlands", "countryCode": "NL", "stationGroup": "europe", "terminal": "Rail Service Center Rotterdam", "address": "Albert Plesmanweg 200-210, 3088 GD Rotterdam, Netherlands", "lat": 51.8722, "lon": 4.4283, "sourceNote": "RSC official address; Ships25 terminal coordinates"},
    {"slug": "dunajska-streda", "name": "Dunajská Streda / 多瑙斯特雷达", "city": "Dunajská Streda, Slovakia", "countryCode": "SK", "stationGroup": "europe", "terminal": "METRANS Danubia Dunajská Streda", "address": "METRANS Danubia, Dunajská Streda, Slovakia", "lat": 47.980125, "lon": 17.632186, "sourceNote": "METRANS terminal page GPS"},
    {"slug": "fenyeslitke-east-west-gate", "name": "East-West Gate Fényeslitke / 扎霍尼-费涅什利特凯", "city": "Fényeslitke / Záhony, Hungary", "countryCode": "HU", "stationGroup": "europe", "terminal": "East-West Gate Intermodal Terminal", "address": "Fényeslitke, Hungary", "lat": 48.2853775, "lon": 22.1201239, "sourceNote": "East-West Gate official terminal GPS"},
    {"slug": "lodz-spedcont", "name": "Łódź Spedcont / 罗兹", "city": "Łódź, Poland", "countryCode": "PL", "stationGroup": "europe", "terminal": "Spedcont Łódź terminal", "address": "Tomaszowska 60, 93-231 Łódź, Poland", "lat": 51.7246208, "lon": 19.5419983, "sourceNote": "Spedcont terminal address; Nominatim door-level geocode"},
    {"slug": "mannheim-duss", "name": "Mannheim DUSS / 曼海姆", "city": "Mannheim, Germany", "countryCode": "DE", "stationGroup": "europe", "terminal": "DUSS Terminal Mannheim", "address": "Werfthallenstrasse 40, 68159 Mannheim, Germany", "lat": 49.4945387, "lon": 8.4500662, "sourceNote": "DUSS terminal address; Nominatim street/terminal-area geocode"},
    {"slug": "nurnberg-tricon", "name": "Nürnberg TriCon / 纽伦堡", "city": "Nürnberg, Germany", "countryCode": "DE", "stationGroup": "europe", "terminal": "TriCon Container-Terminal Nürnberg", "address": "Hamburger Strasse 59, 90451 Nürnberg, Germany", "lat": 49.4021364, "lon": 11.0531753, "sourceNote": "TriCon terminal address; Nominatim street/terminal-area geocode"},
    {"slug": "neuss-contargo", "name": "Neuss Contargo / 诺伊斯", "city": "Neuss, Germany", "countryCode": "DE", "stationGroup": "europe", "terminal": "Contargo Neuss Trimodal Terminal", "address": "Flosshafenstrasse 37, 41460 Neuss, Germany", "lat": 51.2195987, "lon": 6.70766, "sourceNote": "Contargo terminal address; Nominatim company-level geocode"},
    {"slug": "bremerhaven-ntb", "name": "Bremerhaven NTB / 不莱梅哈芬", "city": "Bremerhaven, Germany", "countryCode": "DE", "stationGroup": "europe", "terminal": "NTB North Sea Terminal Bremerhaven", "address": "Senator-Borttscheller-Strasse 14, 27568 Bremerhaven, Germany", "lat": 53.5946658, "lon": 8.5370234, "sourceNote": "NTB terminal address; Nominatim company-level geocode"},
    {"slug": "wilhelmshaven-jwp", "name": "Wilhelmshaven JadeWeserPort / 威廉港", "city": "Wilhelmshaven, Germany", "countryCode": "DE", "stationGroup": "europe", "terminal": "JadeWeserPort Wilhelmshaven", "address": "Pazifik 1, 26388 Wilhelmshaven, Germany", "lat": 53.5821209, "lon": 8.1396155, "sourceNote": "JadeWeserPort address; Nominatim port-office geocode"},
    {"slug": "altynkol", "name": "Altynkol / 阿腾科里", "city": "Altynkol, Kazakhstan", "countryCode": "KZ", "stationGroup": "central_asia", "terminal": "Altynkol railway station", "address": "Altynkol railway station, Almaty Region, Kazakhstan", "lat": 44.16465759, "lon": 80.29522705, "sourceNote": "Alta/FreiCON railway-station coordinate reference"},
    {"slug": "tashkent-chukursay", "name": "Tashkent Chukursay / 塔什干丘库尔赛", "city": "Tashkent, Uzbekistan", "countryCode": "UZ", "stationGroup": "central_asia", "terminal": "Chukursay railway station / customs terminal", "address": "Chukursay railway station, Tashkent, Uzbekistan", "lat": 41.38828, "lon": 69.23332, "sourceNote": "OSM/Mapcarta station coordinates; UNECE station listing cross-check"},
    {"slug": "aktau-port", "name": "Aktau Port / 阿克套港", "city": "Aktau, Kazakhstan", "countryCode": "KZ", "stationGroup": "central_asia", "terminal": "Aktau International Sea Commercial Port", "address": "Port of Aktau, Aktau, Kazakhstan", "lat": 43.6465, "lon": 51.1638, "sourceNote": "Wikidata/port coordinate reference cross-check"},
    {"slug": "tbilisi", "name": "Tbilisi / 第比利斯", "city": "Tbilisi, Georgia", "countryCode": "GE", "stationGroup": "central_asia", "terminal": "Tbilisi Dry Port", "address": "Tbilisi Dry Port, Tbilisi, Georgia", "lat": 41.6634026, "lon": 44.9137714, "sourceNote": "Tbilisi Dry Port public location reference"},
]

PORT_DEFINITIONS = [
    {
        "name": "阿拉山口 / 多斯特克口岸",
        "shortName": "阿拉山口/多斯特克",
        "countries": "中国 - 哈萨克斯坦",
        "lat": 45.167,
        "lon": 82.575,
        "radiusKm": 60,
        "note": "中哈铁路口岸，按口岸中心点半径自动匹配。",
    },
    {
        "name": "奥伦堡方向哈俄口岸",
        "shortName": "奥伦堡方向哈俄口岸",
        "countries": "哈萨克斯坦 - 俄罗斯",
        "lat": 51.46,
        "lon": 56.37,
        "radiusKm": 180,
        "note": "按轨迹从哈萨克斯坦西北部进入俄罗斯推定，接近奥伦堡方向通道。",
    },
    {
        "name": "克拉斯诺耶 / 奥西诺夫卡口岸",
        "shortName": "克拉斯诺耶/奥西诺夫卡",
        "countries": "俄罗斯 - 白俄罗斯",
        "lat": 54.73,
        "lon": 31.72,
        "radiusKm": 130,
        "note": "俄白铁路边境口岸，按口岸中心点半径自动匹配。",
    },
    {
        "name": "布列斯特 / 特雷斯波尔口岸",
        "shortName": "布列斯特/特雷斯波尔",
        "countries": "白俄罗斯 - 波兰",
        "lat": 52.083,
        "lon": 23.66,
        "radiusKm": 80,
        "note": "白波边境铁路/公路口岸，按口岸中心点半径自动匹配。",
    },
]

PORT_NOTES = {port["name"]: port["note"] for port in PORT_DEFINITIONS}


def load_port_definitions(con: sqlite3.Connection, route_corridor: str = "china-europe") -> list[dict[str, Any]]:
    try:
        rows = con.execute(
            """
            SELECT port_name, port_short_name, countries, lat, lng, radius_km, note
            FROM gps_port_definitions
            WHERE active = 1 AND route_corridor = ?
            ORDER BY sort_order, port_name
            """,
            (route_corridor,),
        ).fetchall()
    except sqlite3.Error:
        return [dict(port) for port in PORT_DEFINITIONS]
    if not rows:
        return [dict(port) for port in PORT_DEFINITIONS]
    return [
        {
            "name": row["port_name"],
            "shortName": row["port_short_name"],
            "countries": row["countries"],
            "lat": row["lat"],
            "lon": row["lng"],
            "radiusKm": row["radius_km"],
            "note": row["note"],
        }
        for row in rows
    ]


def default_truck_freight_rules() -> dict[str, Any]:
    return {
        "baseEur": TRUCK_FREIGHT_BASE_EUR,
        "distanceBands": TRUCK_FREIGHT_DISTANCE_BANDS,
        "defaultEurPerKm": TRUCK_FREIGHT_EUR_PER_KM,
        "countryFactors": TRUCK_FREIGHT_COUNTRY_FACTORS,
        "countrySurcharges": TRUCK_FREIGHT_COUNTRY_SURCHARGES,
        "minimumEur": TRUCK_FREIGHT_MIN_EUR,
        "emptyReturnMultiplier": 0.65,
        "crossBorderSurchargeEur": 120.0,
        "fuelSurchargeRates": {},
        "cityAccessRules": [],
    }


def load_truck_stations(con: sqlite3.Connection) -> list[dict[str, Any]]:
    try:
        rows = con.execute(
            """
            SELECT slug, name, city, country_code, station_group, terminal, address, lat, lng,
                   source_note, sort_order
            FROM truck_stations
            WHERE active = 1
            ORDER BY sort_order, name
            """
        ).fetchall()
    except sqlite3.Error:
        return [dict(station) for station in TRUCK_STATIONS]
    if not rows:
        return [dict(station) for station in TRUCK_STATIONS]
    return [
        {
            "slug": row["slug"],
            "name": row["name"],
            "city": row["city"],
            "countryCode": row["country_code"],
            "stationGroup": row["station_group"],
            "terminal": row["terminal"],
            "address": row["address"],
            "lat": row["lat"],
            "lon": row["lng"],
            "sourceNote": row["source_note"],
            "sortOrder": row["sort_order"],
        }
        for row in rows
    ]


def load_truck_freight_rules(con: sqlite3.Connection) -> dict[str, Any]:
    rules = default_truck_freight_rules()
    try:
        rows = con.execute(
            """
            SELECT rule_type, country_code, city_pattern, distance_limit_km, amount_eur, multiplier, note
            FROM truck_freight_rules
            WHERE active = 1
            ORDER BY sort_order, rule_key
            """
        ).fetchall()
    except sqlite3.Error:
        return rules
    if not rows:
        return rules
    distance_bands: list[tuple[float, float]] = []
    country_factors: dict[str, float] = {}
    country_surcharges: dict[str, float] = {}
    fuel_surcharge_rates: dict[str, float] = {}
    city_access_rules: list[dict[str, Any]] = []
    for row in rows:
        rule_type = row["rule_type"]
        country_code = str(row["country_code"] or "").upper()
        if rule_type == "base" and row["amount_eur"] is not None:
            rules["baseEur"] = float(row["amount_eur"])
        elif rule_type == "minimum" and row["amount_eur"] is not None:
            rules["minimumEur"] = float(row["amount_eur"])
        elif rule_type == "empty_return_multiplier" and row["multiplier"] is not None:
            rules["emptyReturnMultiplier"] = float(row["multiplier"])
        elif rule_type == "cross_border_surcharge" and row["amount_eur"] is not None:
            rules["crossBorderSurchargeEur"] = float(row["amount_eur"])
        elif rule_type == "fuel_surcharge_rate" and country_code and row["multiplier"] is not None:
            fuel_surcharge_rates[country_code] = float(row["multiplier"])
        elif rule_type in {"city_access_fee", "city_access_advisory"} and row["city_pattern"]:
            city_access_rules.append(
                {
                    "ruleType": rule_type,
                    "countryCode": country_code,
                    "cityPattern": row["city_pattern"],
                    "amountEur": float(row["amount_eur"]) if row["amount_eur"] is not None else None,
                    "note": row["note"],
                }
            )
        elif rule_type == "distance_band" and row["distance_limit_km"] is not None and row["amount_eur"] is not None:
            distance_bands.append((float(row["distance_limit_km"]), float(row["amount_eur"])))
        elif rule_type == "country_factor" and country_code and row["multiplier"] is not None:
            country_factors[country_code] = float(row["multiplier"])
        elif rule_type == "country_surcharge" and country_code and row["amount_eur"] is not None:
            country_surcharges[country_code] = float(row["amount_eur"])
    if distance_bands:
        rules["distanceBands"] = distance_bands
        rules["defaultEurPerKm"] = distance_bands[-1][1]
    if country_factors:
        rules["countryFactors"] = country_factors
    if country_surcharges:
        rules["countrySurcharges"] = country_surcharges
    if fuel_surcharge_rates:
        rules["fuelSurchargeRates"] = fuel_surcharge_rates
    if city_access_rules:
        rules["cityAccessRules"] = city_access_rules
    return rules


def load_truck_market_references(
    con: sqlite3.Connection,
    destination: dict[str, Any] | None = None,
) -> dict[str, Any]:
    country_code = destination_country_code(destination)
    geography_codes = {"EUROPE"}
    if country_code:
        geography_codes.add(country_code)
    try:
        source_rows = con.execute(
            """
            SELECT source_key, source_name, source_type, access_type, coverage_note,
                   url, reliability_level
            FROM truck_market_sources
            WHERE active = 1
            ORDER BY source_type, source_key
            """
        ).fetchall()
        placeholders = ",".join("?" for _ in geography_codes)
        snapshot_rows = con.execute(
            f"""
            SELECT snapshot_id, source_key, observed_at, valid_from, valid_to,
                   geography_code, lane_origin_country, lane_destination_country,
                   equipment_type, metric_type, value_min, value_max, value_pct,
                   currency, unit, confidence, note, source_url
            FROM truck_market_rate_snapshots
            WHERE active = 1
              AND (geography_code IN ({placeholders}) OR metric_type LIKE '%_capability')
            ORDER BY observed_at DESC, metric_type, snapshot_id
            """,
            tuple(sorted(geography_codes)),
        ).fetchall()
    except sqlite3.Error:
        return {"sourceCount": 0, "snapshotCount": 0, "sources": [], "snapshots": []}
    sources = [
        {
            "sourceKey": row["source_key"],
            "sourceName": row["source_name"],
            "sourceType": row["source_type"],
            "accessType": row["access_type"],
            "coverageNote": row["coverage_note"],
            "url": row["url"],
            "reliabilityLevel": row["reliability_level"],
        }
        for row in source_rows
    ]
    snapshots = [
        {
            "snapshotId": row["snapshot_id"],
            "sourceKey": row["source_key"],
            "observedAt": row["observed_at"],
            "validFrom": row["valid_from"],
            "validTo": row["valid_to"],
            "geographyCode": row["geography_code"],
            "laneOriginCountry": row["lane_origin_country"],
            "laneDestinationCountry": row["lane_destination_country"],
            "equipmentType": row["equipment_type"],
            "metricType": row["metric_type"],
            "valueMin": row["value_min"],
            "valueMax": row["value_max"],
            "valuePct": row["value_pct"],
            "currency": row["currency"],
            "unit": row["unit"],
            "confidence": row["confidence"],
            "note": row["note"],
            "sourceUrl": row["source_url"],
        }
        for row in snapshot_rows
    ]
    return {
        "sourceCount": len(sources),
        "snapshotCount": len(snapshots),
        "sources": sources,
        "snapshots": snapshots,
    }


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def json_dumps(data: Any) -> bytes:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def parse_body(raw: bytes) -> dict[str, Any]:
    if not raw:
        return {}
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("JSON body must be an object")
    return data


def as_int(value: str | None, default: int, max_value: int = MAX_LIMIT) -> int:
    if not value:
        return default
    parsed = int(value)
    if parsed < 1:
        return default
    return min(parsed, max_value)


def first_param(params: dict[str, list[str]], name: str) -> str | None:
    values = params.get(name)
    if not values:
        return None
    return values[0]


def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def parse_time(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


def duration_text(start: datetime, end: datetime) -> str:
    seconds = max(0, int((end - start).total_seconds()))
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    if days:
        return f"{days}天{hours}小时{minutes}分"
    return f"{hours}小时{minutes}分"


def haversine_km(a: dict[str, Any], b: dict[str, Any]) -> float:
    radius_km = 6371.0088
    lat1 = math.radians(float(a["lat"]))
    lat2 = math.radians(float(b["lat"]))
    dlat = lat2 - lat1
    dlon = math.radians(float(b["lon"]) - float(a["lon"]))
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * radius_km * math.asin(math.sqrt(h))


def estimate_truck_hours(distance_km: float) -> float:
    return round(float(distance_km) / TRUCK_AVERAGE_KMH, 1)


def freight_rate_per_km(distance_km: float, rules: dict[str, Any] | None = None) -> float:
    distance = float(distance_km)
    active_rules = rules or default_truck_freight_rules()
    for limit, rate in active_rules["distanceBands"]:
        if distance <= limit:
            return rate
    return active_rules["defaultEurPerKm"]


def destination_country_code(destination: dict[str, Any] | None) -> str | None:
    if not destination:
        return None
    country_code = destination.get("countryCode")
    if country_code:
        return str(country_code).upper()
    label = str(destination.get("label") or "").upper()
    country_keywords = {
        "GB": ["UNITED KINGDOM", "ENGLAND", "SCOTLAND", "WALES"],
        "IE": ["IRELAND"],
        "CH": ["SWITZERLAND", "SUISSE", "SCHWEIZ"],
        "NO": ["NORWAY"],
        "SE": ["SWEDEN"],
        "FI": ["FINLAND"],
        "DK": ["DENMARK"],
        "IT": ["ITALY", "ITALIA"],
        "ES": ["SPAIN", "ESPAÑA"],
        "PT": ["PORTUGAL"],
        "RO": ["ROMANIA", "ROMÂNIA"],
        "BG": ["BULGARIA"],
        "RS": ["SERBIA"],
        "EE": ["ESTONIA", "EESTI"],
        "LV": ["LATVIA"],
        "LT": ["LITHUANIA"],
        "RU": ["RUSSIA", "РОССИЯ"],
        "BY": ["BELARUS"],
        "KZ": ["KAZAKHSTAN"],
        "AZ": ["AZERBAIJAN"],
        "GE": ["GEORGIA"],
    }
    for code, keywords in country_keywords.items():
        if any(keyword in label for keyword in keywords):
            return code
    return None


EUROPE_COUNTRY_CODES = {
    "AT", "BE", "BG", "CH", "CZ", "DE", "DK", "EE", "ES", "FI", "FR", "GB", "GR",
    "HR", "HU", "IE", "IT", "LT", "LU", "LV", "NL", "NO", "PL", "PT", "RO", "RS",
    "SE", "SI", "SK",
}
CENTRAL_ASIA_COUNTRY_CODES = {"KZ", "AZ", "GE", "AM", "UZ", "TM", "TJ", "KG"}
TRUCK_STATION_GROUP_LABELS = {
    "europe": "欧洲",
    "central_asia": "中亚",
    "russia": "俄罗斯",
    "belarus": "白罗斯",
}


def resolve_requested_station_group(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().lower().replace("-", "_")
    if not normalized or normalized == "auto":
        return None
    if normalized not in TRUCK_STATION_GROUP_LABELS:
        allowed = ", ".join(["auto", *TRUCK_STATION_GROUP_LABELS.keys()])
        raise ValueError(f"invalid station_group: {value}; allowed: {allowed}")
    return normalized


def destination_station_group(destination: dict[str, Any] | None) -> str | None:
    code = destination_country_code(destination)
    if code == "RU":
        return "russia"
    if code == "BY":
        return "belarus"
    if code in CENTRAL_ASIA_COUNTRY_CODES:
        return "central_asia"
    if code in EUROPE_COUNTRY_CODES:
        return "europe"
    return None


def filter_truck_stations_for_destination(
    stations: list[dict[str, Any]],
    destination: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], str | None]:
    group = destination_station_group(destination)
    if not group:
        return stations, None
    filtered = [station for station in stations if station.get("stationGroup") == group]
    return filtered or stations, group


def filter_truck_stations_for_group(
    stations: list[dict[str, Any]],
    station_group: str | None,
) -> tuple[list[dict[str, Any]], str | None, str]:
    requested_group = resolve_requested_station_group(station_group)
    if not requested_group:
        return stations, None, "auto"
    filtered = [station for station in stations if station.get("stationGroup") == requested_group]
    return filtered or stations, requested_group, "manual"


def fuel_surcharge_rate(country_codes: set[str], rules: dict[str, Any]) -> float:
    rates = rules.get("fuelSurchargeRates") or {}
    country_rates = [rates[code] for code in country_codes if code in rates]
    if country_rates:
        return max(country_rates)
    if country_codes & EUROPE_COUNTRY_CODES and "EUROPE" in rates:
        return rates["EUROPE"]
    return 0.0


def city_access_components(destination: dict[str, Any] | None, rules: dict[str, Any]) -> tuple[float, list[str]]:
    if not destination:
        return 0.0, []
    label = str(destination.get("label") or "").upper()
    country_code = destination_country_code(destination)
    surcharge = 0.0
    notes: list[str] = []
    for rule in rules.get("cityAccessRules") or []:
        if rule.get("countryCode") and country_code and rule["countryCode"] != country_code:
            continue
        pattern = str(rule.get("cityPattern") or "")
        if not pattern or not re.search(pattern, label, flags=re.IGNORECASE):
            continue
        note = str(rule.get("note") or "")
        if note:
            notes.append(note)
        if rule.get("ruleType") == "city_access_fee" and rule.get("amountEur") is not None:
            surcharge += float(rule["amountEur"])
    return surcharge, notes


def calculate_truck_freight_model(
    distance_km: float,
    destination: dict[str, Any] | None = None,
    station: dict[str, Any] | None = None,
    return_station: dict[str, Any] | None = None,
    rules: dict[str, Any] | None = None,
    loaded_km: float | None = None,
    empty_return_km: float = 0.0,
) -> dict[str, Any]:
    distance = float(distance_km)
    loaded_distance = float(loaded_km if loaded_km is not None else max(0.0, distance - float(empty_return_km or 0.0)))
    empty_distance = float(empty_return_km or 0.0)
    active_rules = rules or default_truck_freight_rules()
    country_codes = {
        code
        for code in [
            station.get("countryCode") if station else None,
            destination_country_code(destination),
            return_station.get("countryCode") if return_station else None,
        ]
        if code
    }
    factor = max([active_rules["countryFactors"].get(code, 1.0) for code in country_codes] or [1.0])
    country_surcharge = sum(active_rules["countrySurcharges"].get(code, 0) for code in country_codes)
    cross_border_surcharge = active_rules["crossBorderSurchargeEur"] if len(country_codes) > 1 else 0.0
    rate = freight_rate_per_km(distance, active_rules)
    weighted_km = loaded_distance + empty_distance * active_rules["emptyReturnMultiplier"]
    linehaul_eur = weighted_km * rate * factor
    fuel_rate = fuel_surcharge_rate(country_codes, active_rules)
    fuel_surcharge = linehaul_eur * fuel_rate
    city_access_surcharge, city_access_notes = city_access_components(destination, active_rules)
    surcharge = country_surcharge + cross_border_surcharge + city_access_surcharge
    raw = active_rules["baseEur"] + linehaul_eur + fuel_surcharge + surcharge
    total = int(round(max(active_rules["minimumEur"], raw) / 10.0) * 10)
    return {
        "totalEur": total,
        "ratePerKm": rate,
        "loadedKm": round(loaded_distance, 1),
        "emptyReturnKm": round(empty_distance, 1),
        "billableKm": round(weighted_km, 1),
        "linehaulEur": round(linehaul_eur, 2),
        "fuelSurchargeRate": fuel_rate,
        "fuelSurchargeEur": round(fuel_surcharge, 2),
        "emptyReturnMultiplier": active_rules["emptyReturnMultiplier"],
        "regionalFactor": round(factor, 2),
        "surchargeEur": surcharge,
        "countrySurchargeEur": country_surcharge,
        "crossBorderSurchargeEur": cross_border_surcharge,
        "cityAccessSurchargeEur": round(city_access_surcharge, 2),
        "cityAccessNotes": city_access_notes,
        "minimumEur": active_rules["minimumEur"],
        "countryCodes": sorted(country_codes),
        "confidence": "estimate",
        "note": "FTL 1x40HQ 20-23t market estimate; excludes waiting, special permits, ADR, appointment and supplier-specific surcharges.",
    }


def calculate_truck_freight_eur(
    distance_km: float,
    destination: dict[str, Any] | None = None,
    station: dict[str, Any] | None = None,
    return_station: dict[str, Any] | None = None,
    rules: dict[str, Any] | None = None,
) -> int:
    return calculate_truck_freight_model(distance_km, destination, station, return_station, rules)["totalEur"]


def find_truck_station(slug: str | None, stations: list[dict[str, Any]] | None = None) -> dict[str, Any] | None:
    if not slug:
        return None
    for station in stations or TRUCK_STATIONS:
        if station["slug"] == slug:
            return station
    raise ValueError(f"unknown return_station: {slug}")


def parse_coordinate_query(value: str) -> dict[str, float] | None:
    parts = [part.strip() for part in value.replace("，", ",").split(",")]
    if len(parts) != 2:
        return None
    try:
        lat = float(parts[0])
        lon = float(parts[1])
    except ValueError:
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return {"lat": lat, "lon": lon}


def http_json(url: str, timeout: float = 15.0) -> Any:
    request = Request(url, headers={"User-Agent": HTTP_USER_AGENT, "Accept": "application/json"})
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def extract_uk_postcode(address: str) -> str | None:
    match = UK_POSTCODE_PATTERN.search(address.replace("\u00a0", " "))
    if not match:
        return None
    raw = re.sub(r"\s+", "", match.group(1).upper())
    return f"{raw[:-3]} {raw[-3:]}"


def geocode_uk_postcode(address: str) -> dict[str, Any] | None:
    postcode = extract_uk_postcode(address)
    if not postcode:
        return None
    from urllib.parse import quote

    data = http_json(f"https://api.postcodes.io/postcodes/{quote(postcode.replace(' ', ''))}", timeout=12.0)
    result = data.get("result") if isinstance(data, dict) else None
    if not result or result.get("latitude") is None or result.get("longitude") is None:
        return None
    label_parts = [
        result.get("postcode") or postcode,
        result.get("parish"),
        result.get("admin_district"),
        result.get("admin_county"),
        result.get("country"),
    ]
    return {
        "label": ", ".join(str(part) for part in label_parts if part),
        "lat": float(result["latitude"]),
        "lon": float(result["longitude"]),
        "countryCode": "GB",
        "source": "postcodes.io",
        "query": postcode,
    }


def append_candidate(candidates: list[str], candidate: str | None) -> None:
    if not candidate:
        return
    cleaned = re.sub(r"\s+", " ", candidate).strip(" ,")
    if cleaned and cleaned not in candidates:
        candidates.append(cleaned)


def romanian_ascii(value: str) -> str:
    return value.translate(str.maketrans({"ă": "a", "â": "a", "î": "i", "ș": "s", "ş": "s", "ț": "t", "ţ": "t", "Ă": "A", "Â": "A", "Î": "I", "Ș": "S", "Ş": "S", "Ț": "T", "Ţ": "T"}))


def normalize_country_aliases(value: str) -> str:
    normalized = value
    for alias, country in COUNTRY_ALIASES.items():
        normalized = re.sub(rf"\b{re.escape(alias)}\b", country, normalized, flags=re.IGNORECASE)
    return normalized


def strip_non_address_noise(value: str) -> str:
    cleaned = value.replace("\u00a0", " ").replace("\n", " ")
    cleaned = re.sub(r"\bGHIMB\s+AV\b", "GHIMBAV", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r",?\s*VAT\s+[A-Z]{2}[A-Z0-9]+\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r",?\s*(?:TEL|PHONE|MOB|MOBILE|CONTACT|ATTN)\.?\s*[:：]?\s*[^,;]+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,")
    return normalize_country_aliases(cleaned)


def strip_company_prefix(value: str) -> str:
    stripped = re.sub(
        r"^\s*.*?\b(?:Warehouse|Limited|Ltd|GmbH|S\.?A\.?|S\.?R\.?L\.?|SAS|SARL|S\.?R\.?O\.?|Sp\.?\s*z\s*o\.?o\.?|NV|BV)\b\s*,?\s*",
        "",
        value,
        flags=re.IGNORECASE,
    ).strip(" ,")
    stripped = re.sub(r"^(?:s\.?r\.?o\.?|s\.?r\.?l\.?|sp\.?\s*z\s*o\.?o\.?)\s*,?\s*", "", stripped, flags=re.IGNORECASE)
    return re.sub(r"^[\s,.;:-]+", "", stripped).strip(" ,")


def add_european_postcode_candidates(candidates: list[str], source: str) -> None:
    for country, postcode_pattern in EUROPEAN_POSTCODE_RULES:
        if not re.search(rf"\b{re.escape(country)}\b", source, flags=re.IGNORECASE):
            continue
        pattern = rf"(.+?)(?:,\s*)?({postcode_pattern})[,\s]+([^,]+?)(?:,\s*{re.escape(country)})?$"
        match = re.search(pattern, source, flags=re.IGNORECASE)
        if not match:
            continue
        street, postcode, city = match.groups()
        street = street.strip(" ,")
        postcode = re.sub(r"\s+", " ", postcode.upper()).strip()
        city = city.strip(" ,")
        append_candidate(candidates, f"{street}, {postcode} {city}, {country}")
        append_candidate(candidates, f"{postcode} {city}, {country}")


def truck_geocode_candidates(address: str) -> list[str]:
    cleaned_address = strip_non_address_noise(address)
    candidates: list[str] = []
    append_candidate(candidates, cleaned_address)
    append_candidate(candidates, extract_uk_postcode(cleaned_address))

    normalized_address = cleaned_address
    replacements = {
        r"\bJUD\.\s*": "",
        r"\bORS\.\s*": "",
        r"\bStr\.\s*": "Strada ",
        r"\bNr\.?\s*": "",
        r"\bBI\.?\s*": "",
        r"\bBl\.?\s*": "",
        r"\bHala\s*\d+\b": "",
        r"\.?\blocatia\s*\d+\b": "",
    }
    for pattern, value in replacements.items():
        normalized_address = re.sub(pattern, value, normalized_address, flags=re.IGNORECASE)
    normalized_address = re.sub(r"\bSteet\b", "Street", normalized_address, flags=re.IGNORECASE)
    normalized_address = re.sub(r"\bStr\.?\b", "Street", normalized_address, flags=re.IGNORECASE)
    normalized_address = re.sub(r"\s*,\s*", ", ", normalized_address)
    normalized_address = re.sub(r"\s+", " ", normalized_address).strip(" ,")
    append_candidate(candidates, normalized_address)

    address_without_company = strip_company_prefix(normalized_address)
    append_candidate(candidates, address_without_company)
    add_european_postcode_candidates(candidates, normalized_address)
    if address_without_company != normalized_address:
        add_european_postcode_candidates(candidates, address_without_company)

    upper = normalized_address.upper()
    if "GHIMBAV" in upper and "HERMANN OBERTH" in upper:
        append_candidate(candidates, "Strada Hermann Oberth 23, Ghimbav, Brasov, Romania")
        append_candidate(candidates, "Hermann Oberth 23, Ghimbav, Brasov, Romania")
        append_candidate(candidates, "Ghimbav, Brasov, Romania")
    ascii_address = romanian_ascii(normalized_address)
    ro_oltenitei_match = re.search(
        r"\b(\d+[A-Z]?)\s+Oltenitei\s+Street,?\s*([^,]+),?\s*Ilfov,?\s*(\d{6})\b",
        ascii_address,
        flags=re.IGNORECASE,
    )
    if ro_oltenitei_match:
        number, city, postcode = ro_oltenitei_match.groups()
        city_ascii = romanian_ascii(city).strip(" ,")
        append_candidate(candidates, f"Soseaua Oltenitei {number.upper()}, {postcode} {city_ascii}, Ilfov, Romania")
        append_candidate(candidates, f"Sos. Oltenitei nr. {number.upper()}, {postcode} {city_ascii}, Ilfov, Romania")
        append_candidate(candidates, f"Șoseaua Olteniței {number.upper()}, Popești-Leordeni, Ilfov, Romania")
        append_candidate(candidates, f"CTPark Bucharest South, Oltenitei 249, Popesti-Leordeni, Romania")
    bg_plovdiv_match = re.search(
        r"\b(\d+[A-Z]?)\s+([A-Z][A-Z .'-]+?)\s+Street,?\s*Plovdiv,?\s*Bulgaria\b",
        normalized_address,
        flags=re.IGNORECASE,
    )
    if bg_plovdiv_match:
        number, street = bg_plovdiv_match.groups()
        street = re.sub(r"\s+", " ", street).title().strip(" ,")
        append_candidate(candidates, f"{street} {number.upper()}, 4023 Plovdiv, Bulgaria")
        append_candidate(candidates, f"ul. {street} {number.upper()}, 4023 Plovdiv, Bulgaria")
        append_candidate(candidates, f"{number.upper()} {street} Street, 4023 Plovdiv, Bulgaria")
    return candidates

    cleaned = " ".join(address.replace("\u00a0", " ").replace("\n", " ").split())
    cleaned = re.sub(r"\bGHIMB\s+AV\b", "GHIMBAV", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r",?\s*VAT\s+[A-Z]{2}[A-Z0-9]+\b", "", cleaned, flags=re.IGNORECASE).strip(" ,")
    candidates = [cleaned]
    normalized = cleaned.replace("The Netherlad", "The Netherlands").replace("Netherlad", "Netherlands")
    replacements = {
        r"\bJUD\.\s*": "",
        r"\bORS\.\s*": "",
        r"\bStr\.\s*": "Strada ",
        r"\bNr\.?\s*": "",
        r"\bBI\.?\s*": "",
        r"\bBl\.?\s*": "",
        r"\bHala\s*\d+\b": "",
        r"\.?\blocatia\s*\d+\b": "",
    }
    for pattern, value in replacements.items():
        normalized = re.sub(pattern, value, normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\s*,\s*", ", ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip(" ,")
    if normalized and normalized not in candidates:
        candidates.append(normalized)

    # Company names often make public geocoders miss otherwise valid street/postcode addresses.
    address_without_company = re.sub(
        r"^\s*.*?\b(?:Warehouse|Limited|Ltd|GmbH|S\.?A\.?|S\.?R\.?L\.?)\b\s*,?\s*",
        "",
        normalized,
        flags=re.IGNORECASE,
    ).strip(" ,")
    if address_without_company and address_without_company not in candidates:
        candidates.append(address_without_company)

    nl_match = re.search(r"([A-Za-zÀ-ÿ' .-]+\s+\d+[A-Za-z]?)\s*,?\s*(\d{4}\s*[A-Z]{2})\s+([A-Za-zÀ-ÿ' .-]+)", normalized, flags=re.IGNORECASE)
    if nl_match:
        street, postcode, city = nl_match.groups()
        nl_candidates = [
            f"{street.strip()}, {postcode.upper().strip()} {city.strip()}, Netherlands",
            f"{postcode.upper().strip()} {city.strip()}, Netherlands",
        ]
        for candidate in nl_candidates:
            if candidate not in candidates:
                candidates.append(candidate)

    ee_match = re.search(r"([A-Za-zÀ-ÿ' .-]+\s+\d+[A-Za-z]?)\s*,?\s*(\d{5})\s*,?\s*([A-Za-zÀ-ÿ' .-]+)\s*,?\s*ESTONIA", normalized, flags=re.IGNORECASE)
    if ee_match:
        street, postcode, city = ee_match.groups()
        ee_candidates = [
            f"{street.strip()}, {postcode.strip()} {city.strip()}, Estonia",
            f"{postcode.strip()} {city.strip()}, Estonia",
        ]
        for candidate in ee_candidates:
            if candidate not in candidates:
                candidates.append(candidate)

    upper = normalized.upper()
    if "GHIMBAV" in upper and "HERMANN OBERTH" in upper:
        candidates.extend(
            [
                "Strada Hermann Oberth 23, Ghimbav, Brasov, Romania",
                "Hermann Oberth 23, Ghimbav, Brasov, Romania",
                "Ghimbav, Brasov, Romania",
            ]
        )

    unique: list[str] = []
    for candidate in candidates:
        if candidate and candidate not in unique:
            unique.append(candidate)
    return unique


def geocode_address(address: str) -> dict[str, Any]:
    coordinates = parse_coordinate_query(address)
    if coordinates:
        return {
            "label": f"{coordinates['lat']}, {coordinates['lon']}",
            "lat": coordinates["lat"],
            "lon": coordinates["lon"],
            "source": "coordinates",
        }
    postcode_result = geocode_uk_postcode(address)
    if postcode_result:
        return postcode_result
    from urllib.parse import urlencode

    tried: list[str] = []
    for candidate in truck_geocode_candidates(address):
        tried.append(candidate)
        query = urlencode({"format": "jsonv2", "limit": "1", "q": candidate, "addressdetails": "1"})
        data = http_json(f"https://nominatim.openstreetmap.org/search?{query}", timeout=18.0)
        if isinstance(data, list) and data:
            item = data[0]
            return {
                "label": item.get("display_name") or candidate,
                "lat": float(item["lat"]),
                "lon": float(item["lon"]),
                "countryCode": str((item.get("address") or {}).get("country_code") or "").upper() or None,
                "source": "nominatim",
                "query": candidate,
            }

    upper = address.upper()
    if "GHIMBAV" in upper and "HERMANN OBERTH" in upper:
        return {
            "label": "Strada Hermann Oberth 23, Ghimbav, Brasov, Romania",
            "lat": 45.6877,
            "lon": 25.51944,
            "countryCode": "RO",
            "source": "known-fallback",
            "query": tried[-1] if tried else address,
        }
    if "NESTOR ABADZHIEV" in upper and "PLOVDIV" in upper and "BULGARIA" in upper:
        return {
            "label": "57 Nestor Abadzhiev str., 4023 Plovdiv, Bulgaria",
            "lat": 42.118611,
            "lon": 24.783611,
            "countryCode": "BG",
            "source": "known-fallback",
            "query": tried[-1] if tried else address,
        }
    raise ValueError("address not found")


def build_truck_distance_fallback(
    destination: dict[str, Any],
    return_station: dict[str, Any] | None = None,
    stations: list[dict[str, Any]] | None = None,
    freight_rules: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for station in stations or TRUCK_STATIONS:
        door_km = haversine_km(station, destination) * 1.28
        return_km = haversine_km(destination, return_station) * 1.28 if return_station else 0.0
        estimate_km = door_km + return_km
        freight_model = calculate_truck_freight_model(
            estimate_km,
            destination,
            station,
            return_station,
            freight_rules,
            loaded_km=door_km,
            empty_return_km=return_km,
        )
        results.append(
            {
                "station": station,
                "distanceKm": round(estimate_km, 1),
                "durationHours": estimate_truck_hours(estimate_km),
                "freightEur": freight_model["totalEur"],
                "freightModel": freight_model,
                "returnStation": return_station,
                "source": "estimate",
                "geometry": None,
            }
        )
    return sorted(results, key=lambda item: item["distanceKm"])


def osrm_route(
    station: dict[str, Any],
    destination: dict[str, Any],
    return_station: dict[str, Any] | None = None,
    freight_rules: dict[str, Any] | None = None,
) -> dict[str, Any]:
    coordinates = [
        f"{station['lon']},{station['lat']}",
        f"{destination['lon']},{destination['lat']}",
    ]
    if return_station:
        coordinates.append(f"{return_station['lon']},{return_station['lat']}")
    url = (
        "https://router.project-osrm.org/route/v1/driving/"
        f"{';'.join(coordinates)}"
        "?overview=simplified&geometries=geojson&alternatives=false&steps=false"
    )
    data = http_json(url, timeout=25.0)
    routes = data.get("routes") if isinstance(data, dict) else None
    if not routes:
        raise ValueError("route not found")
    route = routes[0]
    distance_km = float(route["distance"]) / 1000
    legs = route.get("legs") or []
    loaded_km = float(legs[0]["distance"]) / 1000 if legs else distance_km
    empty_return_km = float(legs[1]["distance"]) / 1000 if return_station and len(legs) > 1 else 0.0
    freight_model = calculate_truck_freight_model(
        distance_km,
        destination,
        station,
        return_station,
        freight_rules,
        loaded_km=loaded_km,
        empty_return_km=empty_return_km,
    )
    return {
        "station": station,
        "distanceKm": round(distance_km, 1),
        "durationHours": round(float(route["duration"]) / 3600, 1),
        "freightEur": freight_model["totalEur"],
        "freightModel": freight_model,
        "returnStation": return_station,
        "source": "osrm",
        "geometry": route.get("geometry"),
    }


def calculate_truck_distances(
    destination: dict[str, Any],
    return_station_slug: str | None = None,
    stations: list[dict[str, Any]] | None = None,
    freight_rules: dict[str, Any] | None = None,
    return_station: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    active_stations = stations or TRUCK_STATIONS
    if return_station is None:
        return_station = find_truck_station(return_station_slug, active_stations)
    results: list[dict[str, Any]] = []
    for station in active_stations:
        try:
            results.append(osrm_route(station, destination, return_station, freight_rules))
        except Exception:
            estimate = build_truck_distance_fallback(destination, return_station, active_stations, freight_rules)
            fallback = next(item for item in estimate if item["station"]["slug"] == station["slug"])
            results.append(fallback)
    return sorted(results, key=lambda item: item["distanceKm"])


def nearest_port_match(point: dict[str, Any], port_definitions: list[dict[str, Any]]) -> dict[str, Any] | None:
    nearest: dict[str, Any] | None = None
    nearest_distance: float | None = None
    for port in port_definitions:
        if port.get("lat") is None or port.get("lon") is None:
            continue
        distance = haversine_km(point, {"lat": port["lat"], "lon": port["lon"]})
        if nearest_distance is None or distance < nearest_distance:
            nearest = port
            nearest_distance = distance
    if nearest is None or nearest_distance is None:
        return None
    radius_km = float(nearest.get("radiusKm") or 0)
    matched = radius_km > 0 and nearest_distance <= radius_km * 1.5
    return {
        "port": nearest,
        "distanceKm": round(nearest_distance, 1),
        "matched": matched,
    }


def hours_between(a: dict[str, Any], b: dict[str, Any]) -> float:
    return max((b["_dt"] - a["_dt"]).total_seconds() / 3600, 1e-9)


def country_for_point(lat: float, lon: float) -> dict[str, str]:
    # Route-corridor spatial rules for the current China-Europe railway lane.
    # These longitude thresholds avoid broad country bounding-box overlap.
    # Keep this isolated so it can later be replaced by GeoJSON point-in-polygon.
    if 18.0 <= lat <= 54.8 and lon >= 82.56:
        return {"name": "中国", "code": "CN"}
    if 40.0 <= lat <= 56.5 and 60.0 <= lon < 82.56:
        return {"name": "哈萨克斯坦", "code": "KZ"}
    if 41.0 <= lat <= 82.5 and 33.0 <= lon < 60.0:
        return {"name": "俄罗斯", "code": "RU"}
    if 51.0 <= lat <= 56.5 and 23.05 <= lon < 33.0:
        return {"name": "白俄罗斯", "code": "BY"}
    if 49.0 <= lat <= 55.2 and 14.0 <= lon < 23.05:
        return {"name": "波兰", "code": "PL"}
    return {"name": "未知", "code": "UN"}


def analyze_track(device_id: str, rows: list[dict[str, Any]], port_definitions: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    raw_points: list[dict[str, Any]] = []
    for row in rows:
        if row.get("lng") is None or row.get("lat") is None or not row.get("loc_at"):
            continue
        idx = len(raw_points) + 1
        loc_at = str(row["loc_at"])
        lat = round(float(row["lat"]), 6)
        lon = round(float(row["lng"]), 6)
        country = country_for_point(lat, lon)
        raw_points.append(
            {
                "idx": idx,
                "device_id": row.get("device_id") or device_id,
                "time": loc_at,
                "_dt": parse_time(loc_at),
                "lat": lat,
                "lon": lon,
                "battery": row.get("soc"),
                "speed": row.get("speed"),
                "country": country["name"],
                "countryCode": country["code"],
            }
        )

    removed: list[dict[str, Any]] = []
    for i in range(1, len(raw_points) - 1):
        prev_point = raw_points[i - 1]
        point = raw_points[i]
        next_point = raw_points[i + 1]
        prev_distance = haversine_km(prev_point, point)
        next_distance = haversine_km(point, next_point)
        shortcut_distance = haversine_km(prev_point, next_point)
        prev_speed = prev_distance / hours_between(prev_point, point)
        next_speed = next_distance / hours_between(point, next_point)
        shortcut_speed = shortcut_distance / hours_between(prev_point, next_point)
        detour_ratio = (prev_distance + next_distance) / max(shortcut_distance, 1)
        if (
            prev_distance > 150
            and next_distance > 150
            and prev_speed > 120
            and next_speed > 120
            and detour_ratio > 3
            and shortcut_speed < 80
        ):
            removed.append(
                {
                    "idx": point["idx"],
                    "time": point["time"],
                    "lat": point["lat"],
                    "lon": point["lon"],
                    "country": point["country"],
                    "prevSpeed": round(prev_speed, 1),
                    "nextSpeed": round(next_speed, 1),
                    "shortcutSpeed": round(shortcut_speed, 1),
                    "detourRatio": round(detour_ratio, 1),
                    "reason": "前后两段速度异常且形成尖刺，跳过该点后路线恢复合理。",
                }
            )

    removed_ids = {point["idx"] for point in removed}
    clean_points = [point for point in raw_points if point["idx"] not in removed_ids]
    country_order = ["中国", "哈萨克斯坦", "俄罗斯", "白俄罗斯", "波兰", "未知"]
    country_counts = {name: sum(1 for point in clean_points if point["country"] == name) for name in country_order}
    active_port_definitions = port_definitions or PORT_DEFINITIONS

    border_crossings: list[dict[str, Any]] = []
    seen_forward_borders: set[tuple[str, str]] = set()
    for i in range(1, len(clean_points)):
        previous = clean_points[i - 1]
        current = clean_points[i]
        if previous["countryCode"] == current["countryCode"]:
            continue
        if "UN" in {previous["countryCode"], current["countryCode"]}:
            continue
        previous_rank = COUNTRY_ROUTE_RANK.get(previous["countryCode"], 0)
        current_rank = COUNTRY_ROUTE_RANK.get(current["countryCode"], 0)
        if current_rank <= previous_rank:
            continue
        border_key = (previous["countryCode"], current["countryCode"])
        if border_key in seen_forward_borders:
            continue
        seen_forward_borders.add(border_key)
        midpoint = {
            "lat": round((previous["lat"] + current["lat"]) / 2, 6),
            "lon": round((previous["lon"] + current["lon"]) / 2, 6),
        }
        match = nearest_port_match(midpoint, active_port_definitions)
        matched_port = match["port"] if match and match["matched"] else None
        border_crossings.append(
            {
                "seqNo": len(border_crossings) + 1,
                "fromCountry": previous["country"],
                "fromCountryCode": previous["countryCode"],
                "toCountry": current["country"],
                "toCountryCode": current["countryCode"],
                "fromPoint": previous["idx"],
                "toPoint": current["idx"],
                "crossingTime": current["time"],
                "lat": midpoint["lat"],
                "lon": midpoint["lon"],
                "matchedPortName": matched_port.get("name") if matched_port else None,
                "matchedPortShortName": matched_port.get("shortName") if matched_port else None,
                "matchedDistanceKm": match["distanceKm"] if match else None,
                "confidence": 0.85 if matched_port else 0.55,
                "note": "根据相邻有效轨迹点的国家归属变化自动识别；坐标取两点中点。",
            }
        )

    ports: list[dict[str, Any]] = []
    segments: list[dict[str, Any]] = []
    origin = "始发站"
    destination = "目的站"
    if clean_points:
        origin = f"始发站（{clean_points[0]['country']}）"
        destination = f"目的站（{clean_points[-1]['country']}）"
    last_node = {
        "name": origin,
        "departTime": clean_points[0]["time"] if clean_points else "",
        "departDt": clean_points[0]["_dt"] if clean_points else None,
    }

    for definition in active_port_definitions:
        port = dict(definition)
        inside = [
            point
            for point in clean_points
            if haversine_km(point, {"lat": port["lat"], "lon": port["lon"]}) <= port["radiusKm"]
        ]
        if inside:
            arrival = inside[0]
            departure = inside[-1]
            port.update(
                {
                    "arrivalPoint": arrival["idx"],
                    "departurePoint": departure["idx"],
                    "nearPoints": (
                        f"{arrival['idx']}-{departure['idx']}"
                        if arrival["idx"] != departure["idx"]
                        else str(arrival["idx"])
                    ),
                    "arrivalTime": arrival["time"],
                    "departureTime": departure["time"],
                    "waitDuration": duration_text(arrival["_dt"], departure["_dt"]),
                    "waitHours": round((departure["_dt"] - arrival["_dt"]).total_seconds() / 3600, 1),
                }
            )
            if last_node["departDt"]:
                segments.append(
                    {
                        "name": f"{last_node['name']} → {port['shortName']}",
                        "from": last_node["name"],
                        "to": port["shortName"],
                        "departTime": last_node["departTime"],
                        "arrivalTime": arrival["time"],
                        "transportDuration": duration_text(last_node["departDt"], arrival["_dt"]),
                        "transportHours": round((arrival["_dt"] - last_node["departDt"]).total_seconds() / 3600, 1),
                        "portWait": port["waitDuration"],
                        "portName": port["shortName"],
                    }
                )
            last_node = {"name": port["shortName"], "departTime": departure["time"], "departDt": departure["_dt"]}
        else:
            port.update(
                {
                    "arrivalPoint": None,
                    "departurePoint": None,
                    "nearPoints": "-",
                    "arrivalTime": "-",
                    "departureTime": "-",
                    "waitDuration": "-",
                    "waitHours": 0,
                }
            )
        ports.append(port)

    if clean_points and last_node["departDt"]:
        segments.append(
            {
                "name": f"{last_node['name']} → {destination}",
                "from": last_node["name"],
                "to": destination,
                "departTime": last_node["departTime"],
                "arrivalTime": clean_points[-1]["time"],
                "transportDuration": duration_text(last_node["departDt"], clean_points[-1]["_dt"]),
                "transportHours": round((clean_points[-1]["_dt"] - last_node["departDt"]).total_seconds() / 3600, 1),
                "portWait": "-",
                "portName": "-",
            }
        )

    route_nodes = [origin] + [port["shortName"] for port in ports if port["arrivalPoint"]] + [destination]
    total_duration = duration_text(clean_points[0]["_dt"], clean_points[-1]["_dt"]) if clean_points else "-"
    public_points = [{key: value for key, value in point.items() if key != "_dt"} for point in clean_points]
    return {
        "device_id": device_id,
        "points": public_points,
        "removedPoints": removed,
        "ports": ports,
        "borderCrossings": border_crossings,
        "route": {
            "origin": origin,
            "destination": destination,
            "nodes": route_nodes,
            "routeText": " → ".join(route_nodes),
            "totalDuration": total_duration,
            "startTime": clean_points[0]["time"] if clean_points else "",
            "endTime": clean_points[-1]["time"] if clean_points else "",
            "segments": segments,
        },
        "meta": {
            "device": device_id,
            "rawCount": len(raw_points),
            "count": len(clean_points),
            "removedCount": len(removed),
            "start": clean_points[0]["time"] if clean_points else "",
            "end": clean_points[-1]["time"] if clean_points else "",
            "countries": [name for name in country_order if country_counts[name] > 0],
            "countryCounts": country_counts,
            "totalDuration": total_duration,
        },
    }


class GpsRepository:
    def __init__(self, db_path: Path, schema_path: Path | None = None) -> None:
        self.db_path = db_path
        self.schema_path = schema_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        if schema_path and schema_path.exists():
            with self.connect() as con:
                self.apply_lightweight_migrations(con)
                con.executescript(schema_path.read_text(encoding="utf-8"))
                con.commit()

    def connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(str(self.db_path))
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        return con

    def apply_lightweight_migrations(self, con: sqlite3.Connection) -> None:
        try:
            columns = {row["name"] for row in con.execute("PRAGMA table_info(truck_stations)").fetchall()}
            if columns and "station_group" not in columns:
                con.execute("ALTER TABLE truck_stations ADD COLUMN station_group TEXT NOT NULL DEFAULT 'europe'")
            freight_columns = {row["name"] for row in con.execute("PRAGMA table_info(truck_freight_rules)").fetchall()}
            if freight_columns and "city_pattern" not in freight_columns:
                con.execute("ALTER TABLE truck_freight_rules ADD COLUMN city_pattern TEXT")
        except sqlite3.Error:
            pass

    def port_definitions(self, route_corridor: str = "china-europe") -> list[dict[str, Any]]:
        with self.connect() as con:
            return load_port_definitions(con, route_corridor)

    def truck_stations(self) -> list[dict[str, Any]]:
        with self.connect() as con:
            return load_truck_stations(con)

    def truck_freight_rules(self) -> dict[str, Any]:
        with self.connect() as con:
            return load_truck_freight_rules(con)

    def truck_market_references(self, destination: dict[str, Any] | None = None) -> dict[str, Any]:
        with self.connect() as con:
            return load_truck_market_references(con, destination)

    def list_port_definitions(self, params: dict[str, list[str]]) -> list[dict[str, Any]]:
        route_corridor = first_param(params, "route_corridor") or "china-europe"
        include_inactive = first_param(params, "include_inactive") in {"1", "true", "yes"}
        sql = """
            SELECT port_id, port_name, port_short_name, countries, lat, lng, radius_km,
                   note, route_corridor, sort_order, active, created_at, updated_at
            FROM gps_port_definitions
            WHERE route_corridor = ?
        """
        values: list[Any] = [route_corridor]
        if not include_inactive:
            sql += " AND active = 1"
        sql += " ORDER BY sort_order, port_name"
        with self.connect() as con:
            return [row_to_dict(row) for row in con.execute(sql, values).fetchall()]

    def list_devices(self, params: dict[str, list[str]]) -> list[dict[str, Any]]:
        limit = as_int(first_param(params, "limit"), 200)
        status = first_param(params, "status")
        active_only = first_param(params, "active_only") in {"1", "true", "yes"}
        sql = """
            SELECT device_id, org_root_id, org_id, status, last_loc_at, last_upload_at,
                   last_lng, last_lat, soc, upload_frequency, service_expire_at
            FROM hbt_devices
            WHERE 1 = 1
        """
        values: list[Any] = []
        if status:
            sql += " AND status = ?"
            values.append(int(status))
        if active_only:
            sql += " AND last_loc_at IS NOT NULL"
        sql += " ORDER BY CASE WHEN status = 1 THEN 0 ELSE 1 END, last_loc_at IS NULL, last_loc_at DESC, device_id LIMIT ?"
        values.append(limit)
        with self.connect() as con:
            return [row_to_dict(row) for row in con.execute(sql, values).fetchall()]

    def list_trajectory_devices(self, params: dict[str, list[str]]) -> list[dict[str, Any]]:
        limit = as_int(first_param(params, "limit"), 100)
        with self.connect() as con:
            rows = con.execute(
                """
                SELECT c.device_id, c.payload_json, c.precomputed_at,
                       d.status, d.last_loc_at, d.soc
                FROM gps_trajectory_cache c
                LEFT JOIN hbt_devices d ON d.device_id = c.device_id
                ORDER BY d.last_loc_at IS NULL, d.last_loc_at DESC, c.device_id
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        devices: list[dict[str, Any]] = []
        for row in rows:
            meta: dict[str, Any] = {}
            try:
                payload = json.loads(row["payload_json"])
                if isinstance(payload, dict) and isinstance(payload.get("meta"), dict):
                    meta = payload["meta"]
            except json.JSONDecodeError:
                meta = {}
            devices.append(
                {
                    "deviceId": row["device_id"],
                    "status": row["status"],
                    "lastLocAt": row["last_loc_at"],
                    "soc": row["soc"],
                    "trackPointCount": meta.get("count"),
                    "rawPointCount": meta.get("rawCount"),
                    "removedCount": meta.get("removedCount"),
                    "totalDuration": meta.get("totalDuration"),
                    "start": meta.get("start"),
                    "end": meta.get("end"),
                    "precomputedAt": row["precomputed_at"],
                }
            )
        return devices

    def list_bindings(self, params: dict[str, list[str]]) -> list[dict[str, Any]]:
        limit = as_int(first_param(params, "limit"), 200)
        sql = """
            SELECT b.*, r.route_code, r.route_name
            FROM device_business_bindings b
            LEFT JOIN business_routes r ON r.route_id = b.route_id
            WHERE 1 = 1
        """
        values: list[Any] = []
        for field in ("device_id", "container_no", "route_id", "order_id", "truck_no"):
            value = first_param(params, field)
            if value:
                sql += f" AND b.{field} = ?"
                values.append(value)
        active_at = first_param(params, "active_at")
        if active_at:
            sql += " AND b.bind_start_at <= ? AND (b.bind_end_at IS NULL OR b.bind_end_at > ?)"
            values.extend([active_at, active_at])
        sql += " ORDER BY b.bind_start_at DESC, b.binding_id DESC LIMIT ?"
        values.append(limit)
        with self.connect() as con:
            return [row_to_dict(row) for row in con.execute(sql, values).fetchall()]

    def create_binding(self, body: dict[str, Any]) -> dict[str, Any]:
        required = ["device_id", "bind_start_at", "source"]
        missing = [name for name in required if not body.get(name)]
        if missing:
            raise ValueError(f"missing required fields: {', '.join(missing)}")
        if not any(body.get(name) for name in ("container_no", "route_id", "shipment_id", "order_id", "truck_no")):
            raise ValueError("one business key is required: container_no, route_id, shipment_id, order_id, or truck_no")

        now = utc_now_iso()
        raw_payload = body.get("raw_payload")
        if raw_payload is not None and not isinstance(raw_payload, str):
            raw_payload = json.dumps(raw_payload, ensure_ascii=False, separators=(",", ":"))

        with self.connect() as con:
            device = con.execute("SELECT 1 FROM hbt_devices WHERE device_id = ?", (body["device_id"],)).fetchone()
            if not device:
                raise ValueError(f"unknown device_id: {body['device_id']}")

            route_id = body.get("route_id")
            route_name = body.get("route_name")
            if route_id and route_name:
                con.execute(
                    """
                    INSERT INTO business_routes (route_id, route_code, route_name, updated_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(route_id) DO UPDATE SET
                      route_code=COALESCE(excluded.route_code, business_routes.route_code),
                      route_name=excluded.route_name,
                      updated_at=excluded.updated_at
                    """,
                    (route_id, body.get("route_code"), route_name, now),
                )

            container_no = body.get("container_no")
            if container_no:
                con.execute(
                    """
                    INSERT INTO business_containers (container_no, container_type, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(container_no) DO UPDATE SET
                      container_type=COALESCE(excluded.container_type, business_containers.container_type),
                      updated_at=excluded.updated_at
                    """,
                    (container_no, body.get("container_type"), now),
                )

            columns = [
                "device_id",
                "route_id",
                "container_no",
                "shipment_id",
                "order_id",
                "truck_no",
                "bind_start_at",
                "bind_end_at",
                "source",
                "confidence",
                "raw_payload",
                "updated_at",
            ]
            values = [
                body.get("device_id"),
                route_id,
                container_no,
                body.get("shipment_id"),
                body.get("order_id"),
                body.get("truck_no"),
                body.get("bind_start_at"),
                body.get("bind_end_at"),
                body.get("source"),
                body.get("confidence"),
                raw_payload,
                now,
            ]
            if body.get("binding_id"):
                assignments = ", ".join(f"{col} = ?" for col in columns[1:])
                con.execute(
                    f"UPDATE device_business_bindings SET {assignments} WHERE binding_id = ?",
                    values[1:] + [body["binding_id"]],
                )
                binding_id = int(body["binding_id"])
            else:
                placeholders = ", ".join("?" for _ in columns)
                con.execute(
                    f"INSERT INTO device_business_bindings ({', '.join(columns)}) VALUES ({placeholders})",
                    values,
                )
                binding_id = int(con.execute("SELECT last_insert_rowid()").fetchone()[0])
            con.commit()
            row = con.execute(
                """
                SELECT b.*, r.route_code, r.route_name
                FROM device_business_bindings b
                LEFT JOIN business_routes r ON r.route_id = b.route_id
                WHERE b.binding_id = ?
                """,
                (binding_id,),
            ).fetchone()
            return row_to_dict(row)

    def device_track(self, device_id: str, params: dict[str, list[str]]) -> list[dict[str, Any]]:
        limit = as_int(first_param(params, "limit"), 2000)
        start = first_param(params, "start")
        end = first_param(params, "end")
        sql = """
            SELECT device_id, loc_at, lng, lat, speed, direction, temperature, humidity,
                   vibration, tilt_x, tilt_y, tilt_z, light, elock_status, is_valid
            FROM hbt_track_points
            WHERE device_id = ?
        """
        values: list[Any] = [device_id]
        if start:
            sql += " AND loc_at >= ?"
            values.append(start)
        if end:
            sql += " AND loc_at <= ?"
            values.append(end)
        sql += " ORDER BY loc_at LIMIT ?"
        values.append(limit)
        with self.connect() as con:
            return [row_to_dict(row) for row in con.execute(sql, values).fetchall()]

    def device_trajectory(self, device_id: str, params: dict[str, list[str]]) -> dict[str, Any]:
        use_cache = first_param(params, "use_cache")
        if use_cache != "0":
            with self.connect() as con:
                row = con.execute(
                    "SELECT payload_json FROM gps_trajectory_cache WHERE device_id = ?",
                    (device_id,),
                ).fetchone()
            if row:
                data = json.loads(row["payload_json"])
                route_summary = self.device_route_summary(device_id)
                if route_summary["meta"]["segmentCount"] > 0:
                    data["ports"] = route_summary["ports"]
                    data["route"] = route_summary["route"]
                border_crossings = self.device_border_crossings(device_id)
                if border_crossings:
                    data["borderCrossings"] = border_crossings
                data.setdefault("meta", {})
                data["meta"]["precomputed"] = True
                data["meta"]["structuredRoute"] = route_summary["meta"]["segmentCount"] > 0
                data["meta"]["borderCrossingCount"] = len(data.get("borderCrossings") or [])
                return data
        rows = self.device_track(device_id, params)
        data = analyze_track(device_id, rows, self.port_definitions())
        data.setdefault("meta", {})
        data["meta"]["precomputed"] = False
        data["meta"]["borderCrossingCount"] = len(data.get("borderCrossings") or [])
        return data

    def device_border_crossings(self, device_id: str) -> list[dict[str, Any]]:
        with self.connect() as con:
            rows = con.execute(
                """
                SELECT device_id, seq_no, from_country, from_country_code, to_country,
                       to_country_code, from_point_idx, to_point_idx, crossing_at,
                       lat, lng, matched_port_name, matched_port_short_name,
                       matched_distance_km, confidence, note, algorithm_version,
                       precomputed_at
                FROM gps_border_crossings
                WHERE device_id = ?
                ORDER BY seq_no
                """,
                (device_id,),
            ).fetchall()
        return [
            {
                "seqNo": row["seq_no"],
                "fromCountry": row["from_country"],
                "fromCountryCode": row["from_country_code"],
                "toCountry": row["to_country"],
                "toCountryCode": row["to_country_code"],
                "fromPoint": row["from_point_idx"],
                "toPoint": row["to_point_idx"],
                "crossingTime": row["crossing_at"],
                "lat": row["lat"],
                "lon": row["lng"],
                "matchedPortName": row["matched_port_name"],
                "matchedPortShortName": row["matched_port_short_name"],
                "matchedDistanceKm": row["matched_distance_km"],
                "confidence": row["confidence"],
                "note": row["note"],
                "algorithmVersion": row["algorithm_version"],
                "precomputedAt": row["precomputed_at"],
            }
            for row in rows
        ]

    def device_route_summary(self, device_id: str) -> dict[str, Any]:
        with self.connect() as con:
            port_rows = con.execute(
                """
                SELECT device_id, port_name, port_short_name, countries, lat, lng, radius_km,
                       arrival_point_idx, departure_point_idx, arrival_at, departure_at,
                       wait_hours, wait_duration_text, matched, algorithm_version, precomputed_at
                FROM gps_port_passages
                WHERE device_id = ?
                ORDER BY id
                """,
                (device_id,),
            ).fetchall()
            segment_rows = con.execute(
                """
                SELECT device_id, seq_no, segment_name, from_node, to_node, depart_at,
                       arrival_at, transport_hours, transport_duration_text, port_name,
                       port_wait_text, algorithm_version, precomputed_at
                FROM gps_route_segments
                WHERE device_id = ?
                ORDER BY seq_no
                """,
                (device_id,),
            ).fetchall()

        ports: list[dict[str, Any]] = []
        for row in port_rows:
            arrival_idx = row["arrival_point_idx"]
            departure_idx = row["departure_point_idx"]
            if arrival_idx and departure_idx:
                near_points = f"{arrival_idx}-{departure_idx}" if arrival_idx != departure_idx else str(arrival_idx)
            else:
                near_points = "-"
            ports.append(
                {
                    "name": row["port_name"],
                    "shortName": row["port_short_name"],
                    "countries": row["countries"],
                    "lat": row["lat"],
                    "lon": row["lng"],
                    "radiusKm": row["radius_km"],
                    "note": PORT_NOTES.get(row["port_name"], "由预处理结果写入结构化口岸表。"),
                    "arrivalPoint": arrival_idx,
                    "departurePoint": departure_idx,
                    "nearPoints": near_points,
                    "arrivalTime": row["arrival_at"] or "-",
                    "departureTime": row["departure_at"] or "-",
                    "waitDuration": row["wait_duration_text"] or "-",
                    "waitHours": row["wait_hours"],
                    "matched": bool(row["matched"]),
                    "algorithmVersion": row["algorithm_version"],
                    "precomputedAt": row["precomputed_at"],
                }
            )

        segments: list[dict[str, Any]] = []
        for row in segment_rows:
            segments.append(
                {
                    "seqNo": row["seq_no"],
                    "name": row["segment_name"],
                    "from": row["from_node"],
                    "to": row["to_node"],
                    "departTime": row["depart_at"],
                    "arrivalTime": row["arrival_at"],
                    "transportDuration": row["transport_duration_text"],
                    "transportHours": row["transport_hours"],
                    "portName": row["port_name"] or "-",
                    "portWait": row["port_wait_text"] or "-",
                    "algorithmVersion": row["algorithm_version"],
                    "precomputedAt": row["precomputed_at"],
                }
            )

        origin = segments[0]["from"] if segments else ""
        destination = segments[-1]["to"] if segments else ""
        nodes = [origin] + [segment["to"] for segment in segments if segment.get("to")]
        start_time = segments[0]["departTime"] if segments else ""
        end_time = segments[-1]["arrivalTime"] if segments else ""
        total_duration = "-"
        if start_time and end_time:
            total_duration = duration_text(parse_time(start_time), parse_time(end_time))
        algorithm_version = ""
        precomputed_at = ""
        if segments:
            algorithm_version = segments[0]["algorithmVersion"]
            precomputed_at = segments[0]["precomputedAt"]
        elif ports:
            algorithm_version = ports[0]["algorithmVersion"]
            precomputed_at = ports[0]["precomputedAt"]

        return {
            "device_id": device_id,
            "ports": ports,
            "route": {
                "origin": origin,
                "destination": destination,
                "nodes": nodes,
                "routeText": " → ".join(nodes),
                "totalDuration": total_duration,
                "startTime": start_time,
                "endTime": end_time,
                "segments": segments,
            },
            "meta": {
                "device": device_id,
                "portCount": len(ports),
                "matchedPortCount": sum(1 for port in ports if port["matched"]),
                "segmentCount": len(segments),
                "algorithmVersion": algorithm_version,
                "precomputedAt": precomputed_at,
            },
        }

    def container_track(self, container_no: str, params: dict[str, list[str]]) -> list[dict[str, Any]]:
        limit = as_int(first_param(params, "limit"), 3000)
        start = first_param(params, "start")
        end = first_param(params, "end")
        sql = """
            SELECT p.device_id, p.loc_at, p.lng, p.lat, p.speed, p.direction,
                   p.temperature, p.humidity, p.elock_status,
                   b.binding_id, b.container_no, b.route_id, b.order_id, b.shipment_id
            FROM device_business_bindings b
            JOIN hbt_track_points p
              ON p.device_id = b.device_id
             AND p.loc_at >= b.bind_start_at
             AND (b.bind_end_at IS NULL OR p.loc_at < b.bind_end_at)
            WHERE b.container_no = ?
        """
        values: list[Any] = [container_no]
        if start:
            sql += " AND p.loc_at >= ?"
            values.append(start)
        if end:
            sql += " AND p.loc_at <= ?"
            values.append(end)
        sql += " ORDER BY p.loc_at LIMIT ?"
        values.append(limit)
        with self.connect() as con:
            return [row_to_dict(row) for row in con.execute(sql, values).fetchall()]

    def list_site_events(self, params: dict[str, list[str]]) -> list[dict[str, Any]]:
        limit = as_int(first_param(params, "limit"), 1000)
        device_id = first_param(params, "device_id")
        container_no = first_param(params, "container_no")
        route_id = first_param(params, "route_id")
        start = first_param(params, "start")
        end = first_param(params, "end")
        values: list[Any] = []
        if container_no or route_id:
            sql = """
                SELECT e.*, b.container_no, b.route_id, b.order_id, b.shipment_id
                FROM hbt_site_events e
                JOIN device_business_bindings b
                  ON b.device_id = e.device_id
                 AND e.in_at >= b.bind_start_at
                 AND (b.bind_end_at IS NULL OR e.in_at < b.bind_end_at)
                WHERE 1 = 1
            """
            if container_no:
                sql += " AND b.container_no = ?"
                values.append(container_no)
            if route_id:
                sql += " AND b.route_id = ?"
                values.append(route_id)
        else:
            sql = "SELECT e.* FROM hbt_site_events e WHERE 1 = 1"
        if device_id:
            sql += " AND e.device_id = ?"
            values.append(device_id)
        if start:
            sql += " AND e.in_at >= ?"
            values.append(start)
        if end:
            sql += " AND e.in_at <= ?"
            values.append(end)
        sql += " ORDER BY e.in_at DESC LIMIT ?"
        values.append(limit)
        with self.connect() as con:
            return [row_to_dict(row) for row in con.execute(sql, values).fetchall()]

    def route_current_devices(self, route_id: str, params: dict[str, list[str]]) -> list[dict[str, Any]]:
        active_at = first_param(params, "active_at") or utc_now_iso()
        limit = as_int(first_param(params, "limit"), 500)
        sql = """
            SELECT b.binding_id, b.route_id, b.container_no, b.order_id, b.shipment_id,
                   d.device_id, d.status, d.last_loc_at, d.last_upload_at, d.last_lng,
                   d.last_lat, d.soc, d.upload_frequency
            FROM device_business_bindings b
            JOIN hbt_devices d ON d.device_id = b.device_id
            WHERE b.route_id = ?
              AND b.bind_start_at <= ?
              AND (b.bind_end_at IS NULL OR b.bind_end_at > ?)
            ORDER BY d.last_loc_at IS NULL, d.last_loc_at DESC, d.device_id
            LIMIT ?
        """
        with self.connect() as con:
            return [row_to_dict(row) for row in con.execute(sql, (route_id, active_at, active_at, limit)).fetchall()]

    def summary(self) -> dict[str, Any]:
        queries = {
            "devices": "SELECT COUNT(*) FROM hbt_devices",
            "track_points": "SELECT COUNT(*) FROM hbt_track_points",
            "site_events": "SELECT COUNT(*) FROM hbt_site_events",
            "alarm_events": "SELECT COUNT(*) FROM hbt_alarm_events",
            "bindings": "SELECT COUNT(*) FROM device_business_bindings",
            "trajectory_cache": "SELECT COUNT(*) FROM gps_trajectory_cache",
            "port_passages": "SELECT COUNT(*) FROM gps_port_passages",
            "border_crossings": "SELECT COUNT(*) FROM gps_border_crossings",
            "route_segments": "SELECT COUNT(*) FROM gps_route_segments",
        }
        with self.connect() as con:
            return {name: con.execute(sql).fetchone()[0] for name, sql in queries.items()}


class GpsApiHandler(BaseHTTPRequestHandler):
    repo: GpsRepository

    def send_json(self, status: int, data: Any) -> None:
        payload = json_dumps(data)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_OPTIONS(self) -> None:
        self.send_json(204, {})

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        params = parse_qs(parsed.query)
        try:
            if path == "/health":
                self.send_json(200, {"ok": True, "db_path": str(self.repo.db_path), "summary": self.repo.summary()})
            elif path == "/devices":
                self.send_json(200, {"items": self.repo.list_devices(params)})
            elif path == "/api/trajectory-devices":
                self.send_json(200, {"items": self.repo.list_trajectory_devices(params)})
            elif path == "/api/port-definitions":
                self.send_json(200, {"items": self.repo.list_port_definitions(params)})
            elif path == "/bindings":
                self.send_json(200, {"items": self.repo.list_bindings(params)})
            elif path.startswith("/tracks/device/"):
                device_id = path.rsplit("/", 1)[-1]
                self.send_json(200, {"items": self.repo.device_track(device_id, params)})
            elif path == "/api/trajectory":
                device_id = first_param(params, "device_id")
                if not device_id:
                    raise ValueError("device_id is required")
                self.send_json(200, self.repo.device_trajectory(device_id, params))
            elif path == "/api/route-summary":
                device_id = first_param(params, "device_id")
                if not device_id:
                    raise ValueError("device_id is required")
                self.send_json(200, self.repo.device_route_summary(device_id))
            elif path == "/api/border-crossings":
                device_id = first_param(params, "device_id")
                if not device_id:
                    raise ValueError("device_id is required")
                self.send_json(200, {"items": self.repo.device_border_crossings(device_id)})
            elif path.startswith("/tracks/container/"):
                container_no = path.rsplit("/", 1)[-1]
                self.send_json(200, {"items": self.repo.container_track(container_no, params)})
            elif path == "/site-events":
                self.send_json(200, {"items": self.repo.list_site_events(params)})
            elif path.startswith("/routes/") and path.endswith("/current-devices"):
                route_id = path.split("/")[2]
                self.send_json(200, {"items": self.repo.route_current_devices(route_id, params)})
            else:
                self.send_json(404, {"error": "not_found", "path": path})
        except Exception as exc:
            self.send_json(400, {"error": "bad_request", "message": str(exc)})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = parse_body(self.rfile.read(length))
            if path == "/bindings":
                self.send_json(201, {"item": self.repo.create_binding(body)})
            else:
                self.send_json(404, {"error": "not_found", "path": path})
        except Exception as exc:
            self.send_json(400, {"error": "bad_request", "message": str(exc)})

    def log_message(self, fmt: str, *args: Any) -> None:
        print(json.dumps({"ts": utc_now_iso(), "client": self.client_address[0], "message": fmt % args}, ensure_ascii=False), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-path", default=DEFAULT_DB_PATH)
    parser.add_argument("--schema-path", default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8015)
    args = parser.parse_args()

    schema_path = Path(args.schema_path)
    repo = GpsRepository(Path(args.db_path), schema_path if schema_path.exists() else None)
    GpsApiHandler.repo = repo
    server = ThreadingHTTPServer((args.host, args.port), GpsApiHandler)
    print(json.dumps({"ts": utc_now_iso(), "event": "api_start", "host": args.host, "port": args.port, "db_path": args.db_path}, ensure_ascii=False), flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
