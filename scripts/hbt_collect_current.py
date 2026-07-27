#!/usr/bin/env python3
"""Collect current HBT device status in batches and store snapshots."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from datetime import timezone
from pathlib import Path
from typing import Any

from hbt_stage1_collect import HbtClient, Stage1Collector, parse_hbt_datetime, parse_int, parse_number, utc_now_iso


METHOD = "device.interfaces.getCurrentsByGpsnos"
BATCH_SIZE = 50


def chunks(values: list[str], size: int) -> list[list[str]]:
    return [values[i:i + size] for i in range(0, len(values), size)]


class CurrentStatusCollector:
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
        self.con.executescript(self.schema_path.read_text(encoding="utf-8"))
        self.con.commit()
        self.log("schema_checked", db_path=str(self.db_path))

    def load_device_ids(self, requested: list[str], limit: int | None) -> list[str]:
        params: list[Any] = []
        where = ""
        if requested:
            placeholders = ",".join("?" for _ in requested)
            where = f"where device_id in ({placeholders})"
            params.extend(requested)
        sql = f"select device_id from hbt_devices {where} order by device_id"
        if limit is not None:
            sql += " limit ?"
            params.append(limit)
        return [str(row["device_id"]) for row in self.con.execute(sql, params).fetchall()]

    def insert_snapshots(self, items: list[dict[str, Any]], snapshot_at: str) -> int:
        values = []
        for item in items:
            device_id = item.get("deviceId")
            if not device_id:
                continue
            values.append(
                (
                    str(device_id),
                    snapshot_at,
                    parse_hbt_datetime(item.get("lastLocTime")),
                    parse_hbt_datetime(item.get("lastUploadTime")),
                    parse_number(item.get("longitude")),
                    parse_number(item.get("latitude")),
                    parse_int(item.get("status")),
                    parse_number(item.get("soc")),
                    parse_number(item.get("sp")),
                    parse_number(item.get("direction")),
                    parse_number(item.get("tp")),
                    parse_number(item.get("hd") or item.get("hp")),
                    parse_number(item.get("vibration")),
                    parse_number(item.get("tilty")),
                    parse_number(item.get("lp")),
                    parse_int(item.get("elockStatus")),
                    json.dumps(item, ensure_ascii=False, separators=(",", ":")),
                )
            )
        before = self.con.total_changes
        self.con.executemany(
            """
            INSERT INTO hbt_device_snapshots (
              device_id, snapshot_at, last_loc_at, last_upload_at, lng, lat, status,
              soc, speed, direction, temperature, humidity, vibration, tilt_y,
              light, elock_status, raw_payload
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(device_id, snapshot_at) DO UPDATE SET
              last_loc_at=excluded.last_loc_at,
              last_upload_at=excluded.last_upload_at,
              lng=excluded.lng,
              lat=excluded.lat,
              status=excluded.status,
              soc=excluded.soc,
              speed=excluded.speed,
              direction=excluded.direction,
              temperature=excluded.temperature,
              humidity=excluded.humidity,
              vibration=excluded.vibration,
              tilt_y=excluded.tilt_y,
              light=excluded.light,
              elock_status=excluded.elock_status,
              raw_payload=excluded.raw_payload
            """,
            values,
        )
        self.con.commit()
        return self.con.total_changes - before

    def update_cursor(self) -> None:
        now = utc_now_iso()
        self.con.execute(
            """
            INSERT INTO hbt_sync_cursors (
              cursor_key, cursor_type, last_success_at, last_run_at, status, updated_at
            )
            VALUES ('current_status:all', 'current_status', ?, ?, 'idle', ?)
            ON CONFLICT(cursor_key) DO UPDATE SET
              last_success_at=excluded.last_success_at,
              last_run_at=excluded.last_run_at,
              status='idle',
              error_message=NULL,
              updated_at=excluded.updated_at
            """,
            (now, now, now),
        )
        self.con.commit()

    def run(self, requested: list[str], limit: int | None, max_batches: int | None) -> dict[str, int]:
        self.apply_schema()
        device_ids = self.load_device_ids(requested, limit)
        batches = chunks(device_ids, BATCH_SIZE)
        if max_batches is not None:
            batches = batches[:max_batches]
        stats = {
            "devices_considered": len(device_ids),
            "batches_planned": len(batches),
            "batches_success": 0,
            "batches_failed": 0,
            "items_reported": 0,
            "snapshots_changed": 0,
        }
        self.log("current_start", devices=len(device_ids), batches=len(batches), dry_run=self.dry_run)
        snapshot_at = utc_now_iso()
        for index, batch in enumerate(batches, start=1):
            if self.dry_run:
                self.log("current_batch_planned", batch_no=index, count=len(batch), first=batch[0] if batch else None)
                continue
            if not self.client or not self.stage1:
                raise RuntimeError("HBT credentials are required unless --dry-run is used")
            try:
                result = self.client.call(METHOD, {"gpsnos": batch})
                items = result.get("data") or []
                self.stage1.upsert_devices(items)
                changed = self.insert_snapshots(items, snapshot_at)
                stats["batches_success"] += 1
                stats["items_reported"] += len(items)
                stats["snapshots_changed"] += changed
                self.log("current_batch_done", batch_no=index, requested=len(batch), reported=len(items), snapshots_changed=changed)
            except Exception as exc:
                stats["batches_failed"] += 1
                self.log("current_batch_failed", batch_no=index, requested=len(batch), error=str(exc))
            if self.sleep_seconds > 0:
                time.sleep(self.sleep_seconds)
        if not self.dry_run and stats["batches_failed"] == 0:
            self.update_cursor()
        self.log("current_done", **stats)
        return stats


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-path", required=True)
    parser.add_argument("--schema-path", required=True)
    parser.add_argument("--log-path", required=True)
    parser.add_argument("--device-id", action="append", default=[])
    parser.add_argument("--limit-devices", type=int)
    parser.add_argument("--max-batches", type=int)
    parser.add_argument("--sleep-seconds", type=float, default=0.3)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    client = None
    if not args.dry_run:
        app_key = os.environ.get("HBT_APP_KEY")
        app_secret = os.environ.get("HBT_APP_SECRET")
        if not app_key or not app_secret:
            print("HBT_APP_KEY and HBT_APP_SECRET are required unless --dry-run is used", file=sys.stderr)
            return 2
        client = HbtClient(app_key=app_key, app_secret=app_secret, api_url=os.environ.get("HBT_API_URL", "https://openapi.51hbt.com/"))

    collector = CurrentStatusCollector(
        db_path=Path(args.db_path),
        schema_path=Path(args.schema_path),
        log_path=Path(args.log_path),
        client=client,
        dry_run=args.dry_run,
        sleep_seconds=args.sleep_seconds,
    )
    try:
        collector.run(args.device_id, args.limit_devices, args.max_batches)
    finally:
        collector.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
