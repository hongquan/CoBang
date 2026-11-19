# CyperusCoi Agent Guide

## Project Overview
- Native Linux QR/Barcode scanner written in Python with GTK 3 + libhandy, GStreamer, PipeWire, and NetworkManager (NM) integration.
- This branch (`gtk3-libhandy`) is a fork of CoBang (GTK 4 + libadwaita) ported to GTK 3 + libhandy for better performance and reliability on X11, where the GTK4 `gtk4paintablesink` GStreamer integration is problematic. Display sinks: `gtksink` (X11, Cairo drawing, no GL context) and `gtkglsink` wrapped in `glsinkbin` (Wayland).
- Fork identity: brand **CyperusCoi**, binary/short name `cyperuscoi`, app id `vn.quokka.CyperusCoi`. The gettext domain stays `cobang` so upstream translations carry over.
- Core modules live under `src/` as an installable package; UI is defined as hand-written GtkBuilder `.ui` XML files in `src/ui/` (blueprint-compiler is GTK4-only and is NOT used on this branch; there are no `.blp` files).
- Logging uses Logbook and is bridged into GLib (`src/app.py`).

## Repository Structure
- `src/`: Application package (`app.py`, `window.py`, helpers, `pages/` subpackage, `ui/` GtkBuilder XML, `cyperuscoi.gresource.xml`).
- `data/`: Desktop, AppStream, schema, icons, and service definitions (`data/meson.build` wires validation/tests), all under the `vn.quokka.CyperusCoi` name.
- `src/tests/`: Lightweight test suite targeting message parsing (no GI required).
- `po/`: gettext translations, meson integration (`po/meson.build`).
- `flatpak/`, `snap/`: Packaging manifests.
- `misc/screenshots`, `data/*x*`: assets bundled via Meson/GResource.
- `dev/`: development tools (`ui_smoke.py` non-visual UI tests, `check_ui_paths.py` consistency checks, `extraction.py` widget hierarchy).

## Tooling & Dependencies
- System packages: review `deb-packages.txt` (GTK 3, libhandy, XdpGtk3, GStreamer gtk3 plugin, PipeWire, NM, ZBar, etc.). Install quickly on Debian/Ubuntu with `xargs -a deb-packages.txt sudo apt install`.
- Python tooling: runtime libs listed in `flatpak/requirements.txt` (Pillow, Logbook, qrcode) and development stubs in `requirements-dev.txt` (PyGObject stubs).
- There is no UI compiler: edit the `.ui` GtkBuilder XML directly.
- Meson/Ninja drive the build; ensure both are present.
- Ruff linter configured via `ruff.toml` (line length 120, single quotes, `E4/E7/E9/F/B/Q/I/UP` rules).

## Build & Run Workflow
1. Setup build dir (only once or after dependency changes):
   ```sh
   meson setup build --prefix "$HOME/.local/"
   ```
2. Build and install locally:
   ```sh
   meson compile -C build
   meson install -C build
   ```
3. Launch the app from the shell:
   ```sh
   G_MESSAGES_DEBUG=cyperuscoi cyperuscoi
   ```
   This uses the wrapper generated from `src/cyperuscoi.in` (`src/meson.build`).
4. To clean/reconfigure, use `meson setup build --reconfigure` (or `--wipe` when necessary).

## Testing & Quality
- Non-visual UI smoke tests (run under a virtual display):
  ```sh
  xvfb-run -a python3 dev/ui_smoke.py
  ```
  They instantiate every template class and assert template children, stack child names, HdyFlap children, property bindings and declarative handler wiring.
- Resource/manifest consistency: `python3 dev/check_ui_paths.py`.
- Meson data validations: `meson test -C build` runs desktop/appstream/schema checks if the optional tooling is available.
- Python unit tests: the functions in `src/tests/` (message parsing; no GI required).
- Linting: `ruff check src` and `ruff format src`.
  - Files using `gi.require_version` before `from gi.repository import ...` are listed in `ruff.toml[lint.per-file-ignores]` with `E402` ignored, so no `--ignore E402` is needed.
- Headless launch check: `timeout 20s env GDK_BACKEND=x11 xvfb-run -a ~/.local/bin/cyperuscoi` — exit code 124 means the app stayed alive; there must be no `Gtk-WARNING`/`Handy-WARNING`/traceback on stderr.
- Keep in mind that UI/portal logic isn't fully covered by automated tests; manual testing with a webcam or sandbox is often required.
- Do not make constants, functions, object methods private (underscore prefix), except when being asked to do so.

## Localization Workflow
- The gettext domain is `cobang` (kept from upstream so translations carry over): `po/meson.build` calls `i18n.gettext('cobang', preset 'glib')` and the launcher calls `locale.bindtextdomain('cobang', ...)`.
- `po/POTFILES` lists the Python and `.ui` sources (`.ui` files are extracted as Glade by xgettext).
- Merge translations with `msgmerge` across `po/*.po` when strings change.

## Core Modules & Patterns
- `src/app.py`: Sets up `Gtk.Application` + `Handy.init()`, enforces GI versions, integrates portal access, registers application actions and accelerators (`win.paste-image` = Ctrl+V, registered here because GTK3 builder has no ShortcutController).
- `src/window.py`: Manages the main window (an `Hdy.ApplicationWindow` whose header bar is packed in-content — HdyApplicationWindow rejects the `titlebar` child type), derives `in-mobile-screen` from window width (threshold 550 px, replacing Adw.Breakpoint), wires all properties that used to be Blueprint `bind`s, handles sandbox detection (`ENV_EMULATE_SANDBOX`), webcam start-up, and Wi-Fi workflows via NetworkManager.
- `src/pages/scanner.py`: Builds the GStreamer pipeline (display sink chosen per display server: `videoconvert ! gtksink` on X11, `glsinkbin sink="gtkglsink"` on Wayland), packs the sink's `widget` property into `webcam_display`, interacts with PipeWire/v4l2 devices, decodes frames with `zbar`, and emits signals consumed by the window. Clipboard uses `Gtk.Clipboard.request_*` (async), file dialogs use `Gtk.FileChooserNative`, DnD uses `drag_dest_set` + `drag-data-received`.
- `src/pages/generator.py`: Orchestrates generator flow with `GeneratorPage`; QR output is a `GdkPixbuf.Pixbuf` (was `Gdk.Texture`); mobile/desktop layouts are toggled by reordering a single `GtkBox` (replacing Adw.MultiLayoutView).
- `src/pages/generator_form.py`: `GeneratorForm` collects QR content. libhandy 1.8 has no EntryRow/PasswordEntryRow/SwitchRow/ButtonRow: entries/switches are `Gtk.Entry`/`Gtk.Switch` attached to `HdyActionRow` suffixes via `GeneratorForm.add_row_suffix()`; combo rows are `HdyComboRow` + `bind_name_model(Gio.ListStore, ...)`, selected via `selected-index`.
- `src/pages/generator_qr_preview_pane.py`: `GeneratorQRPreviewPane` displays the generated QR code (scaled `Gtk.Image`) and action buttons; colors via `GtkColorButton`, error correction via `GtkComboBoxText`.
- `src/pages/generator_wifi_network_picker.py`: `Gtk.Dialog` with a `GtkTreeView` + `GtkListStore` + `GtkTreeModelFilter` (search/erroneous filtering via `visible_func` + `refilter()`); hides instead of destroying itself so it can be reused.
- `src/messages.py`: Parsing utilities for scanned content (WiFi, vCard, URL). Tests cover `parse_wifi_message` and `mecard_unescape`.
- `src/net.py`: NetworkManager helpers for Wi-Fi connection management.
- `src/prep.py`: Wraps Gio MIME detection and PIL-based preprocessing (`make_grayscale`, `invert_and_make_grayscale`).
- `src/ui.py`: Builder helpers that load subviews from embedded resources and connect signal handlers.
- `src/consts.py`: Application constants (e.g., `ENV_EMULATE_SANDBOX`, GStreamer element names).
- Custom GObject types live in `src/custom_types.py` (e.g., `WebcamDeviceInfo`).

## UI & GtkBuilder Patterns
- UI definitions are plain GTK3/libhandy GtkBuilder XML in `src/ui/`, bundled by `gnome.compile_resources` into `cyperuscoi.gresource` with `alias="gtk/..."` entries preserving the historical resource paths (`src/cyperuscoi.gresource.xml`).
- GTK templates use `@Gtk.Template.from_resource` referencing `/vn/quokka/CyperusCoi/gtk/*.ui`.
- GtkBuilder GTK3 gotchas (all verified on this stack):
  - Widgets are invisible by default: set `<property name="visible">True</property>` on everything statically visible; conditional widgets get `no-show-all` + Python-driven visibility or `bind_property`.
  - `<packing>` is a sibling of `<object>` inside `<child>` (never nested inside `<object>`).
  - Menus are `<menu id=...>` elements at interface level (an `<object class="GMenu">` is rejected).
  - Header bars pack children via `<packing><property name="pack_type">start|end</property></packing>`.
  - Cell renderers use the Glade form: `<child><object class="GtkCellRendererText"/><attributes><attribute name="text">0</attribute></attributes></child>`.
  - `GtkListStore` columns use `<columns><column type="gchararray"/></columns>`.
  - GTK3 builder has no `<binding>`/closures: all bindings are Python `bind_property`/`notify::` wiring.
- When adding new UI components:
  - Create/edit the `.ui` file in `src/ui/`.
  - Add an `<file alias="gtk/...">` entry to `src/cyperuscoi.gresource.xml`.
  - Ensure `Gtk.Template.Child()` entries line up with the XML ids.
  - Run `python3 dev/check_ui_paths.py` and `xvfb-run -a python3 dev/ui_smoke.py`.

## Packaging Artefacts
- Flatpak: `vn.quokka.CyperusCoi.yaml` orchestrates dependencies (zbar, NM, etc.). org.gnome.Platform 51 provides libportal XdpGtk3 and the GStreamer gtk3 plugin (`libgstgtk.so`); libhandy is bundled as a module.
- Snap: `snap/snapcraft.yaml` uses the Meson plugin, building against core24 with staged GTK3/libhandy/gtk3-gstreamer GIRs.
- Additional automation/config lives under `dev/` for release workflows.

## Operational Notes & Gotchas
- Hardware integration requires PipeWire/NM access; inside Flatpak the app relies on xdg-desktop-portal (see `CoBangWindow.portal` and `ScannerPage.setup_camera_for_sandbox`). Use `COBANG_LIKE_IN_SANDBOX=1` to emulate restricted environments while testing.
- Some optional validation tests need external binaries (`desktop-file-validate`, `appstreamcli`, `glib-compile-schemas`). Install them to avoid Meson disabling those checks.
- GI repositories must be installed system-wide; missing runtime libs surface as `ModuleNotFoundError` at import time. `gir1.2-xdpgtk3-1.0` is in `deb-packages.txt`.
- Translations reference `.ui` names in `po/POTFILES`; keep this file in sync when moving resources.
- The visual/screenshot QA cannot be automated on the dev machine (no observable display) — see `.agents/plans/gtk3-libhandy-x11-plan.md` Phase 6 for the manual checklist.
