-- Local-only bounded diagnostics. The caller supplies wall time (including held frames).
-- Snapshot construction and logging happen only on transitions or every INTERVAL_S, never every frame.
local M = { INTERVAL_S = 5, KEEP = 60 }
function M.new() return { events = {} } end
function M.update(s, kind, clock, snapshot, emit)
  if not kind and not s.kind then return end
  local changed = kind ~= s.kind
  if not changed and clock - s.lastAt < M.INTERVAL_S then return end
  local previous = s.kind
  local started = changed and kind and clock or s.started
  if not s.logWindow or clock - s.logWindow >= 1 then s.logWindow, s.logCount = clock, 0 end
  local e = s.logCount < 2 and snapshot() or { reason = 'diagnostics_rate_limited' }
  e.event = not kind and 'end' or (changed and 'start' or 'waiting')
  e.kind, e.at, e.elapsedS = kind or previous, clock, clock - (started or clock)
  s.kind, s.started, s.lastAt = kind, started, clock
  s.events[#s.events + 1] = e
  if #s.events > M.KEEP then table.remove(s.events, 1) end
  -- A broken pause/resume cycle can toggle every frame; keep lightweight transitions, cap probes and log spam.
  if s.logCount < 2 then
    e.suppressedLogs = s.suppressed
    s.logCount, s.suppressed = s.logCount + 1, nil
    emit(e)
  else
    s.suppressed = (s.suppressed or 0) + 1
  end
end
return M
