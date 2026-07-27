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
