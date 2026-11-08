/* Shared MapLibre/OpenFreeMap transport. CEF HTTP is unavailable: use the game connection. */
(function () {
  'use strict';
  const STYLE = 'https://tiles.openfreemap.org/styles/dark';
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
  // Navigation-oriented contrast; keep the provider's geometry, filters and zoom rules.
  function prepareStyle(style) {
    for (const layer of style.layers || []) {
      const paint = layer.paint || (layer.paint = {});
      const source = layer['source-layer'];
      if (layer.type === 'background') paint['background-color'] = '#161c25';
      if (source === 'water' && layer.type === 'fill') paint['fill-color'] = '#213e52';
      if (source === 'building' && layer.type === 'fill') {
        paint['fill-color'] = '#303a48'; paint['fill-outline-color'] = '#4d5c6e';
      }
      if (source === 'landuse' || source === 'landcover') {
        if (layer.type === 'fill') paint['fill-color'] = /wood|park/.test(layer.id) ? '#21372e' : '#1d2530';
      }
      if (source === 'transportation' && layer.type === 'line') {
        if (/casing/.test(layer.id)) paint['line-color'] = '#10151d';
        else if (/motorway/.test(layer.id)) paint['line-color'] = '#cba66a';
        else if (/major/.test(layer.id)) paint['line-color'] = '#9baabd';
        else if (/rail/.test(layer.id)) paint['line-color'] = '#637087';
        else paint['line-color'] = '#65758a';
        if (layer.id === 'highway_path') {
          paint['line-color'] = '#3e4a59'; paint['line-width'] = 1; paint['line-opacity'] = 0.65;
        }
      }
      if (layer.type === 'symbol' && layer.layout && layer.layout['text-field']) {
        paint['text-color'] = source === 'water_name' ? '#9cc9e2' : '#e4eaf1';
        paint['text-halo-color'] = '#161c25'; paint['text-halo-width'] = 1.25;
        paint['text-opacity'] = 1;
      }
    }
    return style;
  }
  let registered = false;
  function createMap(container, onError) {
    if (window.EarthCanvas) {
      const probe = document.createElement('canvas');
      const gl = probe.getContext('webgl2') || probe.getContext('webgl');
      if (!gl) return window.EarthCanvas.createMap(container, request, onError, STYLE);
      const lose = gl.getExtension('WEBGL_lose_context');
      if (lose) lose.loseContext();
    }
    if (!registered) {
      maplibregl.addProtocol('earth', async (params, controller) => {
        const data = await request(params.url.replace(/^earth:\/\//, 'https://'), controller.signal);
        if (params.type !== 'json') return { data };
        const json = JSON.parse(new TextDecoder().decode(data));
        return { data: params.url.includes('/styles/dark') ? prepareStyle(json) : json };
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
  function routeFeature(route) {
    const coordinates = (route && Array.isArray(route.points) ? route.points : [])
      .filter(p => Array.isArray(p) && Number.isFinite(p[0]) && Number.isFinite(p[1]))
      .map(p => [p[1], p[0]]);
    return { type: 'Feature', properties: {}, geometry: coordinates.length > 1
      ? { type: 'LineString', coordinates } : null };
  }
  function setRoute(map, route) {
    const feature = routeFeature(route);
    if (map.setRoute) { map.setRoute(feature); return; }
    if (!map.isStyleLoaded()) return;
    const source = map.getSource('earth-route');
    if (source) { source.setData(feature); return; }
    map.addSource('earth-route', { type: 'geojson', data: feature });
    for (const [id, color, width] of [['earth-route-casing', '#102a48', 8], ['earth-route-line', '#3aa0ff', 5]]) {
      map.addLayer({ id, type: 'line', source: 'earth-route',
        layout: { 'line-join': 'round', 'line-cap': 'round' },
        paint: { 'line-color': color, 'line-width': width } });
    }
  }
  function dispose() {
    queue.length = 0;
    for (const id of Array.from(pending.keys())) finish(id, null, new Error('Map closed'));
  }
  window.EarthVector = { createMap, resourceData, dispose, CREDIT, prepareStyle, setRoute, routeFeature };
}());
