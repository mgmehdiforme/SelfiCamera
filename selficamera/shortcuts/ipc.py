"""Unix-domain-socket IPC server used by hotkeys, the CLI and automation tools."""

from __future__ import annotations

import json
import logging
import os
import socket
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

from PySide6.QtCore import QThread, Signal

from selficamera.ipc_client import ShortcutIPCClient, get_ipc_socket_path, send_command

logger = logging.getLogger(__name__)

__all__ = ["ShortcutIPCServer", "ShortcutIPCClient", "get_ipc_socket_path", "send_command"]

Validator = Callable[[str, Dict[str, Any]], Tuple[bool, str]]


class ShortcutIPCServer(QThread):
    """Accepts one JSON request per connection and forwards it to the GUI thread."""

    action_received = Signal(str, dict)
    started_listening = Signal()

    def __init__(
        self,
        state_provider: Optional[Callable[[], Dict[str, Any]]] = None,
        socket_path: Optional[Path | str] = None,
        validator: Optional[Validator] = None,
    ) -> None:
        super().__init__()
        self.socket_path = Path(socket_path) if socket_path else get_ipc_socket_path()
        self.state_provider = state_provider
        self.validator = validator
        self._running = False
        self._is_listening = False
        self._server_sock: Optional[socket.socket] = None

    @property
    def is_listening(self) -> bool:
        return self._is_listening

    def _bind(self) -> bool:
        if self.socket_path.exists():
            if send_command("ping", timeout=0.2, socket_path=self.socket_path).get("success"):
                logger.error("Another SelfiCamera instance owns %s", self.socket_path)
                return False
            try:
                self.socket_path.unlink()
            except OSError:
                pass
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            old_umask = os.umask(0o177)
            try:
                sock.bind(str(self.socket_path))
            finally:
                os.umask(old_umask)
            os.chmod(self.socket_path, 0o600)
            sock.listen(8)
            sock.settimeout(0.3)
            self._server_sock = sock
            self._is_listening = True
            self.started_listening.emit()
            logger.info("IPC listening on %s", self.socket_path)
            return True
        except Exception as exc:
            logger.error("Cannot bind IPC socket %s: %s", self.socket_path, exc)
            return False

    def _handle(self, conn: socket.socket) -> None:
        conn.settimeout(1.0)
        buffer = b""
        while b"\n" not in buffer and len(buffer) < 65536:
            chunk = conn.recv(4096)
            if not chunk:
                break
            buffer += chunk
        if not buffer:
            return
        try:
            request = json.loads(buffer.decode("utf-8").strip())
            action = str(request.get("action", ""))
            params = request.get("params") or {}
            if not isinstance(params, dict):
                raise ValueError("params must be an object")
        except Exception as exc:
            conn.sendall((json.dumps({"success": False, "error": f"Bad request: {exc}"}) + "\n").encode("utf-8"))
            return

        ok, message = (True, "")
        if self.validator is not None:
            ok, message = self.validator(action, params)
        if ok and action not in ("ping", "get_status", "status"):
            self.action_received.emit(action, params)
        state = self.state_provider() if self.state_provider else {}
        response = {
            "success": ok,
            "action": action,
            "message": message or f"{action}: ok",
            "state": state,
        }
        if not ok:
            response["error"] = message
        conn.sendall((json.dumps(response, default=str) + "\n").encode("utf-8"))

    def run(self) -> None:
        self._running = True
        if not self._bind():
            return
        assert self._server_sock is not None
        while self._running:
            try:
                conn, _ = self._server_sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            try:
                self._handle(conn)
            except Exception as exc:
                logger.debug("IPC connection error: %s", exc)
            finally:
                try:
                    conn.close()
                except Exception:
                    pass
        self._cleanup()

    def _cleanup(self) -> None:
        if self._server_sock is not None:
            try:
                self._server_sock.close()
            except Exception:
                pass
            self._server_sock = None
        self._is_listening = False
        try:
            if self.socket_path.exists():
                self.socket_path.unlink()
        except OSError:
            pass

    def stop(self) -> None:
        self._running = False
        self.wait(2000)
        self._cleanup()
