---
name: gtk-signal-result
description: "Use when implementing work delegation in GTK4/Adwaita apps where Window → Parent Page → Child Page, and the child page's work result flows back up via signals to the layer that coordinates with other system components."
---

# gtk-signal-result — Work Delegation with Result Callback via Signals

GTK4/Adwaita apps use **GObject signals** for child→parent result propagation instead of callback injection. The child page performs a subtask and emits the result; the parent (or Window) coordinates the result with other system components.

## Delegation Chain

```
Window
  └── Parent Page (orchestrator, coordinates)
        └── Child Page A (performs subtask A, emits result via signal)
        └── Child Page B (performs subtask B, emits result via signal)
```

**Key insight:** The child knows nothing about what happens with its result. The parent coordinates multiple children and decides what to do with their combined outputs.

## When to Use

- Child page performs a focused subtask (collect input, generate data, scan)
- Result needs to flow UP to coordinate with other components
- Parent holds references to other children/pages that need the result
- **Anti-pattern to avoid:** passing handler callbacks from parent to child

## Pattern

### 1. Child Page: Declare Signal (2 ways)

**Decorator style** (`generator_starting.py:38-44`):

```python
from gi.repository import GObject, Gtk

@Gtk.Template.from_resource('/path/to/template.ui')
class GeneratorStartingPage(Gtk.Box):
    __gtype_name__ = 'GeneratorStartingPage'

    @GObject.Signal('generate-qr', flags=GObject.SignalFlags.RUN_LAST, arg_types=(str,))
    def signal_generate_qr(self, text: str):  # Emitted when work is done
        pass
```

**`__gsignals__` dict style** (`generator_wifi.py:46-50`):

```python
class GeneratorWiFiPage(Adw.Bin):
    __gtype_name__ = 'GeneratorWiFiPage'

    __gsignals__ = {
        'generate-qr-for-wifi': (GObject.SignalFlags.RUN_FIRST, None, (WifiNetworkInfo,)),
        'back-to-start': (GObject.SignalFlags.RUN_FIRST, None, ()),
    }
```

### 2. Child Page: Emit Signal with Result

```python
@Gtk.Template.Callback()
def on_btn_generate_clicked(self, _btn: Gtk.Button):
    text = self.text_entry.get_text().strip()
    if text:
        self.emit('generate-qr', text)  # Emit result upward
```

### 3. Parent Page: Wire Signal to Handler in `__init__`

```python
class GeneratorPage(Adw.Bin):
    __gtype_name__ = 'GeneratorPage'

    starting_page: GeneratorStartingPage = Gtk.Template.Child()
    wifi_page: GeneratorWiFiPage = Gtk.Template.Child()
    qr_code_page: GeneratorQRCodePage = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Wire each child's signal to appropriate handler
        self.starting_page.connect('generate-qr', self.on_qr_code_generation_requested)
        self.starting_page.connect('switch-to-wifi', self.on_switch_to_wifi)
        self.wifi_page.connect('generate-qr-for-wifi', self.on_generate_qr_for_wifi_network)
        self.wifi_page.connect('back-to-start', self.on_back_to_start)
```

### 4. Parent Page: Handle Result

```python
def on_qr_code_generation_requested(self, _src: GeneratorStartingPage, text: str):
    """Parent coordinates: take text from starting page, generate QR, show in qr_code_page."""
    qr = qrcode.QRCode(border=2)
    qr.add_data(text)
    qr.make(fit=True)
    img = qr.make_image(fill_color='black', back_color='white')
    # ... convert to texture, display in qr_code_page
    self.qr_code_page.set_original_text(text)
    self.qr_code_page.qr_picture.set_paintable(texture)
    self.active_sub_page = GeneratorSubPage.QR_CODE_RESULT
```

## Signal Examples in This Project

| Child Page | Signal | Payload | What Parent Does with Result |
|------------|--------|---------|------------------------------|
| `GeneratorStartingPage` | `generate-qr` | `str` | Generate QR image, display in `qr_code_page` |
| `GeneratorStartingPage` | `switch-to-wifi` | — | Switch to wifi child page |
| `GeneratorQRCodePage` | `back-to-start` | — | Clear QR page, return to starting page |
| `GeneratorWiFiPage` | `request-saved-wifi-networks` | — | Load networks, populate wifi list |
| `GeneratorWiFiPage` | `generate-qr-for-wifi` | `WifiNetworkInfo` | Generate QR for selected network |
| `GeneratorWiFiPage` | `back-to-start` | — | Return to starting page |
| `ScannerPage` | `poll-wifi-connection-status` | `WifiInfoMessage` | Check if already connected |
| `ScannerPage` | `request-connect-wifi` | `WifiInfoMessage` | Connect to scanned WiFi |

## Adding a New Delegation Signal

1. **Child page: Declare signal**
   ```python
   @GObject.Signal('work-done', flags=GObject.SignalFlags.RUN_LAST, arg_types=(MyResult,))
   def signal_work_done(self, result: MyResult):
       pass
   ```

2. **Child page: Emit when work completes**
   ```python
   @Gtk.Template.Callback()
   def on_work_trigger(self, _btn: Gtk.Button):
       result = self.perform_work()
       self.emit('work-done', result)
   ```

3. **Parent page: Wire signal in `__init__`**
   ```python
   self.child_page.connect('work-done', self.on_child_work_done)
   ```

4. **Parent page: Handle result (may coordinate with OTHER children)**
   ```python
   def on_child_work_done(self, _src: ChildPage, result: MyResult):
       # Parent coordinates: maybe update another child, trigger system action, etc.
       self.other_child.update(result)
       self.system_component.process(result)
   ```

## Key Principles

- **Child is dumb about result fate** — only emits signal, knows nothing of parent
- **Parent is the coordinator** — wires signals, holds refs to all children
- **Signal carries typed result** — use `arg_types` tuple for payload type
- **Handler gets source** — first param is emitting child (use `_src` if not needed)
- **Result may need further processing** — parent does coordination, not just UI updates
