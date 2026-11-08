-- luajit mod/tests/test_dashboard.lua (vehicle vector-map camera and screen lifecycle)
local dir = (arg[0]:match('^(.*)[/\\]') or '.')
local T = dofile(dir .. '/testlib.lua')
local dashboard = require('beamngEarth/dashboard')

T.check(dashboard.zoomFor(0) == dashboard.ZOOM_CITY and dashboard.zoomFor(60) == dashboard.ZOOM_FAST,
  'the live speed selects an appropriate dashboard zoom')

-- a vehicle replaced in place keeps its id, not its screens: no more calls to the old screen afterwards
do
  local calls, encoded, redirects, routeCalls = 0, nil, 0, 0
  local veh = { queueJSUITexture = function(_, _, js)
    calls = calls + 1
    if js:find('.setRoute(', 1, true) then routeCalls = routeCalls + 1 end
    if js:find('window.location.replace', 1, true) then redirects = redirects + 1 end
  end }
  local nav = { requestVehicleDashboardMap = function() return true end }
  local saved = { scenetree = rawget(_G, 'scenetree'), be = rawget(_G, 'be'), extensions = rawget(_G, 'extensions'),
    jsonEncode = rawget(_G, 'jsonEncode') }
  scenetree = { findObjectById = function(id) return id == 7 and veh or nil end }
  be = { getPlayerVehicleID = function() return 7 end }
  jsonEncode = function(value) encoded = value; return '{}' end
  extensions = { ui_uinavi = nav, beamngEarth_core = { dashboardContext = function()
    return { active = true, connected = true, mapPort = 1, player = { lat = 39.28, lon = -76.6, speed = 0, heading = 73 } } end } }
  dashboard.onExtensionLoaded()
  dashboard.onClientStartMission()
  nav.requestVehicleDashboardMap('@scintilla_gps_screen', {}, 7)   -- (the car's navigator registers its screen)
  T.check(calls > 0, 'the screen of the player\'s car is taken over')
  local clock, t = os.clock, 1000
  os.clock = function() return t end
  dashboard.onUpdate()
  T.check(encoded.lat == 39.28 and encoded.lon == -76.6 and encoded.heading == 73,
    'dashboard receives geographic center and heading')
  T.check(encoded.zoom == dashboard.ZOOM_CITY - 1, '512px vector zoom matches the old 256px raster scale')
  dashboard.screenReady(7, '@scintilla_gps_screen')
  local redirected = redirects
  nav.requestVehicleDashboardMap('@scintilla_gps_screen', {}, 7)
  T.check(redirects == redirected + 1, 'a stock screen re-registration replaces the old acknowledged page')
  t = t + 2; dashboard.onUpdate()
  T.check(redirects == redirected + 2, 'missing screen-ready acknowledgement retries discarded navigation')
  dashboard.screenReady(7, '@scintilla_gps_screen')
  redirected = redirects
  t = t + 2; dashboard.onUpdate()
  T.check(redirects == redirected, 'an acknowledged page is not reloaded by the retry timer')
  nav.requestVehicleDashboardMap('@scintilla_gps_screen', {}, 7)
  redirected = redirects
  for _ = 1, 8 do t = t + 2; dashboard.onUpdate() end
  T.check(redirects == redirected + dashboard.TAKEOVER_ATTEMPTS - 1, 'failed takeovers have bounded retries')
  local route = {version = 5, points = {{56.84,60.6},{56.85,60.61}}}
  extensions.beamngEarth_core.dashboardRoute = function() return route end
  dashboard.screenReady(7, '@scintilla_gps_screen')
  local sent = routeCalls
  t = t + 2; dashboard.onUpdate()
  T.check(routeCalls == sent + 1 and encoded.version == 5, 'newly ready navigator receives the same GPS route')
  t = t + 2; dashboard.onUpdate()
  T.check(routeCalls == sent + 1, 'unchanged GPS route is not copied every frame')
  route = {version = 0, points = {}}
  t = t + 2; dashboard.onUpdate()
  T.check(routeCalls == sent + 2 and encoded.version == 0, 'clearing GPS clears the navigator route')
  dashboard.onVehicleReplaced(7)
  local before = calls
  os.clock = function() return t end          -- (the view goes out every VIEW_INTERVAL_S)
  for _ = 1, 5 do t = t + 1; dashboard.onUpdate() end
  os.clock = clock
  T.check(calls == before, 'replaced in place: the old screen is not called again (' .. (calls - before) .. ' calls)')
  dashboard.onClientEndMission()
  scenetree, be, extensions, jsonEncode = saved.scenetree, saved.be, saved.extensions, saved.jsonEncode
end

T.done('test_dashboard')
