#!/usr/bin/env python3
"""Non-visual smoke tests for the GTK3 + libhandy UI templates.

Loads every .ui file via Gtk.Builder (non-template ones directly, template
ones through their Python classes), and asserts that:
- every Gtk.Template.Child resolves to a widget of the expected type,
- GtkStack child names match the enum constants,
- the HdyFlap has both content and flap children,
- declarative signal handlers exist on the classes.

Run under a virtual display, e.g.:
    xvfb-run -a python3 dev/ui_smoke.py [path/to/cyperuscoi.gresource]

If a compiled gresource bundle path is given (or build/src/cyperuscoi.gresource
exists), it is registered so the template classes can be imported without
installing the app first.
"""

from __future__ import annotations

import sys
from pathlib import Path

import gi


gi.require_version('Gtk', '3.0')
gi.require_version('Handy', '1')

from gi.repository import Gio, Gtk, Handy


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.consts import JobName, ScanSourceName, WebcamPageLayoutName


WARNINGS: list[str] = []


def check(condition: bool, message: str):
    if condition:
        print(f'  ok: {message}')
    else:
        WARNINGS.append(message)
        print(f'  FAIL: {message}')


def load_resource(bundle_path: str | None):
    path = bundle_path or Path(__file__).resolve().parent.parent / 'build' / 'src' / 'cyperuscoi.gresource'
    if not path.exists():
        print(f'No gresource bundle at {path}; template classes cannot be imported.')
        raise SystemExit(1)
    resource = Gio.Resource.load(str(path))
    resource._register()
    print(f'Registered gresource: {path}')


def load_plain_ui_files(src_dir: Path):
    print('== Non-template UI files ==')
    for rel in ('scanner/wifi.ui', 'scanner/url.ui', 'shortcuts-dialog.ui'):
        builder = Gtk.Builder()
        builder.add_from_file(str(src_dir / 'ui' / rel))
        objects = builder.get_objects()
        check(bool(objects), f'{rel} loads ({len(objects)} objects)')


def check_signal_handlers(cls: type, template_xml: str):
    """Verify every <signal handler="..."> in the template XML has a matching method."""
    import re

    for handler in sorted(set(re.findall(r'handler="([^"]+)"', template_xml))):
        check(hasattr(cls, handler), f'{cls.__name__} has handler {handler}')


def check_template_children(instance, expected: dict[str, type], cls_name: str):
    for name, expected_type in expected.items():
        widget = getattr(instance, name, None)
        ok = isinstance(widget, expected_type)
        check(ok, f'{cls_name}.{name} is {expected_type.__name__}')


def main():
    Handy.init()
    check(Gtk.init_check(), 'GTK initialized')

    project_root = Path(__file__).resolve().parent.parent
    src_dir = project_root / 'src'

    bundle = sys.argv[1] if len(sys.argv) > 1 else None
    load_resource(bundle)

    load_plain_ui_files(src_dir)

    # Import after resource registration, so @Gtk.Template.from_resource works.
    from src.pages.generator import GeneratorPage
    from src.pages.generator_form import GeneratorForm
    from src.pages.generator_qr_preview_pane import GeneratorQRPreviewPane
    from src.pages.generator_wifi_network_picker import GeneratorWifiNetworkPickerDialog
    from src.pages.scanner import ScannerPage
    from src.window import CoBangWindow

    print('== ScannerPage ==')
    scanner = ScannerPage()
    check_template_children(
        scanner,
        {
            'webcam_store': Gtk.ListStore,
            'file_filter': Gtk.FileFilter,
            'scanner_flap': Handy.Flap,
            'scan_source_viewstack': Gtk.Stack,
            'webcam_multilayout': Gtk.Stack,
            'webcam_display': Gtk.Box,
            'box_playpause': Gtk.Box,
            'btn_play': Gtk.ToggleButton,
            'btn_pause': Gtk.ToggleButton,
            'mirror_switch': Gtk.Switch,
            'frame_image': Gtk.Frame,
            'pasted_image': Gtk.Image,
            'btn_filechooser': Gtk.Button,
            'label_chosen_file': Gtk.Label,
            'result_display_frame': Gtk.Frame,
            'result_bin': Gtk.Box,
            'raw_result_display': Gtk.TextView,
            'raw_result_expander': Gtk.Expander,
            'webcam_dropdown': Gtk.ComboBox,
            'btn_show_result': Gtk.Button,
        },
        'ScannerPage',
    )
    check(
        scanner.scanner_flap.get_content() is not None,
        'HdyFlap has content child',
    )
    check(
        scanner.scanner_flap.get_flap() is not None,
        'HdyFlap has flap child',
    )
    check(
        [c for c in scanner.scan_source_viewstack.get_children()] and True,
        'scan_source_viewstack has children',
    )
    for name in (ScanSourceName.WEBCAM, ScanSourceName.IMAGE):
        child = scanner.scan_source_viewstack.get_child_by_name(name)
        check(child is not None, f'scan_source_viewstack has child "{name}"')
    for name in (
        WebcamPageLayoutName.REQUESTING,
        WebcamPageLayoutName.AVAILABLE,
        WebcamPageLayoutName.UNAVAILABLE,
    ):
        child = scanner.webcam_multilayout.get_child_by_name(name)
        check(child is not None, f'webcam_multilayout has child "{name}"')
    check(scanner.webcam_store.get_n_columns() == 2, 'webcam_store has 2 columns')
    # Signal wiring probe: scanner state change updates the state labels.
    scanner.scanner_state = 5  # TEXT_FOUND
    check(
        scanner.label_result_title.get_visible() and scanner.result_bin.get_visible(),
        'scanner_state -> result labels visible',
    )
    check(not scanner.label_idle.get_visible(), 'scanner_state -> idle label hidden')
    scanner.scanner_state = 0
    check(scanner.label_idle.get_visible(), 'scanner_state -> idle label visible')
    # Webcam frame property probe.
    check(scanner.image_webcam_placeholder.get_visible(), 'no webcam frame -> placeholder visible')
    scanner.has_webcam_frame = True
    check(scanner.webcam_overlay.get_visible(), 'webcam frame -> overlay visible')
    check(not scanner.image_webcam_placeholder.get_visible(), 'webcam frame -> placeholder hidden')
    scanner.has_webcam_frame = False
    # Mobile layout reconfiguration probe.
    scanner.scanner_state = 5  # TEXT_FOUND
    scanner.in_mobile_screen = True
    check(
        scanner.scanner_flap.get_orientation() == Gtk.Orientation.VERTICAL,
        'mobile -> flap vertical',
    )
    check(scanner.btn_show_result.get_visible(), 'mobile + result -> show-result button visible')
    scanner.in_mobile_screen = False
    check(
        scanner.scanner_flap.get_orientation() == Gtk.Orientation.HORIZONTAL,
        'desktop -> flap horizontal',
    )
    check(not scanner.btn_show_result.get_visible(), 'desktop -> show-result button hidden')

    print('== GeneratorQRPreviewPane ==')
    pane = GeneratorQRPreviewPane()
    check_template_children(
        pane,
        {
            'qr_preview': Gtk.Image,
            'qr_placeholder': Gtk.Box,
            'qr_pixel_size_row': Gtk.SpinButton,
            'qr_border_size_row': Gtk.SpinButton,
            'btn_foreground': Gtk.ColorButton,
            'btn_background': Gtk.ColorButton,
            'row_error_correction': Gtk.ComboBoxText,
        },
        'GeneratorQRPreviewPane',
    )
    check(pane.row_error_correction.get_model() is not None, 'error-correction combo has model')
    check(
        pane.row_error_correction.get_active() == 0,
        'error-correction synced to default level',
    )
    check(pane.qr_placeholder.get_visible(), 'qr-empty -> placeholder visible')
    check(
        abs(pane.qr_pixel_size_row.get_value() - pane.qr_pixel_size) < 1e-6,
        'pixel size spin bound to property',
    )
    pane.set_pixbuf(None)
    check(pane.qr_empty, 'set_pixbuf(None) -> qr-empty')

    print('== GeneratorForm ==')
    form = GeneratorForm()
    check_template_children(
        form,
        {
            'content_type_row': Handy.ComboRow,
            'wifi_auth_method_row': Handy.ComboRow,
            'text_row': Handy.ActionRow,
            'wifi_ssid_row': Handy.ActionRow,
            'wifi_password_row': Handy.ActionRow,
            'wifi_hidden_row': Handy.ActionRow,
            'choose_saved_wifi_network_row': Handy.ActionRow,
            'group_text': Handy.PreferencesGroup,
            'group_wifi': Handy.PreferencesGroup,
            'group_vcard': Handy.PreferencesGroup,
        },
        'GeneratorForm',
    )
    check(form.content_type_row.get_selected_index() == 0, 'content type combo bound and selected')
    check(form.group_text.get_visible(), 'text group visible for default type')
    check(not form.group_wifi.get_visible(), 'wifi group hidden for default type')
    changed_fired = []
    form.content_changed.connect(lambda *a: changed_fired.append(True))
    form.text_content = 'hello'
    check(
        form.text_entry.get_text() == 'hello',
        'entry text bidirectionally bound to text-content',
    )
    check(changed_fired, 'content-changed emitted on property change')
    check(
        form.wifi_hidden_row.get_activatable_widget() is form.wifi_hidden_switch,
        'hidden-network row activatable widget is the switch',
    )

    print('== GeneratorPage ==')
    page = GeneratorPage()
    check_template_children(
        page,
        {
            'generator_page_box': Gtk.Box,
            'qr_preview_widget': GeneratorQRPreviewPane,
            'form': GeneratorForm,
        },
        'GeneratorPage',
    )
    page.in_mobile_screen = True
    check(
        page.generator_page_box.get_orientation() == Gtk.Orientation.VERTICAL,
        'mobile -> generator box vertical',
    )
    check(
        page.generator_page_box.get_children()[0] is page.form,
        'mobile -> form first',
    )
    page.in_mobile_screen = False
    check(
        page.generator_page_box.get_orientation() == Gtk.Orientation.HORIZONTAL,
        'desktop -> generator box horizontal',
    )
    check(
        page.generator_page_box.get_children()[0] is page.box_preview,
        'desktop -> preview first',
    )

    print('== GeneratorWifiNetworkPickerDialog ==')
    picker = GeneratorWifiNetworkPickerDialog()
    check_template_children(
        picker,
        {
            'wifi_network_picker_list_store': Gtk.ListStore,
            'wifi_network_picker_filter_model': Gtk.TreeModelFilter,
            'wifi_network_picker_list_view': Gtk.TreeView,
            'wifi_network_picker_search_entry': Gtk.SearchEntry,
            'wifi_network_picker_back_button': Gtk.Button,
        },
        'GeneratorWifiNetworkPickerDialog',
    )
    check(
        picker.wifi_network_picker_filter_model.get_model() is picker.wifi_network_picker_list_store,
        'filter model wraps the list store',
    )

    print('== CoBangWindow ==')
    # Attach to a real application: the window's camera-access path expects one.
    app = Gtk.Application(application_id='org.smoke.UiTest')
    app.register(None)
    window = CoBangWindow(application=app)
    check_template_children(
        window,
        {
            'job_viewstack': Gtk.Stack,
            'job_switcher': Handy.ViewSwitcher,
            'job_toggler_box': Gtk.Box,
            'toggle_scanner': Gtk.ToggleButton,
            'toggle_generator': Gtk.ToggleButton,
            'scanner_page': ScannerPage,
            'generator_page': GeneratorPage,
        },
        'CoBangWindow',
    )
    for name, title in ((JobName.SCANNER, 'Scanner'), (JobName.GENERATOR, 'Generator')):
        child = window.job_viewstack.get_child_by_name(name)
        check(child is not None, f'job_viewstack has child "{name}"')
        if child is not None:
            child_title = window.job_viewstack.child_get_property(child, 'title')
            check(child_title == title, f'job_viewstack child "{name}" title is "{title}"')
    check(window.toggle_scanner.get_active(), 'toggle_scanner active by default')
    check(window.job_switcher.get_visible(), 'desktop -> job switcher visible')
    check(not window.job_toggler_box.get_visible(), 'desktop -> toggler box hidden')
    # Stack switch should mirror the toggle buttons.
    window.job_viewstack.set_visible_child_name(JobName.GENERATOR)
    check(window.toggle_generator.get_active(), 'stack -> generator toggles buttons')
    check(not window.toggle_scanner.get_active(), 'stack -> generator deactivates scanner button')
    window.toggle_scanner.set_active(True)
    check(
        window.job_viewstack.get_visible_child_name() == JobName.SCANNER,
        'scanner toggle switches stack',
    )
    window.in_mobile_screen = True
    check(not window.job_switcher.get_visible(), 'mobile -> job switcher hidden')
    check(window.job_toggler_box.get_visible(), 'mobile -> toggler box visible')
    check(
        window.scanner_page.in_mobile_screen,
        'in-mobile-screen bound to scanner page',
    )

    # Handler wiring check for all template classes.

    ui_files = {
        CoBangWindow: 'window.ui',
        ScannerPage: 'scanner-page.ui',
        GeneratorPage: 'generator-page.ui',
        GeneratorForm: 'generator/form.ui',
        GeneratorQRPreviewPane: 'generator/qr-preview-pane.ui',
        GeneratorWifiNetworkPickerDialog: 'generator/wifi-network-picker-dialog.ui',
    }
    print('== Declarative signal handlers exist ==')
    for cls, rel in ui_files.items():
        xml = (src_dir / 'ui' / rel).read_text()
        check_signal_handlers(cls, xml)

    print()
    if WARNINGS:
        print(f'{len(WARNINGS)} FAILURES:')
        for w in WARNINGS:
            print(f' - {w}')
        sys.exit(1)
    print('All UI smoke checks passed.')


if __name__ == '__main__':
    main()
