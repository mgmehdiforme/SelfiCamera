"""Command-line entry point.

Remote-control commands (``--toggle``, ``--scene`` …) talk to the running instance
over IPC without importing Qt, so they return in a few milliseconds.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

from selficamera import __app_name__, __version__

logger = logging.getLogger("selficamera")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="selficamera",
        description="SelfiCamera: an offline webcam overlay for screen recording and streaming on Linux.",
        epilog="Run without remote-control flags to start the app. If it is already running, the camera is shown.",
    )
    p.add_argument("-v", "--version", action="version", version=f"{__app_name__} {__version__}")

    start = p.add_argument_group("startup options")
    start.add_argument("-d", "--device", help="Camera device, e.g. /dev/video0")
    start.add_argument("-W", "--width", type=int, help="Capture width (e.g. 1280)")
    start.add_argument("-H", "--height", type=int, help="Capture height (e.g. 720)")
    start.add_argument("-f", "--fps", type=int, help="Capture frame rate")
    start.add_argument("-s", "--size", type=int, help="Bubble size (short side, 120-800 px)")
    start.add_argument("--shape", choices=["circle", "rounded", "landscape", "portrait"], help="Bubble shape")
    start.add_argument("--background", choices=["none", "blur", "color", "image", "remove"], help="Background effect")
    start.add_argument("--no-mirror", action="store_true", help="Start with mirror off")
    start.add_argument("--ghost", action="store_true", help="Start in click-through mode")
    start.add_argument("--demo", "--headless-mock", dest="demo", action="store_true", help="Use a synthetic camera and mic")
    start.add_argument("--config", help="Use a different config file")
    start.add_argument("--debug", action="store_true", help="Verbose logging")

    remote = p.add_argument_group("remote control (running instance)")
    remote.add_argument("--toggle", action="store_true", help="Show / hide the camera")
    remote.add_argument("--show", action="store_true", help="Show the camera")
    remote.add_argument("--hide", action="store_true", help="Hide the camera")
    remote.add_argument("--spotlight", action="store_true", help="Toggle spotlight (big and centered)")
    remote.add_argument("--background-cycle", "--blur-cycle", dest="background_cycle", action="store_true", help="Next background effect")
    remote.add_argument("--mirror-toggle", action="store_true", help="Toggle mirror")
    remote.add_argument("--toggle-ghost", action="store_true", help="Toggle click-through")
    remote.add_argument("--settings", action="store_true", help="Open / close settings")
    remote.add_argument("--snap", type=int, choices=[1, 2, 3, 4, 5], help="1 TL, 2 TR, 3 BL, 4 BR, 5 center")
    remote.add_argument("--scene", metavar="NAME", help="Apply a saved scene")
    remote.add_argument("--set", metavar="KEY=VALUE", action="append", help="Change a setting, e.g. --set size=320")
    remote.add_argument("--status", action="store_true", help="Print the running instance's state as JSON")
    remote.add_argument("--exit", "--quit", dest="exit", action="store_true", help="Quit the running instance")

    setup = p.add_argument_group("setup")
    setup.add_argument("--install-shortcuts", action="store_true", help="Register global shortcuts in GNOME")
    setup.add_argument("--remove-shortcuts", action="store_true", help="Remove GNOME shortcuts")
    setup.add_argument("--install-model", action="store_true", help="Download the offline AI models: background and face (one time, ~500 KB)")
    return p


def remote_actions(args: argparse.Namespace) -> List[Tuple[str, Dict[str, Any]]]:
    """Translate remote-control flags into IPC (action, params) pairs."""
    from selficamera.config import parse_cli_value

    actions: List[Tuple[str, Dict[str, Any]]] = []
    for item in args.set or []:
        if "=" not in item:
            raise SystemExit(f"--set expects KEY=VALUE, got '{item}'")
        key, raw = item.split("=", 1)
        try:
            value = parse_cli_value(key.strip(), raw.strip())
        except (KeyError, ValueError) as exc:
            raise SystemExit(f"Invalid --set {item}: {exc}") from None
        actions.append(("set", {"key": key.strip(), "value": value}))
    flags = (
        ("toggle", "toggle_visibility"),
        ("show", "show"),
        ("hide", "hide"),
        ("spotlight", "toggle_spotlight"),
        ("background_cycle", "cycle_background"),
        ("mirror_toggle", "toggle_mirror"),
        ("toggle_ghost", "toggle_ghost"),
        ("settings", "toggle_settings"),
    )
    for attr, action in flags:
        if getattr(args, attr):
            actions.append((action, {}))
    if args.snap is not None:
        actions.append(("snap", {"position": args.snap}))
    if args.scene:
        actions.append(("scene", {"name": args.scene}))
    if args.status:
        actions.append(("get_status", {}))
    if args.exit:
        actions.append(("quit", {}))
    return actions


def run_setup(args: argparse.Namespace) -> Optional[int]:
    from selficamera import desktop

    if args.install_shortcuts:
        ok, msg = desktop.GnomeShortcuts().install()
        print(msg)
        return 0 if ok else 1
    if args.remove_shortcuts:
        ok, msg = desktop.GnomeShortcuts().remove()
        print(msg)
        return 0 if ok else 1
    if args.install_model:
        print("Downloading the MediaPipe Selfie Segmenter model (Apache-2.0, ~250 KB)…")
        ok, msg = desktop.install_model()
        print(msg)
        print("Downloading the YuNet face detector for auto light (MIT, ~230 KB)…")
        ok_face, msg_face = desktop.install_face_model()
        print(msg_face)
        return 0 if ok and ok_face else 1
    return None


def cli_overrides(args: argparse.Namespace) -> Dict[str, Any]:
    o: Dict[str, Any] = {}
    if args.device:
        o["device_path"] = args.device
    if args.width and args.height:
        o["resolution"] = [args.width, args.height]
    if args.fps:
        o["fps"] = args.fps
    if args.size:
        o["size"] = args.size
    if args.shape:
        o["shape"] = args.shape
    if args.background:
        o["background_mode"] = args.background
    if args.no_mirror:
        o["mirror"] = False
    if args.ghost:
        o["click_through"] = True
    return o


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    code = run_setup(args)
    if code is not None:
        return code

    from selficamera.ipc_client import send_command

    actions = remote_actions(args)
    if actions:
        exit_code = 0
        for action, params in actions:
            res = send_command(action, params)
            if not res.get("success"):
                if action in ("toggle_visibility", "show") and "not running" in str(res.get("error", "")):
                    break  # fall through and start the app
                print(f"SelfiCamera: {res.get('error', 'failed')}", file=sys.stderr)
                return 1
            if action == "get_status":
                print(json.dumps(res.get("state", {}), indent=2, sort_keys=True))
        else:
            return exit_code

    # Single instance: a second launch just shows the running camera.
    if send_command("ping", timeout=0.3).get("success"):
        send_command("show")
        print("SelfiCamera is already running.")
        return 0

    from selficamera.desktop import XCB_HINT, choose_qt_platform, setup_logging

    log_file = setup_logging(args.debug)
    platform, limited = choose_qt_platform()
    if platform:
        os.environ["QT_QPA_PLATFORM"] = platform
    if limited:
        logger.warning(
            "Running as a native Wayland window: GNOME will not let the camera stay on top or "
            "snap to corners. Fix: %s, then restart SelfiCamera.",
            XCB_HINT,
        )
    os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.*=false")

    import signal

    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from selficamera.app import SelfiCameraApp
    from selficamera.ui.icons import app_icon

    qt_app = QApplication(sys.argv[:1])
    qt_app.setApplicationName(__app_name__)
    qt_app.setApplicationDisplayName(__app_name__)
    qt_app.setApplicationVersion(__version__)
    qt_app.setDesktopFileName("selficamera")
    qt_app.setWindowIcon(app_icon())
    qt_app.setQuitOnLastWindowClosed(False)
    logger.info("SelfiCamera %s starting (log: %s, platform: %s)", __version__, log_file, qt_app.platformName())

    controller = SelfiCameraApp(config_path=args.config, mock_mode=args.demo, cli_overrides=cli_overrides(args))
    controller.limited_wayland = qt_app.platformName().startswith("wayland")
    if "GNOME" in os.environ.get("XDG_CURRENT_DESKTOP", "").upper():
        # Shadow/rounded-corner extensions would draw a box around the transparent bubble.
        from selficamera.desktop import ShadowExtensions

        ShadowExtensions().exclude()
    controller.initialize()
    controller.start()

    def _on_signal(signum, _frame) -> None:
        logger.info("Signal %s received", signum)
        controller.quit()

    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)
    keepalive = QTimer()
    keepalive.timeout.connect(lambda: None)
    keepalive.start(400)
    return qt_app.exec()


if __name__ == "__main__":
    sys.exit(main())
