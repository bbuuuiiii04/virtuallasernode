#!/bin/bash
# Bidirectional capture stop mute watcher.
# Mutes system output when fixture_model_orchestrator.py is absent; unmutes when it returns.
# Read-only toward the capture stack: pgrep + osascript only. Does not touch DMX or camera.
LOG=/tmp/vln_capture_stop_mute_watcher.log
POLL_SEC=5
ORCH_PATTERN='fixture_model_orchestrator.py'
log() {
  echo "$(date '+%Y-%m-%dT%H:%M:%S') $*" >>"$LOG"
}

set_muted() {
  local want=$1
  if [ "$want" = 1 ]; then
    osascript -e 'set volume output muted true' >/dev/null 2>&1 || true
  else
    osascript -e 'set volume output muted false' >/dev/null 2>&1 || true
  fi
}

output_is_muted() {
  [ "$(osascript -e 'output muted of (get volume settings)' 2>/dev/null)" = "true" ]
}

orch_running() {
  pgrep -f "$ORCH_PATTERN" >/dev/null 2>&1
}

sync_mute_state() {
  if orch_running; then
    if output_is_muted; then
      set_muted 0
      log "unmuted because capture running"
    fi
  else
    if ! output_is_muted; then
      set_muted 1
      log "muted because capture exited"
    fi
  fi
}

log "watcher start pid=$$ poll=${POLL_SEC}s"
sync_mute_state

while true; do
  sync_mute_state
  sleep "$POLL_SEC"
done
