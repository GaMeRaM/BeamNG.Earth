import {test} from 'node:test';
import assert from 'node:assert/strict';
import View from 'ol/View.js';
import {compose, create, apply} from 'ol/transform.js';
import {applyCamera} from './camera.mjs';

// Use the actual OL coordinate-to-pixel transform, as MapRenderer does.
// A point ahead of the car must stay up, and a point to its right must stay right.
for (const bearing of [0, 30, 90, 135, 180, 225, 270, 330, -90, 360]) {
  test(`heading-up camera at ${bearing} degrees`, () => {
    const view = new View({constrainRotation: false});
    applyCamera(view, {center: [60.6, 56.84], zoom: 15, bearing});
    const {center, resolution, rotation} = view.getState();
    const matrix = compose(create(), 200, 100, 1 / resolution, -1 / resolution,
      -rotation, -center[0], -center[1]);
    const h = bearing * Math.PI / 180;
    const ahead = apply(matrix, [center[0] + 100 * Math.sin(h), center[1] + 100 * Math.cos(h)]);
    const right = apply(matrix, [center[0] + 100 * Math.cos(h), center[1] - 100 * Math.sin(h)]);
    assert.ok(Math.abs(ahead[0] - 200) < 1e-6, 'forward point stays on the car axis');
    assert.ok(ahead[1] < 100, 'forward point is above the car');
    assert.ok(right[0] > 200, 'right point remains on the right');
    assert.ok(Math.abs(right[1] - 100) < 1e-6);
    assert.equal(view.getZoom(), 16, 'vector/raster scale is preserved');
  });
}
