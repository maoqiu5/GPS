#!/usr/bin/env python3
"""Backfill HBT full-info track points by device and 7-day windows.

This script is intentionally conservative:
- it reads devices from the local SQLite database
- it skips successful windows unless --force is set
- it supports --dry-run, --limit-devices, and --max-windows
- it logs JSON lines and writes success/failure window records
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from hbt_stage1_collect import HbtClient, Stage1Collector, parse_hbt_datetime, utc_now_iso


BEIJING = ZoneInfo("Asia/Shanghai")
METHOD = "device.interfaces.getPlayBackFullInfoByGpsno"


def parse_local_datetime(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=BEIJING)


def format_local_datetime(value: datetime) -> str:
    return value.astimezone(BEIJING).strftime("%Y-%m-%d %H:%M:%S")


def utc_iso_to_local_text(value: str) -> str:
    return datetime.fromisoformat(value).astimezone(BEIJING).strftime("%Y-%m-%d %H:%M:%S")


def iter_windows(start: datetime, end: datetime, days: int = 7) -> list[tuple[str, str]]:
    windows: list[tuple[str, str]] = []
    cursor = start
    while cursor < end:
        window_end = min(cursor + timedelta(days=days) - timedelta(seconds=1), end)
        windows.append((format_local_datetime(cursor), format_local_datetime(window_end)))
        cursor = window_end + timedelta(seconds=1)
    return windows


class TrackBackfiller:
    def __init__(
        self,
        db_path: Path,
        schema_path: Path,
        log_path: Path,
        client: HbtClient | None,
        sleep_seconds: float,
        dry_run: bool,
        force: bool,
    ) -> None:
        self.db_path = db_path
        self.schema_path = schema_path
        self.log_path = log_path
        self.client = client
        self.sleep_seconds = sleep_seconds
        self.dry_run = dry_run
        self.force = force
        self.con = sqlite3.connect(str(db_path))
        self.con.row_factory = sqlite3.Row
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.stage1 = Stage1Collector(db_path, schema_path, log_path, client) if client else None

    def close(self) -> None:
        if self.stage1:
            self.stage1.close()
        self.con.close()

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
        self.log("schema_checked", db_path=str(self.db_path))

    def load_devices(self, requested: list[str], limit: int | None, order_by: str) -> list[sqlite3.Row]:
        params: list[Any] = []
        where = ""
        if requested:
            placeholders = ",".join("?" for _ in requested)
            where = f"where device_id in ({placeholders})"
            params.extend(requested)
        order_clauses = {
            "device_id": "device_id",
            "last_loc_at_desc": "last_loc_at is null, last_loc_at desc, device_id",
            "online_recent": "case when status = 1 then 0 else 1 end, last_loc_at is null, last_loc_at desc, device_id",
        }
        order_clause = order_clauses[order_by]
        sql = f"""
            select device_id, status, service_start_at, service_expire_at, last_loc_at
            from hbt_devices
            {where}
            order by {order_clause}
        """
        if limit is not None:
            sql += " limit ?"
            params.append(limit)
        rows = self.con.execute(sql, params).fetchall()
        return rows

    def window_already_success(self, device_id: str, start_text: str, end_text: str) -> bool:
        start_iso = parse_hbt_datetime(start_text)
        end_iso = parse_hbt_datetime(end_text)
        row = self.con.execute(
            """
            select 1 from hbt_track_fetch_windows
            where device_id = ?
              and window_start_at = ?
              and window_end_at = ?
              and method = ?
              and status = 'success'
            """,
            (device_id, start_iso, end_iso, METHOD),
        ).fetchone()
        return row is not None

    def record_failed_window(self, device_id: str, start_text: str, end_text: str, error: str) -> None:
        now = utc_now_iso()
        self.con.execute(
            """
            INSERT INTO hbt_track_fetch_windows (
              device_id, window_start_at, window_end_at, method, status, point_count,
              error_message, started_at, finished_at, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, 'failed', 0, ?, ?, ?, ?, ?)
            ON CONFLICT(device_id, window_start_at, window_end_at, method) DO UPDATE SET
              status='failed',
              error_message=excluded.error_message,
              finished_at=excluded.finished_at,
              updated_at=excluded.updated_at
            """,
            (
                device_id,
                parse_hbt_datetime(start_text),
                parse_hbt_datetime(end_text),
                METHOD,
                error,
                now,
                now,
                now,
                now,
            ),
        )
        self.con.commit()

    def cursor_start_for_device(self, row: sqlite3.Row, fallback_start: datetime) -> datetime:
        cursor = self.con.execute(
            "select last_success_at from hbt_sync_cursors where cursor_key = ?",
            (f"track:{row['device_id']}",),
        ).fetchone()
        if cursor and cursor["last_success_at"]:
            return datetime.fromisoformat(cursor["last_success_at"]).astimezone(BEIJING) - timedelta(minutes=30)
        if row["service_start_at"]:
            try:
                return max(datetime.fromisoformat(row["service_start_at"]).astimezone(BEIJING), fallback_start)
            except ValueError:
                return fallback_start
        return fallback_start

    def run(
        self,
        requested_devices: list[str],
        start: datetime,
        end: datetime,
        limit_devices: int | None,
        max_windows: int | None,
        use_cursors: bool,
        order_by: str,
    ) -> dict[str, int]:
        self.apply_schema()
        devices = self.load_devices(requested_devices, limit_devices, order_by)
        stats = {
            "devices_considered": len(devices),
            "windows_planned": 0,
            "windows_skipped": 0,
            "windows_success": 0,
            "windows_failed": 0,
            "points_reported": 0,
        }
        self.log(
            "backfill_start",
            devices=len(devices),
            start=format_local_datetime(start),
            end=format_local_datetime(end),
            dry_run=self.dry_run,
            force=self.force,
            use_cursors=use_cursors,
            order_by=order_by,
        )
        processed_windows = 0
        for device in devices:
            device_id = device["device_id"]
            device_start = self.cursor_start_for_device(device, start) if use_cursors else start
            if device_start >= end:
                self.log("device_no_window", device_id=device_id, reason="cursor_after_end")
                continue
            windows = iter_windows(device_start, end)
            self.log("device_windows", device_id=device_id, windows=len(windows))
            for start_text, end_text in windows:
                if max_windows is not None and processed_windows >= max_windows:
                    self.log("backfill_stop", reason="max_windows", **stats)
                    return stats
                processed_windows += 1
                stats["windows_planned"] += 1
                if not self.force and self.window_already_success(device_id, start_text, end_text):
                    stats["windows_skipped"] += 1
                    self.log("window_skipped", device_id=device_id, start=start_text, end=end_text)
                    continue
                if self.dry_run:
                    self.log("window_planned", device_id=device_id, start=start_text, end=end_text)
                    continue
                if not self.client or not self.stage1:
                    raise RuntimeError("HBT credentials are required unless --dry-run is used")
                try:
                    result = self.client.call(
                        METHOD,
                        {"Gpsno": device_id, "starttime": start_text, "endtime": end_text, "includEemptyLoc": "0"},
                    )
                    data = result.get("data") or {}
                    self.stage1.upsert_track_window(device_id, start_text, end_text, data)
                    stats["windows_success"] += 1
                    stats["points_reported"] += len(data.get("detail") or [])
                except Exception as exc:
                    stats["windows_failed"] += 1
                    self.record_failed_window(device_id, start_text, end_text, str(exc))
                    self.log("window_failed", device_id=device_id, start=start_text, end=end_text, error=str(exc))
                if self.sleep_seconds > 0:
                    time.sleep(self.sleep_seconds)
        self.log("backfill_done", **stats)
        return stats


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-path", required=True)
    parser.add_argument("--schema-path", required=True)
    parser.add_argument("--log-path", required=True)
    parser.add_argument("--start", required=True, help="Beijing time, YYYY-MM-DD HH:MM:SS")
    parser.add_argument("--end", required=True, help="Beijing time, YYYY-MM-DD HH:MM:SS")
    parser.add_argument("--device-id", action="append", default=[])
    parser.add_argument("--limit-devices", type=int)
    parser.add_argument("--max-windows", type=int)
    parser.add_argument("--sleep-seconds", type=float, default=0.5)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--use-cursors", action="store_true")
    parser.add_argument("--order-by", choices=["device_id", "last_loc_at_desc", "online_recent"], default="device_id")
    args = parser.parse_args(argv)

    client = None
    if not args.dry_run:
        app_key = os.environ.get("HBT_APP_KEY")
        app_secret = os.environ.get("HBT_APP_SECRET")
        if not app_key or not app_secret:
            print("HBT_APP_KEY and HBT_APP_SECRET are required unless --dry-run is used", file=sys.stderr)
            return 2
        client = HbtClient(
            app_key=app_key,
            app_secret=app_secret,
            api_url=os.environ.get("HBT_API_URL", "https://openapi.51hbt.com/"),
        )

    backfiller = TrackBackfiller(
        db_path=Path(args.db_path),
        schema_path=Path(args.schema_path),
        log_path=Path(args.log_path),
        client=client,
        sleep_seconds=args.sleep_seconds,
        dry_run=args.dry_run,
        force=args.force,
    )
    try:
        backfiller.run(
            requested_devices=args.device_id,
            start=parse_local_datetime(args.start),
            end=parse_local_datetime(args.end),
            limit_devices=args.limit_devices,
            max_windows=args.max_windows,
            use_cursors=args.use_cursors,
            order_by=args.order_by,
        )
    finally:
        backfiller.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
