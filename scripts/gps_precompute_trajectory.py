#!/usr/bin/env python3
"""Precompute trajectory map payloads for GPS devices.

The map API can render directly from gps_trajectory_cache instead of rebuilding
drift filtering, port passages, and route timing on every request.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gps_query_api import DEFAULT_DB_PATH, DEFAULT_SCHEMA_PATH, analyze_track, json_dumps, load_port_definitions, row_to_dict


ALGORITHM_VERSION = "trajectory-precompute-v6"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(db_path: str) -> sqlite3.Connection:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def apply_schema(con: sqlite3.Connection, schema_path: str | None) -> None:
    if not schema_path:
        return
    path = Path(schema_path)
    if path.exists():
        con.executescript(path.read_text(encoding="utf-8"))


def device_ids(con: sqlite3.Connection, requested: list[str], limit: int | None) -> list[str]:
    if requested:
        return requested[:limit] if limit else requested
    sql = """
        SELECT device_id
        FROM hbt_track_points
        GROUP BY device_id
        HAVING COUNT(*) > 0
        ORDER BY MAX(loc_at) DESC, device_id
    """
    if limit:
        sql += " LIMIT ?"
        return [str(row["device_id"]) for row in con.execute(sql, (limit,)).fetchall()]
    return [str(row["device_id"]) for row in con.execute(sql).fetchall()]


def load_rows(con: sqlite3.Connection, device_id: str) -> list[dict[str, Any]]:
    rows = con.execute(
        """
        SELECT device_id, loc_at, lng, lat, speed, direction, temperature, humidity,
               vibration, tilt_x, tilt_y, tilt_z, light, elock_status, is_valid
        FROM hbt_track_points
        WHERE device_id = ?
        ORDER BY loc_at
        """,
        (device_id,),
    ).fetchall()
    return [row_to_dict(row) for row in rows]


def update_drift_flags(con: sqlite3.Connection, device_id: str, payload: dict[str, Any]) -> None:
    con.execute(
        "UPDATE hbt_track_points SET is_valid = 1, is_drift_candidate = 0 WHERE device_id = ?",
        (device_id,),
    )
    for point in payload.get("removedPoints", []):
        con.execute(
            """
            UPDATE hbt_track_points
            SET is_valid = 0, is_drift_candidate = 1
            WHERE device_id = ? AND loc_at = ? AND ROUND(lat, 6) = ? AND ROUND(lng, 6) = ?
            """,
            (device_id, point["time"], point["lat"], point["lon"]),
        )


def save_cache(con: sqlite3.Connection, device_id: str, payload: dict[str, Any], raw_rows: list[dict[str, Any]]) -> None:
    meta = payload.get("meta", {})
    now = utc_now_iso()
    source_max_loc_at = max((str(row["loc_at"]) for row in raw_rows if row.get("loc_at")), default=None)
    con.execute(
        """
        INSERT INTO gps_trajectory_cache (
          device_id, raw_count, display_count, removed_count, start_at, end_at,
          total_duration_text, payload_json, source_max_loc_at, source_point_count,
          precomputed_at, algorithm_version
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(device_id) DO UPDATE SET
          raw_count=excluded.raw_count,
          display_count=excluded.display_count,
          removed_count=excluded.removed_count,
          start_at=excluded.start_at,
          end_at=excluded.end_at,
          total_duration_text=excluded.total_duration_text,
          payload_json=excluded.payload_json,
          source_max_loc_at=excluded.source_max_loc_at,
          source_point_count=excluded.source_point_count,
          precomputed_at=excluded.precomputed_at,
          algorithm_version=excluded.algorithm_version
        """,
        (
            device_id,
            int(meta.get("rawCount") or 0),
            int(meta.get("count") or 0),
            int(meta.get("removedCount") or 0),
            meta.get("start"),
            meta.get("end"),
            meta.get("totalDuration"),
            json_dumps(payload).decode("utf-8"),
            source_max_loc_at,
            len(raw_rows),
            now,
            ALGORITHM_VERSION,
        ),
    )


def save_structured_outputs(con: sqlite3.Connection, device_id: str, payload: dict[str, Any]) -> None:
    now = utc_now_iso()
    con.execute("DELETE FROM gps_port_passages WHERE device_id = ?", (device_id,))
    con.execute("DELETE FROM gps_border_crossings WHERE device_id = ?", (device_id,))
    con.execute("DELETE FROM gps_route_segments WHERE device_id = ?", (device_id,))
    for port in payload.get("ports", []):
        con.execute(
            """
            INSERT INTO gps_port_passages (
              device_id, port_name, port_short_name, countries, lat, lng, radius_km,
              arrival_point_idx, departure_point_idx, arrival_at, departure_at,
              wait_hours, wait_duration_text, matched, algorithm_version, precomputed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                device_id,
                port.get("name"),
                port.get("shortName"),
                port.get("countries"),
                port.get("lat"),
                port.get("lon"),
                port.get("radiusKm"),
                port.get("arrivalPoint"),
                port.get("departurePoint"),
                None if port.get("arrivalTime") == "-" else port.get("arrivalTime"),
                None if port.get("departureTime") == "-" else port.get("departureTime"),
                float(port.get("waitHours") or 0),
                port.get("waitDuration"),
                1 if port.get("arrivalPoint") else 0,
                ALGORITHM_VERSION,
                now,
            ),
        )
    for crossing in payload.get("borderCrossings", []):
        con.execute(
            """
            INSERT INTO gps_border_crossings (
              device_id, seq_no, from_country, from_country_code, to_country,
              to_country_code, from_point_idx, to_point_idx, crossing_at, lat, lng,
              matched_port_name, matched_port_short_name, matched_distance_km,
              confidence, note, algorithm_version, precomputed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                device_id,
                crossing.get("seqNo"),
                crossing.get("fromCountry"),
                crossing.get("fromCountryCode"),
                crossing.get("toCountry"),
                crossing.get("toCountryCode"),
                crossing.get("fromPoint"),
                crossing.get("toPoint"),
                crossing.get("crossingTime"),
                crossing.get("lat"),
                crossing.get("lon"),
                crossing.get("matchedPortName"),
                crossing.get("matchedPortShortName"),
                crossing.get("matchedDistanceKm"),
                float(crossing.get("confidence") or 0),
                crossing.get("note"),
                ALGORITHM_VERSION,
                now,
            ),
        )
    for seq_no, segment in enumerate(payload.get("route", {}).get("segments", []), start=1):
        con.execute(
            """
            INSERT INTO gps_route_segments (
              device_id, seq_no, segment_name, from_node, to_node, depart_at, arrival_at,
              transport_hours, transport_duration_text, port_name, port_wait_text,
              algorithm_version, precomputed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                device_id,
                seq_no,
                segment.get("name"),
                segment.get("from"),
                segment.get("to"),
                segment.get("departTime"),
                segment.get("arrivalTime"),
                float(segment.get("transportHours") or 0),
                segment.get("transportDuration"),
                segment.get("portName"),
                segment.get("portWait"),
                ALGORITHM_VERSION,
                now,
            ),
        )


def precompute_device(con: sqlite3.Connection, device_id: str, port_definitions: list[dict[str, Any]]) -> tuple[int, int, int]:
    rows = load_rows(con, device_id)
    payload = analyze_track(device_id, rows, port_definitions)
    payload.setdefault("meta", {})
    payload["meta"]["precomputed"] = True
    payload["meta"]["algorithmVersion"] = ALGORITHM_VERSION
    update_drift_flags(con, device_id, payload)
    save_cache(con, device_id, payload, rows)
    save_structured_outputs(con, device_id, payload)
    return len(rows), int(payload["meta"].get("count") or 0), int(payload["meta"].get("removedCount") or 0)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-path", default=DEFAULT_DB_PATH)
    parser.add_argument("--schema-path", default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--device-id", action="append", default=[])
    parser.add_argument("--limit-devices", type=int)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    started_at = utc_now_iso()
    processed_devices = 0
    processed_points = 0
    status = "success"
    error_message = None
    with connect(args.db_path) as con:
        apply_schema(con, args.schema_path)
        run_id = con.execute(
            """
            INSERT INTO gps_precompute_runs (run_type, device_id, status, started_at)
            VALUES (?, ?, ?, ?)
            """,
            ("trajectory", ",".join(args.device_id) if args.device_id else None, "running", started_at),
        ).lastrowid
        con.commit()
        try:
            ids = device_ids(con, args.device_id, args.limit_devices)
            port_definitions = load_port_definitions(con)
            for device_id in ids:
                raw_count, display_count, removed_count = precompute_device(con, device_id, port_definitions)
                processed_devices += 1
                processed_points += raw_count
                print(
                    json.dumps(
                        {
                            "ts": utc_now_iso(),
                            "event": "device_precomputed",
                            "device_id": device_id,
                            "raw_points": raw_count,
                            "display_points": display_count,
                            "removed_points": removed_count,
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
            if args.dry_run:
                con.rollback()
            else:
                con.commit()
        except Exception as exc:
            status = "failed"
            error_message = str(exc)
            con.rollback()
            raise
        finally:
            con.execute(
                """
                UPDATE gps_precompute_runs
                SET status = ?, processed_devices = ?, processed_points = ?, error_message = ?, finished_at = ?
                WHERE run_id = ?
                """,
                (status, processed_devices, processed_points, error_message, utc_now_iso(), run_id),
            )
            con.commit()
    print(
        json.dumps(
            {
                "ts": utc_now_iso(),
                "event": "precompute_done",
                "status": status,
                "processed_devices": processed_devices,
                "processed_points": processed_points,
                "dry_run": args.dry_run,
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
