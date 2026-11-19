# X11 performance validation notes (GTK 3 + libhandy port)

## What was verified headlessly (agent-runnable, 2026-11-19)

On the dev machine (Wayland session, app driven through XWayland with
`GDK_BACKEND=x11`, render surface Xvfb):

1. The app starts and stays alive (15-20 s runs, exit code 124 from `timeout`),
   with **zero** `Gtk-WARNING` / `Handy-WARNING` / `Gtk-CRITICAL` on stderr —
   also under `G_DEBUG=fatal-warnings` (with `NO_AT_BRIDGE=1`, because the bare
   test session has no accessibility bus and AT-SPI warnings are fatal then).
2. The X11 display-sink path builds exactly the intended pipeline:

   ```
   pipewiresrc name=webcam_source target-object=… !
   videoflip name=videoflip method=horizontal-flip ! videoconvert !
   tee name=t ! queue leaky=2 ! videoscale !
   videoconvert ! gtksink name=widget_sink
   t. ! queue leaky=2 max-size-buffers=2 ! videoconvert !
   video/x-raw,format=GRAY8 ! appsink name=app_sink max_buffers=2 drop=1 leaky-type=2
   ```

3. The `GstGtkSink` element is retrieved via `pipeline.get_by_name('widget_sink')`,
   its `widget` (a plain GtkWidget) is packed into the `webcam_display` box, and
   the appsink scan branch consumes frames — i.e. the webcam was streaming
   through the Cairo-based `gtksink` with no GL context involved.

Reproduce with:

```sh
meson install -C build
G_MESSAGES_DEBUG=cyperuscoi timeout 15s env GDK_BACKEND=x11 XDG_SESSION_TYPE=x11 \
  xvfb-run -a -s "-screen 0 1280x800x24" ~/.local/bin/cyperuscoi 2>&1 | \
  grep -E "To build pipeline|Sink element|Pipeline built"
```

## What still needs the human (visible display)

- The numeric CPU/GPU comparison against the GTK4 + `gtk4paintablesink` build
  (acceptance metric of the fork). Suggested procedure:

  ```sh
  # With a webcam connected, run each build for a minute and sample:
  pidstat -p $(pgrep -f bin/cyperuscoi) 1 60   # or: top -b -d 1 -n 60 -p <pid>
  # GPU: intel_gpu_top (Intel) / nvtop (NVIDIA), while the webcam view is visible
  ```

  Compare against the `main` (GTK 4) build running the same scenario.
- Subjective checks from the Phase 6 manual matrix in
  `.agents/plans/gtk3-libhandy-x11-plan.md`: window resize across the 550 px
  breakpoint (Flap reconfiguration), webcam device switching, mirror toggle,
  result panel / bottom-sheet behavior, theme (light/dark) rendering of the
  `GtkComboBox` (risk R3) and clipboard/DnD flows (risk R4).
- Python 3.14 teardown behavior with `gtksink` (risk R5).
