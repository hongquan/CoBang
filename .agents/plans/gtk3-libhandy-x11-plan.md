# CoBang fork plan: GTK 3 + libhandy (X11 performance)

## Goal
Fork CoBang's UI stack from GTK 4 + libadwaita to GTK 3 + libhandy to improve performance and
reliability for X11 users, where the GTK 4 + `gtk4paintablesink` GStreamer integration is
currently problematic (GL context stalls, high CPU/GPU usage). Keep the overall app structure
(Python + PyGObject composite templates) and the scanner/generator feature set.

## Non-goals
- No changes to QR decoding logic (ZBar, qrcode, `src/prep.py`) beyond the image-object swap
  (`Gdk.Texture` → `GdkPixbuf.Pixbuf`).
- No GStreamer replacement: keep the `v4l2src`/`pipewiresrc → videoflip → videoconvert → tee →
  [display sink | appsink]` topology; only the display sink element changes.

---

## 0. Verified constraints (research findings — these correct the original plan)

These were verified against the installed stack (Ubuntu, libhandy 1.8.3, blueprint-compiler
0.19.0, GStreamer 1.28.2) and change the shape of the plan:

| # | Finding | Evidence | Consequence |
|---|---------|----------|-------------|
| 1 | **blueprint-compiler supports GTK 4 only.** `using Gtk 3.0;` fails with "Only GTK 4 is supported"; `using Handy 1;` alongside `using Gtk 4.0;` is a version conflict (Handy imports Gtk 3.0). | `/usr/lib/python3/dist-packages/blueprintcompiler/language/imports.py:40`, blueprint docs (`wrong_compiler_version`, `version_conflict`) | The original premise "keep `.blp` as the UI source" is **not achievable**. UI source becomes hand-written GtkBuilder `.ui` XML (see Decision D1). |
| 2 | **GTK 3 GtkBuilder has no `<binding>` support.** `<binding>` → "Unhandled tag" error. | runtime test | Every `bind` / `expr` closure in the current `.blp` files must be re-implemented as Python `bind_property()` / `notify::` wiring (Phase 4). This is the largest code-side work item. |
| 3 | **libhandy 1.8 has no** `EntryRow`, `PasswordEntryRow`, `SwitchRow`, `ButtonRow`, or `Dialog`. It **does have**: `ApplicationWindow`, `Window`, `HeaderBar`, `TitleBar`, `ViewSwitcher`, `ViewSwitcherTitle`, `ViewSwitcherBar`, `Leaflet`, `Deck`, `Flap`, `Squeezer`, `Clamp`, `StatusPage`, `PreferencesGroup/Page/Row/Window`, `ActionRow`, `ComboRow`, `ExpanderRow`, `SearchBar`, `Avatar`, `TabView/TabBar`. | introspection of `Handy-1` typelib | Original plan's Phase-2E mapping (`Handy.EntryRow` etc.) is invalid; use the corrected mapping in Phase 2. |
| 4 | `HdyActionRow` GtkBuilder supports child type `prefix`; `suffix` warns "'suffix' is not a valid child type". Suffix widgets must be attached via `add_suffix()` in Python. | runtime test | Form rows: declare `HdyActionRow` in XML, attach `Gtk.Entry`/`Gtk.Switch` as suffix in code. |
| 5 | `Handy.ComboRow` has **no** `model` property / `expression`. It binds data via `bind_model(model, create_list_widget_func, …)` / `bind_name_model(model, get_name_func)` and exposes `selected-index` (+ `notify::selected-index`). | introspection | Keep `Gio.ListStore` + `GeneratorChoiceItem` for combo rows; wire in Python. |
| 6 | **GTK 3 `GtkBin` is abstract** ("cannot create instance of abstract type 'GtkBin'"). Subclassing is fine; bare `<object class="GtkBin">` in XML is not. | runtime test | `Adw.Bin` inline containers → `Gtk.Box` / `Gtk.Frame`; `Adw.Bin` base classes → `Gtk.Bin` subclasses (works) or `Gtk.Box`. |
| 7 | `gtksink` / `gtkglsink` exist locally (from `gstreamer1.0-gtk3`, plugin `libgstgtk.so`, gst-plugins-good). They expose a **`widget` property (a GtkWidget)**, not a paintable. | `gst-inspect-1.0 gtksink` | `build_display_sink_desc()` and `attach_gstreamer_sink_to_window()` change shape: pack the sink widget into a container. |
| 8 | `gir1.2-xdpgtk3-1.0` exists (candidate 0.9.1) → `XdpGtk3.parent_new_gtk(window)` is a drop-in for `XdpGtk4.parent_new_gtk()`. | `apt-cache policy` | Portal parent wiring is a 2-line change. |
| 9 | GTK 3 has `Gtk.ShortcutsWindow/Section/Group/ShortcutsShortcut` (with `action-name`), `Gtk.ApplicationWindow.set_help_overlay()`, `Gtk.MenuButton.menu-model`, `Gtk.Application.set_accels_for_action()`, `Gtk.FileChooserNative`, `GtkFileFilter` `<mime-types>` XML, `Gtk.Stack` child properties via `<packing>`. | runtime tests | Shortcuts window, menus, and file filters port cleanly to GtkBuilder XML. |
| 11 | **GTK3 builder XML syntax differs from GTK4 in non-obvious ways (all verified):** menus are the `<menu>` **element** at interface level (`<object class="GMenu">` is REJECTED as "Invalid object type" in GTK3 builder); header bars (both `GtkHeaderBar` and `HdyHeaderBar`) pack start/end children via `<packing><property name="pack_type">start|end</property></packing>`, NOT via `<child type="start">` (warns "not a valid child type"); `HdyFlap` accepts both `<child type="content|flap">` and `<property name="flap">id</property>` references; cell renderers in `GtkComboBox`/`GtkTreeViewColumn` use the Glade form with `<attributes>` inside the `<child>` element: `<child><object class="GtkCellRendererText"/><attributes><attribute name="text">0</attribute></attributes></child>`. | runtime tests | All template XML in this plan must follow these canonical GTK3 forms, not the GTK4/Blueprint equivalents. |
| 10 | `Adw.AboutDialog` has no GTK3 counterpart with the same API; `Gtk.AboutDialog` uses different property names and is shown modally. `Gtk.Application` has **no** `set_version()`. | GTK3 docs | `app.py` about dialog and version plumbing need rework (Phase 3.1). |

## 1. Key decisions

**D1 — FINAL DECISION: the UI source format is plain GtkBuilder `.ui` XML. Blueprint is
dropped entirely on this fork.**
- Since blueprint-compiler supports GTK 4 only (constraint 1), each `src/ui/**/*.blp` is
  converted to a hand-written `src/ui/**/*.ui` (GtkBuilder XML for GTK 3), keeping the same
  object ids, template class names, and signal handler names so Python churn is minimal.
- No `.blp` files remain on the `gtk3-libhandy` branch; they stay only on the GTK4 `main`
  branch. No blueprint-compiler fork/patch will be attempted.
- `blueprint-compiler` may still be used **locally, once**, as a reference tool: compiling the
  current `.blp` files to GTK4 XML (see “Conversion workflow” in Phase 2) to compare structure
  while hand-porting. It is never a build dependency of this fork.

**D2 — Resource paths stay identical during the port (Phases 0–6).**
- Keep resource paths `/vn/hoabinh/quan/CoBang/gtk/…` so `Gtk.Template.from_resource(...)` calls
  are unchanged. In `cobang.gresource.xml`, point at the real files with aliases:
  `<file alias="gtk/window.ui" preprocess="xml-stripblanks">ui/window.ui</file>` etc.
- (The prefix later changes to `/vn/quokka/CyperusCoi/…` in Phase 7, in one mechanical sweep.)
- The `shortcuts-dialog.ui` alias (outside `gtk/`, "autodetected by AdwApplication") changes:
  GTK3 has no auto-detection; load it explicitly and pass it to
  `Gtk.ApplicationWindow.set_help_overlay()` (verified to exist in GTK3).

**D3 — Adaptive layout strategy: `Handy.Flap` / `Handy.Leaflet` instead of `Adw.MultiLayoutView`.**
- `Adw.MultiLayoutView` shares slot content between named layouts (a widget placed by
  `Adw.LayoutSlot` in several layouts). GTK 3 widgets have exactly one parent, so the slot model
  cannot be replicated; duplication or runtime reparenting would be needed. libhandy's
  `Handy.Flap` (content + flap + separator, `flap-position`, `reveal-flap`, `modal`,
  `fold-policy`, swipe) expresses **both** scanner arrangements — desktop side panel and mobile
  bottom sheet — with one widget tree, reconfigured from Python.
- `Adw.Breakpoint` (max-width 550sp) → drive the existing `in_mobile_screen` property from the
  window's `size-allocate` (threshold ≈ 550 px) or from `Handy.Leaflet`/`ViewSwitcherTitle`
  fold signals. Property and downstream Python callbacks stay.

**D4 — Display sink strategy.**
- X11 (the fork's focus): `videoconvert ! gtksink name=widget_sink` (Cairo drawing into a
  GtkWidget — no GL context involvement, avoiding the `glsinkbin` stall seen with
  `gtk4paintablesink` on X11).
- Wayland: `glsinkbin sink="gtkglsink name=widget_sink" name=sink_bin` (keep GL acceleration).
- Retrieval: `sink = pipeline.get_by_name(GST_SINK_NAME)` (or `sink_bin.get_property('sink')`
  under `glsinkbin`, same trick as today), then `widget = sink.get_property('widget')` and pack
  it into the `webcam_display` container.

**D5 — Combo/list widgets.**
- `Handy.ComboRow` (form rows): keep `Gio.ListStore` of `GeneratorChoiceItem`, bind via
  `bind_name_model()`, read `selected-index`.
- Inline dropdowns/combos outside preference groups (webcam chooser, error-correction):
  `Gtk.ComboBox` + `Gtk.ListStore(str, object)` + `Gtk.CellRendererText`, `changed` signal.
- WiFi picker: `Gtk.TreeView` + `Gtk.ListStore` + `Gtk.TreeModelFilter` (see Phase 2F).

**D6 — FINAL DECISION: fork identity/name = “CyperusCoi”.**
- Brand name: **CyperusCoi** (from *Cyperus*, the sedge genus that includes the mat sedge —
  “cỏ cói” — woven into chiếu mats with grid patterns like QR modules; a deliberate sibling of
  upstream CoBang, which is named after another weaving plant, Cỏ bàng).
- Short name / binary: `cyperuscoi` (lowercase, no hyphen).
- Application ID: `vn.quokka.CyperusCoi` — the **vendor namespace changes too**
  (`vn.hoabinh.quan` → `vn.quokka`), which cascades into the gresource prefix, gschema path,
  icon file names, DBus service name and Flatpak ID. The fork gets a fully independent
  identity and installs alongside upstream CoBang.
- Gettext domain stays **`cobang`** (po/cobang.pot) so all existing translations carry over —
  only new/changed strings need translation.
- README.rst: title becomes `CyperusCoi`; the “Name” section tells the CoBang → CyperusCoi
  story (“same craft, lighter weave: GTK 3 + libhandy”).
- Sequencing: keep the CoBang ids during Phases 0–5 (renaming mid-port would churn resource
  paths and template URIs while iterating); do the full rename as a dedicated, mechanical
  final phase (Phase 7) once the port is green.

---

## Phase 0: branch + dependency matrix
1. Branch `gtk3-libhandy` (already created).
2. Verify dev environment provides: `gir1.2-gtk-3.0`, `gir1.2-handy-1`, `gir1.2-xdpgtk3-1.0`,
   `gstreamer1.0-gtk3` (`gst-inspect-1.0 gtksink` must list the element), and keep
   `python3-gst-1.0`, `gir1.2-gst-plugins-base-1.0`, `gstreamer1.0-plugins-good`,
   `gir1.2-nm-1.0`, `python3-zbar`, `python3-qrcode`, `python3-pil`, `python3-logbook`,
   `librsvg2-bin`.
3. `blueprint-compiler` is no longer a build dependency; remove it from `deb-packages.txt`.
   It may stay installed locally as a one-time reference tool (D1) and for the GTK4 branch.
4. Decide Flatpak bundling needs early (risk R1): check whether `org.gnome.Platform` ships
   `libhandy-1` and a GStreamer build with the `gtk` (gtksink) plugin; if not, add modules for
   libhandy and gst-plugins-good built against GTK3.

---

## Phase 1: build system + packaging

### 1.1 `src/meson.build`
- Delete the `custom_target('blueprints', …)` block and the `blueprints` dependency.
- `gnome.compile_resources('cobang', 'cobang.gresource.xml', …)` stays; the gresource XML now
  references the real `.ui` files (with `alias=` to keep the `gtk/…` resource paths, D2).

### 1.2 `src/cobang.gresource.xml`
- Replace generated `gtk/*.ui` entries with aliases to `ui/*.ui` sources (see D2).
- Keep `img/wireframe-image-add.svg` and `style.css` entries unchanged.

### 1.3 `deb-packages.txt`
- Remove: `gir1.2-xdpgtk4-1.0`, `gstreamer1.0-gtk4`, `blueprint-compiler`.
- Add: `gir1.2-gtk-3.0`, `gir1.2-handy-1`, `gir1.2-xdpgtk3-1.0`, `gstreamer1.0-gtk3`.
- Keep everything else as-is.

### 1.4 `vn.hoabinh.quan.CoBang.yaml` (Flatpak)
- Keep finish-args (wayland + fallback-x11 sockets unchanged).
- Add/verify modules: `libhandy` (meson, `-Dintrospection=enabled`), and GStreamer gtk3 plugin
  if the runtime lacks it (see R1).

### 1.5 `snap/snapcraft.yaml`
- Drop the `gstreamer-gtk4` part (gst-plugins-rs `gst-plugin-gtk4` build) and its `after:` ref.
- Swap stage packages: `gir1.2-gtk-4.0` → `gir1.2-gtk-3.0`, add `gir1.2-handy-1`,
  `gir1.2-xdpgtk3-1.0`, `gstreamer1.0-gtk3`.

---

## Phase 2: template conversions (`.blp` → `.ui`)

### Conversion workflow (per file, in this order)
1. **Reference compile (once, optional but recommended):** dump the current GTK4 XML next to
   the blueprint for side-by-side comparison:
   `blueprint-compiler batch-compile /tmp/ref-ui src/ui src/ui/*.blp` (repeat for
   `src/ui/generator/`). This is reference material only; the GTK4 XML itself is not reusable
   (GTK4-only constructs: `<binding>`, layout properties, `Adw.*` types).
2. **Hand-port** the file to `src/ui/**/*.ui` following the mapping rules and per-file sections
   below. Preserve every object `id`, template class name, and signal handler name.
3. **Smoke-test the XML in isolation** before touching Python — a throwaway harness script:
   ```python
   import gi
   gi.require_version('Gtk', '3.0'); gi.require_version('Handy', '1')
   from gi.repository import Gtk, Handy
   Handy.init()
   builder = Gtk.Builder()
   # non-template files (wifi.ui, url.ui, shortcuts-dialog.ui):
   builder.add_from_file('src/ui/scanner/url.ui')
   ```
   - Template files (`window.ui`, pages, dialogs) need their Python class registered first —
     test them together with their module (Phase 3) via `Gtk.Template.from_file` during the
     port, then switch to `from_resource` when the gresource is wired (Phase 1).
   - Treat every `Gtk-WARNING`/`Handy-WARNING` on stderr as a bug to fix (invalid child type,
     unknown property, unhandled tag) — GTK3 aborts on hard errors like unhandled tags.
4. **Delete the `.blp` source** and its meson reference only after the `.ui` replacement passes
   its smoke test and the app builds.

Conversion rules that apply to every file:
- `using Gtk 4.0;` / `using Adw 1;` headers disappear; widget class names become GType names
  (`Gtk.Box` → `GtkBox`, `Handy.ActionRow` → `HdyActionRow`).
- Every `bind …` and `$func(...)` value becomes a plain property (default value) + Python wiring.
- GTK3 widgets are invisible by default: set `<property name="visible">True</property>` on
  widgets that must be visible at startup; for conditionally shown widgets prefer
  `no-show-all=True` + explicit `show()`/`hide()` from Python so `show_all()` on the window
  doesn't force them visible.
- Box children use `<child>…<packing><property name="expand|fill|pack-type">…` instead of
  GTK4 layout properties. `Gtk.Stack` children use `<packing>` with `name`/`title`/`icon-name`
  (verified working in GTK3 builder).
- Header bars (`GtkHeaderBar`, `HdyHeaderBar`): start/end children use
  `<packing><property name="pack_type">start|end</property></packing>`, NOT
  `<child type="start">` (verified: GTK3 builder warns "not a valid child type").
- Menus: `<menu id="…">` element at interface level with `<section>`/`<item>`/`<attribute>`
  children (verified; `<object class="GMenu">` is rejected by GTK3 builder).
- Cell renderers (`GtkComboBox`, `GtkTreeViewColumn`) use the Glade form with `<attributes>`
  inside the `<child>` element:
  `<child><object class="GtkCellRendererText"/><attributes><attribute name="text">0</attribute></attributes></child>`
  (verified; `<attributes>` elsewhere is an unhandled tag).
- `HdyFlap` accepts both `<child type="content|flap">` children and
  `<property name="flap">object_id</property>` references (both verified).
- `styles [...]` blocks → `<style><class name="…"/></style>` where the widget supports it, else
  `get_style_context().add_class()` in Python.
- Signal wiring stays declarative: `<signal name="clicked" handler="on_btn_copy_clicked"/>`;
  `@Gtk.Template.Callback()` decorators and `Gtk.Template.from_resource` work unchanged in GTK3.

### A) `src/ui/window.ui` (from `window.blp`)
- `template $CoBangWindow: Adw.ApplicationWindow` → `<template class="CoBangWindow"
  parent="HdyApplicationWindow">`. `height-request: 520` → `default-height` (+ `default-width`).
- `show => $on_shown()` keeps working (`show` signal exists in GTK3).
- `close-request => $on_close_request()` → `<signal name="delete-event"
  handler="on_close_request"/>` (Python returns `True` to stop delete; adjust `window.py`).
- `Adw.Breakpoint` → delete entirely; `in_mobile_screen` is now driven from Python (D3).
- `Adw.ToolbarView` → vertical `GtkBox` (or titlebar child type) with `HdyHeaderBar` on top.
- `Adw.HeaderBar` → `HdyHeaderBar`; `[start]`/`[end]` blueprint child annotations become
  `<packing><property name="pack_type">start</property></packing>` (verified: `<child
  type="start">` is NOT a valid child type for header bars in GTK3 builder — constraint 11).
- `Adw.ViewSwitcher job_switcher { policy: wide; stack: job_viewstack }` → `HdyViewSwitcher`
  (same `policy` + `stack` properties; `stack` must point at the `GtkStack`).
- `Adw.ViewStack job_viewstack` → `GtkStack`; `Adw.ViewStackPage` children →
  `<child><object …/><packing><property name="name">scanner</property><property
  name="title" translatable="yes">Scanner</property><property
  name="icon-name">view-reveal-symbolic</property></packing></child>`.
- `Adw.ViewSwitcherBar scan_source_switcher_bar` (in scanner page) → `HdyViewSwitcherBar`
  (`stack` + `reveal` properties exist in libhandy).
- `MenuButton { primary: true; … }` → drop `primary` (GTK4-only); `menu-model` + `icon-name`
  are supported in GTK3. Menu model → `<menu id="primary_menu">` **element** with
  `<section>`/`<item>` children (verified; `<object class="GMenu">` is rejected by the GTK3
  builder — constraint 11).
- Bindings to move to Python (window.py `__init__`, after template init):
  - `job_switcher.visible ⇔ ¬in_mobile_screen` → `bind_property('in-mobile-screen',
    job_switcher, 'visible', INVERT_BOOLEAN | SYNC_CREATE)`.
  - `job_toggler_box.visible ⇔ in_mobile_screen` → same binding, non-inverted.
  - `scanner_page.in-mobile-screen` / `generator_page.in-mobile-screen` /
    `scanner_page.is-outside-sandbox` → `bind_property` from the window properties.
  - `toggle_scanner.active ⇔ $in_scanner_mode(job_viewstack.visible-child-name)` →
    `notify::visible-child-name` handler + `toggled` handler (`switch_to_scanner`) unchanged.

### B) `src/ui/scanner-page.ui` (from `scanner-page.blp`) — largest file
- Template root: `<template class="ScannerPage" parent="GtkBin">` (subclassing `GtkBin` works;
  instantiating bare `GtkBin` does not — see constraint 6).
- `Adw.MultiLayoutView scanner_page_multilayout` (layouts `sidebar` / `bottom-sheet`, slots
  `primary`/`secondary`) → single `HdyFlap scanner_flap`:
  - `content` = old `[primary]` subtree (toolbar box),
  - `flap` = old `[secondary]` subtree (result panel box),
  - desktop mode: `flap-position=end`, `modal=false`, `fold-policy=never`-ish,
  - mobile mode: `flap-position=bottom`, `modal=true`, `swipe-to-open/close=true`,
  - `Adw.BottomSheet.open` → `reveal-flap`; `btn_show_result` sets `reveal-flap=True`;
    the `bottom-bar-height` margin binding disappears (Flap manages layout itself).
  - Python `on_in_mobile_screen_changed()` reconfigures the properties above.
- `Adw.ToolbarView toolbarview_scanner` → vertical `GtkBox` (content + `HdyViewSwitcherBar`
  at the bottom).
- `Adw.ViewStack scan_source_viewstack` → `GtkStack` (`notify::visible-child` handler kept;
  pages via `<packing>` `name`/`title`/`icon-name`).
- `Adw.MultiLayoutView webcam_multilayout` (webcam-requesting / unavailable / available) →
  `GtkStack webcam_multilayout` with three named children; every
  `self.webcam_multilayout.set_layout_name(x)` in `scanner.py` becomes
  `set_visible_child_name(x)` (`WebcamPageLayoutName` consts stay).
- `Adw.Bin status_page_webcam_requesting` → `GtkBox`.
- `Adw.StatusPage webcam_unavailable_page` → `HdyStatusPage` (title/icon-name/description —
  all supported by libhandy).
- `Picture webcam_display` → `GtkBox webcam_display` (container). The GStreamer sink widget is
  packed here at runtime (D4). The fallback `Image` visibility bind
  (`$is_empty(webcam_display.paintable)`) → replace with a Python-maintained boolean property
  (e.g. `has-webcam-frame`) toggled in attach/detach, bound to both the fallback Image and the
  Overlay's visibility.
- `Picture pasted_image` → `GtkImage pasted_image`. GTK3 `GtkImage` has no `file` property
  readable back; track the chosen `Gio.File` in a Python attribute (see Phase 3.3).
- `DropTargetAsync image_drop_target` → delete from XML; wire in Python:
  `self.frame_image.drag_dest_set(Gtk.DestDefaults.ALL,
  [Gtk.TargetEntry.new('text/uri-list', 0, 0)], Gdk.DragAction.COPY)` and connect
  `drag-data-received` (replaces `on_image_drop_target_accept` / `on_image_dropped`).
- `ShortcutController { <Control>v → win.paste-image }` → delete from XML; add
  `self.set_accels_for_action('win.paste-image', ['<Primary>v'])` in `app.py` (verified
  `set_accels_for_action` exists in GTK3).
- `DropDown webcam_dropdown` (+ `SingleSelection`, `BuilderListItemFactory`/`ListItem`) →
  `GtkComboBox webcam_dropdown` + `GtkListStore webcam_store` (columns: name `gchararray`,
  device `gpointer`/object) + `GtkCellRendererText` with the Glade `<attributes>` form
  (constraint 11); `notify::selected` → `changed` signal.
  `webcam_store` moves from XML root object to Python creation (constraint 2/5).
- `Switch mirror_switch` + `state-set` → unchanged in GTK3.
- `Frame frame_image`, `Expander raw_result_expander`, `TextView raw_result_display` → all
  exist in GTK3; drop the `vadjustment: Adjustment {}` (TextView manages its own).
- `Adw.Bin result_bin` → `GtkBox result_bin` (children added dynamically by `ui.py` code).
- Closures to move to Python (`scanner.py`): `$scanner_page_layout_name(...)`,
  `$has_some(result_display_frame.child)`, `$is_idle/$is_scanning/$is_no_result/
  $has_scanning_result(template.scanner-state)`, `$scanning_result_title(...)`,
  `$passed_image_name(pasted_image.file)`, `$vertical_in_mobile_screen(...)`,
  `$box_mirror_halign/valign(...)`, `$box_webcam_selector_halign(...)`,
  `visible: bind template.is_outside_sandbox inverted` (sandboxed-webcam label).

### C) `src/ui/generator-page.ui` (from `generator-page.blp`)
- `Adw.MultiLayoutView generator_page_multilayout` (desktop: `[preview | sep | form]`
  horizontal; mobile: `form` / `preview` vertical) → single `GtkBox generator_page_box` whose
  `orientation` and child order are toggled from Python on `in-mobile-screen` change
  (`box.set_orientation(...)` + `box.reorder_child(...)`). No slot duplication needed since the
  children (`qr_preview_widget`, `form`) are the same widgets in both layouts.
- `[preview] Adw.Bin` wrapper → `GtkBox`; `[form] $GeneratorForm form` → keep as child object.

### D) `src/ui/generator/form.ui` (from `form.blp`)
- `Adw.Clamp` → `HdyClamp` (`maximum-size`, `tightening-threshold` — same names).
- `Adw.PreferencesGroup` → `HdyPreferencesGroup` (`title`, `description` supported).
- `Adw.ComboRow content_type_row` / `wifi_auth_method_row` → `HdyComboRow`; delete the
  `SingleSelection` + `expression` blocks; the `GioListStore` roots move to Python and are
  attached with `row.bind_name_model(store, lambda item: item.label)`.
- `Adw.EntryRow text_row` / `wifi_ssid_row` → `HdyActionRow` (title/subtitle) + `GtkEntry`
  attached via `row.add_suffix(entry)` in Python; `text: bind … bidirectional` →
  `row.bind_property('text', self, 'wifi-ssid', BIDIRECTIONAL|SYNC_CREATE)` etc.
- `Adw.PasswordEntryRow wifi_password_row` → `GtkEntry` with `visibility=False`,
  `input-purpose=password`, `secondary-icon-name=dialog-password-symbolic` — the exact pattern
  already used in `src/ui/scanner/wifi.blp`.
- `Adw.SwitchRow wifi_hidden_row` → `HdyActionRow` + `GtkSwitch` suffix with
  `activatable-widget` set to the switch.
- `Adw.ButtonRow choose_saved_wifi_network_row` → `HdyActionRow` with `activatable=True` and
  `<signal name="activated" handler="on_choose_saved_wifi_network_clicked"/>`
  (`HdyActionRow::activated` exists).
- vCard placeholder `Adw.StatusPage` → `HdyStatusPage` (title/description).

### E) `src/ui/generator/qr-preview-pane.ui` (from `qr-preview-pane.blp`)
- Template root stays `GtkBox`.
- `Picture qr_preview` → `GtkImage qr_preview`; `content-fit: contain` has no GTK3 equivalent —
  wrap in `GtkAspectFrame` or scale the pixbuf before display (decide during implementation;
  start with `Gtk.Image.set_from_pixbuf` + AspectFrame).
- `ColorDialog color_dialog` / `ColorDialogButton btn_foreground/btn_background` →
  `GtkColorButton` (`rgba` property, opens its own chooser; no separate dialog object needed).
  `rgba: bind template.foreground-color bidirectional` → `bind_property('rgba', self,
  'foreground-color', BIDIRECTIONAL)` in Python.
- `DropDown row_error_correction` (+ store/expression) → `GtkComboBoxText`; populate labels in
  Python; keep a parallel list mapping active index → `ErrorCorrectionLevel`;
  `notify::selected` → `changed`; `select_error_correction_level()` uses `set_active(index)`.
- `SpinButton qr_pixel_size_row` / `qr_border_size_row` + `Adjustment` → unchanged in GTK3;
  `value: bind … bidirectional` → `bind_property('value', …)` in Python.
- `qr_placeholder` overlay box + `visible: bind template.qr-empty` → `bind_property` in Python.

### F) `src/ui/generator/wifi-network-picker-dialog.ui`
- `Adw.Dialog` → `GtkDialog` with `use-header-bar=True`; keep `wifi_network_picker_back_button`
  as a header-bar start button (`HdyHeaderBar` via titlebar child); `on_back_clicked` →
  `self.response(Gtk.ResponseType.CANCEL)` or keep a close method. `content-width/-height` →
  `default-width`/`default-height`.
- `ListView` + `SingleSelection` + `EveryFilter`/`StringFilter`/`BoolFilter` +
  `FilterListModel` + `BuilderListItemFactory` → GTK3 tree model stack:
  - `GtkListStore wifi_network_picker_list_store` with columns:
    `(ssid str, signal_icon str, erroneous bool, is_active bool, network GObject)`.
  - `GtkTreeModelFilter wifi_network_picker_filter_model` with `child-model` = the store;
    `visible_func` set in Python: keep row iff `not erroneous` and `search.lower() in
    ssid.lower()`; call `filter.refilter()` on search-entry `notify::text`.
  - `GtkTreeView` with two columns: `GtkCellRendererText` (ssid, `ellipsize=middle`) and
    `GtkCellRendererPixbuf` bound to `signal_icon` with the `visible` attribute driven by
    `is_active`/`erroneous` columns — renderers in the Glade `<attributes>` form (constraint 11).
  - selection: `treeview.get_selection()` (mode `GTK_SELECTION_SINGLE`).
- Python (`generator_wifi_network_picker.py`):
  - `populate_wifi_networks()` → `list_store.clear()` + `append((ssid, icon, err, active, obj))`.
  - `update_wifi_password()` / `set_network_error()` → iterate store rows, mutate the
    `WifiNetworkInfo` object **and** the row values, then `model.row_changed(...)` +
    `filter.refilter()` (GTK3 has no automatic item-notify redraw).
  - `on_network_activated()` → `row-activated` handler: `filter_model.get_iter(path)` →
    `get_value(iter, OBJECT_COL)` → `pick_and_close(item)`.
  - `on_search_stopped()` unchanged (`stop-search` exists in GTK3).
- `styles ['rich-list']` is a libadwaita class; drop it or restyle in `style.css`.

### G) `src/ui/shortcuts-dialog.ui`
- `Adw.ShortcutsDialog` → `GtkShortcutsWindow` with `GtkShortcutsSection` →
  `GtkShortcutsGroup` → `GtkShortcutsShortcut` (`title` + `action-name` — verified `action-name`
  exists in GTK3's ShortcutsShortcut). Verified this XML loads in GTK3 builder.
- Keep resource path `/vn/hoabinh/quan/CoBang/shortcuts-dialog.ui` (non-`gtk/` alias).
- `app.py`: `win.set_help_overlay(shortcuts_window)` + menu item action
  `win.show-help-overlay` (replaces the Adw auto-detected `app.shortcuts`).

### H) `src/ui/scanner/wifi.ui`, `src/ui/scanner/url.ui`
- `wifi.blp`: pure GTK3 already in spirit (`GtkGrid`, `GtkEntry` with `secondary-icon-name`) —
  straight XML conversion; `styles ['dimmed','dim-label','text-xs']` → `<style>` or Python.
- `url.blp`: `Adw.Bin box_url` → `GtkBox`; `GtkLinkButton` unchanged.

---

## Phase 3: Python port

### 3.1 `src/app.py`
- `gi.require_version('Gtk', '3.0')`, add `gi.require_version('Handy', '1')`; drop
  `'Adw', '1'`, `'XdpGtk4', '1.0'` → `'XdpGtk3', '1.0'`.
- `class CoBangApplication(Gtk.Application)`.
- `do_startup()`: replace `Adw.Application.do_startup(self)` with
  `Gtk.Application.do_startup(self)`; call `Handy.init()` once here (required before any
  libhandy widget is created); add `self.set_accels_for_action('win.paste-image', ['<Primary>v'])`.
- `on_about_action()`: `Adw.AboutDialog(...)` → `Gtk.AboutDialog()`. Property mapping:
  `application_name`→`program-name`, `application_icon`→`logo-icon-name`, `developers`→`authors`,
  `issue_url`→ no property (fold into `comments` or `website`), `developer_name`→ fold into
  `comments`. Show with `about.set_transient_for(win); about.set_modal(True); about.present()`
  (`Gtk.Window.present()` exists in GTK3).
- Remove `app.set_version(version)` in `main()` (GTK3 `Gtk.Application` has no `set_version`);
  keep the version for the About dialog (module constant or stash on the app object).

### 3.2 `src/window.py`
- Base class `Adw.ApplicationWindow` → `Handy.ApplicationWindow`.
- Imports: drop `Adw`; add `Handy`; `XdpGtk4` → `XdpGtk3`.
- `self.portal_parent = XdpGtk4.parent_new_gtk(self)` → `XdpGtk3.parent_new_gtk(self)`
  (same signature).
- `job_viewstack: Adw.ViewStack` → `Gtk.Stack`; `viewstack.get_visible_child_name()` call
  sites unchanged.
- `on_close_request` → delete-event handler signature `(self, window, event) -> bool`
  (return `True` to block destruction).
- Add the property bindings enumerated in Phase 2A and the `size-allocate`-based
  `in_mobile_screen` update (D3) in `__init__`.

### 3.3 `src/pages/scanner.py`
- Base class `Adw.Bin` → `Gtk.Bin`; import `Handy`, drop `Adw`.
- Template child type updates per Phase 2B (`Gtk.Stack`, `Hdy.Flap`, `Gtk.ComboBox`,
  `Gtk.ListStore`, `Gtk.Image`, `Gtk.Box` containers).
- `build_display_sink_desc()` (scanner.py:68):
  - Wayland: `glsinkbin sink="gtkglsink name=widget_sink" name=sink_bin`
  - else (X11): `videoconvert ! gtksink name=widget_sink`
  (`GST_SINK_NAME = 'widget_sink'` already matches.)
- `attach_gstreamer_sink_to_window()` (scanner.py:446): keep the `get_by_name` /
  `sink_bin.get_property('sink')` retrieval, then replace the paintable plumbing with:
  ```python
  widget = sink.get_property('widget')   # gtksink/gtkglsink expose a GtkWidget
  self.webcam_display.pack_start(widget, True, True, 0)
  widget.show_all()
  ```
  `detach_gstreamer_sink()` → remove + destroy the child widget, reset the `has-webcam-frame`
  property.
- Webcam store: `Gio.ListStore` semantics → `Gtk.ListStore`:
  - `append(WebcamDeviceInfo(...))` → `append((name, info))`
  - `get_n_items()` → `len(store)`
  - `next(iter(store), None)` → `store.get_iter_first()` / row value
  - `store.remove(pos)` → `store.remove(store.get_iter((pos,)))`
  - `webcam_dropdown.set_selected(0)` → `webcam_dropdown.set_active(0)`
- `on_webcam_device_selected()` (scanner.py:313): signal `notify::selected` → `changed`;
  `dropdown.get_selected_item()` → `model.get_value(model.get_iter(path_or_active), OBJ_COL)`.
- DnD (scanner.py:338-350): delete the `DropTargetAsync` callbacks; new
  `on_drag_data_received(widget, context, x, y, data, info, time)`: uris =
  `data.get_uris()`; `file = Gio.File.new_for_uri(uris[0])`; `Gtk.drag_finish(context, True,
  False, time)`; then `self.process_passed_image_file(file, mime)`.
- Clipboard (scanner.py:618-661): `Gdk.Display.get_clipboard()` /
  `read_texture_async` → `clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)`;
  `clipboard.request_image(cb)` (async, GDK threads) with fallback to `request_uris` /
  `request_text` for file URIs. `cb_texture_read_from_clipboard` becomes
  `cb_image_read_from_clipboard(clipboard, pixbuf)` → display + `decode_from_pixbuf`.
- File chooser (scanner.py:154, 681): `Gtk.FileDialog` → `Gtk.FileChooserNative.new(title,
  parent, Gtk.FileChooserAction.OPEN, _('_Open'), _('_Cancel'))`, `set_filter(...)`; the
  `open_finish` callback becomes a `response` handler checking `Gtk.ResponseType.ACCEPT` and
  calling `get_file()`.
- `process_passed_image_file()` (scanner.py:697): `pasted_image.set_file(file)` /
  `get_paintable()` → load a `GdkPixbuf.Pixbuf` (local: `Pixbuf.new_from_stream` on
  `file.read()` or `new_from_file` for local paths; keeps remote-URI support), store
  `self.pasted_file = file` for `passed_image_name()`, `pasted_image.set_from_pixbuf(pixbuf)`.
- `decode_from_texture()` (scanner.py:721) → `decode_from_pixbuf(pixbuf)`: derive PIL image via
  `Image.frombytes('RGBA' if pixbuf.get_has_alpha() else 'RGB', (w, h),
  pixbuf.get_pixels())` (or PNG round-trip through `pixbuf.save_to_bufferv`); the rest of the
  grayscale/invert/ZBar logic in `prep.py` is untouched.
- `set_layout_name(...)` call sites → `set_visible_child_name(...)` (webcam stack),
  `scanner_bottom_sheet.open` → `scanner_flap.set_reveal_flap(...)`,
  `on_btn_show_result_clicked` → `set_reveal_flap(True)`.

### 3.4 `src/pages/generator.py`
- Base class `Adw.Bin` → `Gtk.Bin`.
- `self.current_paintable: Gdk.Texture` → `self.current_pixbuf: GdkPixbuf.Pixbuf`.
- `Gdk.Texture.new_from_bytes(GLib.Bytes.new(buf.getvalue()))` (generator.py:157) →
  `GdkPixbuf.Pixbuf.new_from_bytes(GLib.Bytes.new(rgba_bytes), GdkPixbuf.Colorspace.RGB,
  has_alpha, 8, w, h, rowstride)` from the PIL image (no PNG detour needed).
- `qr_preview_widget.set_paintable(texture)` → `set_pixbuf(pixbuf)` (renamed method on the
  preview pane).
- Save flow (generator.py:189-229): `Gtk.FileDialog.save(...)` + `paintable.save_to_png_bytes()`
  → `Gtk.FileChooserNative` (SAVE action) + `pixbuf.savev(path, 'png', [], [])` (or keep the
  PNG `bytes` produced by `qrcode` and write them directly).
- Copy flow (generator.py:231-237): `Gdk.ContentProvider.new_for_bytes('image/png', ...)` →
  `Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_image(self.current_pixbuf)`.
- `generator_page_multilayout` callbacks → the `GtkBox` orientation/reorder logic from D3/C.

### 3.5 `src/pages/generator_form.py`
- Base class `Adw.Bin` → `Gtk.Bin`; `Adw.ComboRow` → `Handy.ComboRow`.
- Store population: keep `Gio.ListStore` of `GeneratorChoiceItem`; in `__init__` call
  `row.bind_name_model(store, lambda item: item.label)` for both combo rows.
- `on_content_type_row_selected` / `on_wifi_auth_method_row_selected`: signal
  `notify::selected` → `notify::selected-index`; `row.get_selected_item()` →
  `store[row.get_selected_index()]` (keep a Python reference to each store).
- `select_content_type()` / `select_wifi_auth_method()` → `row.set_selected_index(index)`.
- Text/password entries: after attaching suffix `Gtk.Entry` widgets (Phase 2D), wire
  `bind_property('text', self, 'text-content'|'wifi-ssid'|'wifi-password',
  BIDIRECTIONAL|SYNC_CREATE)`; `wifi_hidden_row` switch ↔ `wifi-hidden` likewise.

### 3.6 `src/pages/generator_qr_preview_pane.py`
- `qr_preview: Gtk.Picture` → `Gtk.Image`; `set_paintable()` → `set_pixbuf()` (update
  `generator.py` call sites), keep the `qr_empty` property logic.
- `row_error_correction: Gtk.DropDown` → `Gtk.ComboBoxText` (see Phase 2E).
- Color buttons + spin buttons: replace `.blp` binds with `bind_property(...)` calls in
  `__init__` (properties `foreground-color`, `background-color`, `qr-pixel-size`,
  `qr-border-size` are already GObject properties — unchanged).

### 3.7 `src/pages/generator_wifi_network_picker.py`
- Base class `Adw.Dialog` → `Gtk.Dialog`; `self.close()` still exists.
- Model/filter/selection changes per Phase 2F.
- `wifi-picked` GObject signal with `WifiNetworkInfo` arg — unchanged.

### 3.8 `src/ui.py`
- `Gtk.Builder.new_from_resource` exists in GTK3 — unchanged.
- `on_secondary_icon_pressed(entry, pos)` — GTK3 `icon-press` delivers
  `(entry, icon_pos, event)`; add the third parameter.
- `Gtk.LinkButton.set_uri/set_label` — unchanged.

### 3.9 Minor
- `dev/extraction.py`: update its namespace lists (`Adw` → `Handy`) so the dev tool keeps
  working.
- `src/tests/` (parse/serialization) don't touch GTK — unchanged.

---

## Phase 4: binding re-implementation checklist
All `bind`/`expr` constructs die with Blueprint (constraint 2). Track them per file; each needs
either `GObject.bind_property` (simple, with `INVERT_BOOLEAN`/`BIDIRECTIONAL`/`SYNC_CREATE`)
or a `notify::` handler (closures):

| Source binding (`.blp`) | Replacement |
|---|---|
| `window.blp`: switcher/toggler visibility, page `in-mobile-screen`, `is-outside-sandbox`, `toggle_scanner.active` closure | `window.py` `__init__` (Phase 2A list) |
| `window.blp`: `active: bind toggle_scanner.active inverted` (generator toggle) | `bind_property` or `toggled` handler |
| `scanner-page.blp`: all `$…` closures + visibility binds | `scanner.py`: bind `scanner-state` `notify::` → update labels; `has-webcam-frame` property; flap layout config handler |
| `generator-page.blp`: `layout-name` closure | generator.py box orientation/reorder handler |
| `form.blp`: row text/switch bidirectional binds | `generator_form.py` `bind_property` calls |
| `qr-preview-pane.blp`: color/spin/empty binds | `generator_qr_preview_pane.py` `bind_property` calls |
| `wifi-network-picker-dialog.blp`: search filter bind | `Gtk.TreeModelFilter.visible_func` + `refilter()` |

---

## Phase 5: CSS (`src/style.css`) GTK3 fixes
- `var(--accent-color)` → `@theme_selected_bg_color` (GTK3 has no CSS variables).
- `:focus-within` → `:focus` (GTK3 lacks `:focus-within`).
- `@keyframes` + `transform` → GTK3 CSS has no `transform`; replace the scanning animation with
  an `opacity` keyframe animation or a `GtkSpinner`.
- `font-size: 0.75rem` → `font-size: 75%` (GTK3 supports % / pt / px).
- `alpha(currentColor, 0.4)`, `border-radius`, `box-shadow` are fine in GTK3.
- Verify `.osd`, `.linked`, `.dim-label` exist in the GTK3 Adwaita theme (they do); `.dimmed`
  and `.rich-list` are libadwaita-only — restyle manually if still wanted.

---

## Phase 6: build + test strategy

> **Dev-machine constraint (Wayload): the desktop cannot be observed from the agent
> environment — launching the app and taking a screenshot shows nothing.** All automated
> verification on this machine must be **non-visual** (logs, exit codes, introspection);
> visual/screenshot QA is done by the human on a visible display. The steps below are written
> accordingly.

1. `deb-packages.txt` updated; `sudo apt install` the new set; confirm
   `gst-inspect-1.0 gtksink` and `python3 -c "import gi; gi.require_version('Handy','1')"`.
2. Run the per-file XML smoke tests from the Phase 2 “Conversion workflow” (every `.ui` loads
   via `Gtk.Builder` with zero warnings) before attempting a full build.
3. `meson setup build` + `meson compile -C build` — no blueprint step; failures here should only
   come from gresource paths.
4. **Headless launch test (agent-runnable, no screenshots):**
   - `timeout 20s env GDK_BACKEND=x11 meson install -C build && ~/.local/bin/cobang` — the
     app must stay alive for the full timeout (exit code 124 = no crash) with **no Python
     traceback / no `Gtk-WARNING` / `Handy-WARNING` on stderr** (logbook is piped to GLib log,
     so failures are visible in stderr/journal).
   - X11 exercise on a Wayland machine: `GDK_BACKEND=x11` routes GTK3 through **XWayland**, which
     is a real X11 server — good enough to validate the `gtksink` path; use `xvfb-run -a` if a
     fully virtual X server is preferred (check `which Xvfb`).
   - D-Bus level checks: `gapplication list-apps | grep CoBang` (or `CyperusCoi` after Phase 7),
     `gapplication launch <id>`; also `G_DEBUG=fatal-warnings` in a debug run converts lingering
     builder warnings into crashes so they can't hide.
5. **Programmatic UI assertions instead of screenshots:** a small throwaway harness (pytest-style
   or plain script) that instantiates each template class — `CoBangWindow`, `ScannerPage`,
   `GeneratorPage`, … — without `present()`ing it, then asserts:
   - every `Gtk.Template.Child` resolves to a non-None widget of the expected type,
   - `GtkStack` child names/titles/icon-names match the enum consts (`JobName`,
     `ScanSourceName`, `WebcamPageLayoutName`),
   - `HdyFlap` has both `content` and `flap` children,
   - callback wiring exists (connect a probe handler, emit the signal, assert it fired).
   This is the regression net for every template iteration while no display is observable.
6. **Manual/visual test matrix (human, on a visible display — same checklist as before):**
   - App startup; Scanner/Generator switch; window resize across the 550px mobile threshold
     (flap reconfigures: side panel ↔ bottom sheet).
   - Scanner webcam: device discovery, selection from combo, play/pause, mirror toggle
     (videoflip still applied), X11 frame rendering through `gtksink`.
   - Sandbox path (flatpak): portal camera access via `XdpGtk3` parent, `pipewiresrc` branch.
   - Image source: file chooser (native dialog), clipboard paste (image + URI), drag & drop
     (uri-list), decode of pasted/dropped image.
   - Result panel: raw text copy, WiFi connect form, URL link button.
   - Generator: text/WiFi QR generation, pixel/border/color/error-correction controls, save
     (native chooser), copy to clipboard, "New" reset.
   - WiFi picker: search filtering (substring + erroneous exclusion), row activation,
     warning icon, async password update visible after retrieval.
   - Shortcuts window via `win.show-help-overlay` (F1); About dialog; quit accelerator.
7. Performance notes on X11: compare CPU/GPU vs the GTK4 build (`top`/`intel_gpu_top`) —
   this is the acceptance metric for the fork. (Possible headlessly: launch both builds under
   `GDK_BACKEND=x11`, sample `top -b` while a webcam pipeline runs, record numbers.)

---

## Phase 7: rename to **CyperusCoi** (final, mechanical, once the port is green)

Goal (D6): the fork gets a distinct identity — brand **CyperusCoi**, short/binary name
`cyperuscoi`, app id `vn.quokka.CyperusCoi` — so it installs and runs alongside upstream
CoBang. The gettext domain stays `cobang` to keep existing translations.

Rename checklist (exact current touchpoints, verified in the repo):

1. **Python constants** — `src/consts.py`:
   `SHORT_NAME = 'cyperuscoi'`, `BRAND_NAME = 'CyperusCoi'`,
   `APP_ID = 'vn.quokka.CyperusCoi'` (feeds the About dialog icon, gschema/desktop refs).
2. **Resource prefix** — `src/cobang.gresource.xml`: prefix
   `/vn/hoabinh/quan/CoBang` → `/vn/quokka/CyperusCoi`; rename the file to
   `cyperuscoi.gresource.xml` (and the `gnome.compile_resources('cobang', …)` call in
   `src/meson.build`). Update every `Gtk.Template.from_resource` / `Builder.new_from_resource`
   string in `src/window.py`, `src/pages/*.py`, `src/ui.py`, **plus in-document resource URIs
   inside the `.ui` files** (e.g. `resource:
   '/vn/hoabinh/quan/CoBang/img/wireframe-image-add.svg'` in `scanner-page.ui`), and
   `Gio.Resource.load('cobang.gresource')` in the launcher script. D2's "resource paths stay
   identical" stops applying here — do it in one sweep, then re-run the Phase 6 smoke tests.
3. **Launcher + module** — `src/cobang.in` → `src/cyperuscoi.in`:
   - `from cobang import app` → `from cyperuscoi import app`; the installed package dir
     (`moduledir = pkgdatadir / 'cobang'` in `src/meson.build`) → `'cyperuscoi'`.
   - `locale.bindtextdomain('cobang', localedir)` stays `cobang` (D6).
   - `configure_file(input: 'cobang.in', output: 'cobang', …)` → new names (binary
     becomes `cyperuscoi`).
4. **Top-level meson** — `project('cobang', …)` → `project('cyperuscoi', …)`; this also moves
   `pkgdatadir` to `share/cyperuscoi`.
5. **`data/` files** — rename all `vn.hoabinh.quan.CoBang.*` → `vn.quokka.CyperusCoi.*`
   (desktop.in, service.in, gschema.xml, metainfo.xml.in, svg, 48x48 + 24x24 png) and update
   `data/meson.build`, `data/48x48/meson.build`, `data/24x24/meson.build`:
   - desktop: `Name=CyperusCoi`, `X-GNOME-FullName=…`, `Exec=cyperuscoi %u`,
     `Icon=vn.quokka.CyperusCoi`; `DBusActivatable=true` stays.
   - service.in: `Name=vn.quokka.CyperusCoi`,
     `Exec=@bindir@/cyperuscoi --gapplication-service`.
   - gschema: `id="vn.quokka.CyperusCoi"` and `path="/vn/quokka/CyperusCoi/"` (**keep the
     trailing slash** — `glib-compile-schemas --strict --dry-run` is already wired as a meson
     test in `data/meson.build`, so a mismatch fails the build). The `window-size` key is
     currently **unused** by the code (no `Gio.Settings` call sites), so this rename is
     zero-risk.
   - metainfo: `<id>`, `<name>`, `<summary>`, `<launchable>`; decide whether `<url>` entries
     point at the fork's repo or keep upstream's.
6. **Translation domain for merged files** — `i18n.merge_file` in `data/meson.build` uses the
   project name as gettext domain by default; after step 4 pass an explicit `domain: 'cobang'`
   (verify the kwarg on the installed Meson version, risk R6) so existing desktop/metainfo
   translations keep working, or accept re-extraction.
7. **Flatpak** — rename `vn.hoabinh.quan.CoBang.yaml` → `vn.quokka.CyperusCoi.yaml`; set
   `id:`, `command: cyperuscoi`, and the main module name.
8. **Snap** — `snap/snapcraft.yaml`: `name: cyperuscoi`, app command, summary/description.
9. **README.rst** — title `CyperusCoi`; add a fork banner ("GTK 3 + libhandy fork of CoBang,
   optimized for X11", link upstream); rewrite the `Name` section with the Cyperus/cỏ cói story;
   replace install instructions with the GTK3 dependency list from Phase 1.3; point PPA/AUR/
   COPR/funding sections at the fork's channels (or drop them until the fork has its own).
10. **Dev tooling** — `.agents/skills/cobang-release/SKILL.md` references
    `data/vn.hoabinh.quan.CoBang.metainfo.xml.in` and CoBang tag conventions; update the
    paths/names or the release workflow breaks.

Verification after rename: `meson setup build && meson install` →
`gapplication list-apps | grep -i cyperuscoi`, launch `cyperuscoi`, confirm icon, desktop
entry, DBus activation (`vn.quokka.CyperusCoi` owns the bus name — the desktop file,
service file, gschema id and `APP_ID` must all match it exactly), and that strings are still
translated (domain unchanged). Also re-check the release skill (step 10) and run
`dev/extraction.py` if it embeds ids.

---

## Risks / open questions
- **R1 — Flatpak runtime contents**: `org.gnome.Platform` may lack `libhandy` and/or the
  GStreamer `gtk` (gtksink) plugin. Verify inside the sandbox early; budget modules for
  libhandy and gst-plugins-good (GTK3 build) if missing.
- **R2 — `Handy.Flap` semantics**: confirm flap `fold-policy`/`reveal-flap` combos reproduce
  the desktop "always-visible sidebar" and mobile "bottom sheet + Show result button"
  behaviors; if the desktop sidebar needs independent resizing, fall back to `Gtk.Paned` for
  desktop mode and Flap only for mobile.
- **R3 — `Gtk.ComboBox` restyling**: GTK3 combos render differently from `Adw.DropDown`;
  visual QA on both light/dark themes.
- **R4 — Clipboard image/URI priority**: GTK3 clipboard probing (`wait_is_image_available` vs
  `wait_is_uris_available`) is synchronous; prefer the async `request_*` API to avoid UI stalls.
- **R5 — Python 3.14 teardown crash** observed with GTK4 pipelines (window.py comment): retest
  `teardown_webcam()` behavior with `gtksink` under the same interpreter.
- **R6 — `i18n.merge_file` domain**: if the installed Meson does not accept an explicit
  `domain:` kwarg for merged desktop/metainfo files, renaming the project (Phase 7.4)
  silently orphans those translations. Verify before the rename commit.
- **R7 — two installable identities**: after Phase 7 the fork must be launchable next to
  upstream CoBang (different app-id, DBus name, gresource prefix). If that coexistence is *not*
  wanted, skip Phase 7.2–7.4 app-id changes and only rebrand README/metainfo display names.
- Translations: `.ui` XML is extractable by `xgettext --language=Glade`; confirm `po/meson.build`
  (`i18n.gettext(preset 'glib')`) picks up the new files.

---

## Deliverables
- `gtk3-libhandy` branch with:
  - GtkBuilder `.ui` templates (GTK3/libhandy) replacing all `.blp` files,
  - Python port completing the mapping above (no `Adw.*` left; `Handy` used where it adds value),
  - meson/gresource/packaging updated (no blueprint-compiler; GTK3 GIR/deps),
  - GStreamer display path on `gtksink`/`gtkglsink` with X11-safe default,
  - distinct **CyperusCoi** identity (Phase 7) installable alongside upstream CoBang,
  - X11 performance validation notes.

## Files to touch
- Templates: `src/ui/window.ui`, `src/ui/scanner-page.ui`, `src/ui/generator-page.ui`,
  `src/ui/generator/form.ui`, `src/ui/generator/qr-preview-pane.ui`,
  `src/ui/generator/wifi-network-picker-dialog.ui`, `src/ui/shortcuts-dialog.ui`,
  `src/ui/scanner/wifi.ui`, `src/ui/scanner/url.ui` (converted from `.blp`; `.blp` files
  deleted on this branch)
- Python: `src/app.py`, `src/window.py`, `src/pages/scanner.py`, `src/pages/generator.py`,
  `src/pages/generator_form.py`, `src/pages/generator_qr_preview_pane.py`,
  `src/pages/generator_wifi_network_picker.py`, `src/ui.py`
- Build/packaging: `src/meson.build`, `src/cobang.gresource.xml`, `deb-packages.txt`,
  `vn.hoabinh.quan.CoBang.yaml`, `snap/snapcraft.yaml`
- Rename (Phase 7): `src/consts.py`, `src/cobang.in`, `src/cobang.gresource.xml`,
  `data/*` (desktop/service/gschema/metainfo/icons + three `meson.build`), top `meson.build`,
  Flatpak manifest, `snap/snapcraft.yaml`
- Docs/tooling: `README.rst` (retitled "CyperusCoi"), `src/style.css`, `dev/extraction.py`,
  `.agents/skills/cobang-release/SKILL.md`

## Suggested commit sequence (keeps every commit buildable)
1. Build system: meson/gresource switch + empty `.ui` stubs + packaging dep swap.
2. `window.ui` + `window.py` + `app.py` (app boots with an empty shell).
3. Generator pages (form, preview pane, picker dialog) + their Python.
4. Scanner page templates + `scanner.py` (sink, DnD, clipboard, file chooser).
5. CSS fixes, shortcuts/about polish, Flatpak/Snap verification, perf notes.
6. Phase 7 rename to **CyperusCoi** — one mechanical commit last (avoids churn while resource
   paths/template URIs are still moving during phases 1–5).
