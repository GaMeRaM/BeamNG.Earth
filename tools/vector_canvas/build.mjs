import {build} from 'esbuild';
import fs from 'node:fs';
import path from 'node:path';
const out = '../../mod/beamng_earth/vehicles/common/';
await build({ entryPoints: ['index.js'], bundle: true, minify: true, target: 'chrome90', outfile: out + 'earth_canvas.js' });
const notices = [];
for (const entry of fs.readdirSync('node_modules')) {
  if (entry.startsWith('.')) continue;
  const dirs = entry.startsWith('@') ? fs.readdirSync('node_modules/' + entry).map(name => entry + '/' + name) : [entry];
  for (const dir of dirs) {
    const root = path.join('node_modules', dir);
    if (!fs.existsSync(path.join(root, 'package.json'))) continue;
    const pkg = JSON.parse(fs.readFileSync(path.join(root, 'package.json')));
    for (const name of fs.readdirSync(root).filter(name => /^(licen[cs]e|copying|notice)(\.|$)/i.test(name))) {
      if (fs.statSync(path.join(root, name)).isFile()) notices.push(`${pkg.name} ${pkg.version} — ${name}\n${fs.readFileSync(path.join(root, name), 'utf8')}`);
    }
  }
}
fs.writeFileSync(out + 'earth_canvas.LICENSES.txt', notices.join('\n\n--------------------\n\n'));
