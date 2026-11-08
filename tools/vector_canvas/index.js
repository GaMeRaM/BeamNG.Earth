import Map from 'ol/Map.js';
import View from 'ol/View.js';
import {fromLonLat} from 'ol/proj.js';
import {apply} from 'ol-mapbox-style';
import 'ol/ol.css';
import {applyCamera} from './camera.mjs';

// Implements the small MapLibre camera/lifecycle interface used by both game screens.
// VectorTile layers created by apply() use OpenLayers' Canvas2D renderer.
function createMap(container, request, onError, styleUrl = 'https://tiles.openfreemap.org/styles/dark') {
  const listeners = new globalThis.Map();
  const controller = new AbortController();
  let closed = false;
  const map = new Map({ target: container, controls: [], interactions: [],
    view: new View({ center: fromLonLat([0, 20]), zoom: 3, maxZoom: 23,
      constrainResolution: false, constrainRotation: false, multiWorld: true }), maxTilesLoading: 4 });
  const emit = name => { if (!closed) for (const callback of listeners.get(name) || []) callback(); };
  const report = error => { if (!closed && onError) onError(error.message || String(error)); };
  async function response(url) {
    try {
      const bytes = await request(url, controller.signal);
      return new Response(bytes, { headers: { 'Content-Type': url.includes('.png') ? 'image/png' :
        (url.includes('.pbf') ? 'application/x-protobuf' : 'application/json') } });
    } catch (error) { report(error); throw error; }
  }
  response(styleUrl).then(r => r.json()).then(style => {
    if (closed) return;
    // Use system fonts; CEF blocks remote font CSS and Canvas does not consume PBF glyphs.
    for (const layer of style.layers) {
      if (layer.layout && layer.layout['text-font']) layer.layout['text-font'] = ['Arial'];
    }
    if (style.metadata) delete style.metadata['ol:webfonts'];
    return apply(map, style, { styleUrl,
      transformRequest: url => response(url) }).then(() => {
      if (closed) return;
      map.getLayers().forEach(layer => {
        const source = layer.getSource && layer.getSource();
        if (source) source.on('tileloaderror', () => report(new Error('Vector tile could not be loaded')));
      });
      emit('load');
    });
  }).catch(report);
  map.on('rendercomplete', () => emit('idle'));
  return {
    on(name, callback) { if (!listeners.has(name)) listeners.set(name, []); listeners.get(name).push(callback); },
    jumpTo(camera) {
      if (closed) return;
      applyCamera(map.getView(), camera);
    },
    resize() { if (!closed) map.updateSize(); },
    remove() { closed = true; controller.abort(); map.setTarget(undefined); map.dispose(); listeners.clear(); }
  };
}
window.EarthCanvas = { createMap };
