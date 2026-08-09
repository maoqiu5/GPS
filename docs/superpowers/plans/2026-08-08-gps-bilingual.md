# GPS Bilingual UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add BrianHub-standard bilingual UI behavior to the static GPS trajectory page.

**Architecture:** Keep the implementation in `web/index.html` because GPS is a static single-page app. Add locale helpers, stable i18n keys, DOM text application, and a shared cookie-writing language switcher. Add a Node regression test that evaluates the helpers without requiring a browser.

**Tech Stack:** Static HTML, inline JavaScript, Node.js `vm`, existing Git workflow.

## Global Constraints

- Supported locales are exactly `zh-CN` and `en-US`.
- Initial priority is `X-BrianHub-Locale`, then `brianhub_locale`, then default `en-US`.
- Unknown values fall back to `en-US`.
- Language switching writes `brianhub_locale` with `Path=/; Max-Age=31536000; SameSite=Lax`.
- Translate UI chrome only; do not translate business data or API-returned content.
- Do not add a separate user-level language preference system.
- Update `docs/README.md`, `docs/PRD.md`, and `docs/CHANGELOG.md`.

---

### Task 1: i18n Regression Tests

**Files:**
- Create: `tools/test_gps_i18n.js`
- Modify: `web/index.html`

**Interfaces:**
- Consumes: inline script in `web/index.html`.
- Produces: regression checks for `normalizeLocale`, `resolveInitialLocale`, `setLocaleCookie`, `setLocale`, and `UI_COPY`.

- [ ] **Step 1: Write the failing test**

Create `tools/test_gps_i18n.js` that loads `web/index.html`, extracts inline scripts, evaluates them in a VM with a stubbed `document`, and asserts the BrianHub language rules.

- [ ] **Step 2: Run test to verify it fails**

Run: `node tools/test_gps_i18n.js`

Expected: FAIL because locale helpers are not defined yet.

- [ ] **Step 3: Implement minimal page i18n**

Modify `web/index.html` to expose the tested helpers, dictionaries, switcher, and DOM updates.

- [ ] **Step 4: Run test to verify it passes**

Run: `node tools/test_gps_i18n.js`

Expected: PASS.

### Task 2: Existing Smoke Test Compatibility

**Files:**
- Test: `tools/test_gps_only_html_smoke.js`

**Interfaces:**
- Consumes: `web/index.html`, `web/sw.js`.
- Produces: existing GPS-only smoke guarantee remains valid.

- [ ] **Step 1: Run existing smoke test**

Run: `node tools/test_gps_only_html_smoke.js`

Expected: PASS.

- [ ] **Step 2: Fix any regressions**

If it fails, adjust i18n implementation without reintroducing truck/rail/market UI.

### Task 3: Documentation

**Files:**
- Modify: `docs/README.md`
- Modify: `docs/PRD.md`
- Modify: `docs/CHANGELOG.md`

**Interfaces:**
- Consumes: final behavior from Task 1.
- Produces: documentation of BrianHub language rules, translation scope, and verification.

- [ ] **Step 1: Update docs**

Document that GPS uses BrianHub `zh-CN` / `en-US`, priority order, shared cookie, UI-only translation boundary, and test command.

- [ ] **Step 2: Run docs-sensitive tests**

Run: `node tools/test_gps_i18n.js` and `node tools/test_gps_only_html_smoke.js`.

Expected: both PASS.

### Task 4: Final Verification And Commit

**Files:**
- Commit all changed source, tests, and docs.

**Interfaces:**
- Consumes: Tasks 1-3.
- Produces: clean local commit ready to push/deploy.

- [ ] **Step 1: Verify sensitive files are not tracked**

Run tracked path and exact-secret scans before commit.

- [ ] **Step 2: Commit**

Commit message: `Add BrianHub bilingual support to GPS page`.

- [ ] **Step 3: Report**

Report changed files, test commands, and whether deployment/push was performed.

