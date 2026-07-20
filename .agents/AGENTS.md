# CoBang Agent Guide

## Project Overview
- Native Linux QR/Barcode scanner written in Python with GTK4/Libadwaita, GStreamer, PipeWire, and NetworkManager (NM) integration.
- Core modules live under `src/` as an installable package; UI is defined in Blueprint `.blp` files and compiled into GTK templates.
- Logging uses Logbook and is bridged into GLib (`src/logging.py:15-41`).

## Repository Structure
- `src/`: Application package (`app.py`, `window.py`, helpers, resources, `pages/` subpackage, `ui/` blueprints, `cobang.gresource.xml`).
- `data/`: Desktop, AppStream, schema, icons, and service definitions (`data/meson.build` wires validation/tests).
- `tests/`: Lightweight pytest suite targeting message parsing (`tests/test_parse.py`).
- `po/`: gettext translations, meson integration (`po/meson.build`), and Nu scripts for extraction under `dev/`.
- `flatpak/`, `snap/`, `.ansible/`: Packaging manifests and automation targets.
- `misc/screenshots`, `data/*x*`: assets bundled via Meson/GResource.

## Tooling & Dependencies
- System packages: review `deb-packages.txt` (GTK4, GStreamer, PipeWire, NM, ZBar, etc.). Install quickly on Debian/Ubuntu with `xargs -a deb-packages.txt sudo apt install`.
- Python tooling: runtime libs listed in `flatpak/requirements.txt` (Pillow, Logbook, qrcode) and development stubs in `requirements-dev.txt` (PyGObject stubs).
- UI tooling: requires `blueprint-compiler` (used by `src/meson.build:5-26`) to turn `.blp` into `.ui` files.
- Meson/Ninja drive the build; ensure both are present.
- Nu shell is needed for translation scripts under `dev/`.
- Ruff linter configured via `ruff.toml` (line length 120, single quotes, `E4/E7/E9/F/B/Q/I/UP` rules).

## Build & Run Workflow
1. Setup build dir (only once or after dependency changes):
   ```sh
   meson setup __build --prefix "$HOME/.local/"
   ```
2. Build and install locally:
   ```sh
   just build      # or: ninja -C __build
   just install    # or: meson install -C __build
   ```
   Re-run `just install` after source edits to refresh the local install without wiping.
   If a _*.blp_ file is changed, need to do `just uninstall` before `just install`, to expire the cache of GResource.
3. Launch the app from the shell:
   ```sh
   G_MESSAGES_DEBUG=cobang cobang
   ```
   This uses the wrapper generated from `src/cobang.in` (`src/meson.build:36-43`).
4. To clean/reconfigure, use `meson setup __build --reconfigure` (or `--wipe` when necessary).

## Testing & Quality
- Meson data validations: `meson test -C __build` runs desktop/appstream/schema checks if the optional tooling is available (`data/meson.build:10-45`).
- Python unit tests: `pytest tests` (focuses on message parsing; no GI required).
- Type checking: `just type-check` runs `zuban check src/`.
- Linting: `ruff check src tests` (add `--fix` cautiously), and `ruff format src tests` if formatting is desired.
  - Files using `gi.require_version` before `from gi.repository import ...` are listed in `ruff.toml[lint.per-file-ignores]` with `E402` ignored, so no `--ignore E402` is needed.
- UI consistency: `dev/check-ui-file-paths.nu` verifies that every `@Gtk.Template.from_resource` path has a backing `.blp` source, is listed in the blueprints target and gresource manifest, and that every Blueprint callback/class is backed by Python code.
- Keep in mind that UI/portal logic isn't covered by automated tests; manual testing with a webcam or sandbox is often required.
- Do not make constants, functions, object methods private (underscore prefix), except when being asked to do so.

## Localization Workflow
- Extract strings (requires Nu + gettext): `./dev/extract-for-translating.nu` generates/updates `po/cobang.pot`.
- Merge translations: `./dev/update-translated.nu` runs `msgmerge` across `po/*.po`.
- Meson handles installing translations via `po/meson.build` and `data/meson.build` (desktop AppStream files are merged with gettext).

## Core Modules & Patterns
- `src/app.py:62-148`: Sets up `Adw.Application`, enforces GI versions, integrates portal access, and registers application actions.
- `src/window.py:60-243`: Manages the main window, handles sandbox detection (`ENV_EMULATE_SANDBOX`), webcam start-up, and Wi-Fi workflows via NetworkManager.
- `src/pages/scanner.py:79-760`: Builds the GStreamer pipeline, interacts with PipeWire/v4l2 devices, decodes frames with `zbar`, and emits signals consumed by the window.
- `src/pages/generator.py`: Orchestrates generator flow with `GeneratorPage`.
- `src/pages/generator_form.py`: `GeneratorForm` collects QR content (text/WiFi), appearance, and quality settings.
- `src/pages/generator_qr_preview_pane.py`: `GeneratorQRPreviewPane` displays the generated QR code and action buttons.
- `src/pages/old_generator*.py`: Legacy generator pages (to be removed).
- `src/messages.py`: Parsing utilities for scanned content (WiFi, vCard, URL). Tests cover `parse_wifi_message` and `mecard_unescape` (`tests/test_parse.py`).
- `src/net.py`: NetworkManager helpers for Wi-Fi connection management.
- `src/prep.py`: Wraps Gio MIME detection and PIL-based preprocessing (`make_grayscale`, `invert_and_make_grayscale`).
- `src/ui.py`: Builder helpers that load subviews from embedded resources and connect signal handlers.
- `src/consts.py`: Application constants (e.g., `ENV_EMULATE_SANDBOX`).
- Custom GObject types live in `src/custom_types.py` (e.g., `WebcamDeviceInfo`).
- Indentation across `src/pages/` is consistent (4 spaces); match the existing style when editing.

## UI & Blueprint Patterns
- UI definitions originate from Blueprint files in `src/ui/`. Meson custom target `blueprints` compiles them before `gnome.compile_resources` embeds them into `cobang.gresource` (`src/meson.build:5-26`).
- GTK templates use `@Gtk.Template.from_resource` referencing `/vn/hoabinh/quan/CoBang/gtk/*.ui` as defined in `src/cobang.gresource.xml:3-15`.
- Blueprint files live in `src/ui/generator/` (`generator-page.blp`, `form.blp`, `qr-preview-pane.blp`) and `src/ui/scanner/`.
- When adding new UI components:
  - Create/edit `.blp` in `src/ui/` subdirectories.
  - Append filenames to the `blueprints` custom target and gresource manifest.
  - Ensure `Gtk.Template.Child()` entries line up with blueprint IDs.
  - Run `dev/check-ui-file-paths.nu` to verify resource paths, blueprints/gresource registration, and Python backing for callbacks/classes.

## Packaging Artefacts
- Flatpak: `vn.hoabinh.quan.CoBang.yaml` orchestrates dependencies (zbar, libportal, NM, etc.) and consumes `flatpak/generated-sources.yml` for Python wheels.
- Snap: `snap/snapcraft.yaml` uses the Meson plugin, building against core24 with a staged `gst-plugin-gtk4`.
- Additional automation/config lives under `dev/` for release workflows.

## Operational Notes & Gotchas
- Hardware integration requires PipeWire/NM access; inside Flatpak the app relies on xdg-desktop-portal (see `CoBangWindow.portal` and `ScannerPage.setup_camera_for_sandbox`). Use `COBANG_LIKE_IN_SANDBOX=1` to emulate restricted environments while testing.
- Some optional validation tests need external binaries (`desktop-file-validate`, `appstreamcli`, `glib-compile-schemas`). Install them to avoid Meson disabling those checks.
- GI repositories must be installed system-wide; missing runtime libs surface as `ModuleNotFoundError` at import time.
- Translations reference `.ui` names in `po/POTFILES`; keep this file in sync when moving resources.
