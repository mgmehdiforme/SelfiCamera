"""User interface: camera bubble, hover controls, settings window and tray."""

from selficamera.ui.overlay import BubbleWindow

OverlayWindow = BubbleWindow  # backwards-compatible alias

__all__ = ["BubbleWindow", "OverlayWindow"]
