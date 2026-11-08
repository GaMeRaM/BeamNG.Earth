import {fromLonLat} from 'ol/proj.js';

export function applyCamera(view, camera) {
  view.setCenter(fromLonLat(camera.center));
  // MapLibre uses a 512px world, OpenLayers uses 256px.
  view.setZoom(camera.zoom + 1);
  // MapLibre bearing is clockwise from north; OL view rotation has the opposite sign.
  view.setRotation(-(camera.bearing || 0) * Math.PI / 180);
}
