# Handoff Report: R1 (Reliable Mouse Drag-to-Move & Guaranteed Always-On-Top)

**Date**: 2026-10-22  
**Author**: Explorer 1 (`explorer_r2_1`)  
**Scope**: Window Movement, Mouse Event Propagation, Child Widget Interception, Multi-Monitor Dragging, Always-On-Top Persistence on Ubuntu GNOME (Wayland & X11), and Platform Configuration.

---

## 1. Observation

### 1.1 Launcher Script & Platform Flags
- In `run.sh` (lines 32–36):
  ```bash
  export PYTHONPATH="$SCRIPT_DIR:${PYTHONPATH:-}"

  echo "[SelfiCamera] Launching SelfiCamera..."
  exec "$VENV_DIR/bin/python" -m selficamera "$@"
  ```
  `run.sh` does NOT configure `QT_QPA_PLATFORM`. On Ubuntu GNOME (default desktop session `XDG_SESSION_TYPE=wayland`, `WAYLAND_DISPLAY=wayland-0`), Qt 6 defaults to the native Wayland plugin (`wayland`).
- In `selficamera/__main__.py` (lines 107–110):
  ```python
  qt_app = QApplication(sys.argv)
  qt_app.setApplicationName(__app_name__)
  ```
  `QApplication` is initialized without checking or setting `QT_QPA_PLATFORM`. In Qt, platform plugin selection is permanently locked once `QApplication` is created.

### 1.2 Behavior on Live Ubuntu GNOME System
- Live system environment:
  - `XDG_SESSION_TYPE=wayland`
  - `WAYLAND_DISPLAY=wayland-0`
  - `DISPLAY=:0`
- Testing `QT_QPA_PLATFORM=xcb` directly:
  ```
  qt.qpa.plugin: From 6.5.0, xcb-cursor0 or libxcb-cursor0 is needed to load the Qt xcb platform plugin.
  qt.qpa.plugin: Could not load the Qt platform plugin "xcb" in "" even though it was found.
  This application failed to start because no Qt platform plugin could be initialized.
  (Exit code 134)
  ```
  `ldd` check on `libqxcb.so` revealed missing X11 helper libraries (most notably `libxcb-cursor.so.0` and `libxkbcommon-x11.so.0`), which are available via Ubuntu's `libxcb-cursor0` package.
- Testing Qt platform fallback syntax:
  Setting `QT_QPA_PLATFORM="xcb;wayland"`:
  ```
  Platform name with xcb;wayland fallback: wayland
  Window created and shown: <PySide6.QtGui.QWindow(...)>
  ```
  Qt gracefully attempts `xcb` (XWayland) first, and falls back to `wayland` without crashing if X11 libraries are missing.

### 1.3 Child Widget Interception (The Hidden HUD Click Trap)
- In `selficamera/ui/overlay.py` (lines 74–75, 127–134):
  `OverlayWindow` instantiates `AutoHidingHUD` as a child widget and positions it across the bottom arc of the circle:
  ```python
  hud_w = 230
  hud_h = 32
  x = (self.width() - hud_w) // 2
  y = self.shadow_margin + self._diameter - hud_h - 14
  self.hud.setGeometry(x, y, hud_w, hud_h)
  ```
- In `selficamera/ui/hud.py` (lines 65–84, 96–106):
  `AutoHidingHUD` contains five `QPushButton` instances (`btn_flip`, `btn_blur`, `btn_light`, `btn_ghost`, `btn_close`). Opacity is managed via `QGraphicsOpacityEffect(self)`. Initial opacity is `0.0`.
- **Experimental Verification**:
  Testing Qt event propagation when `QGraphicsOpacityEffect` opacity is `0.0`:
  ```python
  # When opacity is 0.0, QPushButton still consumes mouse press
  ev = QMouseEvent(QEvent.Type.MouseButtonPress, ...)
  app.sendEvent(btn, ev)
  # Result: Parent received button press? False
  ```
  Even though `AutoHidingHUD` is visually transparent, its `QPushButton` children remain active in the Qt hit-test tree because `WA_TransparentForMouseEvents` is NOT enabled when faded out. Any click in the bottom 32px of the circular bubble hits invisible buttons, which consume `mousePressEvent`, preventing `OverlayWindow.mousePressEvent` from firing. Dragging fails to start.

### 1.4 High-Frequency Blocking Disk I/O During Drag (`os.fsync`)
- In `selficamera/ui/overlay.py` (lines 239–241):
  ```python
  self.move(new_pos)
  self.position_changed.emit(new_pos.x(), new_pos.y())
  ```
- In `selficamera/app.py` (line 74):
  ```python
  self.overlay.position_changed.connect(lambda x, y: self.config.update(x=x, y=y))
  ```
- In `selficamera/config.py` (lines 78–92, 104–109):
  ```python
  def update(self, auto_save: bool = True, **kwargs: Any) -> None:
      self._data.update(kwargs)
      if auto_save:
          self.save()
  ```
  Where `save()` executes:
  ```python
  with open(temp_path, "w", encoding="utf-8") as f:
      json.dump(self._data, f, indent=2)
      f.flush()
      os.fsync(f.fileno())  # HARDWARE DISK SYNC ON MAIN GUI THREAD
  os.replace(temp_path, self._path)
  ```
  Every single pixel of mouse movement triggers an atomic file replacement and blocking `os.fsync()` on the main GUI thread. At 100+ mouse move events per second, this causes severe stuttering, dropped frames, and compositor lockup symptoms.

### 1.5 Multi-Monitor Boundary Clamping Bug
- In `selficamera/ui/overlay.py` (lines 232–237):
  ```python
  screen = QGuiApplication.primaryScreen()
  if screen:
      geo = screen.availableGeometry()
      clamped_x = max(geo.left(), min(geo.right() - self.width() + 1, new_pos.x()))
      clamped_y = max(geo.top(), min(geo.bottom() - self.height() + 1, new_pos.y()))
      new_pos = QPoint(clamped_x, clamped_y)
  ```
  Dragging is hard-clamped exclusively to `primaryScreen()`. In any multi-monitor setup (e.g. laptop + external display), the user is physically prevented from dragging the overlay bubble past the edge of the primary monitor onto secondary monitors.

### 1.6 Hit Boundary Margin on Border Aura Ring
- In `selficamera/ui/overlay.py` (lines 217–220):
  ```python
  center = QPointF(self.width() / 2.0, self.height() / 2.0)
  dist = (event.position().x() - center.x()) ** 2 + (event.position().y() - center.y()) ** 2
  if dist <= (self._diameter / 2.0) ** 2:
  ```
- In `selficamera/ui/aura.py` (lines 18–21, 69–85):
  The voice aura border ring is drawn with a pen width between 2.5px and 7.0px, extending outside `self._diameter / 2.0`. Clicks on the outer glowing aura border evaluate to `dist > (self._diameter / 2.0) ** 2` and fail to trigger drag.

### 1.7 Dynamic Always-On-Top Window Flags
- In `selficamera/ui/overlay.py` (lines 98–103):
  Initial flags are `FramelessWindowHint | WindowStaysOnTopHint | Tool`.
  There is currently no method to dynamically toggle `WindowStaysOnTopHint`.
- **Experimental Verification**:
  When `setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, ...)` is called on a visible widget in PySide6:
  ```python
  w.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, False)
  # Result: w.isVisible() is False
  w.show()
  # Result: w.isVisible() is True
  ```
  Qt hides the native window upon flag modification; `self.show()` must be called immediately after.

---

## 2. Logic Chain

1. **Root Cause of Bottom-Area Drag Failure (Child Interception)**:
   - Direct observation shows `AutoHidingHUD` sits in the bottom area of the circle with 5 `QPushButton`s.
   - Experiments confirm that `QGraphicsOpacityEffect(0.0)` does not stop `QPushButton` from consuming mouse clicks.
   - Therefore, whenever the HUD is faded out, any drag attempt starting in the bottom half of the circle fails silently because the hidden button intercepts `mousePressEvent`.
   - **Remedy**: When HUD opacity reaches 0.0, set `WA_TransparentForMouseEvents = True` (or `setVisible(False)`). When `trigger_show()` is called, restore `WA_TransparentForMouseEvents = False` (or `setVisible(True)`).

2. **Root Cause of Drag Stuttering & Hitching (Blocking I/O)**:
   - Direct observation shows `self.position_changed.emit()` is called on every pixel during `mouseMoveEvent`.
   - `app.py` forwards this directly to `config.update(auto_save=True)`.
   - `config.save()` calls `os.fsync(f.fileno())` synchronously on the GUI thread.
   - 100+ hardware disk flushes per second freeze the Qt event loop, preventing timely frame rendering and causing cursor lag.
   - **Remedy**: In `mouseMoveEvent`, update coordinates in-memory with `auto_save=False`. Only trigger `config.save()` when dragging terminates in `mouseReleaseEvent`.

3. **Root Cause of Inability to Move to Secondary Displays**:
   - `mouseMoveEvent` clamps coordinates against `QGuiApplication.primaryScreen().availableGeometry()`.
   - Moving the cursor across the primary screen border stops `new_pos` at `geo.right()`.
   - **Remedy**: Find the screen under the cursor using `QGuiApplication.screenAt(event.globalPosition().toPoint()) or QGuiApplication.primaryScreen()`, or clamp against the united bounding rectangle of all screens (`virtualGeometry`).

4. **Compositor Blocking & Always-On-Top on Ubuntu GNOME**:
   - GNOME Shell Mutter on Wayland intentionally does not allow unprivileged client-side absolute window positioning (`move(x, y)` is ignored in `xdg-shell`).
   - GNOME Mutter on Wayland also does not support `_NET_WM_STATE_ABOVE` (WindowStaysOnTopHint) for native Wayland clients, causing full-screen IDEs/browsers to bury the overlay.
   - Under XWayland (`QT_QPA_PLATFORM=xcb`), GNOME Mutter manages the window through EWMH:
     - `_NET_WM_STATE_ABOVE` is strictly enforced over full-screen IDEs, terminals, and browsers.
     - Client-side `move(x, y)` (`XMoveWindow`) is completely permitted.
   - However, Qt 6.5+ requires `libxcb-cursor0`. Blindly hardcoding `xcb` crashes if the library is absent.
   - Using `QT_QPA_PLATFORM="xcb;wayland"` provides automatic graceful fallback.
   - On native Wayland (if fallback occurs), `self.windowHandle().startSystemMove()` in `mousePressEvent` delegates window movement to Mutter.

---

## 3. Caveats

1. **Wayland Native Limitations**: If `libxcb-cursor0` is absent and the app runs on native Wayland, GNOME Mutter will not keep any native Wayland window strictly above full-screen applications due to Wayland protocol design. Installing `libxcb-cursor0` so XWayland (`xcb`) is used is essential for 100% guaranteed Always-On-Top over full-screen apps.
2. **Multi-Monitor DPI Differences**: When dragging between screens with fractional scaling (e.g., 100% and 150%), XWayland handles scaling automatically, but coordinates should reference `event.globalPosition().toPoint()`.
3. **Headless Pytest Compatibility**: Automated tests set `QT_QPA_PLATFORM=offscreen`. Any code setting `QT_QPA_PLATFORM` in Python or bash must check `if "QT_QPA_PLATFORM" not in os.environ:` so test suites are never disrupted.

---

## 4. Conclusion & Recommended Implementation Strategy

### 4.1 Changes to `run.sh`
- Check whether `libxcb-cursor0` is installed on Ubuntu. If not, print an informative one-line guidance notice.
- Set `export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-xcb;wayland}"` before starting Python.

### 4.2 Changes to `selficamera/__main__.py`
- In `main()`, before `QApplication(sys.argv)` is created:
  ```python
  if "QT_QPA_PLATFORM" not in os.environ:
      os.environ["QT_QPA_PLATFORM"] = "xcb;wayland"
  ```

### 4.3 Changes to `selficamera/ui/overlay.py`
1. **Fix HUD Mouse Transparency**:
   In `AutoHidingHUD`:
   - Initialize `self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)` since initial opacity is 0.0.
   - In `trigger_show()`: set `self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)` before starting fade-in.
   - In `_start_fade_out()`: connect `self._anim.finished` to set `WA_TransparentForMouseEvents = True` when opacity reaches 0.0.
2. **Expand Drag Click Radius for Aura Border**:
   In `mousePressEvent`:
   ```python
   radius = (self._diameter / 2.0) + 4.0  # Allow clicking on glowing border ring
   if dist <= radius ** 2:
   ```
3. **Wayland Native startSystemMove() Fallback**:
   In `mousePressEvent`:
   ```python
   if QGuiApplication.platformName() == "wayland":
       wh = self.windowHandle()
       if wh is not None and hasattr(wh, "startSystemMove"):
           if wh.startSystemMove():
               event.accept()
               return
   ```
4. **Multi-Monitor Screen Clamping in `mouseMoveEvent`**:
   ```python
   target_pos = event.globalPosition().toPoint() - self._drag_start_pos
   screens = QGuiApplication.screens()
   if screens:
       # Union of all screen bounding geometries
       virtual_rect = screens[0].geometry()
       for s in screens[1:]:
           virtual_rect = virtual_rect.united(s.geometry())
       clamped_x = max(virtual_rect.left(), min(virtual_rect.right() - self.width() + 1, target_pos.x()))
       clamped_y = max(virtual_rect.top(), min(virtual_rect.bottom() - self.height() + 1, target_pos.y()))
       target_pos = QPoint(clamped_x, clamped_y)
   self.move(target_pos)
   self.position_changed.emit(target_pos.x(), target_pos.y())
   ```
5. **Debounce / Defer Disk Persistence to `mouseReleaseEvent`**:
   - In `mouseReleaseEvent`:
     ```python
     if event.button() == Qt.MouseButton.LeftButton and self._is_dragging:
         self._is_dragging = False
         self.drag_completed.emit(self.pos().x(), self.pos().y())
     ```
6. **Implement Dynamic Always-On-Top Toggle**:
   ```python
   def set_always_on_top(self, enabled: bool) -> None:
       self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, enabled)
       self.show()
       self.always_on_top_changed.emit(enabled)
   ```

### 4.4 Changes to `selficamera/app.py` & `selficamera/config.py`
- In `config.py`: Add `"always_on_top": True` to `DEFAULT_CONFIG`.
- In `app.py`:
  - Connect `self.overlay.position_changed` to in-memory config update: `lambda x, y: self.config.update(auto_save=False, x=x, y=y)`.
  - Connect `self.overlay.drag_completed` to `lambda x, y: self.config.update(auto_save=True, x=x, y=y)` (persists to disk only when drag finishes).
  - Add `set_always_on_top(enabled: bool)` method in `SelfiCameraApp` wired to config and overlay.

---

## 5. Verification Method

### Independent Test Verification Commands:
1. **Run full pytest suite headlessly**:
   ```bash
   .venv/bin/pytest -v
   ```
2. **Run targeted overlay GUI tests**:
   ```bash
   .venv/bin/pytest tests/test_overlay_gui.py -v
   ```
3. **Verify HUD mouse transparency**:
   Synthesize `QMouseEvent` on child buttons while HUD opacity is 0.0, and assert that `overlay._is_dragging` becomes `True`.
4. **Verify multi-monitor dragging**:
   Simulate drag across monitor coordinates beyond `primaryScreen().geometry().right()` and verify window moves into the virtual desktop area.
5. **Verify Always-On-Top persistence & toggling**:
   Call `overlay.set_always_on_top(False)` and `overlay.set_always_on_top(True)`, asserting that `flags & Qt.WindowType.WindowStaysOnTopHint` updates correctly and `overlay.isVisible()` remains `True`.

### Invalidation Conditions:
- If `QT_QPA_PLATFORM` is hardcoded to `xcb` without fallback, and `libxcb-cursor0` is absent, the app will exit with code 134 on Ubuntu.
- If `setWindowFlag(WindowStaysOnTopHint)` is called without `self.show()`, the overlay will unexpectedly disappear from the screen.
- If `os.fsync()` remains in `mouseMoveEvent`, dragging will exhibit noticeable micro-stuttering on high-refresh-rate displays.
