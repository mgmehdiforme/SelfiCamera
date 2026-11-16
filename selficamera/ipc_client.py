"""Qt-free IPC client so command-line hotkeys start fast."""

from __future__ import annotations

import json
import os
import socket
from pathlib import Path
from typing import Any, Dict, Optional


def get_ipc_socket_path() -> Path:
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
    if runtime_dir and os.path.isdir(runtime_dir):
        return Path(runtime_dir) / "selficamera.sock"
    return Path(f"/tmp/selficamera-{os.getuid()}.sock")


def send_command(
    action: str,
    params: Optional[Dict[str, Any]] = None,
    timeout: float = 1.5,
    socket_path: Optional[Path | str] = None,
) -> Dict[str, Any]:
    """Send one JSON request and return the JSON response."""
    sock_path = Path(socket_path) if socket_path else get_ipc_socket_path()
    if not sock_path.exists():
        return {"success": False, "error": "SelfiCamera is not running."}
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.settimeout(timeout)
    try:
        client.connect(str(sock_path))
        client.sendall((json.dumps({"action": action, "params": params or {}}) + "\n").encode("utf-8"))
        data = b""
        while b"\n" not in data:
            chunk = client.recv(65536)
            if not chunk:
                break
            data += chunk
        if not data:
            return {"success": False, "error": "No response from SelfiCamera."}
        return json.loads(data.decode("utf-8"))
    except (ConnectionRefusedError, FileNotFoundError):
        try:
            sock_path.unlink()
        except OSError:
            pass
        return {"success": False, "error": "SelfiCamera is not running."}
    except Exception as exc:
        return {"success": False, "error": str(exc)}
    finally:
        try:
            client.close()
        except Exception:
            pass


class ShortcutIPCClient:
    """Backwards-compatible wrapper."""

    @classmethod
    def send_command(cls, action: str, params: Optional[Dict[str, Any]] = None, timeout: float = 1.5, socket_path: Optional[Path | str] = None) -> Dict[str, Any]:
        return send_command(action, params, timeout, socket_path)
