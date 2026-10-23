"""On-screen floating settings & controls panel for camera, lighting, blur, and window management."""

from __future__ import annotations

import logging
from typing import Optional, Tuple
from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QFont, QGuiApplication, QMouseEvent
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from selficamera.capture.v4l2_devices import V4L2DeviceScanner

logger = logging.getLogger(__name__)

PANEL_STYLESHEET = """
QWidget#panel_container {
    background-color: #1E1E2E;
    border: 1px solid rgba(255, 255, 255, 25);
    border-radius: 12px;
}
QFrame.control_card {
    background-color: #181825;
    border: 1px solid rgba(255, 255, 255, 15);
    border-radius: 8px;
    padding: 2px;
}
QLabel {
    color: #CDD6F4;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    font-size: 11px;
}
QLabel.card_title {
    color: #89B4FA;
    font-weight: 700;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
QLabel.readout {
    color: #A6ADC8;
    font-family: monospace;
    font-size: 11px;
    font-weight: 600;
}
QLabel.hint {
    color: #6C7086;
    font-size: 10px;
    font-style: italic;
}
QCheckBox {
    color: #CDD6F4;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    font-size: 11px;
    spacing: 6px;
}
QCheckBox::indicator {
    width: 15px;
    height: 15px;
    border-radius: 3px;
    border: 1px solid #45475A;
    background-color: #1E1E2E;
}
QCheckBox::indicator:checked {
    background-color: #89B4FA;
    border: 1px solid #89B4FA;
}
QSlider::groove:horizontal {
    height: 5px;
    background-color: #313244;
    border-radius: 2px;
}
QSlider::sub-page:horizontal {
    background-color: #89B4FA;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background-color: #CDD6F4;
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}
QSlider::handle:horizontal:hover {
    background-color: #B4BEFE;
}
QPushButton {
    background-color: #313244;
    color: #CDD6F4;
    border: 1px solid rgba(255, 255, 255, 20);
    border-radius: 6px;
    padding: 3px 8px;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    font-size: 11px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #45475A;
    color: #89B4FA;
}
QPushButton:pressed {
    background-color: rgba(137, 180, 250, 60);
}
QPushButton:checked {
    background-color: #89B4FA;
    color: #11111B;
}
QComboBox {
    background-color: #313244;
    color: #CDD6F4;
    border: 1px solid rgba(255, 255, 255, 20);
    border-radius: 6px;
    padding: 3px 8px;
    font-size: 11px;
}
QComboBox:hover {
    border-color: #89B4FA;
}
QComboBox QAbstractItemView {
    background-color: #1E1E2E;
    color: #CDD6F4;
    selection-background-color: #313244;
    selection-color: #89B4FA;
    border: 1px solid #45475A;
    border-radius: 6px;
    outline: none;
}
"""


class SettingsPanel(QWidget):
    """Standalone, top-level floating settings & controls panel for SelfiCamera."""

    # Explicit signals mandated by specification
    diameter_changed = Signal(int)
    manual_gamma_changed = Signal(float)
    target_luminance_changed = Signal(float)
    auto_light_toggled = Signal(bool)
    blur_tier_selected = Signal(int)
    blur_intensity_changed = Signal(int)
    device_selected = Signal(str)
    resolution_selected = Signal(int, int)
    mirror_toggled = Signal(bool)
    always_on_top_toggled = Signal(bool)
    ghost_mode_toggled = Signal(bool)
    reset_defaults_requested = Signal()
    corner_snap_requested = Signal(int)
    snap_corner_requested = corner_snap_requested  # Semantic alias

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(
            parent,
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedWidth(330)

        self._dragging_panel = False
        self._drag_start_pos = QPoint()
        self._syncing_blur = False

        self._build_ui()
        self.setStyleSheet(PANEL_STYLESHEET)

    def _build_ui(self) -> None:
        """Construct the 5 control cards and title bar inside the panel."""
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(10, 10, 10, 10)
        root_layout.setSpacing(0)

        # Container with soft drop shadow
        self.container = QWidget(self)
        self.container.setObjectName("panel_container")
        shadow = QGraphicsDropShadowEffect(self.container)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 140))
        shadow.setOffset(0, 4)
        self.container.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(8)

        # 0. Custom Draggable Title Bar
        layout.addLayout(self._build_title_bar())

        # 1. Card 1: Lighting & Exposure
        layout.addWidget(self._build_card_lighting())

        # 2. Card 2: Background Blur
        layout.addWidget(self._build_card_blur())

        # 3. Card 3: Bubble Size
        layout.addWidget(self._build_card_size())

        # 4. Card 4: Camera & Video
        layout.addWidget(self._build_card_camera())

        # 5. Card 5: Window Management
        layout.addWidget(self._build_card_window_mgmt())

        # 6. Footer Buttons
        layout.addLayout(self._build_footer())

        root_layout.addWidget(self.container)

    def _build_title_bar(self) -> QHBoxLayout:
        """Create custom draggable title bar with close button."""
        title_box = QHBoxLayout()
        title_box.setContentsMargins(0, 0, 0, 2)

        lbl_icon_title = QLabel("⚙ SelfiCamera Settings", self.container)
        font = lbl_icon_title.font()
        font.setBold(True)
        font.setPointSize(11)
        lbl_icon_title.setFont(font)
        lbl_icon_title.setStyleSheet("color: #CDD6F4;")

        self.btn_title_close = QPushButton("✕", self.container)
        self.btn_title_close.setFixedSize(22, 22)
        self.btn_title_close.setToolTip("Close Settings Panel")
        self.btn_title_close.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #A6ADC8;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                color: #F38BA8;
                background: rgba(243, 139, 168, 30);
                border-radius: 4px;
            }
        """)
        self.btn_title_close.clicked.connect(self.hide)

        title_box.addWidget(lbl_icon_title)
        title_box.addStretch()
        title_box.addWidget(self.btn_title_close)
        return title_box

    # --- Card 1: Lighting & Exposure ---
    def _build_card_lighting(self) -> QFrame:
        card = QFrame(self.container)
        card.setProperty("class", "control_card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(5)

        lbl_card = QLabel("Lighting & Exposure", card)
        lbl_card.setProperty("class", "card_title")
        layout.addWidget(lbl_card)

        # Auto-Light Boost CheckBox
        self.cb_auto_light = QCheckBox("Auto-Light Boost (Adaptive)", card)
        self.cb_auto_light.setChecked(True)
        self.cb_auto_light.toggled.connect(self.auto_light_toggled)
        layout.addWidget(self.cb_auto_light)

        # Manual Brightness / Gamma Slider (40 - 220 -> 0.40x to 2.20x)
        gamma_header = QHBoxLayout()
        lbl_g = QLabel("Brightness / Gamma:", card)
        self.lbl_gamma = QLabel("1.00x", card)
        self.lbl_gamma.setProperty("class", "readout")
        self.btn_gamma_reset = QPushButton("↺", card)
        self.btn_gamma_reset.setToolTip("Reset Gamma to 1.00x")
        self.btn_gamma_reset.setFixedSize(20, 18)
        self.btn_gamma_reset.clicked.connect(lambda: self.slider_gamma.setValue(100))
        gamma_header.addWidget(lbl_g)
        gamma_header.addStretch()
        gamma_header.addWidget(self.lbl_gamma)
        gamma_header.addWidget(self.btn_gamma_reset)
        layout.addLayout(gamma_header)

        self.slider_gamma = QSlider(Qt.Orientation.Horizontal, card)
        self.slider_gamma.setRange(40, 220)
        self.slider_gamma.setValue(100)
        self.slider_gamma.valueChanged.connect(self._on_gamma_slider_changed)
        layout.addWidget(self.slider_gamma)

        # Target Luminance Slider (50 - 220, default 125)
        lum_header = QHBoxLayout()
        lbl_l = QLabel("Target Luminance:", card)
        self.lbl_luminance = QLabel("125", card)
        self.lbl_luminance.setProperty("class", "readout")
        lum_header.addWidget(lbl_l)
        lum_header.addStretch()
        lum_header.addWidget(self.lbl_luminance)
        layout.addLayout(lum_header)

        self.slider_luminance = QSlider(Qt.Orientation.Horizontal, card)
        self.slider_luminance.setRange(50, 220)
        self.slider_luminance.setValue(125)
        self.slider_luminance.valueChanged.connect(self._on_luminance_slider_changed)
        layout.addWidget(self.slider_luminance)

        return card

    def _on_gamma_slider_changed(self, val: int) -> None:
        gamma = val / 100.0
        self.lbl_gamma.setText(f"{gamma:.2f}x")
        self.manual_gamma_changed.emit(gamma)

    def _on_luminance_slider_changed(self, val: int) -> None:
        self.lbl_luminance.setText(str(val))
        self.target_luminance_changed.emit(float(val))

    # --- Card 2: Background Blur ---
    def _build_card_blur(self) -> QFrame:
        card = QFrame(self.container)
        card.setProperty("class", "control_card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(5)

        lbl_card = QLabel("Background Blur", card)
        lbl_card.setProperty("class", "card_title")
        layout.addWidget(lbl_card)

        # Tier Buttons Row: [Off], [Subtle], [Balanced], [Heavy]
        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)
        self.blur_btn_group = QButtonGroup(card)
        self.blur_btn_group.setExclusive(True)

        tiers = [(0, "Off"), (1, "Subtle"), (2, "Balanced"), (3, "Heavy")]
        self.blur_buttons = {}
        for tier_id, name in tiers:
            btn = QPushButton(name, card)
            btn.setCheckable(True)
            if tier_id == 2:
                btn.setChecked(True)
            self.blur_btn_group.addButton(btn, tier_id)
            btn_row.addWidget(btn)
            self.blur_buttons[tier_id] = btn

        self.blur_btn_group.idClicked.connect(self._on_blur_tier_btn_clicked)
        layout.addLayout(btn_row)

        # Blur Intensity Continuous Slider (0 - 100)
        blur_header = QHBoxLayout()
        lbl_i = QLabel("Blur Intensity:", card)
        self.lbl_blur = QLabel("50%", card)
        self.lbl_blur.setProperty("class", "readout")
        blur_header.addWidget(lbl_i)
        blur_header.addStretch()
        blur_header.addWidget(self.lbl_blur)
        layout.addLayout(blur_header)

        self.slider_blur = QSlider(Qt.Orientation.Horizontal, card)
        self.slider_blur.setRange(0, 100)
        self.slider_blur.setValue(50)
        self.slider_blur.valueChanged.connect(self._on_blur_slider_changed)
        layout.addWidget(self.slider_blur)

        return card

    def _on_blur_tier_btn_clicked(self, tier_id: int) -> None:
        """Button click maps to discrete intensity and syncs slider without feedback loop."""
        if self._syncing_blur:
            return
        self._syncing_blur = True
        try:
            tier_to_intensity = {0: 0, 1: 25, 2: 50, 3: 85}
            val = tier_to_intensity.get(tier_id, 50)
            self.slider_blur.setValue(val)
            self.lbl_blur.setText(f"{val}%")
            self.blur_tier_selected.emit(tier_id)
            self.blur_intensity_changed.emit(val)
        finally:
            self._syncing_blur = False

    def _on_blur_slider_changed(self, val: int) -> None:
        """Slider change updates readout and syncs active tier button without feedback loop."""
        if self._syncing_blur:
            return
        self._syncing_blur = True
        try:
            self.lbl_blur.setText(f"{val}%")
            if val == 0:
                tier = 0
            elif val < 38:
                tier = 1
            elif val < 68:
                tier = 2
            else:
                tier = 3

            btn = self.blur_buttons.get(tier)
            if btn and not btn.isChecked():
                btn.setChecked(True)

            self.blur_intensity_changed.emit(val)
            self.blur_tier_selected.emit(tier)
        finally:
            self._syncing_blur = False

    # --- Card 3: Bubble Size ---
    def _build_card_size(self) -> QFrame:
        card = QFrame(self.container)
        card.setProperty("class", "control_card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(5)

        lbl_card = QLabel("Bubble Size", card)
        lbl_card.setProperty("class", "card_title")
        layout.addWidget(lbl_card)

        # Diameter Slider Header
        size_header = QHBoxLayout()
        lbl_d = QLabel("Diameter:", card)
        self.lbl_diameter = QLabel("260 px", card)
        self.lbl_diameter.setProperty("class", "readout")
        size_header.addWidget(lbl_d)
        size_header.addStretch()
        size_header.addWidget(self.lbl_diameter)
        layout.addLayout(size_header)

        # Continuous Diameter Slider (120 - 600 px) with [-] and [+] step buttons
        slider_row = QHBoxLayout()
        slider_row.setSpacing(6)

        self.btn_size_minus = QPushButton("−", card)
        self.btn_size_minus.setFixedSize(26, 26)
        self.btn_size_minus.setToolTip("Step Size Smaller (-25px)")
        self.btn_size_minus.clicked.connect(lambda: self.slider_diameter.setValue(self.slider_diameter.value() - 25))

        self.slider_diameter = QSlider(Qt.Orientation.Horizontal, card)
        self.slider_diameter.setRange(120, 600)
        self.slider_diameter.setValue(260)
        self.slider_diameter.valueChanged.connect(self._on_diameter_slider_changed)

        self.btn_size_plus = QPushButton("+", card)
        self.btn_size_plus.setFixedSize(26, 26)
        self.btn_size_plus.setToolTip("Step Size Larger (+25px)")
        self.btn_size_plus.clicked.connect(lambda: self.slider_diameter.setValue(self.slider_diameter.value() + 25))

        slider_row.addWidget(self.btn_size_minus)
        slider_row.addWidget(self.slider_diameter, 1)
        slider_row.addWidget(self.btn_size_plus)
        layout.addLayout(slider_row)

        # Preset Buttons: [160 px], [260 px], [380 px]
        preset_row = QHBoxLayout()
        preset_row.setSpacing(4)
        for preset in [160, 260, 380]:
            btn = QPushButton(f"{preset} px", card)
            btn.clicked.connect(lambda checked, p=preset: self.slider_diameter.setValue(p))
            preset_row.addWidget(btn)
        layout.addLayout(preset_row)

        return card

    def _on_diameter_slider_changed(self, val: int) -> None:
        self.lbl_diameter.setText(f"{val} px")
        self.diameter_changed.emit(val)

    # --- Card 4: Camera & Video ---
    def _build_card_camera(self) -> QFrame:
        card = QFrame(self.container)
        card.setProperty("class", "control_card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(5)

        lbl_card = QLabel("Camera & Video", card)
        lbl_card.setProperty("class", "card_title")
        layout.addWidget(lbl_card)

        # Device selection row with refresh button
        dev_row = QHBoxLayout()
        dev_row.setSpacing(4)
        self.combo_device = QComboBox(card)
        self.combo_device.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContentsOnFirstShow)
        self.btn_rescan_dev = QPushButton("🔄", card)
        self.btn_rescan_dev.setToolTip("Rescan V4L2 Camera Devices")
        self.btn_rescan_dev.setFixedSize(24, 24)
        self.btn_rescan_dev.clicked.connect(lambda: self.populate_devices(self.combo_device.currentData() or ""))

        dev_row.addWidget(self.combo_device, 1)
        dev_row.addWidget(self.btn_rescan_dev)
        layout.addLayout(dev_row)

        self.combo_device.activated.connect(self._on_device_combo_activated)

        # Resolution dropdown
        res_row = QHBoxLayout()
        res_row.setSpacing(4)
        lbl_r = QLabel("Resolution:", card)
        self.combo_res = QComboBox(card)
        self.combo_res.addItem("640 x 480 (SD)", (640, 480))
        self.combo_res.addItem("1280 x 720 (HD)", (1280, 720))
        self.combo_res.addItem("1920 x 1080 (FHD)", (1920, 1080))
        self.combo_res.setCurrentIndex(1)  # Default 720p
        self.combo_res.activated.connect(self._on_res_combo_activated)

        res_row.addWidget(lbl_r)
        res_row.addWidget(self.combo_res, 1)
        layout.addLayout(res_row)

        # Horizontal Mirror CheckBox
        self.cb_mirror = QCheckBox("Horizontal Mirror (Flip)", card)
        self.cb_mirror.setChecked(True)
        self.cb_mirror.toggled.connect(self.mirror_toggled)
        layout.addWidget(self.cb_mirror)

        return card

    def populate_devices(self, current_path: str = "/dev/video0") -> None:
        """Scan and populate available V4L2 cameras in combo box."""
        self.combo_device.blockSignals(True)
        self.combo_device.clear()
        devices = V4L2DeviceScanner.list_devices()

        if not devices:
            self.combo_device.addItem("No cameras detected (Mock Mode)", "/dev/video0")
        else:
            selected_idx = 0
            for i, dev in enumerate(devices):
                self.combo_device.addItem(dev.display_name, dev.device_path)
                if dev.device_path == current_path:
                    selected_idx = i
            self.combo_device.setCurrentIndex(selected_idx)

        self.combo_device.blockSignals(False)

    def _on_device_combo_activated(self, index: int) -> None:
        dev_path = self.combo_device.itemData(index)
        if dev_path:
            self.device_selected.emit(str(dev_path))

    def _on_res_combo_activated(self, index: int) -> None:
        res = self.combo_res.itemData(index)
        if res and isinstance(res, (tuple, list)):
            self.resolution_selected.emit(int(res[0]), int(res[1]))

    # --- Card 5: Window Management ---
    def _build_card_window_mgmt(self) -> QFrame:
        card = QFrame(self.container)
        card.setProperty("class", "control_card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(5)

        lbl_card = QLabel("Window Management", card)
        lbl_card.setProperty("class", "card_title")
        layout.addWidget(lbl_card)

        # Snap & Position Section
        lbl_snap = QLabel("Position & Snap:", card)
        layout.addWidget(lbl_snap)

        grid_snap = QGridLayout()
        grid_snap.setSpacing(4)
        grid_snap.setContentsMargins(0, 0, 0, 2)

        self.btn_snap_tl = QPushButton("↖ TL", card)
        self.btn_snap_tl.setToolTip("Snap to Top-Left corner (Super+Alt+1)")
        self.btn_snap_tl.clicked.connect(lambda: self.corner_snap_requested.emit(1))

        self.btn_snap_center = QPushButton("⏺ Center", card)
        self.btn_snap_center.setToolTip("Snap to screen center")
        self.btn_snap_center.clicked.connect(lambda: self.corner_snap_requested.emit(5))

        self.btn_snap_tr = QPushButton("↗ TR", card)
        self.btn_snap_tr.setToolTip("Snap to Top-Right corner (Super+Alt+2)")
        self.btn_snap_tr.clicked.connect(lambda: self.corner_snap_requested.emit(2))

        self.btn_snap_bl = QPushButton("↙ BL", card)
        self.btn_snap_bl.setToolTip("Snap to Bottom-Left corner (Super+Alt+3)")
        self.btn_snap_bl.clicked.connect(lambda: self.corner_snap_requested.emit(3))

        self.btn_snap_br = QPushButton("↘ BR", card)
        self.btn_snap_br.setToolTip("Snap to Bottom-Right corner (Super+Alt+4)")
        self.btn_snap_br.clicked.connect(lambda: self.corner_snap_requested.emit(4))

        grid_snap.addWidget(self.btn_snap_tl, 0, 0)
        grid_snap.addWidget(self.btn_snap_center, 0, 1)
        grid_snap.addWidget(self.btn_snap_tr, 0, 2)
        grid_snap.addWidget(self.btn_snap_bl, 1, 0)
        grid_snap.addWidget(self.btn_snap_br, 1, 2)
        layout.addLayout(grid_snap)

        lbl_drag_hint = QLabel("Move: Click and drag anywhere inside camera bubble", card)
        lbl_drag_hint.setProperty("class", "hint")
        layout.addWidget(lbl_drag_hint)

        # Always-On-Top CheckBox
        self.cb_always_on_top = QCheckBox("Always-On-Top (Pin above windows)", card)
        self.cb_always_on_top.setChecked(True)
        self.cb_always_on_top.toggled.connect(self.always_on_top_toggled)
        layout.addWidget(self.cb_always_on_top)

        # Click-Through Ghost Mode CheckBox
        self.cb_ghost_mode = QCheckBox("Click-Through Ghost Mode", card)
        self.cb_ghost_mode.setChecked(False)
        self.cb_ghost_mode.toggled.connect(self.ghost_mode_toggled)
        layout.addWidget(self.cb_ghost_mode)

        lbl_note = QLabel("Exit Ghost Mode: Press Super+Alt+X", card)
        lbl_note.setProperty("class", "hint")
        layout.addWidget(lbl_note)

        return card

    # --- Footer Buttons ---
    def _build_footer(self) -> QHBoxLayout:
        footer = QHBoxLayout()
        footer.setContentsMargins(0, 4, 0, 0)
        footer.setSpacing(8)

        self.btn_reset_defaults = QPushButton("Reset Defaults", self.container)
        self.btn_reset_defaults.setToolTip("Reset all settings to initial defaults")
        self.btn_reset_defaults.clicked.connect(self.reset_defaults_requested)

        self.btn_footer_close = QPushButton("Close", self.container)
        self.btn_footer_close.clicked.connect(self.hide)

        footer.addWidget(self.btn_reset_defaults)
        footer.addStretch()
        footer.addWidget(self.btn_footer_close)
        return footer

    # --- Dynamic Positioning Alongside Overlay ---
    def position_alongside_overlay(self, overlay: QWidget) -> None:
        """Position panel docking to right of overlay, flipping to left on screen edge overflow."""
        screen = overlay.screen() or QGuiApplication.primaryScreen()
        avail_geo = screen.availableGeometry() if screen else QRect(0, 0, 1920, 1080)

        panel_w = max(self.width(), 330)
        panel_h = max(self.height(), 460)

        # Dock to right of overlay with 12px margin
        target_x = overlay.x() + overlay.width() + 12
        if target_x + panel_w > avail_geo.right():
            # Flip to left of overlay
            target_x = overlay.x() - panel_w - 12

        # Clamp inside visible screen bounds
        clamped_x = max(avail_geo.left() + 8, min(avail_geo.right() - panel_w - 8, target_x))
        clamped_y = max(avail_geo.top() + 8, min(avail_geo.bottom() - panel_h - 8, overlay.y()))

        self.move(clamped_x, clamped_y)

    # --- Draggable Window Event Handlers ---
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging_panel = True
            self._drag_start_pos = event.globalPosition().toPoint() - self.pos()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._dragging_panel and (event.buttons() & Qt.MouseButton.LeftButton):
            self.move(event.globalPosition().toPoint() - self._drag_start_pos)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging_panel = False
            event.accept()
            return
        super().mouseReleaseEvent(event)

    # --- State Synchronization Setters (Prevent Feedback Loops) ---
    def set_diameter_value(self, val: int) -> None:
        """Update diameter slider and readout without re-emitting signals."""
        self.slider_diameter.blockSignals(True)
        self.slider_diameter.setValue(int(val))
        self.lbl_diameter.setText(f"{int(val)} px")
        self.slider_diameter.blockSignals(False)

    def set_manual_gamma_value(self, val: float) -> None:
        """Update gamma slider and readout without re-emitting signals."""
        int_val = int(round(val * 100))
        self.slider_gamma.blockSignals(True)
        self.slider_gamma.setValue(int_val)
        self.lbl_gamma.setText(f"{val:.2f}x")
        self.slider_gamma.blockSignals(False)

    def set_target_luminance_value(self, val: float) -> None:
        """Update luminance slider and readout without re-emitting signals."""
        self.slider_luminance.blockSignals(True)
        self.slider_luminance.setValue(int(round(val)))
        self.lbl_luminance.setText(str(int(round(val))))
        self.slider_luminance.blockSignals(False)

    def set_auto_light_checked(self, checked: bool) -> None:
        """Update auto-light checkbox without re-emitting signals."""
        self.cb_auto_light.blockSignals(True)
        self.cb_auto_light.setChecked(checked)
        self.cb_auto_light.blockSignals(False)

    def set_blur_intensity_value(self, val: int) -> None:
        """Update blur intensity and corresponding tier button without re-emitting signals."""
        self._syncing_blur = True
        try:
            self.slider_blur.setValue(int(val))
            self.lbl_blur.setText(f"{int(val)}%")
            if val == 0:
                tier = 0
            elif val < 38:
                tier = 1
            elif val < 68:
                tier = 2
            else:
                tier = 3
            btn = self.blur_buttons.get(tier)
            if btn:
                btn.setChecked(True)
        finally:
            self._syncing_blur = False

    def set_blur_tier_value(self, tier: int) -> None:
        """Update blur tier buttons and slider without re-emitting signals."""
        self._syncing_blur = True
        try:
            btn = self.blur_buttons.get(tier)
            if btn:
                btn.setChecked(True)
            tier_to_intensity = {0: 0, 1: 25, 2: 50, 3: 85}
            val = tier_to_intensity.get(tier, 50)
            self.slider_blur.setValue(val)
            self.lbl_blur.setText(f"{val}%")
        finally:
            self._syncing_blur = False

    def set_device_selection(self, device_path: str) -> None:
        """Select device in combo box without emitting signal."""
        self.combo_device.blockSignals(True)
        idx = self.combo_device.findData(device_path)
        if idx >= 0:
            self.combo_device.setCurrentIndex(idx)
        self.combo_device.blockSignals(False)

    def set_resolution_selection(self, width: int, height: int) -> None:
        """Select resolution in combo box without emitting signal."""
        self.combo_res.blockSignals(True)
        idx = self.combo_res.findData((width, height))
        if idx >= 0:
            self.combo_res.setCurrentIndex(idx)
        self.combo_res.blockSignals(False)

    def set_mirror_checked(self, checked: bool) -> None:
        """Update mirror checkbox without emitting signal."""
        self.cb_mirror.blockSignals(True)
        self.cb_mirror.setChecked(checked)
        self.cb_mirror.blockSignals(False)

    def set_always_on_top_checked(self, checked: bool) -> None:
        """Update always-on-top checkbox without emitting signal."""
        self.cb_always_on_top.blockSignals(True)
        self.cb_always_on_top.setChecked(checked)
        self.cb_always_on_top.blockSignals(False)

    def set_ghost_mode_checked(self, checked: bool) -> None:
        """Update ghost mode checkbox without emitting signal."""
        self.cb_ghost_mode.blockSignals(True)
        self.cb_ghost_mode.setChecked(checked)
        self.cb_ghost_mode.blockSignals(False)
