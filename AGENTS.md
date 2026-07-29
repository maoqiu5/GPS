# GPS Project Agent Instructions

## Scope

This is an existing BrianHub production project at `/root/apps/gps`. Do not treat it as a new scaffold. The project currently serves three business areas from one `/gps/` entry: GPS trajectory visualization, truck on-carriage distance/freight estimation, and rail freight lookup/prediction.

## Must Read First

Before development or deployment, read these project docs:

- `docs/README.md`
- `docs/PRD.md`
- `docs/DEPLOYMENT.md`
- `docs/CHANGELOG.md`
- `docs/HANDOFF.md` if it is later created

Also read BrianHub shared rules when the change touches deployment, gateway, SSO, AI configuration, documentation, or security:

- `/root/apps/portal/docs/BRIANHUB_DEVELOPMENT_STANDARD.md`
- `/root/apps/portal/docs/NEW_PROJECT_DOCUMENTATION_REQUIREMENTS.md`
- `/root/apps/portal/docs/BRIANHUB_GATEWAY_AND_SSO.md`

Read Engramory memory indexes before changing code:

- `.engramory-memory/MEMORY.md`
- Notes referenced by `MEMORY.md` that match the task area

## Project Boundaries

- Frontend production files live under `/root/apps/gps/web`.
- Backend API lives at `/root/apps/gps/scripts/gps_query_api.py` and is run by systemd, not by a long-lived manual `nohup` process.
- SQLite schema lives under `/root/apps/gps/schema` and `/root/apps/gps/docs/HBT_SQLITE_SCHEMA.sql`.
- Production SQLite data lives under `/root/apps/gps/data/gps/gps_tracking.db` and must be preserved.
- Do not replace this project with a generic Docker template; `docs/DEPLOYMENT.md` documents the current non-Docker production shape.

## Safety Boundaries

- Do not read, print, copy, or commit real `.env`, `.env.production`, secret, token, key, cookie, or credential files.
- Do not read or modify `data/`, `backups/`, `logs/`, `runtime/`, `secrets/`, database files, or large raw logs unless the user explicitly asks and the task requires it.
- Do not delete or overwrite `/root/apps/gps/data`, `/root/apps/gps/schema`, or production SQLite files.
- Do not modify global Codex configuration, Codex native memories, or local sqlite memory stores.
- Do not install git hooks or other persistent developer hooks.
- Do not expose BrianHub internal tokens, HBT credentials, API keys, private keys, or database contents in docs, logs, pages, or responses.

## Engramory Rules

- `.engramory-memory/` is project-local memory and must stay out of git.
- `MEMORY.md` is only a short index. Keep it below 200 lines and 25 KB.
- Prefer updating an existing note over creating a duplicate note.
- Memory notes should record future-facing reminders: boundaries, traps, workflows, and pointers. Do not duplicate long details already maintained in `docs/`.
- Archive obsolete notes by moving them to an archive note only when needed; do not silently delete useful context.

## Verification Commands

Use the smallest relevant checks for the change. Common commands:

```bash
python3 -m py_compile /root/apps/gps/scripts/gps_query_api.py
systemctl is-active gps-query-api-edge.service
curl -s http://172.19.0.1:8015/health
curl -sS --max-time 15 -o /dev/null -w 'page %{http_code} %{time_total}\n' https://brianhub.net/gps/
curl -sS --max-time 15 https://brianhub.net/gps/api/health
```

Truck module smoke checks:

```bash
curl -sS 'http://172.19.0.1:8015/api/truck-stations'
curl -sS 'http://172.19.0.1:8015/api/truck-distance?address=Katowice%2C%20Poland&station_group=europe'
```

If frontend rail calculator files are changed, use the project test commands named in `docs/CHANGELOG.md`, such as:

```bash
node tools/test_rail_calculator.js
node tools/test_rail_html_smoke.js
```

## Deployment Reminder

After backend changes, upload/sync the changed file, restart `gps-query-api-edge.service`, and verify the internal API plus public `/gps/` route. After frontend changes, preserve `web/data`, update Service Worker cache version when needed, and verify with a no-cache browser or HTTP checks.
