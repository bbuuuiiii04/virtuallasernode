#!/bin/bash
# launchd-managed auto-resume supervisor for the final fixture-model capture run.
# Survives shell/harness reaps; resumes across Continuity Camera dropouts.
# NEVER kill -9 the Pro daemon. Always leave the rig blacked out between attempts.
cd /Users/bbui/virtuallasernode || exit 99
PORT=/dev/cu.usbserial-EN396681
PY=calib/.venv/bin/python
MASTER="captures/fixture_model/run_supervisor.log"
DONE_SENTINEL="captures/fixture_model/RUN_COMPLETE"
MAXATTEMPTS=200
MUTE_WATCHER="calib/capture_stop_mute_watcher.sh"
MUTE_WATCHER_PID=""
say(){ echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$MASTER"; }

stop_mute_watcher(){
  if [ -n "$MUTE_WATCHER_PID" ] && kill -0 "$MUTE_WATCHER_PID" 2>/dev/null; then
    kill "$MUTE_WATCHER_PID" 2>/dev/null || true
    wait "$MUTE_WATCHER_PID" 2>/dev/null || true
  fi
  osascript -e 'set volume output muted false' >/dev/null 2>&1 || true
}

start_mute_watcher(){
  if pgrep -f "capture_stop_mute_watcher.sh" >/dev/null 2>&1; then
    say "mute watcher already running"
    return
  fi
  nohup bash "$MUTE_WATCHER" >>/tmp/vln_capture_stop_mute_watcher.out 2>&1 &
  MUTE_WATCHER_PID=$!
  say "mute watcher started pid=$MUTE_WATCHER_PID"
}

cleanup(){
  stop_mute_watcher
}
trap cleanup EXIT INT TERM

camera_present(){
  # Parse AVFoundation list like the orchestrator; ignore ffmpeg's non-zero exit.
  $PY - <<'PY' >/dev/null 2>&1
import subprocess
want = "brandon Camera".lower()
cp = subprocess.run(
    ["ffmpeg", "-hide_banner", "-f", "avfoundation", "-list_devices", "true", "-i", ""],
    text=True, capture_output=True, check=False,
)
in_video = False
for line in (cp.stderr + cp.stdout).splitlines():
    if "AVFoundation video devices:" in line:
        in_video = True
        continue
    if "AVFoundation audio devices:" in line:
        break
    if not in_video or "] [" not in line or "] " not in line:
        continue
    _idx, name = line.split("] [", 1)[1].split("] ", 1)
    low = name.strip().lower()
    if low == want or want in low:
        if not low.startswith("capture screen") and "desk view" not in low:
            raise SystemExit(0)
raise SystemExit(1)
PY
}
port_free(){ ! lsof "$PORT" >/dev/null 2>&1; }
blackout(){ $PY calib/dmx_pro.py blackout --port "$PORT" --require-hardware >>"$MASTER" 2>&1; }

# If a previous successful completion is recorded, do nothing (prevents launchd relaunch loop).
if [ -f "$DONE_SENTINEL" ]; then
  say "RUN_COMPLETE sentinel present; supervisor idle (nothing to do)."
  exit 0
fi

say "supervisor start (launchd)"
start_mute_watcher

# Startup cleanup: terminate any stale orchestrator/daemon from a prior reaped session.
if pgrep -f "fixture_model_orchestrator.py" >/dev/null 2>&1; then
  say "stale orchestrator found; SIGTERM"; pkill -TERM -f "fixture_model_orchestrator.py"; sleep 6
fi
if pgrep -f "dmx_pro.py daemon" >/dev/null 2>&1; then
  say "stale daemon found; SIGTERM"; pkill -TERM -f "dmx_pro.py daemon"; sleep 4
fi
waitp=0
while ! port_free; do say "waiting for $PORT to free ($waitp s)"; sleep 5; waitp=$((waitp+5)); [ "$waitp" -ge 120 ] && break; done
blackout || say "startup blackout best-effort (port may be free)"

attempt=0
while [ "$attempt" -lt "$MAXATTEMPTS" ]; do
  attempt=$((attempt+1))
  waited=0
  while ! camera_present; do
    say "attempt $attempt: 'brandon Camera' absent; waiting ($waited s)"
    sleep 20; waited=$((waited+20))
  done
  port_free || { say "attempt $attempt: port busy; waiting"; sleep 10; continue; }
  blackout || say "attempt $attempt: pre-launch blackout best-effort"
  ts=$(date +%Y%m%d_%H%M%S); log="captures/fixture_model/final_ch1_19_${ts}.log"
  echo "$log" > /tmp/vln_run_log_path.txt
  say "attempt $attempt: launching orchestrator -> $log"
  caffeinate -dimsu $PY -u calib/fixture_model_orchestrator.py \
    --rig-confirmed --dmx-backend pro --dmx-port "$PORT" \
    --camera-name "brandon Camera" --camera-size 1280x720 \
    --resume-from 1 --max-new-captures 10000 > "$log" 2>&1
  rc=$?
  say "attempt $attempt: orchestrator exited rc=$rc"
  if [ "$rc" -eq 0 ]; then
    touch "$DONE_SENTINEL"
    say "RUN COMPLETED SUCCESSFULLY (rc=0); wrote $DONE_SENTINEL"
    blackout || true
    exit 0
  fi
  blackout || true
  say "attempt $attempt: blacked out; backoff 15s"
  sleep 15
done
say "supervisor exhausted $MAXATTEMPTS attempts; giving up (rig blacked out)"
blackout || true
exit 1
