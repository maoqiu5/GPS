# GPS Bilingual UI Design

## Goal

Connect the GPS trajectory page to the BrianHub unified bilingual standard for `zh-CN` and `en-US`, without adding an independent language preference system.

## Scope

Only the GPS trajectory page is in scope. The page currently lives in `web/index.html` and shows trajectory query, map controls, route summary, status messages, popups, legends, and empty/error states. Truck and rail modules are out of scope because GPS currently only displays trajectory.

## Architecture

The project is a static HTML app, so the bilingual layer will live in the page script instead of a Next.js helper. The implementation will add stable i18n keys, a `UI_COPY` dictionary for `zh-CN` and `en-US`, locale normalization helpers, DOM application logic, and a local switcher that writes the shared BrianHub cookie.

Initial locale resolution follows the BrianHub standard:

1. `X-BrianHub-Locale`
2. `brianhub_locale` cookie
3. default `en-US`

Because a static browser page cannot directly read arbitrary request headers after navigation, the page will support a header-compatible bootstrap path through a meta tag or global value when the gateway/server injects one in the future, while cookie/default behavior works immediately. Tests cover the helper behavior directly, including header precedence.

## Translation Boundaries

Translate only UI strings: menu labels, titles, buttons, form labels and placeholders, validation/loading/empty/error messages, popup chrome text, map legend labels, route table columns, and control labels.

Do not translate business data: device IDs, GPS coordinates, raw point values, country/port names returned by APIs, route text returned by APIs, user input, Markdown/document body text, or AI output.

## Cookie Behavior

The language switcher writes:

```text
brianhub_locale=<locale>; Path=/; Max-Age=31536000; SameSite=Lax
```

Switching language updates the current page immediately without navigating or storing any separate user preference.

## Testing

Add `tools/test_gps_i18n.js` to parse the static HTML and execute the inline helpers in a VM-backed DOM stub. Regression coverage:

- `zh-CN` and `en-US` normalize successfully.
- Unknown locale values fall back to `en-US`.
- Header locale takes precedence over cookie locale.
- Cookie locale is used when header is absent.
- Switching language writes `brianhub_locale`.
- Chinese dictionary values do not contain `??` or `???`.

The existing GPS-only HTML smoke test must continue to pass.

