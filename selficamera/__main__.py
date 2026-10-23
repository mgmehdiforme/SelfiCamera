"""Command Line Interface (CLI) entrypoint for SelfiCamera."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from PySide6.QtWidgets import QApplication

from selficamera import __app_name__, __version__
from selficamera.app import SelfiCameraApp
from selficamera.shortcuts.ipc import ShortcutIPCClient, get_ipc_socket_path

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("selficamera")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="selficamera",
        description="SelfiCamera: Ultra-lightweight offline circular presenter camera overlay for Ubuntu Linux.",
    )
    parser.add_argument("-v", "--version", action="version", version=f"{__app_name__} {__version__}")

    # Launch configuration options
    parser.add_argument("-d", "--device", type=str, default=None, help="V4L2 camera device node path (e.g. /dev/video0)")
    parser.add_argument("-W", "--width", type=int, default=None, help="Capture width (default 1280)")
    parser.add_argument("-H", "--height", type=int, default=None, help="Capture height (default 720)")
    parser.add_argument("-f", "--fps", type=int, default=None, help="Capture frames per second (default 30)")
    parser.add_argument("-s", "--size", type=int, default=None, help="Initial circle diameter (120..600)")
    parser.add_argument("-b", "--blur", type=int, choices=[0, 1, 2, 3], default=None, help="Initial blur tier (0..3)")
    parser.add_argument("--no-mirror", action="store_true", help="Start with horizontal mirror disabled")
    parser.add_argument("--no-light", action="store_true", help="Start with Auto-Light Boost disabled")
    parser.add_argument("--ghost", action="store_true", help="Start immediately in click-through Ghost Mode")
    parser.add_argument("--headless-mock", action="store_true", help="Run with synthetic mock video & audio feeds")
    parser.add_argument("--config", type=str, default=None, help="Custom configuration JSON path")

    # Client IPC triggers (when instance is already running)
    parser.add_argument("--toggle", action="store_true", help="IPC: Toggle overlay visibility (Show / Hide)")
    parser.add_argument("--toggle-ghost", action="store_true", help="IPC: Toggle click-through Ghost Mode")
    parser.add_argument("--snap", type=int, choices=[1, 2, 3, 4], default=None, help="IPC: Snap to desktop corner (1..4)")
    parser.add_argument("--blur-cycle", action="store_true", help="IPC: Step blur level (0 -> 1 -> 2 -> 3 -> 0)")
    parser.add_argument("--status", action="store_true", help="IPC: Query status of running instance")
    parser.add_argument("--exit", action="store_true", help="IPC: Gracefully terminate running SelfiCamera instance")

    return parser.parse_args()


def handle_ipc_command(args: argparse.Namespace) -> bool:
    """Check if command is an IPC action and forward to running instance."""
    action = None
    params = {}

    if args.toggle:
        action = "toggle_visibility"
    elif args.toggle_ghost:
        action = "toggle_ghost"
    elif args.snap is not None:
        action = "snap_corner"
        params["corner"] = args.snap
    elif args.blur_cycle:
        action = "cycle_blur"
    elif args.status:
        action = "get_status"
    elif args.exit:
        action = "quit"

    if action is not None:
        res = ShortcutIPCClient.send_command(action, params)
        if res.get("success"):
            if action == "get_status":
                print(json.dumps(res.get("state", {}), indent=2))
            else:
                print(f"[SelfiCamera IPC] {res.get('message', 'Action sent successfully')}")
            return True
        else:
            if args.toggle_ghost:
                print("[SelfiCamera] No active instance running. Starting new instance in Ghost Mode...")
                args.ghost = True
                return False
            elif args.toggle:
                print("[SelfiCamera] No active instance running. Starting new instance...")
                return False
            else:
                print(f"[SelfiCamera IPC] No active SelfiCamera instance is currently running.\nLaunch SelfiCamera with: ./run.sh", file=sys.stderr)
                sys.exit(1)

    return False


def main() -> None:
    args = parse_args()

    # 1. Handle explicit IPC actions
    if handle_ipc_command(args):
        sys.exit(0)

    # 2. Check for existing running instance before starting a new one
    sock_path = get_ipc_socket_path()
    if sock_path.exists():
        test_res = ShortcutIPCClient.send_command("ping", timeout=0.1)
        if test_res.get("success"):
            print("[SelfiCamera] An active instance is already running. Bringing to focus.")
            ShortcutIPCClient.send_command("toggle_visibility")
            sys.exit(0)

    # 3. Launch main GUI application
    if "QT_QPA_PLATFORM" not in os.environ:
        os.environ["QT_QPA_PLATFORM"] = "xcb;wayland"

    # Set high DPI and Wayland / X11 attributes if needed
    qt_app = QApplication(sys.argv)
    qt_app.setApplicationName(__app_name__)
    qt_app.setApplicationVersion(__version__)
    qt_app.setQuitOnLastWindowClosed(False)

    cli_overrides = {}
    if args.device:
        cli_overrides["device_path"] = args.device
    if args.width and args.height:
        cli_overrides["resolution"] = [args.width, args.height]
    if args.fps:
        cli_overrides["fps"] = args.fps
    if args.size:
        cli_overrides["diameter"] = args.size
    if args.blur is not None:
        cli_overrides["blur_level"] = args.blur
    if args.no_mirror:
        cli_overrides["mirror"] = False
    if args.no_light:
        cli_overrides["auto_light"] = False
    if args.ghost:
        cli_overrides["click_through"] = True

    app_controller = SelfiCameraApp(
        config_path=args.config,
        mock_mode=args.headless_mock,
        cli_overrides=cli_overrides,
    )
    app_controller.initialize()
    app_controller.start()

    sys.exit(qt_app.exec())


if __name__ == "__main__":
    main()
