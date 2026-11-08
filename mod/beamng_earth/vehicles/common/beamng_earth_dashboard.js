(function () {
  'use strict';
  const status = document.getElementById('status');
  document.getElementById('credits').textContent = EarthVector.CREDIT;
  let map = null;
  let lastView = null, lastRoute = null, mapError = '';
  function setRoute(route) {
    lastRoute = route;
    if (map) EarthVector.setRoute(map, route);
  }
  function setView(view) {
    lastView = view;
    status.textContent = view.status || mapError;
    if (!map || !Number.isFinite(view.lat) || !Number.isFinite(view.lon)) return;
    map.jumpTo({ center: [view.lon, view.lat], zoom: view.zoom, bearing: view.heading || 0 });
  }
  function restore() {
    const original = new URLSearchParams(window.location.search).get('return');
    if (original && /^local:\/\//i.test(original)) window.location.replace(original);
  }
  window.map = { setData: function () {}, updateData: function () {}, setBootscreenImage: function () {} };
  window.beamngEarthDashboard = { setView, setRoute, restore, resourceData: EarthVector.resourceData };
  try {
    map = EarthVector.createMap('map', message => { mapError = 'Map: ' + message; status.textContent = mapError; });
    map.on('idle', () => { mapError = ''; if (lastView) status.textContent = lastView.status || ''; });
    map.on('load', () => { if (lastView) setView(lastView); setRoute(lastRoute); });
  } catch (error) { status.textContent = 'MapLibre unavailable: ' + error.message; }
  window.addEventListener('resize', () => { if (map) map.resize(); });
  window.addEventListener('pagehide', () => { if (map) map.remove(); EarthVector.dispose(); });
  const params = new URLSearchParams(window.location.search);
  const vehicleId = Number(params.get('vehicle'));
  const screen = params.get('screen');
  if (Number.isInteger(vehicleId) && screen && window.beamng && beamng.sendEngineLua) {
    beamng.sendEngineLua('if beamngEarth_dashboard then beamngEarth_dashboard.screenReady('
      + vehicleId + ',' + JSON.stringify(screen) + ') end');
  }
}());
