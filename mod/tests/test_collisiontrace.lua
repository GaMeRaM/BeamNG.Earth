local dir = (arg[0]:match('^(.*)[/\\]') or '.')
local T = dofile(dir .. '/testlib.lua')
local trace = require('beamngEarth/collisiontrace')
local s, calls, lines = trace.new(), 0, {}
local function snapshot() calls = calls + 1; return { reason = 'server_terrain' } end
local function emit(e) lines[#lines + 1] = e end
trace.update(s, nil, 0, snapshot, emit)
T.check(calls == 0, 'no holds: no snapshot or logging work')
trace.update(s, 'edge', 1, snapshot, emit)
T.check(lines[1].event == 'start' and lines[1].kind == 'edge', 'hold start')
for i = 1, 499 do trace.update(s, 'edge', 1 + i / 100, snapshot, emit) end
T.check(calls == 1, 'held frames do not rebuild diagnostics before five seconds')
trace.update(s, 'edge', 6, snapshot, emit)
T.check(lines[2].event == 'waiting' and lines[2].elapsedS == 5, 'real time continues while physics held')
trace.update(s, nil, 8, snapshot, emit)
T.check(lines[3].event == 'end' and lines[3].elapsedS == 7, 'release records full wait')
trace.update(s, 'drop', 9, snapshot, emit)
T.check(lines[4].kind == 'drop' and lines[4].elapsedS == 0, 'next hold starts a new timer')
for i = 1, 100 do trace.update(s, i % 2 == 0 and 'edge' or nil, 9 + i / 1000, snapshot, emit) end
T.check(calls == 5, 'rapid toggles do not repeat the expensive snapshot probe')
T.check(#lines == 5 and #s.events == trace.KEEP, 'rapid toggles bounded in memory and throttled in log')
trace.update(s, 'edge', 15, snapshot, emit)
T.check(lines[#lines].suppressedLogs ~= nil, 'next emitted sample accounts for suppressed lines')
local short = trace.new()
trace.update(short, 'edge', 20, snapshot, emit)
trace.update(short, nil, 20.1, snapshot, emit)
T.check(lines[#lines].event == 'end' and lines[#lines].elapsedS > 0, 'short normal hold logs start and end')
T.done('test_collisiontrace')
