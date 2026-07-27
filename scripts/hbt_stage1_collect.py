#!/usr/bin/env python3
"""Stage 1 HBT data collector for the GPS project.

The script creates/updates the SQLite schema, then collects:
- all visible HBT devices
- all HBT sites
- one sample device full-info playback window

Secrets are read from environment variables and never written to logs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


DEFAULT_API_URL = "https://openapi.51hbt.com/"
DEFAULT_DEVICE = "61007408"
DEFAULT_START = "2026-06-23 00:00:00"
DEFAULT_END = "2026-06-29 23:59:59"
BEIJING = ZoneInfo("Asia/Shanghai")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_hbt_datetime(value: Any) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value) / 1000, timezone.utc).replace(microsecond=0).isoformat()
    text = str(value).strip()
    if not text:
        return None
    try:
        dt = datetime.strptime(text, "%Y-%m-%d %H:%M:%S").replace(tzinfo=BEIJING)
        return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()
    except ValueError:
        return text


def parse_number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


@dataclass
class HbtClient:
    app_key: str
    app_secret: str
    api_url: str = DEFAULT_API_URL

    def call(self, method: str, data_obj: dict[str, Any]) -> dict[str, Any]:
        data = json.dumps(data_obj, ensure_ascii=False, separators=(",", ":"))
        timestamp = datetime.now(BEIJING).strftime("%Y-%m-%d %H:%M:%S")
        params = {
            "app_key": self.app_key,
            "data": data,
            "method": method,
            "timestamp": timestamp,
        }
        sign_body = "".join(k + params[k] for k in sorted(params))
        params["sign"] = hashlib.md5(
            (self.app_secret + sign_body + self.app_secret).encode("utf-8")
        ).hexdigest().upper()
        encoded = urllib.parse.urlencode(params).encode("utf-8")
        request = urllib.request.Request(
            self.api_url,
            data=encoded,
            headers={"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = response.read().decode("utf-8", "replace")
        result = json.loads(payload)
        if result.get("code") != 0:
            raise RuntimeError(f"{method} failed: code={result.get('code')} message={result.get('message') or result.get('msg')}")
        return result


class Stage1Collector:
    def __init__(self, db_path: Path, schema_path: Path, log_path: Path, client: HbtClient) -> None:
        self.db_path = db_path
        self.schema_path = schema_path
        self.log_path = log_path
        self.client = client
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(str(self.db_path))
        self.con.row_factory = sqlite3.Row

    def log(self, event: str, **fields: Any) -> None:
        record = {"ts": utc_now_iso(), "event": event, **fields}
        line = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
        print(line, flush=True)
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    def apply_schema(self) -> None:
        sql = self.schema_path.read_text(encoding="utf-8")
        self.con.executescript(sql)
        self.con.commit()
        tables = self.con.execute(
            "select count(*) from sqlite_master where type='table' and name not like 'sqlite_%'"
        ).fetchone()[0]
        indexes = self.con.execute("select count(*) from sqlite_master where type='index'").fetchone()[0]
        self.log("schema_applied", db_path=str(self.db_path), tables=tables, indexes=indexes)

    def upsert_devices(self, devices: list[dict[str, Any]]) -> None:
        now = utc_now_iso()
        rows = []
        for item in devices:
            rows.append(
                (
                    str(item.get("deviceId")),
                    item.get("orgRootId"),
                    item.get("orgId"),
                    parse_int(item.get("status")),
                    parse_hbt_datetime(item.get("lastLocTime")),
                    parse_hbt_datetime(item.get("lastUploadTime")),
                    parse_number(item.get("longitude")),
                    parse_number(item.get("latitude")),
                    parse_number(item.get("soc")),
                    parse_int(item.get("uploadFrequency")),
                    parse_hbt_datetime(item.get("serviceStartDate")),
                    parse_hbt_datetime(item.get("serviceExpireDate")),
                    json.dumps(item, ensure_ascii=False, separators=(",", ":")),
                    now,
                    now,
                )
            )
        self.con.executemany(
            """
            INSERT INTO hbt_devices (
              device_id, org_root_id, org_id, status, last_loc_at, last_upload_at,
              last_lng, last_lat, soc, upload_frequency, service_start_at,
              service_expire_at, raw_payload, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(device_id) DO UPDATE SET
              org_root_id=excluded.org_root_id,
              org_id=excluded.org_id,
              status=excluded.status,
              last_loc_at=excluded.last_loc_at,
              last_upload_at=excluded.last_upload_at,
              last_lng=excluded.last_lng,
              last_lat=excluded.last_lat,
              soc=excluded.soc,
              upload_frequency=excluded.upload_frequency,
              service_start_at=excluded.service_start_at,
              service_expire_at=excluded.service_expire_at,
              raw_payload=excluded.raw_payload,
              updated_at=excluded.updated_at
            """,
            rows,
        )
        self.con.commit()

    def collect_devices(self) -> None:
        method = "device.syncDeviceInfos"
        page_no = 1
        page_size = 1000
        all_devices: list[dict[str, Any]] = []
        while True:
            result = self.client.call(method, {"pageNo": str(page_no), "pageSize": str(page_size)})
            data = result.get("data") or {}
            items = data.get("result") or []
            total = int(data.get("totalCount") or len(items))
            all_devices.extend(items)
            self.log("devices_page", page_no=page_no, count=len(items), total=total)
            if len(all_devices) >= total or not items:
                break
            page_no += 1
        self.upsert_devices(all_devices)
        online = sum(1 for d in all_devices if str(d.get("status")) == "1")
        offline = sum(1 for d in all_devices if str(d.get("status")) == "2")
        self.log("devices_done", count=len(all_devices), online=online, offline=offline)

    def upsert_sites(self, sites: list[dict[str, Any]]) -> None:
        now = utc_now_iso()
        rows = []
        for item in sites:
            site_id = item.get("id")
            if not site_id:
                continue
            rows.append(
                (
                    str(site_id),
                    str(item.get("name") or ""),
                    item.get("address"),
                    parse_number(item.get("centerLng")),
                    parse_number(item.get("centerLat")),
                    item.get("orgId") or item.get("orgid"),
                    item.get("orgRootId"),
                    parse_hbt_datetime(item.get("createTime")),
                    parse_hbt_datetime(item.get("updateTime")),
                    json.dumps(item, ensure_ascii=False, separators=(",", ":")),
                    now,
                    now,
                )
            )
        self.con.executemany(
            """
            INSERT INTO hbt_sites (
              site_id, name, address, center_lng, center_lat, org_id, org_root_id,
              source_created_at, source_updated_at, raw_payload, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(site_id) DO UPDATE SET
              name=excluded.name,
              address=excluded.address,
              center_lng=excluded.center_lng,
              center_lat=excluded.center_lat,
              org_id=excluded.org_id,
              org_root_id=excluded.org_root_id,
              source_created_at=excluded.source_created_at,
              source_updated_at=excluded.source_updated_at,
              raw_payload=excluded.raw_payload,
              updated_at=excluded.updated_at
            """,
            rows,
        )
        self.con.commit()

    def collect_sites(self) -> None:
        result = self.client.call("basic.getAllSites", {})
        sites = result.get("data") or []
        self.upsert_sites(sites)
        self.log("sites_done", count=len(sites))

    def upsert_track_window(self, device_id: str, start: str, end: str, response_data: dict[str, Any]) -> None:
        method = "device.interfaces.getPlayBackFullInfoByGpsno"
        now = utc_now_iso()
        detail = response_data.get("detail") or []
        rows = []
        for point in detail:
            ts = point.get("timestamp")
            lng = parse_number(point.get("lng"))
            lat = parse_number(point.get("lat"))
            loc_at = parse_hbt_datetime(ts)
            if not loc_at or lng is None or lat is None:
                continue
            rows.append(
                (
                    device_id,
                    loc_at,
                    parse_int(ts),
                    lng,
                    lat,
                    parse_number(point.get("sp")),
                    parse_number(point.get("direction")),
                    parse_number(point.get("tp")),
                    parse_number(point.get("hd")),
                    parse_number(point.get("vbx")),
                    parse_number(point.get("vby")),
                    parse_number(point.get("vbz")),
                    parse_number(point.get("vibration")),
                    parse_number(point.get("tiltx")),
                    parse_number(point.get("tilty")),
                    parse_number(point.get("tiltz")),
                    parse_number(point.get("lp")),
                    parse_int(point.get("elockStatus")),
                    method,
                    json.dumps(point, ensure_ascii=False, separators=(",", ":")),
                    now,
                )
            )
        before = self.con.total_changes
        self.con.executemany(
            """
            INSERT INTO hbt_track_points (
              device_id, loc_at, source_timestamp_ms, lng, lat, speed, direction,
              temperature, humidity, vbx, vby, vbz, vibration, tilt_x, tilt_y,
              tilt_z, light, elock_status, source_method, raw_payload, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(device_id, loc_at, lng, lat) DO UPDATE SET
              speed=excluded.speed,
              direction=excluded.direction,
              temperature=excluded.temperature,
              humidity=excluded.humidity,
              vbx=excluded.vbx,
              vby=excluded.vby,
              vbz=excluded.vbz,
              vibration=excluded.vibration,
              tilt_x=excluded.tilt_x,
              tilt_y=excluded.tilt_y,
              tilt_z=excluded.tilt_z,
              light=excluded.light,
              elock_status=excluded.elock_status,
              source_method=excluded.source_method,
              raw_payload=excluded.raw_payload
            """,
            rows,
        )
        after = self.con.total_changes
        inserted_or_updated = after - before
        self.con.execute(
            """
            INSERT INTO hbt_track_fetch_windows (
              device_id, window_start_at, window_end_at, method, status, point_count,
              distance_m, started_at, finished_at, raw_response, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, 'success', ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(device_id, window_start_at, window_end_at, method) DO UPDATE SET
              status='success',
              point_count=excluded.point_count,
              distance_m=excluded.distance_m,
              finished_at=excluded.finished_at,
              raw_response=excluded.raw_response,
              updated_at=excluded.updated_at
            """,
            (
                device_id,
                parse_hbt_datetime(start),
                parse_hbt_datetime(end),
                method,
                len(detail),
                parse_number(response_data.get("distance")),
                now,
                utc_now_iso(),
                json.dumps(
                    {
                        "gpsno": response_data.get("gpsno"),
                        "distance": response_data.get("distance"),
                        "detail_count": len(detail),
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
                now,
                now,
            ),
        )
        cursor_key = f"track:{device_id}"
        max_loc_at = max((row[1] for row in rows), default=parse_hbt_datetime(end))
        self.con.execute(
            """
            INSERT INTO hbt_sync_cursors (
              cursor_key, cursor_type, device_id, last_success_at, last_run_at, status, updated_at
            )
            VALUES (?, 'track', ?, ?, ?, 'idle', ?)
            ON CONFLICT(cursor_key) DO UPDATE SET
              last_success_at=excluded.last_success_at,
              last_run_at=excluded.last_run_at,
              status='idle',
              error_message=NULL,
              updated_at=excluded.updated_at
            """,
            (cursor_key, device_id, max_loc_at, now, now),
        )
        self.con.commit()
        self.log(
            "track_window_done",
            device_id=device_id,
            start=start,
            end=end,
            points=len(detail),
            rows_changed=inserted_or_updated,
            distance_m=response_data.get("distance"),
        )

    def collect_sample_track(self, device_id: str, start: str, end: str) -> None:
        method = "device.interfaces.getPlayBackFullInfoByGpsno"
        result = self.client.call(
            method,
            {"Gpsno": device_id, "starttime": start, "endtime": end, "includEemptyLoc": "0"},
        )
        self.upsert_track_window(device_id, start, end, result.get("data") or {})

    def write_job_log(self, status: str, started_at: str, error: str | None = None) -> None:
        self.con.execute(
            """
            INSERT INTO hbt_sync_jobs (
              job_type, status, request_count, started_at, finished_at, error_message
            )
            VALUES ('stage1_sample_collect', ?, 3, ?, ?, ?)
            """,
            (status, started_at, utc_now_iso(), error),
        )
        self.con.commit()

    def close(self) -> None:
        self.con.close()


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-path", required=True)
    parser.add_argument("--schema-path", required=True)
    parser.add_argument("--log-path", required=True)
    parser.add_argument("--sample-device", default=DEFAULT_DEVICE)
    parser.add_argument("--sample-start", default=DEFAULT_START)
    parser.add_argument("--sample-end", default=DEFAULT_END)
    args = parser.parse_args(argv)

    app_key = os.environ.get("HBT_APP_KEY")
    app_secret = os.environ.get("HBT_APP_SECRET")
    if not app_key or not app_secret:
        print("HBT_APP_KEY and HBT_APP_SECRET are required", file=sys.stderr)
        return 2

    client = HbtClient(app_key=app_key, app_secret=app_secret, api_url=os.environ.get("HBT_API_URL", DEFAULT_API_URL))
    collector = Stage1Collector(
        db_path=Path(args.db_path),
        schema_path=Path(args.schema_path),
        log_path=Path(args.log_path),
        client=client,
    )
    started_at = utc_now_iso()
    try:
        collector.log("stage1_start", db_path=args.db_path, sample_device=args.sample_device)
        collector.apply_schema()
        collector.collect_devices()
        collector.collect_sites()
        collector.collect_sample_track(args.sample_device, args.sample_start, args.sample_end)
        collector.write_job_log("success", started_at)
        collector.log("stage1_done", status="success")
        return 0
    except Exception as exc:
        collector.write_job_log("failed", started_at, str(exc))
        collector.log("stage1_done", status="failed", error=str(exc))
        raise
    finally:
        collector.close()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
