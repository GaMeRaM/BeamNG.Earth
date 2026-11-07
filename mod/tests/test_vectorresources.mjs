// node --test mod/tests/test_vectorresources.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import fs from 'node:fs';

test('MapLibre bridge decodes JSON/binary, limits concurrency and handles aborts', async () => {
  const sent = [];
  let protocol;
  const window = { location: { pathname: '/beamng_earth_dashboard.html' },
    beamng: { sendEngineLua: code => {
      const args = code.match(/requestVectorResource\((.*)\) end/)[1];
      const [id, url] = JSON.parse('[' + args + ']');
      sent.push({ id, url });
    } } };
  const maplibregl = { addProtocol: (name, callback) => { protocol = callback; },
    Map: class { constructor(options) { this.options = options; } on() {} } };
  const context = vm.createContext({ window, beamng: window.beamng, maplibregl,
    Map, Promise, Uint8Array, TextDecoder, setTimeout, clearTimeout, atob });
  vm.runInContext(fs.readFileSync(new URL('../beamng_earth/vehicles/common/earth_vector.js', import.meta.url), 'utf8'), context);
  const transport = window.EarthVector;
  const map = transport.createMap('map');
  assert.equal(map.options.transformRequest('https://tiles.openfreemap.org/styles/liberty').url,
    'earth://tiles.openfreemap.org/styles/liberty');
  const controller = new AbortController();
  const json = protocol({ url: 'earth://tiles.openfreemap.org/planet', type: 'json' }, controller);
  assert.equal(sent[0].url, 'https://tiles.openfreemap.org/planet');
  transport.resourceData({ id: sent[0].id, data: btoa('{"tiles":[]}') });
  assert.equal(JSON.stringify((await json).data), '{"tiles":[]}');
  const binary = protocol({ url: 'earth://tiles.openfreemap.org/fonts/test/0-255.pbf', type: 'arrayBuffer' }, controller);
  transport.resourceData({ id: sent[1].id, data: btoa('\x00\xff\x80') });
  assert.deepEqual([...new Uint8Array((await binary).data)], [0, 255, 128]);
  const controllers = Array.from({ length: 6 }, () => new AbortController());
  const results = controllers.map(c => protocol({ url: 'earth://tiles.openfreemap.org/planet', type: 'json' }, c));
  const settled = Promise.allSettled(results);
  assert.equal(sent.length, 6, 'only four more requests start');
  controllers[4].abort(); // queued request never sent
  controllers[0].abort(); // release a slot for the sixth request
  assert.equal(sent.length, 7);
  transport.dispose();
  assert.ok((await settled).every(result => result.status === 'rejected'));
});
