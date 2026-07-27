# GPS Only Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep the GPS project focused on GPS trajectory viewing and remove freight-rate modules now served by the standalone `rates` project.

**Architecture:** The GPS frontend should expose only the GPS trajectory module and map controls. The GPS API should keep health, trajectory, device, route and binding endpoints, while no longer exposing truck-rate endpoints. Rail static assets and helper tools move out of GPS ownership because `C:\Users\12514\Documents\rates` now owns them.

**Tech Stack:** Static HTML/CSS/JS, Leaflet, Python standard-library API, Node smoke tests.

## Global Constraints

- Do not touch the standalone `rates` project behavior.
- Do not delete the GPS SQLite database tables during this cleanup.
- Keep `/gps/` and `gps-query-api-edge.service` working.
- Keep `/rates/` and `rates-api-edge.service` working after deployment.

---

### Task 1: GPS-only frontend contract

**Files:**
- Create: `tools/test_gps_only_html_smoke.js`
- Modify: `web/index.html`
- Modify: `web/sw.js`
- Delete: `web/rail-calculator.js`
- Delete: `web/data/rail-*.json`
- Delete: `tools/test_rail_*.js`
- Delete: `tools/extract_rail_*.py`
- Delete: `tools/build_rates_*.js`

**Interfaces:**
- Consumes: `web/index.html` as a static page.
- Produces: a GPS-only page with `data-module="gps"` and `id="module-gps"`; no `truck`, `rail`, or `market` module ids.

- [ ] **Step 1: Write failing frontend smoke test**

```js
const fs = require('fs');
const vm = require('vm');

const html = fs.readFileSync('web/index.html', 'utf8');
const sw = fs.readFileSync('web/sw.js', 'utf8');

if (!html.includes('<title>Brianhub GPS</title>')) throw new Error('GPS title missing');
if (!html.includes('data-module="gps"')) throw new Error('GPS nav missing');
if (!html.includes('id="module-gps"')) throw new Error('GPS module missing');
['truck', 'rail', 'market'].forEach(name => {
  if (html.includes(`data-module="${name}"`)) throw new Error(`${name} nav should be removed`);
  if (html.includes(`id="module-${name}"`)) throw new Error(`${name} panel should be removed`);
});
['rail-calculator.js', 'rail-rates-', 'truck-distance', 'truck-stations', 'truck-market'].forEach(text => {
  if (html.includes(text)) throw new Error(`freight residue in HTML: ${text}`);
  if (sw.includes(text)) throw new Error(`freight residue in service worker: ${text}`);
});

const inlineScripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(match => match[1]);
inlineScripts.forEach((script, index) => new vm.Script(script, { filename: `inline-${index}.js` }));

console.log('gps-only html smoke passed');
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node tools/test_gps_only_html_smoke.js`

Expected: FAIL because freight modules still exist.

- [ ] **Step 3: Remove freight UI/static assets**

Edit `web/index.html` to remove freight nav/panels and freight initialization calls. Edit `web/sw.js` to cache only GPS page assets. Delete rail data/calculator/extraction/test/build helper files from GPS.

- [ ] **Step 4: Run test to verify it passes**

Run: `node tools/test_gps_only_html_smoke.js`

Expected: `gps-only html smoke passed`.

### Task 2: GPS API endpoint contract

**Files:**
- Create: `tools/test_gps_only_api.py`
- Modify: `scripts/gps_query_api.py`

**Interfaces:**
- Consumes: `scripts/gps_query_api.py`.
- Produces: `GpsApiHandler` without `/api/truck-stations`, `/api/truck-market-references`, or `/api/truck-distance` routes.

- [ ] **Step 1: Write failing API smoke test**

```python
from pathlib import Path

source = Path("scripts/gps_query_api.py").read_text(encoding="utf-8")

for endpoint in ["/api/truck-stations", "/api/truck-market-references", "/api/truck-distance"]:
    assert endpoint not in source, f"{endpoint} should be removed from GPS API"

assert "/api/trajectory" in source
assert "/api/trajectory-devices" in source
assert "/api/route-summary" in source
print("gps-only api smoke passed")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python tools/test_gps_only_api.py`

Expected: FAIL because truck endpoints still exist.

- [ ] **Step 3: Remove truck endpoint branches**

Delete the three `/api/truck-*` branches from `GpsApiHandler.do_GET`. Leave database schema/data untouched.

- [ ] **Step 4: Run test to verify it passes**

Run: `python tools/test_gps_only_api.py`

Expected: `gps-only api smoke passed`.

### Task 3: Deployment verification

**Files:**
- Modify on VPS: `/root/apps/gps/web`
- Modify on VPS: `/root/apps/gps/scripts/gps_query_api.py`

**Interfaces:**
- Consumes: local verified GPS files.
- Produces: `/gps/` GPS-only UI and active GPS API.

- [ ] **Step 1: Deploy verified GPS files**

Upload GPS web files and `scripts/gps_query_api.py`; restart `gps-query-api-edge.service`.

- [ ] **Step 2: Verify GPS and rates**

Run:

```bash
curl -fsS http://172.19.0.1:8015/health
curl -fsS http://172.19.0.1:8015/api/trajectory-devices?limit=1
curl -fsS http://172.19.0.1:8025/api/health
```

Expected: GPS and rates health return `ok`.
