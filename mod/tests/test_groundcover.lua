local dir = (arg[0]:match('^(.*)[/\\]') or '.')
local T = dofile(dir .. '/testlib.lua')
dofile(dir .. '/stubs.lua')
local gc = require('beamngEarth/groundcover')
local function fields(def)
  local result = {}
  for _, c in ipairs(gc.fieldsFor(def, 'bngEarthGroundGrass', 0.5)) do
    result[c[1] .. ':' .. c[2]] = c[3]
  end
  return result
end
local a = fields({ Types = { { layer = 'grass', probability = 1 },
  { layer = '', invertLayer = true, probability = 0.5 }, { probability = 0 } } })
for i = 0, 2 do
  T.check(a['layer:' .. i] == 'bngEarthGroundGrass', 'legacy type bound even when blank/missing ' .. i)
  T.check(a['invertLayer:' .. i] == '0', 'legacy type never excludes grass ' .. i)
end
local b = fields({ layer = { 'grass', '', 'rock' }, invertLayer = { false, true, false },
  probability = { 0.7, 0.2, 0.1 }, billboardUVs = { { 0, 0, 0.5, 1 }, { 0.5, 0, 0.5, 1 } },
  maxElements = 1000 })
for i = 0, 2 do
  T.check(b['layer:' .. i] == 'bngEarthGroundGrass', 'array type bound ' .. i)
  T.check(b['invertLayer:' .. i] == '0', 'array type never excludes grass ' .. i)
end
T.check(b['probability:1'] == '0.2', 'per-type probability not flattened into type zero')
T.check(b['billboardUVs:1'] == '0.5 0 0.5 1', 'per-type UV vector preserved')
T.check(b['maxElements:0'] == '500', 'density preserved')
T.done('test_groundcover')
