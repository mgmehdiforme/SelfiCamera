"""Settings window: sidebar navigation with Camera, Look, Background, Light, Scenes,
Shortcuts and General pages. All changes apply live through the app controller."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Protocol, Tuple

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QCloseEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from selficamera import __version__
from selficamera.config import (
    BACKGROUND_COLOR_PRESETS,
    BACKGROUND_LABELS,
    BACKGROUND_MODES,
    BORDER_COLOR_PRESETS,
    FPS_CHOICES,
    MAX_SIZE,
    MIN_SIZE,
    RESOLUTIONS,
    SHAPE_LABELS,
    SHAPES,
    SIZE_PRESETS,
)
from selficamera.ui import icons, theme
from selficamera.ui.overlay import BOTTOM_LEFT, BOTTOM_RIGHT, CENTER, TOP_LEFT, TOP_RIGHT
from selficamera.ui.widgets import ColorSwatches, Segmented, SliderRow, card, switch_row

PAGES: Tuple[Tuple[str, str, str], ...] = (
    ("camera", "Camera", "camera"),
    ("look", "Look", "shape"),
    ("background", "Background", "background"),
    ("light", "Light & Color", "sun"),
    ("scenes", "Scenes", "layers"),
    ("shortcuts", "Shortcuts", "keyboard"),
    ("general", "General", "sliders"),
)

SHORTCUT_ROWS = (
    ("Super+Alt+C", "Show / hide camera"),
    ("Super+Alt+Z", "Spotlight (big & centered)"),
    ("Super+Alt+B", "Next background effect"),
    ("Super+Alt+M", "Mirror"),
    ("Super+Alt+X", "Click-through on / off"),
    ("Super+Alt+O", "Open settings"),
    ("Super+Alt+1…4", "Snap to corner"),
    ("Super+Alt+5", "Snap to center"),
)


class Controller(Protocol):  # pragma: no cover - typing only
    setting_changed: Signal

    def get(self, key: str) -> Any: ...
    def set(self, key: str, value: Any) -> None: ...


def _fmt_signed(v: int) -> str:
    return f"{v:+d}" if v else "0"


class SettingsWindow(QWidget):
    """Top-level settings window bound to a SelfiCameraApp controller."""

    def __init__(self, controller: Any, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent, Qt.WindowType.Window)
        self.c = controller
        self.setObjectName("SettingsWindow")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setWindowTitle("SelfiCamera Settings")
        self.setWindowIcon(icons.app_icon())
        self.setStyleSheet(theme.APP_STYLESHEET)
        self.resize(780, 640)
        self.setMinimumSize(QSize(640, 480))
        self._syncing = False
        self._binders: Dict[str, List[Callable[[Any], None]]] = {}

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_sidebar())
        self.stack = QStackedWidget(self)
        root.addWidget(self.stack, 1)

        builders = {
            "camera": self._page_camera,
            "look": self._page_look,
            "background": self._page_background,
            "light": self._page_light,
            "scenes": self._page_scenes,
            "shortcuts": self._page_shortcuts,
            "general": self._page_general,
        }
        self.pages: Dict[str, QWidget] = {}
        for key, _title, _icon in PAGES:
            page = builders[key]()
            self.pages[key] = page
            self.stack.addWidget(page)
        self.nav.setCurrentRow(0)

        QShortcut(QKeySequence(QKeySequence.StandardKey.Close), self, activated=self.close)
        QShortcut(QKeySequence("Escape"), self, activated=self.close)

        self.c.setting_changed.connect(self._on_setting_changed)
        self.sync_all()

    # ----------------------------------------------------------------- shell
    def _build_sidebar(self) -> QWidget:
        side = QWidget(self)
        side.setObjectName("Sidebar")
        side.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        side.setFixedWidth(196)
        layout = QVBoxLayout(side)
        layout.setContentsMargins(12, 18, 12, 14)
        layout.setSpacing(12)
        brand = QHBoxLayout()
        logo = QLabel(side)
        logo.setPixmap(icons.app_icon().pixmap(28, 28))
        name = QLabel("SelfiCamera", side)
        name.setStyleSheet("font-size: 16px; font-weight: 800;")
        brand.addWidget(logo)
        brand.addWidget(name)
        brand.addStretch(1)
        layout.addLayout(brand)

        self.nav = QListWidget(side)
        self.nav.setObjectName("Nav")
        self.nav.setIconSize(QSize(18, 18))
        for key, title, icon_name in PAGES:
            item = QListWidgetItem(icons.icon(icon_name, 18, theme.TEXT_MUTED), title)
            item.setData(Qt.ItemDataRole.UserRole, key)
            self.nav.addItem(item)
        self.nav.currentRowChanged.connect(lambda row: self.stack.setCurrentIndex(row))
        layout.addWidget(self.nav, 1)

        version = QLabel(f"Version {__version__} · offline", side)
        version.setObjectName("Hint")
        layout.addWidget(version)
        return side

    def _page(self, title: str, subtitle: str) -> Tuple[QWidget, QVBoxLayout]:
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget(scroll)
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(26, 22, 26, 26)
        layout.setSpacing(14)
        t = QLabel(title, inner)
        t.setObjectName("PageTitle")
        s = QLabel(subtitle, inner)
        s.setObjectName("PageSubtitle")
        s.setWordWrap(True)
        layout.addWidget(t)
        layout.addWidget(s)
        layout.addSpacing(4)
        scroll.setWidget(inner)
        return scroll, layout

    def show_page(self, key: str) -> None:
        for i, (k, _, _) in enumerate(PAGES):
            if k == key:
                self.nav.setCurrentRow(i)

    # ------------------------------------------------------------- binding
    def _bind(self, key: str, updater: Callable[[Any], None]) -> None:
        self._binders.setdefault(key, []).append(updater)

    def _set(self, key: str, value: Any) -> None:
        if not self._syncing:
            self.c.set(key, value)

    def _on_setting_changed(self, key: str, value: Any) -> None:
        self._syncing = True
        try:
            for fn in self._binders.get(key, []):
                fn(value)
        finally:
            self._syncing = False

    def sync_all(self) -> None:
        for key in list(self._binders.keys()):
            self._on_setting_changed(key, self.c.get(key))
        self.refresh_devices()
        self.refresh_mics()
        self.refresh_scenes()
        self.refresh_model_info()
        self.refresh_shortcut_status()

    # ---------------------------------------------------------------- camera
    def _page_camera(self) -> QWidget:
        page, layout = self._page("Camera", "Choose your webcam and frame yourself.")

        src, sl = card("Source", page)
        row = QHBoxLayout()
        self.combo_device = QComboBox(src)
        self.combo_device.activated.connect(lambda i: self._set("device_path", self.combo_device.itemData(i)))
        self.btn_refresh = QPushButton(src)
        self.btn_refresh.setIcon(icons.icon("refresh", 16))
        self.btn_refresh.setToolTip("Look for cameras again")
        self.btn_refresh.clicked.connect(self.refresh_devices)
        row.addWidget(self.combo_device, 1)
        row.addWidget(self.btn_refresh)
        sl.addLayout(row)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.addWidget(QLabel("Resolution", src), 0, 0)
        self.combo_res = QComboBox(src)
        for w, h in RESOLUTIONS:
            label = {480: "SD", 720: "HD", 1080: "Full HD"}.get(h, "")
            self.combo_res.addItem(f"{w} × {h}  {label}", [w, h])
        self.combo_res.activated.connect(lambda i: self._set("resolution", self.combo_res.itemData(i)))
        grid.addWidget(self.combo_res, 0, 1)
        grid.addWidget(QLabel("Frame rate", src), 1, 0)
        self.combo_fps = QComboBox(src)
        for f in FPS_CHOICES:
            self.combo_fps.addItem(f"{f} fps", f)
        self.combo_fps.activated.connect(lambda i: self._set("fps", self.combo_fps.itemData(i)))
        grid.addWidget(self.combo_fps, 1, 1)
        grid.setColumnStretch(1, 1)
        sl.addLayout(grid)
        self.lbl_camera_status = QLabel("", src)
        self.lbl_camera_status.setObjectName("Hint")
        self.lbl_camera_status.setWordWrap(True)
        sl.addWidget(self.lbl_camera_status)
        layout.addWidget(src)

        self._bind("device_path", self._select_device)
        self._bind("resolution", lambda v: self._select_combo(self.combo_res, list(v)))
        self._bind("fps", lambda v: self._select_combo(self.combo_fps, int(v)))

        fr, fl = card("Framing", page)
        mirror_row, self.sw_mirror = switch_row("Mirror", "Shows you like a mirror. Text behind you will appear reversed.", fr)
        self.sw_mirror.toggled.connect(lambda v: self._set("mirror", v))
        self._bind("mirror", self.sw_mirror.set_checked_silently)
        fl.addWidget(mirror_row)

        self.sl_zoom = SliderRow("Zoom", 100, 300, 100, 100, lambda v: f"{v / 100:.1f}×", fr)
        self.sl_zoom.valueChanged.connect(lambda v: self._set("zoom", v / 100.0))
        self._bind("zoom", lambda v: self.sl_zoom.set_value_silently(int(round(float(v) * 100))))
        fl.addWidget(self.sl_zoom)
        self.sl_pan_x = SliderRow("Left / right", -100, 100, 0, 0, _fmt_signed, fr)
        self.sl_pan_x.valueChanged.connect(lambda v: self._set("pan_x", v / 100.0))
        self._bind("pan_x", lambda v: self.sl_pan_x.set_value_silently(int(round(float(v) * 100))))
        fl.addWidget(self.sl_pan_x)
        self.sl_pan_y = SliderRow("Up / down", -100, 100, 0, 0, _fmt_signed, fr)
        self.sl_pan_y.valueChanged.connect(lambda v: self._set("pan_y", v / 100.0))
        self._bind("pan_y", lambda v: self.sl_pan_y.set_value_silently(int(round(float(v) * 100))))
        fl.addWidget(self.sl_pan_y)

        af_row, self.sw_autoframe = switch_row("Auto-frame", "Follows you and keeps your head in the upper third. Needs the AI model.", fr)
        self.sw_autoframe.toggled.connect(lambda v: self._set("auto_frame", v))
        self._bind("auto_frame", self.sw_autoframe.set_checked_silently)
        fl.addWidget(af_row)

        btn_reset = QPushButton("Reset framing", fr)
        btn_reset.clicked.connect(lambda: self.c.reset_framing())
        fl.addWidget(btn_reset, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(fr)
        layout.addStretch(1)
        return page

    def refresh_devices(self) -> None:
        current = self.c.get("device_path")
        self.combo_device.blockSignals(True)
        self.combo_device.clear()
        devices = self.c.camera_devices()
        if not devices:
            self.combo_device.addItem("No camera found", current)
        for path, label in devices:
            self.combo_device.addItem(label, path)
        if current and self.combo_device.findData(current) < 0:
            self.combo_device.addItem(f"{current} (not connected)", current)
        self._select_device(current)
        self.combo_device.blockSignals(False)

    def _select_device(self, path: Any) -> None:
        idx = self.combo_device.findData(path)
        if idx >= 0:
            self.combo_device.setCurrentIndex(idx)

    @staticmethod
    def _select_combo(combo: QComboBox, data: Any) -> None:
        for i in range(combo.count()):
            if combo.itemData(i) == data:
                combo.setCurrentIndex(i)
                return

    def set_camera_status(self, text: str) -> None:
        self.lbl_camera_status.setText(text)

    # ------------------------------------------------------------------ look
    def _page_look(self) -> QWidget:
        page, layout = self._page("Look", "Shape, size, border and where the camera sits on screen.")

        sc, sl = card("Shape & size", page)
        self.seg_shape = Segmented([(s, SHAPE_LABELS[s]) for s in SHAPES], sc)
        self.seg_shape.selected.connect(lambda v: self._set("shape", v))
        self._bind("shape", self.seg_shape.set_current)
        sl.addWidget(self.seg_shape)
        self.sl_size = SliderRow("Size", MIN_SIZE, MAX_SIZE, 260, 260, lambda v: f"{v} px", sc)
        self.sl_size.valueChanged.connect(lambda v: self._set("size", v))
        self._bind("size", self.sl_size.set_value_silently)
        sl.addWidget(self.sl_size)
        presets = QHBoxLayout()
        for label, px in SIZE_PRESETS.items():
            b = QPushButton({"S": "Small", "M": "Medium", "L": "Large"}[label], sc)
            b.clicked.connect(lambda _=False, v=px: self.c.set_size_animated(v))
            presets.addWidget(b)
        sl.addLayout(presets)
        hint = QLabel("Tip: scroll over the camera or drag its edge to resize. Double-click it for Spotlight.", sc)
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        sl.addWidget(hint)
        layout.addWidget(sc)

        bc, bl = card("Border", page)
        self.sl_border = SliderRow("Thickness", 0, 16, 3, 3, lambda v: "Off" if v == 0 else f"{v} px", bc)
        self.sl_border.valueChanged.connect(lambda v: self._set("border_width", v))
        self._bind("border_width", self.sl_border.set_value_silently)
        bl.addWidget(self.sl_border)
        self.sw_border_color = ColorSwatches(BORDER_COLOR_PRESETS, bc)
        self.sw_border_color.colorChosen.connect(lambda v: self._set("border_color", v))
        self._bind("border_color", self.sw_border_color.set_color)
        bl.addWidget(self.sw_border_color)
        glow_row, self.sw_glow = switch_row("Voice wave", "Waves flow around the camera while you talk.", bc)
        self.sw_glow.toggled.connect(lambda v: self._set("voice_glow", v))
        self._bind("voice_glow", self.sw_glow.set_checked_silently)
        bl.addWidget(glow_row)
        mic_row = QHBoxLayout()
        mic_lbl = QLabel(bc)
        mic_lbl.setPixmap(icons.icon("mic", 16, theme.TEXT_MUTED).pixmap(16, 16))
        mic_row.addWidget(mic_lbl)
        self.combo_mic = QComboBox(bc)
        self.combo_mic.activated.connect(lambda i: self._set("mic_device", self.combo_mic.itemData(i)))
        mic_row.addWidget(self.combo_mic, 1)
        bl.addLayout(mic_row)
        self._bind("mic_device", lambda v: self._select_combo(self.combo_mic, v))
        shadow_row, self.sw_shadow = switch_row("Drop shadow", None, bc)
        self.sw_shadow.toggled.connect(lambda v: self._set("shadow", v))
        self._bind("shadow", self.sw_shadow.set_checked_silently)
        bl.addWidget(shadow_row)
        layout.addWidget(bc)

        pc, pl = card("Position", page)
        grid = QGridLayout()
        grid.setSpacing(6)
        spots = (
            (TOP_LEFT, "↖  Top left", 0, 0),
            (CENTER, "Center", 0, 1),
            (TOP_RIGHT, "Top right  ↗", 0, 2),
            (BOTTOM_LEFT, "↙  Bottom left", 1, 0),
            (BOTTOM_RIGHT, "Bottom right  ↘", 1, 2),
        )
        self.snap_buttons: Dict[int, QPushButton] = {}
        for pos, text, r, col in spots:
            b = QPushButton(text, pc)
            b.clicked.connect(lambda _=False, p=pos: self.c.snap(p))
            grid.addWidget(b, r, col)
            self.snap_buttons[pos] = b
        self.btn_spotlight = QPushButton("Spotlight", pc)
        self.btn_spotlight.setIcon(icons.icon("spotlight", 16))
        self.btn_spotlight.setObjectName("Primary")
        self.btn_spotlight.clicked.connect(lambda: self.c.toggle_spotlight())
        grid.addWidget(self.btn_spotlight, 1, 1)
        pl.addLayout(grid)
        self.sl_spot = SliderRow("Spotlight size", 30, 90, 62, 62, lambda v: f"{v}% of screen", pc)
        self.sl_spot.valueChanged.connect(lambda v: self._set("spotlight_scale", v / 100.0))
        self._bind("spotlight_scale", lambda v: self.sl_spot.set_value_silently(int(round(float(v) * 100))))
        pl.addWidget(self.sl_spot)
        layout.addWidget(pc)
        layout.addStretch(1)
        return page

    def refresh_mics(self) -> None:
        self.combo_mic.blockSignals(True)
        self.combo_mic.clear()
        self.combo_mic.addItem("System default microphone", None)
        for dev_id, label in self.c.mic_devices():
            self.combo_mic.addItem(label, dev_id)
        self._select_combo(self.combo_mic, self.c.get("mic_device"))
        self.combo_mic.blockSignals(False)

    # ------------------------------------------------------------ background
    def _page_background(self) -> QWidget:
        page, layout = self._page("Background", "Blur, replace or remove what is behind you. Runs fully offline.")

        mc, ml = card("Effect", page)
        self.seg_bg = Segmented([(m, BACKGROUND_LABELS[m]) for m in BACKGROUND_MODES], mc)
        self.seg_bg.selected.connect(lambda v: self._set("background_mode", v))
        ml.addWidget(self.seg_bg)

        self.sl_blur = SliderRow("Blur strength", 0, 100, 60, 60, lambda v: f"{v}%", mc)
        self.sl_blur.valueChanged.connect(lambda v: self._set("blur_strength", v))
        self._bind("blur_strength", self.sl_blur.set_value_silently)
        ml.addWidget(self.sl_blur)

        self.bg_color_box = QWidget(mc)
        cb = QVBoxLayout(self.bg_color_box)
        cb.setContentsMargins(0, 0, 0, 0)
        cb.addWidget(QLabel("Color", self.bg_color_box))
        self.sw_bg_color = ColorSwatches(BACKGROUND_COLOR_PRESETS, self.bg_color_box)
        self.sw_bg_color.colorChosen.connect(lambda v: self._set("background_color", v))
        self._bind("background_color", self.sw_bg_color.set_color)
        cb.addWidget(self.sw_bg_color)
        green = QLabel("Green (#00B140) works as a chroma key in your video editor.", self.bg_color_box)
        green.setObjectName("Hint")
        cb.addWidget(green)
        ml.addWidget(self.bg_color_box)

        self.bg_image_box = QWidget(mc)
        ib = QHBoxLayout(self.bg_image_box)
        ib.setContentsMargins(0, 0, 0, 0)
        self.lbl_bg_image = QLabel("No image selected", self.bg_image_box)
        self.lbl_bg_image.setObjectName("Hint")
        btn_img = QPushButton("Choose image…", self.bg_image_box)
        btn_img.setIcon(icons.icon("image", 16))
        btn_img.clicked.connect(self._choose_image)
        ib.addWidget(self.lbl_bg_image, 1)
        ib.addWidget(btn_img)
        ml.addWidget(self.bg_image_box)
        self._bind("background_image", lambda v: self.lbl_bg_image.setText(str(v).rsplit("/", 1)[-1] if v else "No image selected"))

        self.lbl_remove_hint = QLabel(
            "Remove makes everything except you transparent, so you float over your screen. "
            "Tip: set Border to Off and turn off Drop shadow for a clean cut-out.",
            mc,
        )
        self.lbl_remove_hint.setObjectName("Hint")
        self.lbl_remove_hint.setWordWrap(True)
        ml.addWidget(self.lbl_remove_hint)
        self._bind("background_mode", self._on_bg_mode)
        layout.addWidget(mc)

        ac, al = card("AI model", page)
        row = QHBoxLayout()
        self.lbl_model_badge = QLabel("", ac)
        self.lbl_model_name = QLabel("", ac)
        row.addWidget(self.lbl_model_badge)
        row.addWidget(self.lbl_model_name, 1)
        al.addLayout(row)
        self.lbl_model_hint = QLabel("", ac)
        self.lbl_model_hint.setObjectName("Hint")
        self.lbl_model_hint.setWordWrap(True)
        self.lbl_model_hint.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        al.addWidget(self.lbl_model_hint)
        layout.addWidget(ac)
        layout.addStretch(1)
        return page

    def _on_bg_mode(self, mode: str) -> None:
        self.seg_bg.set_current(mode)
        self.sl_blur.setVisible(mode == "blur")
        self.bg_color_box.setVisible(mode == "color")
        self.bg_image_box.setVisible(mode == "image")
        self.lbl_remove_hint.setVisible(mode == "remove")

    def _choose_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Choose a background image", "", "Images (*.png *.jpg *.jpeg *.webp *.bmp)")
        if path:
            self.c.set("background_image", path)
            self.c.set("background_mode", "image")

    AUTO_LIGHT_HINTS = {
        "face": "AI face metering: lifts a dark or backlit face and tames a blown-out one. A well-lit face is left alone.",
        "person": "AI metering on you (person mask): lifts you when you are too dark, tames you when too bright.",
        "center": "Brightens dim rooms. Install the AI models (selficamera --install-model) to meter on your face.",
    }

    def refresh_model_info(self) -> None:
        if self.lbl_autolight_hint is not None:
            self.lbl_autolight_hint.setText(self.AUTO_LIGHT_HINTS.get(self.c.auto_light_source(), ""))
        neural, name = self.c.model_info()
        if neural:
            self.lbl_model_badge.setObjectName("Badge")
            self.lbl_model_badge.setText("AI")
            self.lbl_model_name.setText(name)
            self.lbl_model_hint.setText("Accurate person segmentation is active. Everything runs on this computer.")
        else:
            self.lbl_model_badge.setObjectName("BadgeWarn")
            self.lbl_model_badge.setText("Basic")
            self.lbl_model_name.setText("No AI model installed")
            self.lbl_model_hint.setText(
                "Background effects use a fixed head-and-shoulders shape, so edges will not follow you. "
                "Install the AI model once with:  selficamera --install-model"
            )
        self.lbl_model_badge.style().unpolish(self.lbl_model_badge)
        self.lbl_model_badge.style().polish(self.lbl_model_badge)
        self.sw_autoframe.setEnabled(neural)

    # ----------------------------------------------------------------- light
    def _page_light(self) -> QWidget:
        page, layout = self._page("Light & Color", "Look good in any room. Double-click a slider to reset it.")
        lc, ll = card(None, page)
        al_row, self.sw_autolight = switch_row("Auto light", "Brightens dim rooms automatically and smoothly.", lc)
        self.lbl_autolight_hint = al_row.findChild(QLabel, "Hint")
        self.sw_autolight.toggled.connect(lambda v: self._set("auto_light", v))
        self._bind("auto_light", self.sw_autolight.set_checked_silently)
        ll.addWidget(al_row)
        self.sl_brightness = SliderRow("Brightness", -50, 50, 0, 0, _fmt_signed, lc)
        self.sl_contrast = SliderRow("Contrast", -50, 50, 0, 0, _fmt_signed, lc)
        self.sl_saturation = SliderRow("Saturation", -100, 100, 0, 0, _fmt_signed, lc)
        self.sl_warmth = SliderRow("Warmth", -50, 50, 0, 0, _fmt_signed, lc)
        for key, sl in (
            ("brightness", self.sl_brightness),
            ("contrast", self.sl_contrast),
            ("saturation", self.sl_saturation),
            ("warmth", self.sl_warmth),
        ):
            sl.valueChanged.connect(lambda v, k=key: self._set(k, v))
            self._bind(key, sl.set_value_silently)
            ll.addWidget(sl)
        btn = QPushButton("Reset light & color", lc)
        btn.clicked.connect(lambda: self.c.reset_light())
        ll.addWidget(btn, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(lc)
        layout.addStretch(1)
        return page

    # ---------------------------------------------------------------- scenes
    def _page_scenes(self) -> QWidget:
        page, layout = self._page(
            "Scenes",
            "Save a look and position, then switch with one click, the tray, or  selficamera --scene NAME. "
            "Example: a big centered 'Intro' and a small 'Tutorial' in the corner.",
        )
        sc, sl = card(None, page)
        self.list_scenes = QListWidget(sc)
        self.list_scenes.setObjectName("SceneList")
        self.list_scenes.setMinimumHeight(180)
        self.list_scenes.itemDoubleClicked.connect(lambda it: self.c.apply_scene(it.text()))
        sl.addWidget(self.list_scenes)
        row = QHBoxLayout()
        self.btn_scene_save = QPushButton("Save current as…", sc)
        self.btn_scene_save.setObjectName("Primary")
        self.btn_scene_save.setIcon(icons.icon("plus", 16, "#FFFFFF"))
        self.btn_scene_save.clicked.connect(self._save_scene)
        self.btn_scene_apply = QPushButton("Apply", sc)
        self.btn_scene_apply.clicked.connect(self._apply_scene)
        self.btn_scene_delete = QPushButton("Delete", sc)
        self.btn_scene_delete.setObjectName("Danger")
        self.btn_scene_delete.clicked.connect(self._delete_scene)
        row.addWidget(self.btn_scene_save)
        row.addStretch(1)
        row.addWidget(self.btn_scene_apply)
        row.addWidget(self.btn_scene_delete)
        sl.addLayout(row)
        layout.addWidget(sc)
        layout.addStretch(1)
        return page

    def refresh_scenes(self) -> None:
        self.list_scenes.clear()
        names = self.c.scene_names()
        for name in names:
            self.list_scenes.addItem(QListWidgetItem(icons.icon("layers", 16, theme.TEXT_MUTED), name))
        has = bool(names)
        self.btn_scene_apply.setEnabled(has)
        self.btn_scene_delete.setEnabled(has)

    def _selected_scene(self) -> Optional[str]:
        item = self.list_scenes.currentItem()
        return item.text() if item else None

    def _save_scene(self) -> None:
        name, ok = QInputDialog.getText(self, "Save scene", "Scene name:", text=f"Scene {len(self.c.scene_names()) + 1}")
        if ok and name.strip():
            self.c.save_scene(name.strip())

    def _apply_scene(self) -> None:
        name = self._selected_scene()
        if name:
            self.c.apply_scene(name)

    def _delete_scene(self) -> None:
        name = self._selected_scene()
        if name and QMessageBox.question(self, "Delete scene", f"Delete scene “{name}”?") == QMessageBox.StandardButton.Yes:
            self.c.delete_scene(name)

    # ------------------------------------------------------------- shortcuts
    def _page_shortcuts(self) -> QWidget:
        page, layout = self._page("Shortcuts", "Control the camera while recording without touching it.")
        kc, kl = card("Keys", page)
        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(8)
        for i, (keys, desc) in enumerate(SHORTCUT_ROWS):
            k = QLabel(keys, kc)
            k.setStyleSheet(
                f"background:{theme.SURFACE_2}; border:1px solid {theme.BORDER}; border-radius:6px; padding:3px 8px; font-weight:700;"
            )
            grid.addWidget(k, i, 0, Qt.AlignmentFlag.AlignLeft)
            grid.addWidget(QLabel(desc, kc), i, 1)
        grid.setColumnStretch(1, 1)
        kl.addLayout(grid)
        layout.addWidget(kc)

        gc, gl = card("GNOME (Wayland)", page)
        txt = QLabel(
            "GNOME on Wayland does not let apps grab global keys. Install the shortcuts above as GNOME "
            "custom shortcuts with one click. You can change them later in Settings → Keyboard.",
            gc,
        )
        txt.setWordWrap(True)
        txt.setObjectName("Hint")
        gl.addWidget(txt)
        row = QHBoxLayout()
        self.btn_install_keys = QPushButton("Install GNOME shortcuts", gc)
        self.btn_install_keys.setObjectName("Primary")
        self.btn_install_keys.clicked.connect(self._install_shortcuts)
        self.btn_remove_keys = QPushButton("Remove", gc)
        self.btn_remove_keys.clicked.connect(self._remove_shortcuts)
        row.addWidget(self.btn_install_keys)
        row.addWidget(self.btn_remove_keys)
        row.addStretch(1)
        gl.addLayout(row)
        self.lbl_keys_status = QLabel("", gc)
        self.lbl_keys_status.setObjectName("Hint")
        self.lbl_keys_status.setWordWrap(True)
        gl.addWidget(self.lbl_keys_status)
        layout.addWidget(gc)

        cc, cl = card("Command line", page)
        cli = QLabel(
            "selficamera --toggle · --spotlight · --background-cycle · --snap 1-5 · --scene NAME · "
            "--set background_mode=blur · --status",
            cc,
        )
        cli.setWordWrap(True)
        cli.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        cli.setStyleSheet("font-family: monospace; font-size: 12px;")
        cl.addWidget(cli)
        layout.addWidget(cc)
        layout.addStretch(1)
        return page

    def refresh_shortcut_status(self) -> None:
        available, installed, message = self.c.gnome_shortcuts_state()
        self.btn_install_keys.setEnabled(available)
        self.btn_remove_keys.setEnabled(available and installed)
        self.btn_install_keys.setText("Reinstall GNOME shortcuts" if installed else "Install GNOME shortcuts")
        self.lbl_keys_status.setText(message)

    def _install_shortcuts(self) -> None:
        ok, msg = self.c.install_gnome_shortcuts()
        self.refresh_shortcut_status()
        if not ok:
            self.lbl_keys_status.setText(msg)

    def _remove_shortcuts(self) -> None:
        self.c.remove_gnome_shortcuts()
        self.refresh_shortcut_status()

    # --------------------------------------------------------------- general
    def _page_general(self) -> QWidget:
        page, layout = self._page("General", "Window behavior and startup.")
        if getattr(self.c, "limited_wayland", False):
            warn, wl0 = card("Limited mode", page)
            msg = QLabel(
                "SelfiCamera is running as a native Wayland window, so GNOME won't keep it on top or let it "
                "snap to corners. Install the missing library and restart:\n\n    sudo apt install libxcb-cursor0",
                warn,
            )
            msg.setWordWrap(True)
            msg.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            msg.setStyleSheet(f"color: {theme.WARNING};")
            wl0.addWidget(msg)
            layout.addWidget(warn)
        wc, wl = card("Window", page)
        r1, self.sw_on_top = switch_row("Always on top", "Keep the camera above other windows, including full-screen apps.", wc)
        self.sw_on_top.toggled.connect(lambda v: self._set("always_on_top", v))
        self._bind("always_on_top", self.sw_on_top.set_checked_silently)
        wl.addWidget(r1)
        r2, self.sw_ghost = switch_row(
            "Click-through", "The camera ignores the mouse so you can click what is underneath. Turn off from the tray or Super+Alt+X.", wc
        )
        self.sw_ghost.toggled.connect(lambda v: self._set("click_through", v))
        self._bind("click_through", self.sw_ghost.set_checked_silently)
        wl.addWidget(r2)
        r3, self.sw_hover = switch_row(
            "Show controls on hover", "Turn off for a perfectly clean camera while recording. Right-click still works.", wc
        )
        self.sw_hover.toggled.connect(lambda v: self._set("show_controls_on_hover", v))
        self._bind("show_controls_on_hover", self.sw_hover.set_checked_silently)
        wl.addWidget(r3)
        layout.addWidget(wc)

        sc, sl = card("Startup", page)
        r4, self.sw_autostart = switch_row("Start at login", None, sc)
        self.sw_autostart.set_checked_silently(self.c.autostart_enabled())
        self.sw_autostart.toggled.connect(lambda v: self.c.set_autostart(v))
        sl.addWidget(r4)
        layout.addWidget(sc)

        ac, al = card("About", page)
        self.lbl_paths = QLabel("", ac)
        self.lbl_paths.setObjectName("Hint")
        self.lbl_paths.setWordWrap(True)
        self.lbl_paths.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.lbl_paths.setText(
            f"SelfiCamera {__version__}. No network access, no telemetry.\n"
            f"Settings: {self.c.config_path()}\nLog: {self.c.log_path()}"
        )
        al.addWidget(self.lbl_paths)
        row = QHBoxLayout()
        btn_reset = QPushButton("Reset all settings", ac)
        btn_reset.setObjectName("Danger")
        btn_reset.clicked.connect(self._reset_all)
        btn_quit = QPushButton("Quit SelfiCamera", ac)
        btn_quit.setIcon(icons.icon("power", 16))
        btn_quit.clicked.connect(lambda: self.c.quit())
        row.addWidget(btn_reset)
        row.addStretch(1)
        row.addWidget(btn_quit)
        al.addLayout(row)
        layout.addWidget(ac)
        layout.addStretch(1)
        return page

    def _reset_all(self) -> None:
        answer = QMessageBox.question(
            self, "Reset all settings", "Reset every setting to its default? Your saved scenes are kept."
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.c.reset_all()

    # ----------------------------------------------------------------- misc
    def open(self, page: Optional[str] = None) -> None:
        if page:
            self.show_page(page)
        self.sync_all()
        self.show()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event: QCloseEvent) -> None:
        # Closing settings only hides the window; the app keeps running.
        event.ignore()
        self.hide()
