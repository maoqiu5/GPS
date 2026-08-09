const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

const html = fs.readFileSync('web/index.html', 'utf8');
const inlineScripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(match => match[1]);
if (!inlineScripts.length) throw new Error('No inline script found in web/index.html');

function makeElement(id) {
  return {
    id,
    textContent: '',
    innerHTML: '',
    value: '',
    disabled: false,
    dataset: {},
    style: {},
    classList: { add() {}, remove() {}, toggle() { return false; }, contains() { return false; } },
    setAttribute(name, value) { this[name] = String(value); },
    getAttribute(name) { return this[name]; },
    addEventListener() {},
    appendChild() {},
  };
}

function makeContext(cookie = '') {
  const elements = new Map();
  const documentElement = makeElement('html');
  const document = {
    documentElement,
    _cookie: cookie,
    get cookie() { return this._cookie; },
    set cookie(value) { this._cookie = value; },
    getElementById(id) {
      if (!elements.has(id)) elements.set(id, makeElement(id));
      return elements.get(id);
    },
    querySelector() { return makeElement('query'); },
    querySelectorAll() { return []; },
    createElement(tag) { return makeElement(tag); },
    addEventListener() {},
  };
  const context = {
    console,
    document,
    navigator: {},
    localStorage: { getItem() { return null; }, setItem() {} },
    setTimeout(fn) { if (typeof fn === 'function') fn(); return 0; },
    clearTimeout() {},
    fetch: async () => { throw new Error('fetch disabled in i18n test'); },
    location: { pathname: '/gps/', search: '', hash: '', protocol: 'https:' },
    history: { state: {}, replaceState() {}, pushState() {} },
    addEventListener() {},
  };
  context.window = context;
  return context;
}

function loadPage(cookie) {
  const context = makeContext(cookie);
  vm.createContext(context);
  inlineScripts.forEach((script, index) => {
    vm.runInContext(script, context, { filename: `web/index.inline-${index}.js` });
  });
  return context;
}

function flattenStrings(value, out = []) {
  if (typeof value === 'string') out.push(value);
  else if (value && typeof value === 'object') Object.values(value).forEach(item => flattenStrings(item, out));
  return out;
}

const context = loadPage('brianhub_locale=zh-CN');
assert.ok(context.window.GpsI18n, 'window.GpsI18n should be exposed');

const { UI_COPY, normalizeLocale, resolveInitialLocale, setLocale, setLocaleCookie } = context.window.GpsI18n;

assert.strictEqual(normalizeLocale('zh-CN'), 'zh-CN');
assert.strictEqual(normalizeLocale('en-US'), 'en-US');
assert.strictEqual(normalizeLocale('fr-FR'), 'en-US');
assert.strictEqual(normalizeLocale(''), 'en-US');

assert.strictEqual(resolveInitialLocale({ headerLocale: 'zh-CN', cookieLocale: 'en-US' }), 'zh-CN');
assert.strictEqual(resolveInitialLocale({ headerLocale: 'fr-FR', cookieLocale: 'zh-CN' }), 'en-US');
assert.strictEqual(resolveInitialLocale({ cookieLocale: 'zh-CN' }), 'zh-CN');
assert.strictEqual(resolveInitialLocale({ cookieLocale: 'de-DE' }), 'en-US');
assert.strictEqual(resolveInitialLocale({}), 'en-US');

setLocaleCookie('zh-CN');
assert.ok(context.document.cookie.includes('brianhub_locale=zh-CN'), 'locale cookie value should be written');
assert.ok(context.document.cookie.includes('Path=/'), 'locale cookie path should be shared from /');
assert.ok(context.document.cookie.includes('Max-Age=31536000'), 'locale cookie should be long lived');
assert.ok(context.document.cookie.includes('SameSite=Lax'), 'locale cookie should use SameSite=Lax');

setLocale('en-US');
assert.strictEqual(context.document.documentElement.lang, 'en-US');
assert.strictEqual(context.window.GpsI18n.getCurrentLocale(), 'en-US');

assert.ok(UI_COPY['zh-CN'], 'zh-CN dictionary missing');
assert.ok(UI_COPY['en-US'], 'en-US dictionary missing');
const zhStrings = flattenStrings(UI_COPY['zh-CN']);
assert.ok(zhStrings.length > 20, 'zh-CN dictionary should contain UI strings');
zhStrings.forEach(text => {
  assert.ok(!text.includes('??'), `Chinese dictionary contains garbled placeholder: ${text}`);
  assert.ok(!text.includes('???'), `Chinese dictionary contains garbled placeholder: ${text}`);
});

console.log('gps i18n tests passed');
