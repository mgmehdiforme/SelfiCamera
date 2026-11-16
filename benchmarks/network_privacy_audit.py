"""Privacy audit: the app must not open network connections at runtime.

1. Static scan: only `selficamera/desktop.py` (the explicit `--install-model` command)
   may import network modules.
2. Runtime: blocks AF_INET/AF_INET6 sockets, then runs the pipeline and the whole app
   in demo mode for a few seconds. Any attempt to connect fails the audit.
"""

from __future__ import annotations

import ast
import os
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

NETWORK_MODULES = {"requests", "urllib", "urllib3", "httpx", "http", "aiohttp", "ftplib", "grpc", "websocket"}
ALLOWED = {"selficamera/desktop.py"}


def static_scan() -> list:
    bad = []
    for path in (ROOT / "selficamera").rglob("*.py"):
        rel = path.relative_to(ROOT).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for n in names:
                if n.split(".")[0] in NETWORK_MODULES and rel not in ALLOWED:
                    bad.append(f"{rel}: imports {n}")
    return bad


def runtime_check() -> list:
    attempts = []
    real_socket = socket.socket

    class GuardedSocket(real_socket):
        def __init__(self, family=socket.AF_INET, *a, **kw):
            if family in (socket.AF_INET, socket.AF_INET6):
                attempts.append(f"socket(family={family})")
                raise PermissionError("network blocked by privacy audit")
            super().__init__(family, *a, **kw)

    socket.socket = GuardedSocket  # type: ignore[misc]
    try:
        from PySide6.QtCore import QEventLoop, QTimer
        from PySide6.QtWidgets import QApplication

        import tempfile

        tmp = tempfile.mkdtemp(prefix="sc-audit-")
        os.environ["XDG_CONFIG_HOME"] = tmp
        os.environ["XDG_STATE_HOME"] = tmp
        app = QApplication.instance() or QApplication([])  # noqa: F841 - keep the app alive
        from selficamera.app import SelfiCameraApp

        ctl = SelfiCameraApp(mock_mode=True, enable_tray=False, socket_path=f"/tmp/sc-audit-{os.getpid()}.sock")
        ctl.initialize()
        ctl.start()
        for mode in ("blur", "color", "remove", "none"):
            ctl.set("background_mode", mode)
            loop = QEventLoop()
            QTimer.singleShot(600, loop.quit)
            loop.exec()
        ctl.quit()
    finally:
        socket.socket = real_socket  # type: ignore[misc]
    return attempts


def main() -> int:
    bad = static_scan()
    print("Static scan:", "clean" if not bad else "\n  " + "\n  ".join(bad))
    attempts = runtime_check()
    print("Runtime network attempts:", attempts or "none")
    ok = not bad and not attempts
    print("PRIVACY AUDIT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    code = main()
    sys.stdout.flush()
    sys.stderr.flush()
    # Skip interpreter finalization: on Python 3.10, garbage-collecting the Qt objects created
    # by the runtime check can abort *after* the audit has finished ("deallocating None").
    os._exit(code)
