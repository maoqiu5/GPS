# Rates Project Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split truck freight and rail freight modules out of the GPS project into a new BrianHub project with slug `rates`.

**Architecture:** Create a standalone `rates` project with static frontend, copied rail calculator/data, and an independent Python API for truck pricing routes. BrianHub gateway exposes `/rates/` and `/rates/api/*`; portal project cards and document center include the new project.

**Tech Stack:** Static HTML/JS/CSS, Leaflet, Python standard-library HTTP API, SQLite, systemd, BrianHub Caddy gateway.

## Global Constraints

- Project slug: `rates`.
- Public path: `https://brianhub.net/rates/`.
- VPS project directory: `/root/apps/rates`.
- Local project directory: `C:\Users\12514\Documents\rates`.
- API service: `rates-api-edge.service`, systemd-managed, not a manual long-running process.
- API listen address: `172.19.0.1:8025`.
- BrianHub SSO protects page and API routes through portal `/auth/check`.
- Required docs: `docs/README.md`, `docs/PRD.md`, `docs/DEPLOYMENT.md`, `docs/CHANGELOG.md`.
- No real passwords, API keys, cookies, internal tokens, or private keys in code/docs/logs.

---

### Task 1: Scaffold standalone rates project

**Files:**
- Create: `C:\Users\12514\Documents\rates\web\index.html`
- Create: `C:\Users\12514\Documents\rates\web\sw.js`
- Create: `C:\Users\12514\Documents\rates\web\rail-calculator.js`
- Create: `C:\Users\12514\Documents\rates\web\data\*.json`
- Create: `C:\Users\12514\Documents\rates\scripts\rates_api.py`
- Create: `C:\Users\12514\Documents\rates\schema\RATES_SQLITE_SCHEMA.sql`
- Create: `C:\Users\12514\Documents\rates\tools\test_rates_frontend.js`
- Create: `C:\Users\12514\Documents\rates\tools\test_rates_api.py`

**Interfaces:**
- Produces static files under `web/`.
- Produces API routes `/health`, `/api/truck-stations`, `/api/truck-market-references`, `/api/truck-distance`.

- [ ] Write tests asserting rates frontend has no GPS module and points API to `/rates`.
- [ ] Verify tests fail before scaffolding.
- [ ] Copy existing rail assets and build a rates-focused frontend.
- [ ] Copy truck API logic into standalone `rates_api.py` with new default DB/schema paths.
- [ ] Copy truck SQLite tables into `RATES_SQLITE_SCHEMA.sql`.
- [ ] Verify local tests pass.

### Task 2: Add BrianHub-standard docs

**Files:**
- Create: `C:\Users\12514\Documents\rates\docs\README.md`
- Create: `C:\Users\12514\Documents\rates\docs\PRD.md`
- Create: `C:\Users\12514\Documents\rates\docs\DEPLOYMENT.md`
- Create: `C:\Users\12514\Documents\rates\docs\CHANGELOG.md`

**Interfaces:**
- Produces portal-readable documentation for the document center.

- [ ] Write docs with product scope, deployment, data boundary, verification and rollback.
- [ ] Verify docs contain no real secrets.

### Task 3: Deploy rates to VPS

**Files:**
- Create/modify VPS: `/root/apps/rates/**`
- Create VPS systemd unit: `/etc/systemd/system/rates-api-edge.service`

**Interfaces:**
- Produces API at `172.19.0.1:8025`.
- Produces static files at `/root/apps/rates/web`.

- [ ] Upload project files to VPS.
- [ ] Initialize rates SQLite with truck tables.
- [ ] Install and start `rates-api-edge.service`.
- [ ] Verify health and truck API locally on VPS.

### Task 4: Register rates in portal and gateway

**Files:**
- Modify local portal: `C:\Users\12514\Documents\门户\src\projects.js`
- Modify local portal: `C:\Users\12514\Documents\门户\src\documentProjects.js`
- Modify VPS gateway Caddyfile: `/root/apps/brianhub-gateway/Caddyfile`

**Interfaces:**
- Portal card: `境外运价` at `/rates`.
- Gateway routes: `/rates/`, `/rates/api/*`.

- [ ] Add portal project card and docs project.
- [ ] Update gateway route with SSO protection.
- [ ] Reload/rebuild services as required.
- [ ] Verify Caddy route sees `/srv/rates` static files and API proxy.

### Task 5: GPS cleanup handoff

**Files:**
- Modify GPS frontend only if low-risk: remove or redirect truck/rail nav entries.
- Update GPS docs to state rates moved to `/rates/`.

**Interfaces:**
- GPS remains focused on trajectory tools.
- Rates owns freight pricing.

- [ ] Decide whether to remove old modules immediately or show migration link.
- [ ] Verify GPS API remains active and GPS page still works.

## Self-Review

- Covers slug, VPS path, docs, SSO, API, data directory, health check and portal docs center.
- No placeholders or secrets included.
- Keeps first deployment low-risk by making new `rates` functional before altering GPS.
