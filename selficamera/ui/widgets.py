"""Reusable settings widgets: switch, labelled slider, segmented control, color swatches."""

from __future__ import annotations

from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRectF, QSize, Qt, Property, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter
from PySide6.QtWidgets import (
    QAbstractButton,
    QButtonGroup,
    QColorDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from selficamera.ui import theme


class Switch(QAbstractButton):
    """An iOS/GNOME-style toggle switch."""

    def __init__(self, parent: Optional[QWidget] = None, checked: bool = False) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pos = 1.0 if checked else 0.0
        self._anim = QPropertyAnimation(self, b"knob", self)
        self._anim.setDuration(140)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.toggled.connect(self._animate)

    def sizeHint(self) -> QSize:
        return QSize(40, 22)

    def _get_knob(self) -> float:
        return self._pos

    def _set_knob(self, value: float) -> None:
        self._pos = value
        self.update()

    knob = Property(float, _get_knob, _set_knob)

    def _animate(self, checked: bool) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()

    def set_checked_silently(self, checked: bool) -> None:
        self.blockSignals(True)
        self.setChecked(checked)
        self.blockSignals(False)
        self._anim.stop()
        self._set_knob(1.0 if checked else 0.0)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = QRectF(1, 1, 38, 20)
        off, on = QColor(theme.SURFACE_3), QColor(theme.ACCENT)
        t = self._pos
        track = QColor(
            int(off.red() + (on.red() - off.red()) * t),
            int(off.green() + (on.green() - off.green()) * t),
            int(off.blue() + (on.blue() - off.blue()) * t),
        )
        if not self.isEnabled():
            track.setAlpha(110)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(track)
        p.drawRoundedRect(r, 10, 10)
        x = 3 + t * 18
        p.setBrush(QColor("white"))
        p.drawEllipse(QRectF(x, 3, 16, 16))


class SliderRow(QWidget):
    """Title + live value label above a slider. Double-click the slider to reset."""

    valueChanged = Signal(int)
    sliderReleased = Signal(int)

    def __init__(
        self,
        title: str,
        minimum: int,
        maximum: int,
        value: int,
        default: Optional[int] = None,
        fmt: Callable[[int], str] = str,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._fmt = fmt
        self._default = value if default is None else default
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        head = QHBoxLayout()
        self.title = QLabel(title, self)
        self.value_label = QLabel(fmt(value), self)
        self.value_label.setObjectName("Value")
        head.addWidget(self.title)
        head.addStretch(1)
        head.addWidget(self.value_label)
        layout.addLayout(head)
        self.slider = QSlider(Qt.Orientation.Horizontal, self)
        self.slider.setRange(minimum, maximum)
        self.slider.setValue(value)
        self.slider.setToolTip("Double-click to reset")
        self.slider.valueChanged.connect(self._on_changed)
        self.slider.sliderReleased.connect(lambda: self.sliderReleased.emit(self.slider.value()))
        self.slider.mouseDoubleClickEvent = self._reset  # type: ignore[assignment]
        layout.addWidget(self.slider)

    def _on_changed(self, value: int) -> None:
        self.value_label.setText(self._fmt(value))
        self.valueChanged.emit(value)

    def _reset(self, event: QMouseEvent) -> None:
        self.slider.setValue(self._default)

    def value(self) -> int:
        return self.slider.value()

    def setValue(self, value: int) -> None:
        self.slider.setValue(int(value))

    def set_value_silently(self, value: int) -> None:
        self.slider.blockSignals(True)
        self.slider.setValue(int(value))
        self.slider.blockSignals(False)
        self.value_label.setText(self._fmt(self.slider.value()))


class Segmented(QWidget):
    """Exclusive segmented control. Emits the selected key."""

    selected = Signal(str)

    def __init__(self, options: Sequence[Tuple[str, str]], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("SegmentedTrack")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(2)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self.buttons: Dict[str, QPushButton] = {}
        for key, label in options:
            btn = QPushButton(label, self)
            btn.setObjectName("Segment")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.clicked.connect(lambda _=False, k=key: self.selected.emit(k))
            self._group.addButton(btn)
            layout.addWidget(btn)
            self.buttons[key] = btn

    def current(self) -> Optional[str]:
        for key, btn in self.buttons.items():
            if btn.isChecked():
                return key
        return None

    def set_current(self, key: str) -> None:
        btn = self.buttons.get(key)
        if btn is not None:
            btn.setChecked(True)


class ColorSwatches(QWidget):
    """Row of color presets plus a custom color picker."""

    colorChosen = Signal(str)

    def __init__(self, presets: Iterable[str], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self._current = ""
        self._buttons: List[Tuple[str, QPushButton]] = []
        for color in presets:
            btn = QPushButton(self)
            btn.setFixedSize(24, 24)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(color)
            btn.clicked.connect(lambda _=False, c=color: self._choose(c))
            layout.addWidget(btn)
            self._buttons.append((color, btn))
        self.custom = QPushButton("Custom…", self)
        self.custom.clicked.connect(self._pick)
        layout.addWidget(self.custom)
        layout.addStretch(1)
        self._restyle()

    def _choose(self, color: str) -> None:
        self.set_color(color)
        self.colorChosen.emit(color.upper())

    def _pick(self) -> None:
        start = QColor(self._current or "#FFFFFF")
        chosen = QColorDialog.getColor(start, self, "Pick a color")
        if chosen.isValid():
            self._choose(chosen.name().upper())

    def set_color(self, color: str) -> None:
        self._current = color.upper()
        self._restyle()

    def _restyle(self) -> None:
        for color, btn in self._buttons:
            selected = color.upper() == self._current
            ring = "#FFFFFF" if selected and color.upper() != "#FFFFFF" else (theme.ACCENT if selected else "rgba(255,255,255,40)")
            width = 3 if selected else 1
            btn.setStyleSheet(
                f"QPushButton {{ background-color: {color}; border: {width}px solid {ring}; border-radius: 12px; padding: 0; }}"
            )


def card(title: Optional[str] = None, parent: Optional[QWidget] = None) -> Tuple[QFrame, QVBoxLayout]:
    """A rounded settings card with an optional small caps title."""
    frame = QFrame(parent)
    frame.setObjectName("Card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(16, 14, 16, 16)
    layout.setSpacing(12)
    if title:
        lbl = QLabel(title.upper(), frame)
        lbl.setObjectName("SectionTitle")
        layout.addWidget(lbl)
    return frame, layout


def switch_row(text: str, hint: Optional[str] = None, parent: Optional[QWidget] = None) -> Tuple[QWidget, Switch]:
    """A label (+ optional hint) with a switch on the right."""
    row = QWidget(parent)
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    text_box = QVBoxLayout()
    text_box.setSpacing(2)
    lbl = QLabel(text, row)
    text_box.addWidget(lbl)
    if hint:
        h = QLabel(hint, row)
        h.setObjectName("Hint")
        h.setWordWrap(True)
        text_box.addWidget(h)
    layout.addLayout(text_box, 1)
    sw = Switch(row)
    layout.addWidget(sw, 0, Qt.AlignmentFlag.AlignVCenter)
    return row, sw
