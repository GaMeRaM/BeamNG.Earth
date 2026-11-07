/* Shared MapLibre/OpenFreeMap transport. CEF HTTP is unavailable: use the game connection. */
(function () {
  'use strict';
  const STYLE = 'https://tiles.openfreemap.org/styles/liberty';
  const CREDIT = 'OpenFreeMap · © OpenMapTiles · © OpenStreetMap contributors';
  const pending = new Map();
  const queue = [];
  const session = (window.location.pathname.includes('beamng_earth_dashboard') ? 'dashboard-' : 'world-')
    + Math.random().toString(36).slice(2);
  let serial = 0, active = 0;

  function engineLua(code) {
    if (window.beamng && beamng.sendEngineLua) beamng.sendEngineLua(code);
    else if (window.bngApi && bngApi.engineLua) bngApi.engineLua(code);
    else throw new Error('Game connection unavailable');
  }
  function pump() {
    while (active < 4 && queue.length) {
      const item = queue.shift();
      if (!pending.has(item.id)) continue;
      item.started = true;
      active++;
      try {
        engineLua('if beamngEarth_core then beamngEarth_core.requestVectorResource('
          + JSON.stringify(item.id) + ',' + JSON.stringify(item.url) + ') end');
      } catch (error) { finish(item.id, null, error); }
    }
  }
  function finish(id, data, error) {
    const item = pending.get(id);
    if (!item) return;
    pending.delete(id);
    clearTimeout(item.timer);
    item.signal.removeEventListener('abort', item.abort);
    if (item.started) active--;
    if (error) item.reject(error);
    else item.resolve(data);
    pump();
  }
  function request(url, signal) {
    return new Promise((resolve, reject) => {
      if (signal.aborted) { reject(new Error('Map request aborted')); return; }
      const id = session + '-' + (++serial);
      const item = { id, url, resolve, reject, signal, started: false };
      item.abort = () => finish(id, null, new Error('Map request aborted'));
      item.timer = setTimeout(() => finish(id, null, new Error('Map resource timed out')), 60000);
      pending.set(id, item);
      signal.addEventListener('abort', item.abort);
      queue.push(item);
      pump();
    });
  }
  function resourceData(msg) {
    if (!msg || !pending.has(msg.id)) return;
    if (msg.error) { finish(msg.id, null, new Error(msg.error)); return; }
    try {
      const raw = atob(msg.data);
      const bytes = new Uint8Array(raw.length);
      for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
      finish(msg.id, bytes.buffer);
    } catch (error) { finish(msg.id, null, error); }
  }
  let registered = false;
  function createMap(container, onError) {
    if (window.EarthCanvas) {
      const probe = document.createElement('canvas');
      const gl = probe.getContext('webgl2') || probe.getContext('webgl');
      if (!gl) return window.EarthCanvas.createMap(container, request, onError);
      const lose = gl.getExtension('WEBGL_lose_context');
      if (lose) lose.loseContext();
    }
    if (!registered) {
      maplibregl.addProtocol('earth', async (params, controller) => {
        const data = await request(params.url.replace(/^earth:\/\//, 'https://'), controller.signal);
        return { data: params.type === 'json' ? JSON.parse(new TextDecoder().decode(data)) : data };
      });
      registered = true;
      // Keep worker and WebGL cost modest on small vehicle screens.
      maplibregl.workerCount = 1;
    }
    const map = new maplibregl.Map({
      container, style: STYLE, center: [0, 20], zoom: 2,
      interactive: false, attributionControl: false, renderWorldCopies: true,
      fadeDuration: 0, maxPitch: 0,
      transformRequest: url => ({ url: url.replace(/^https:\/\/tiles\.openfreemap\.org\//,
        'earth://tiles.openfreemap.org/') })
    });
    map.on('error', event => onError && onError(event.error.message));
    return map;
  }
  function dispose() {
    queue.length = 0;
    for (const id of Array.from(pending.keys())) finish(id, null, new Error('Map closed'));
  }
  window.EarthVector = { createMap, resourceData, dispose, CREDIT };
}());
