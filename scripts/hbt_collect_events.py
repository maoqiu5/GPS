#!/usr/bin/env python3
"""Collect HBT alarm events and site enter/exit events into SQLite."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from hbt_stage1_collect import HbtClient, parse_hbt_datetime, utc_now_iso


BEIJING = ZoneInfo("Asia/Shanghai")


def parse_local_datetime(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=BEIJING)


def format_local_datetime(value: datetime) -> str:
    return value.astimezone(BEIJING).strftime("%Y-%m-%d %H:%M:%S")


def iter_windows(start: datetime, end: datetime, hours: int) -> list[tuple[str, str]]:
    windows: list[tuple[str, str]] = []
    cursor = start
    while cursor < end:
        window_end = min(cursor + timedelta(hours=hours) - timedelta(seconds=1), end)
        windows.append((format_local_datetime(cursor), format_local_datetime(window_end)))
        cursor = window_end + timedelta(seconds=1)
    return windows


def utc_iso_to_local_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value).astimezone(BEIJING)


def event_hash(parts: list[Any]) -> str:
    text = "|".join("" if p is None else str(p) for p in parts)
    return hashlib.md5(text.encode("utf-8")).hexdigest()


class EventCollector:
    def __init__(
        self,
        db_path: Path,
        schema_path: Path,
        log_path: Path,
        client: HbtClient | None,
        dry_run: bool,
        sleep_seconds: float,
    ) -> None:
        self.db_path = db_path
        self.schema_path = schema_path
        self.log_path = log_path
        self.client = client
        self.dry_run = dry_run
        self.sleep_seconds = sleep_seconds
        self.con = sqlite3.connect(str(db_path))
        self.con.row_factory = sqlite3.Row
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def close(self) -> None:
        self.con.close()

    def log(self, event: str, **fields: Any) -> None:
        record = {"ts": utc_now_iso(), "event": event, **fields}
        line = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
        print(line, flush=True)
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    def apply_schema(self) -> None:
        self.con.executescript(self.schema_path.read_text(encoding="utf-8"))
        self.con.commit()
        self.log("schema_checked", db_path=str(self.db_path))

    def upsert_alarm_events(self, rows: list[dict[str, Any]]) -> int:
        now = utc_now_iso()
        values = []
        for item in rows:
            start_at = parse_hbt_datetime(item.get("startTime"))
            if not item.get("deviceId") or not start_at:
                continue
            end_at = parse_hbt_datetime(item.get("endTime"))
            key = event_hash([item.get("deviceId"), item.get("warningType"), start_at, end_at, item.get("warningDesc")])
            values.append(
                (
                    key,
                    item.get("deviceId"),
                    item.get("orgId"),
                    item.get("orgRootId"),
                    item.get("warningType"),
                    item.get("warningDesc"),
                    start_at,
                    end_at,
                    1 if not end_at else 0,
                    json.dumps(item, ensure_ascii=False, separators=(",", ":")),
                    now,
                    now,
                )
            )
        before = self.con.total_changes
        self.con.executemany(
            """
            INSERT INTO hbt_alarm_events (
              event_key, device_id, org_id, org_root_id, warning_type, warning_desc,
              start_at, end_at, is_open, raw_payload, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(event_key) DO UPDATE SET
              org_id=excluded.org_id,
              org_root_id=excluded.org_root_id,
              warning_desc=excluded.warning_desc,
              end_at=excluded.end_at,
              is_open=excluded.is_open,
              raw_payload=excluded.raw_payload,
              updated_at=excluded.updated_at
            """,
            values,
        )
        self.con.commit()
        return self.con.total_changes - before

    def upsert_site_events(self, rows: list[dict[str, Any]]) -> int:
        now = utc_now_iso()
        values = []
        for item in rows:
            in_at = parse_hbt_datetime(item.get("inTime"))
            if not item.get("deviceId") or not in_at:
                continue
            out_at = parse_hbt_datetime(item.get("outTime"))
            key = event_hash([item.get("deviceId"), item.get("siteId"), in_at, out_at])
            duration = None
            if out_at:
                try:
                    duration = int((datetime.fromisoformat(out_at) - datetime.fromisoformat(in_at)).total_seconds())
                except ValueError:
                    duration = None
            values.append(
                (
                    key,
                    item.get("deviceId"),
                    item.get("siteId"),
                    item.get("siteName"),
                    item.get("orgRootId"),
                    item.get("deviceOrgId"),
                    item.get("siteOrgId"),
                    in_at,
                    out_at,
                    1 if not out_at else 0,
                    duration,
                    json.dumps(item, ensure_ascii=False, separators=(",", ":")),
                    now,
                    now,
                )
            )
        before = self.con.total_changes
        self.con.executemany(
            """
            INSERT INTO hbt_site_events (
              event_key, device_id, site_id, site_name, org_root_id, device_org_id,
              site_org_id, in_at, out_at, is_inside, duration_seconds, raw_payload,
              created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(event_key) DO UPDATE SET
              site_name=excluded.site_name,
              org_root_id=excluded.org_root_id,
              device_org_id=excluded.device_org_id,
              site_org_id=excluded.site_org_id,
              out_at=excluded.out_at,
              is_inside=excluded.is_inside,
              duration_seconds=excluded.duration_seconds,
              raw_payload=excluded.raw_payload,
              updated_at=excluded.updated_at
            """,
            values,
        )
        self.con.commit()
        return self.con.total_changes - before

    def update_cursor(self, cursor_key: str, cursor_type: str, success_at_text: str) -> None:
        now = utc_now_iso()
        success_at = parse_hbt_datetime(success_at_text)
        self.con.execute(
            """
            INSERT INTO hbt_sync_cursors (
              cursor_key, cursor_type, last_success_at, last_run_at, status, updated_at
            )
            VALUES (?, ?, ?, ?, 'idle', ?)
            ON CONFLICT(cursor_key) DO UPDATE SET
              last_success_at=excluded.last_success_at,
              last_run_at=excluded.last_run_at,
              status='idle',
              error_message=NULL,
              updated_at=excluded.updated_at
            """,
            (cursor_key, cursor_type, success_at, now, now),
        )
        self.con.commit()

    def cursor_start(self, cursor_key: str, fallback_start: datetime) -> datetime:
        row = self.con.execute(
            "select last_success_at from hbt_sync_cursors where cursor_key = ?",
            (cursor_key,),
        ).fetchone()
        if row and row["last_success_at"]:
            try:
                return max(utc_iso_to_local_datetime(row["last_success_at"]) - timedelta(minutes=5), fallback_start)
            except ValueError:
                return fallback_start
        return fallback_start

    def run(
        self,
        event_type: str,
        start: datetime,
        end: datetime,
        device_id: str | None,
        max_windows: int | None,
        use_cursors: bool,
    ) -> dict[str, int]:
        self.apply_schema()
        if event_type == "alarm":
            method = "device.searchWarningInfo"
            window_hours = 72
            cursor_key = "alarm:all" if not device_id else f"alarm:{device_id}"
            cursor_type = "alarm"
        elif event_type == "site-events":
            method = "device.searchSiteEvents"
            window_hours = 31 * 24
            cursor_key = "site_event:all" if not device_id else f"site_event:{device_id}"
            cursor_type = "site_event"
        else:
            raise ValueError(f"unsupported event_type: {event_type}")

        effective_start = self.cursor_start(cursor_key, start) if use_cursors else start
        if effective_start >= end:
            stats = {"windows_planned": 0, "windows_success": 0, "windows_failed": 0, "events_reported": 0, "rows_changed": 0}
            self.log(
                "events_start",
                event_type=event_type,
                method=method,
                start=format_local_datetime(effective_start),
                end=format_local_datetime(end),
                windows=0,
                device_id=device_id,
                dry_run=self.dry_run,
                use_cursors=use_cursors,
            )
            self.log("events_done", event_type=event_type, reason="cursor_after_end", **stats)
            return stats

        windows = iter_windows(effective_start, end, window_hours)
        stats = {"windows_planned": len(windows), "windows_success": 0, "windows_failed": 0, "events_reported": 0, "rows_changed": 0}
        self.log(
            "events_start",
            event_type=event_type,
            method=method,
            start=format_local_datetime(effective_start),
            end=format_local_datetime(end),
            windows=len(windows),
            device_id=device_id,
            dry_run=self.dry_run,
            use_cursors=use_cursors,
        )
        for index, (start_text, end_text) in enumerate(windows, start=1):
            if max_windows is not None and index > max_windows:
                self.log("events_stop", reason="max_windows", **stats)
                break
            if self.dry_run:
                self.log("event_window_planned", event_type=event_type, start=start_text, end=end_text, device_id=device_id)
                continue
            if not self.client:
                raise RuntimeError("HBT credentials are required unless --dry-run is used")
            try:
                if event_type == "alarm":
                    payload = {"starttime": start_text, "endtime": end_text}
                    if device_id:
                        payload["deviceid"] = device_id
                else:
                    payload = {"eventTimeFrom": start_text, "eventTimeTo": end_text}
                    if device_id:
                        payload["gpsnos"] = device_id
                result = self.client.call(method, payload)
                rows = result.get("data") or []
                changed = self.upsert_alarm_events(rows) if event_type == "alarm" else self.upsert_site_events(rows)
                stats["windows_success"] += 1
                stats["events_reported"] += len(rows)
                stats["rows_changed"] += changed
                self.update_cursor(cursor_key, cursor_type, end_text)
                self.log("event_window_done", event_type=event_type, start=start_text, end=end_text, reported=len(rows), rows_changed=changed)
            except Exception as exc:
                stats["windows_failed"] += 1
                self.log("event_window_failed", event_type=event_type, start=start_text, end=end_text, error=str(exc))
            if self.sleep_seconds > 0:
                time.sleep(self.sleep_seconds)
        self.log("events_done", event_type=event_type, **stats)
        return stats


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("event_type", choices=["alarm", "site-events"])
    parser.add_argument("--db-path", required=True)
    parser.add_argument("--schema-path", required=True)
    parser.add_argument("--log-path", required=True)
    parser.add_argument("--start", required=True, help="Beijing time, YYYY-MM-DD HH:MM:SS")
    parser.add_argument("--end", required=True, help="Beijing time, YYYY-MM-DD HH:MM:SS")
    parser.add_argument("--device-id")
    parser.add_argument("--max-windows", type=int)
    parser.add_argument("--sleep-seconds", type=float, default=0.5)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--use-cursors", action="store_true")
    args = parser.parse_args(argv)

    client = None
    if not args.dry_run:
        app_key = os.environ.get("HBT_APP_KEY")
        app_secret = os.environ.get("HBT_APP_SECRET")
        if not app_key or not app_secret:
            print("HBT_APP_KEY and HBT_APP_SECRET are required unless --dry-run is used", file=sys.stderr)
            return 2
        client = HbtClient(app_key=app_key, app_secret=app_secret, api_url=os.environ.get("HBT_API_URL", "https://openapi.51hbt.com/"))

    collector = EventCollector(
        db_path=Path(args.db_path),
        schema_path=Path(args.schema_path),
        log_path=Path(args.log_path),
        client=client,
        dry_run=args.dry_run,
        sleep_seconds=args.sleep_seconds,
    )
    try:
        collector.run(
            event_type=args.event_type,
            start=parse_local_datetime(args.start),
            end=parse_local_datetime(args.end),
            device_id=args.device_id,
            max_windows=args.max_windows,
            use_cursors=args.use_cursors,
        )
    finally:
        collector.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
