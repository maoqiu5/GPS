#!/usr/bin/env bash
set -euo pipefail

# Cron-safe incremental runner for GPS/HBT ingestion.
# Requires HBT_APP_KEY and HBT_APP_SECRET in the environment.

ROOT_DIR="${GPS_ROOT_DIR:-/root/apps/gps}"
DB_PATH="${GPS_DB_PATH:-${ROOT_DIR}/data/gps/gps_tracking.db}"
SCHEMA_PATH="${GPS_SCHEMA_PATH:-${ROOT_DIR}/schema/HBT_SQLITE_SCHEMA.sql}"
LOG_DIR="${GPS_LOG_DIR:-${ROOT_DIR}/logs}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
HBT_API_URL="${HBT_API_URL:-https://openapi.51hbt.com/}"

START_AT="${START_AT:-2026-06-23 00:00:00}"
END_AT="${END_AT:-$(TZ=Asia/Shanghai date '+%Y-%m-%d %H:%M:%S')}"
TRACK_MAX_WINDOWS="${TRACK_MAX_WINDOWS:-20}"
TRACK_ORDER_BY="${TRACK_ORDER_BY:-online_recent}"
ALARM_MAX_WINDOWS="${ALARM_MAX_WINDOWS:-8}"
SITE_MAX_WINDOWS="${SITE_MAX_WINDOWS:-2}"
SLEEP_SECONDS="${SLEEP_SECONDS:-0.5}"
DRY_RUN="${DRY_RUN:-0}"

mkdir -p "$LOG_DIR"

timestamp="$(date -u +%Y%m%d-%H%M%S)"
summary_log="${LOG_DIR}/hbt_incremental_${timestamp}.log"

log() {
  printf '{"ts":"%s","event":"%s","message":%s}\n' \
    "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" \
    "$1" \
    "$("$PYTHON_BIN" -c 'import json,sys; print(json.dumps(sys.argv[1], ensure_ascii=False))' "$2")" \
    | tee -a "$summary_log"
}

run_step() {
  local name="$1"
  shift
  log "${name}_start" "$*"
  "$@" 2>&1 | tee -a "$summary_log"
  log "${name}_done" "ok"
}

dry_flag=()
if [ "$DRY_RUN" = "1" ]; then
  dry_flag=(--dry-run)
else
  if [ -z "${HBT_APP_KEY:-}" ] || [ -z "${HBT_APP_SECRET:-}" ]; then
    echo "HBT_APP_KEY and HBT_APP_SECRET are required unless DRY_RUN=1" >&2
    exit 2
  fi
  export HBT_APP_KEY HBT_APP_SECRET HBT_API_URL
fi

log "incremental_start" "db=${DB_PATH}; start=${START_AT}; end=${END_AT}; dry_run=${DRY_RUN}"

run_step "current_status" \
  "$PYTHON_BIN" "${ROOT_DIR}/scripts/hbt_collect_current.py" \
    --db-path "$DB_PATH" \
    --schema-path "$SCHEMA_PATH" \
    --log-path "${LOG_DIR}/hbt_current_status_${timestamp}.log" \
    --sleep-seconds "$SLEEP_SECONDS" \
    "${dry_flag[@]}"

run_step "track_incremental" \
  "$PYTHON_BIN" "${ROOT_DIR}/scripts/hbt_backfill_tracks.py" \
    --db-path "$DB_PATH" \
    --schema-path "$SCHEMA_PATH" \
    --log-path "${LOG_DIR}/hbt_track_incremental_${timestamp}.log" \
    --start "$START_AT" \
    --end "$END_AT" \
    --use-cursors \
    --order-by "$TRACK_ORDER_BY" \
    --max-windows "$TRACK_MAX_WINDOWS" \
    --sleep-seconds "$SLEEP_SECONDS" \
    "${dry_flag[@]}"

run_step "alarm_incremental" \
  "$PYTHON_BIN" "${ROOT_DIR}/scripts/hbt_collect_events.py" alarm \
    --db-path "$DB_PATH" \
    --schema-path "$SCHEMA_PATH" \
    --log-path "${LOG_DIR}/hbt_alarm_incremental_${timestamp}.log" \
    --start "$START_AT" \
    --end "$END_AT" \
    --use-cursors \
    --max-windows "$ALARM_MAX_WINDOWS" \
    --sleep-seconds "$SLEEP_SECONDS" \
    "${dry_flag[@]}"

run_step "site_events_incremental" \
  "$PYTHON_BIN" "${ROOT_DIR}/scripts/hbt_collect_events.py" site-events \
    --db-path "$DB_PATH" \
    --schema-path "$SCHEMA_PATH" \
    --log-path "${LOG_DIR}/hbt_site_events_incremental_${timestamp}.log" \
    --start "$START_AT" \
    --end "$END_AT" \
    --use-cursors \
    --max-windows "$SITE_MAX_WINDOWS" \
    --sleep-seconds "$SLEEP_SECONDS" \
    "${dry_flag[@]}"

log "incremental_done" "ok"
echo "SUMMARY_LOG=${summary_log}"
