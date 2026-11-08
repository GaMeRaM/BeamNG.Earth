-- MapLibre vector map on the vehicle's own BeamNavigator WebView while BeamNG.Earth is active.
-- BeamNavigator calls ui_uinavi.requestVehicleDashboardMap with the screen's actual material tag;
-- that is the supported registration point, so this works without per-vehicle JBeam mappings.
local M = {}

M.DASHBOARD_URI = 'local://local/vehicles/common/beamng_earth_dashboard.html'
M.ZOOM_CITY, M.ZOOM_ROAD, M.ZOOM_HIGHWAY = 17, 16, 15
M.ZOOM_FAST = 14
M.VIEW_INTERVAL_S = 0.1
M.RESTORE_RELOAD_S = 0.5
M.TAKEOVER_RETRY_S = 1.5
M.TAKEOVER_ATTEMPTS = 3

local enabled = true
local active = false
local screens = {}             -- vehicle id + WebView/material tag -> stock registration and current page state
local navExtension, stockRequest, wrappedRequest
local lastViewAt = 0
local currentVehicle = nil

local function extension(name)
  local all = rawget(_G, 'extensions')
  return type(all) == 'table' and all[name] or rawget(_G, name)
end

local function settingsExtension()
  return extension('beamngEarth_settings')
end

local function coreContext()
  local core = extension('beamngEarth_core')
  if not core or type(core.dashboardContext) ~= 'function' then return nil end
  local ok, ctx = pcall(core.dashboardContext)
  return ok and type(ctx) == 'table' and ctx or nil
end

local function readSetting()
  local settings = settingsExtension()
  if settings and type(settings.get) == 'function' then
    local value = settings.get('dashboardSatellite')
    if value ~= nil then enabled = value == true end
  end
end

local function playerVehicleId()
  local beObj = rawget(_G, 'be')
  if not beObj or type(beObj.getPlayerVehicleID) ~= 'function' then return nil end
  local ok, id = pcall(beObj.getPlayerVehicleID, beObj, 0)
  return ok and tonumber(id) or nil
end

local function vehicleFor(id)
  if not id then return nil end
  local tree = rawget(_G, 'scenetree')
  if not tree or type(tree.findObjectById) ~= 'function' then return nil end
  local ok, obj = pcall(tree.findObjectById, id)
  return ok and obj or nil
end

local function screenKey(id, tag)
  return tostring(id) .. '\0' .. tag
end

local function forVehicle(id, fn)
  if id == nil then return end
  local prefix = tostring(id) .. '\0'
  for key, rec in pairs(screens) do
    if key:sub(1, #prefix) == prefix then fn(rec) end
  end
end

local function shouldDisplay(ctx)
  return enabled and ctx ~= nil and ctx.active == true
end

local function dashboardCall(rec, method, data)
  local target = vehicleFor(rec.vehicleId)
  if not target or type(target.queueJSUITexture) ~= 'function' then return false end
  local js = 'window.beamngEarthDashboard&&window.beamngEarthDashboard.' .. method .. '(' .. jsonEncode(data) .. ')'
  target:queueJSUITexture(rec.tag, js)
  return true
end

local function restoreScreen(rec)
  if not rec.applied or rec.restoring then return end
  local target = vehicleFor(rec.vehicleId)
  if not target or type(target.queueJSUITexture) ~= 'function' then
    rec.applied, rec.restoring = false, false
    return
  end
  target:queueJSUITexture(rec.tag, 'window.beamngEarthDashboard&&window.beamngEarthDashboard.restore()')
  rec.applied, rec.restoring = false, true
  rec.restoreAt = os.clock() + M.RESTORE_RELOAD_S
end

local function processRestores(now)
  local restored = false
  for key, rec in pairs(screens) do
    if rec.restoring and now >= rec.restoreAt then
      local target = vehicleFor(rec.vehicleId)
      if target and rec.stockRequest then
        rec.stockRequest(rec.tag, rec.initmap, rec.vehicleId)
      end
      rec.restoring, rec.restoreAt = false, nil
      if not target then screens[key] = nil else restored = true end
    elseif not vehicleFor(rec.vehicleId) then
      screens[key] = nil
    end
  end
  return restored
end

local function applyScreen(rec)
  if rec.applied or rec.restoring then return end
  if rec.vehicleId ~= playerVehicleId() then return end
  local target = vehicleFor(rec.vehicleId)
  if not target or type(target.queueJSUITexture) ~= 'function' then return end
  local prefix = M.DASHBOARD_URI .. '?vehicle=' .. rec.vehicleId .. '&screen='
  target:queueJSUITexture(rec.tag, 'window.location.replace(' .. jsonEncode(prefix)
    .. '+encodeURIComponent(' .. jsonEncode(rec.tag) .. ')+"&return="+encodeURIComponent(window.location.href))')
  rec.applied, rec.ready = true, false
  rec.takeoverAttempts = (rec.takeoverAttempts or 0) + 1
  rec.retryAt = os.clock() + M.TAKEOVER_RETRY_S
  lastViewAt = 0
end

local function activateScreens()
  if not active then return end
  local id = playerVehicleId()
  currentVehicle = id
  forVehicle(id, applyScreen)
end

local function restoreScreens(id)
  if id ~= nil then
    forVehicle(id, restoreScreen)
    return
  end
  for _, rec in pairs(screens) do restoreScreen(rec) end
end

local function registerScreen(tag, initmap, vehId, callback)
  if type(tag) ~= 'string' or tag == '' then return end
  local id = tonumber(vehId) or playerVehicleId()
  if not id then return end
  local key = screenKey(id, tag)
  local rec = screens[key]
  if not rec then
    rec = { vehicleId = id, tag = tag }
    screens[key] = rec
  end
  rec.initmap, rec.stockRequest = initmap, callback
  -- The stock request may recreate the WebView even for an already registered tag.
  -- Its old acknowledgement must not suppress taking over the new page.
  rec.applied, rec.ready, rec.restoring = false, false, false
  rec.takeoverAttempts, rec.routeVersion = 0, nil
  if active and enabled and id == playerVehicleId() then applyScreen(rec) end
end

local function installNavigationHook()
  local all = rawget(_G, 'extensions')
  local nav = type(all) == 'table' and all.ui_uinavi or nil
  local request = nav and nav.requestVehicleDashboardMap
  if type(request) ~= 'function' then return end
  if nav == navExtension and request == wrappedRequest then return end
  navExtension, stockRequest = nav, request
  wrappedRequest = function(tag, initmap, vehId)
    local result = request(tag, initmap, vehId)
    registerScreen(tag, initmap, vehId, request)
    return result
  end
  nav.requestVehicleDashboardMap = wrappedRequest
end

local function zoomFor(speed)
  speed = tonumber(speed) or 0
  if speed >= 60 then return M.ZOOM_FAST end
  if speed >= 35 then return M.ZOOM_HIGHWAY end
  if speed >= 15 then return M.ZOOM_ROAD end
  return M.ZOOM_CITY
end
M.zoomFor = zoomFor

local function sendView(ctx, player, status, now)
  if now - lastViewAt < M.VIEW_INTERVAL_S then return end
  lastViewAt = now
  local view = { status = status or '' }
  if player then
    view.lat, view.lon = player.lat, player.lon
    -- MapLibre's world is 512 px wide at z0; the old raster world was 256 px.
    view.zoom = zoomFor(player.speed) - 1
    view.heading = tonumber(player.heading) or 0
  end
  for _, rec in pairs(screens) do
    if rec.applied and rec.vehicleId == currentVehicle then
      dashboardCall(rec, 'setView', view)
    end
  end
end

-- Each dashboard page has unique request ids; stale responses are ignored in JavaScript.
function M.onResource(msg)
  for _, rec in pairs(screens) do
    if rec.applied and rec.vehicleId == currentVehicle then dashboardCall(rec, 'resourceData', msg) end
  end
end

local function updateDashboard(now, ctx)
  local id = playerVehicleId()
  if id ~= currentVehicle then
    if currentVehicle then restoreScreens(currentVehicle) end
    currentVehicle = id
    forVehicle(id, applyScreen)
  end

  local player = ctx.player
  if not player or type(player.lat) ~= 'number' or type(player.lon) ~= 'number' then
    sendView(ctx, nil, 'Waiting for vehicle position', now)
    return
  end
  if not ctx.connected then
    sendView(ctx, nil, 'Waiting for the Earth server', now)
    return
  end
  sendView(ctx, player, '', now)
  local core = extension('beamngEarth_core')
  local route = core and core.dashboardRoute and core.dashboardRoute() or { version = 0, points = {} }
  for _, rec in pairs(screens) do
    if rec.applied and rec.ready and rec.vehicleId == id and rec.routeVersion ~= route.version then
      dashboardCall(rec, 'setRoute', route)
      rec.routeVersion = route.version
    end
  end
end

-- Navigation discards calls queued for the old page. Send the view again once the new page is ready.
function M.screenReady(vehicleId, tag)
  local id = tonumber(vehicleId)
  if not id or type(tag) ~= 'string' then return false end
  local rec = screens[screenKey(id, tag)]
  if not rec then return false end
  rec.applied, rec.restoring, rec.ready = true, false, true
  if not active or not enabled or id ~= playerVehicleId() then
    restoreScreen(rec)
    return false
  end
  lastViewAt = 0
  rec.routeVersion = nil
  return true
end

function M.setEnabled(on)
  enabled = on == true
  if not enabled then
    active = false
    restoreScreens()
  else
    local ctx = coreContext()
    active = shouldDisplay(ctx)
    if active then activateScreens() end
  end
  return enabled
end

local ctxAt, ctxCached = -1e9, nil
function M.onUpdate()
  installNavigationHook()
  -- (no navigation screen registered, as in most cars: nothing to do, not even the context; else the context at most
  -- every VIEW_INTERVAL_S: it copies the credits and builds the attribution text)
  if not next(screens) then return end
  local now = os.clock()
  local restored = processRestores(now)
  if now - ctxAt >= M.VIEW_INTERVAL_S then ctxAt, ctxCached = now, coreContext() end
  local ctx = ctxCached
  local show = shouldDisplay(ctx)
  if show ~= active then
    active = show
    if active then activateScreens() else restoreScreens() end
    lastViewAt = 0
  elseif active and restored then
    activateScreens()
  end
  if not active then
    return
  end
  for _, rec in pairs(screens) do
    if rec.applied and not rec.ready and not rec.restoring and rec.vehicleId == playerVehicleId()
      and now >= (rec.retryAt or 0) and (rec.takeoverAttempts or 0) < M.TAKEOVER_ATTEMPTS then
      -- Navigation queued before the UI texture existed can be discarded by the engine.
      rec.applied = false
      applyScreen(rec)
    end
  end
  updateDashboard(now, ctx)
end

function M.onClientStartMission()
  readSetting()
  local ctx = coreContext()
  active = shouldDisplay(ctx)
  if active then activateScreens() end
end

function M.onClientEndMission()
  active = false
  restoreScreens()
  currentVehicle = nil
  lastViewAt = 0
end

function M.onVehicleSwitched(oldId, newId)
  oldId, newId = tonumber(oldId), tonumber(newId)
  if oldId and oldId ~= newId then restoreScreens(oldId) end
  currentVehicle = newId
  if active and enabled and newId then forVehicle(newId, applyScreen) end
end

-- A vehicle replaced in place (the vehicle selector, core_vehicles.replaceVehicle) keeps its id but not its screens:
-- calls to the old car's screen tag then failed every frame ("UI texture '@scintilla_gps_screen' not found", ~5,000
-- log lines in a test session that swapped the car for a prop, 2026-11-03). Its records go, without a restore (the
-- screen is gone); a new vehicle's navigator registers its own (requestVehicleDashboardMap).
local function dropScreens(id)
  id = tonumber(id)
  if id == nil then return end
  local prefix = tostring(id) .. '\0'
  for key in pairs(screens) do
    if key:sub(1, #prefix) == prefix then screens[key] = nil end
  end
end
M.onVehicleReplaced = dropScreens
M.onVehicleDestroyed = dropScreens

function M.onExtensionLoaded()
  readSetting()
  installNavigationHook()
end

function M.onExtensionUnloaded()
  restoreScreens()
  if navExtension and navExtension.requestVehicleDashboardMap == wrappedRequest then
    navExtension.requestVehicleDashboardMap = stockRequest
  end
end

readSetting()
return M
