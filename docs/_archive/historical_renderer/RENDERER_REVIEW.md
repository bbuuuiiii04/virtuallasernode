Review the NEWLY IMPLEMENTED step-6 canvas renderer and its wiring in the
VirtualLaserNode package at /Users/bbui/virtuallasernode/.

Files changed/added in this scope (review these):
- static/renderer.js          (NEW — the LaserRenderer: pattern library,
                                interpolation buffer, transform pipeline, color,
                                strobe, draw, rAF loop)
- webserver.py                (NEW SnapshotProducer: builds the SSE frame once
                                per tick on one thread; /stream handlers now send
                                the shared cached frame instead of decoding per
                                client)
- static/app.js               (instantiates LaserRenderer, calls laser.update())
- static/index.html           (adds <canvas id="stage"> + renderer.js script)
- static/style.css            (#stage styling)

The SPEC is docs/RENDERER_PLAN.md — read it, especially the section
"REVISIONS FROM SUB-AGENT REVIEW (locked decisions)" which the implementation
is supposed to follow. The decoder contract is docs/FIXTURE_36CH.md and
fixtures.py (decode_fixture output is the renderer's input).

HARD CONSTRAINTS: stdlib-only Python (no pip), vanilla browser JS (no
frameworks/build step), runs as `python3 -m virtuallasernode --web` from
/Users/bbui. Coexists with SoundSwitch on UDP 6454 (don't re-flag the
multi-socket / broadcast-reply design — it's intentional and documented).

PLEASE FOCUS ON:

1. INTERPOLATION (renderer.js _sample / _loop / update): the plan requires a
   render-BEHIND buffer (render at now-DELAY, bracket by two real snapshots,
   lerp, clamp [0,1], hold on underrun) — NOT extrapolation. Verify _sample
   actually does this, including: single-frame case, underrun (renderTime newer
   than latest), reconnect/gap reset (the >1000ms drop), and that prev/next are
   matched by fixture INDEX. Any off-by-one in the bracket search.

2. TRANSFORM MATH (_transform / _pt): order must be size→zoom→waves→rotZ→
   rotX/Y(3D)→perspective→movement→position→pixels. Verify the 3D rotation +
   perspective divide is correct (no axis mix-up, the `den<=0.1` cull, NaN
   safety) and that waves are applied BEFORE rotation.

3. DIMMER/COLOR/COMPOSITING: dimmer must scale RGB (not globalAlpha) under
   'lighter'; the trail fade must be drawn in 'source-over' then switched to
   'lighter' each frame (else trails never fade). Verify the per-frame
   composite-op sequence in _loop. Check the hue LUT usage has no per-frame
   allocation churn and the perPoint dot coloring indexing is correct.

4. CONTRACT USAGE: does renderer.js read fields the decoder actually emits?
   (rotation.{z,x,y}.{mode,val}; zoom.{mode,val}; movement.{h,v}.{mode,val};
   color.{mode,rgb|null,speed:'off'|'forward'|'reverse'}; scan.mode in
   {line-bright,line,dot}; strobe.{on,speed(0-255 raw)}; position.{x,y,blanked};
   pattern.selection.{index|null,play_all}; second_pattern with its OWN nested
   position/color/rotation/etc.) Flag any field misread or missing handling
   (e.g. selection.index===null / play_all).

5. SnapshotProducer THREAD-SAFETY (webserver.py): the Condition-based
   wait_next/_run. Any missed-wakeup, busy-spin, or stale-frame bug? Is it
   correct that handlers may skip intermediate frames under load (acceptable)?
   Does the 503/semaphore path still work? Does _snapshot's `list(...)` dict
   safety still hold?

6. ROBUSTNESS: backgrounded-tab dt clamp, visibilitychange handling, canvas
   resize/DPR, devicePixelRatio clamp, the buffer size cap. Any unbounded
   growth, divide-by-zero (e.g. nextT==prevT), or NaN that reaches strokeStyle.

7. PERFORMANCE at 60fps: strokeStyle churn, per-frame allocations, the
   full-canvas trail fill cost, point counts. Call out any hot-path issue.

OUTPUT: findings grouped High/Medium/Low with file:line and a concrete fix.
Confirm where the implementation correctly follows the locked plan rather than
re-litigating settled design. Note that full visual correctness can't be
verified without a browser + a live show; focus on code-level correctness.
