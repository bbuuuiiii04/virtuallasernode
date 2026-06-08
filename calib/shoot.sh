#!/bin/bash
# Robust headless-Chrome screenshot with watchdog + retry.
# Chrome on this box is flaky (--headless=new spawns updater/GCM services that
# hang; zombies pile up). This: kills all chrome to zero, uses OLD --headless
# with services disabled, and a per-attempt watchdog that grabs the PNG the
# moment it appears (chrome may write it then hang on exit) and force-kills.
# Usage: shoot.sh <html-path> <out.png> <W> <H>
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
HTML=$1; OUT=$2; W=$3; H=$4
rm -f "$OUT"
for attempt in 1 2 3 4; do
  pkill -9 -if chrome 2>/dev/null; sleep 2
  ud=$(mktemp -d)
  "$CHROME" --headless --disable-gpu --no-sandbox --disable-dev-shm-usage --no-first-run \
    --disable-background-networking --disable-component-update --disable-sync --mute-audio \
    --user-data-dir="$ud" --screenshot="$OUT" --window-size="$W,$H" \
    --virtual-time-budget=900 "file://$HTML" >/dev/null 2>&1 &
  cpid=$!; waited=0
  while [ $waited -lt 18 ]; do [ -s "$OUT" ] && break; sleep 1; waited=$((waited+1)); done
  kill -9 $cpid 2>/dev/null; pkill -9 -if chrome 2>/dev/null; rm -rf "$ud"
  [ -s "$OUT" ] && { echo "OK (attempt $attempt)"; exit 0; }
  echo "attempt $attempt hung, retry"
done
echo "FAILED after 4 attempts"; exit 1
