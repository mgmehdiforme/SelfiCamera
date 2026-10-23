"""Unix Domain Socket IPC server and client for presenter shortcut triggers and CLI control."""

from __future__ import annotations

import json
import logging
import os
import socket
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple
from PySide6.QtCore import QObject, QThread, Signal

logger = logging.getLogger(__name__)


def get_ipc_socket_path() -> Path:
    """Resolve standard XDG runtime directory Unix domain socket path."""
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
    if runtime_dir and os.path.exists(runtime_dir):
        return Path(runtime_dir) / "selficamera.sock"

    uid = os.getuid()
    return Path(f"/tmp/selficamera-{uid}.sock")


class ShortcutIPCClient:
    """CLI client connecting to running SelfiCamera instance via Unix domain socket."""

    @classmethod
    def send_command(
        cls,
        action: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: float = 1.0,
        socket_path: Optional[Path | str] = None,
    ) -> Dict[str, Any]:
        """Send a single JSON command to the running daemon and return the JSON response."""
        sock_path = Path(socket_path) if socket_path else get_ipc_socket_path()
        if not sock_path.exists():
            return {
                "success": False,
                "error": f"No active SelfiCamera instance detected (socket {sock_path} does not exist)",
            }

        client_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client_sock.settimeout(timeout)

        try:
            client_sock.connect(str(sock_path))
            payload = json.dumps({"action": action, "params": params or {}}) + "\n"
            client_sock.sendall(payload.encode("utf-8"))

            response_data = b""
            while b"\n" not in response_data:
                chunk = client_sock.recv(4096)
                if not chunk:
                    break
                response_data += chunk

            if not response_data:
                return {"success": False, "error": "Server closed connection without responding"}

            return json.loads(response_data.decode("utf-8"))
        except (ConnectionRefusedError, FileNotFoundError):
            # Clean up stale socket file left from an ungracefully terminated process
            try:
                if sock_path.exists():
                    sock_path.unlink()
            except OSError:
                pass
            return {
                "success": False,
                "error": "No active SelfiCamera instance detected (server is not running)",
            }
        except Exception as e:
            if getattr(e, "errno", None) == 111 or "111" in str(e):
                try:
                    if sock_path.exists():
                        sock_path.unlink()
                except OSError:
                    pass
                return {
                    "success": False,
                    "error": "No active SelfiCamera instance detected (server is not running)",
                }
            return {"success": False, "error": str(e)}
        finally:
            try:
                client_sock.close()
            except Exception:
                pass


class ShortcutIPCServer(QThread):
    """Listens on Unix Domain Socket in background and dispatches action signals."""

    action_received = Signal(str, dict)  # (action, params)
    started_listening = Signal()

    def __init__(
        self,
        state_provider: Optional[Callable[[], Dict[str, Any]]] = None,
        socket_path: Optional[Path | str] = None,
    ) -> None:
        super().__init__()
        self.socket_path = Path(socket_path) if socket_path else get_ipc_socket_path()
        self.state_provider = state_provider
        self._running = False
        self._is_listening = False
        self._server_sock: Optional[socket.socket] = None

    @property
    def is_listening(self) -> bool:
        """Return True if the server socket is bound, listening, and ready for connections."""
        return self._is_listening

    def run(self) -> None:
        """Bind socket, set permissions 0600, and accept client connections."""
        self._running = True

        # Clean stale socket if dead
        if self.socket_path.exists():
            # Test if another instance is alive
            test_res = ShortcutIPCClient.send_command("ping", timeout=0.08)
            if test_res.get("success"):
                logger.error("Another active SelfiCamera instance is already listening on %s", self.socket_path)
                return
            try:
                self.socket_path.unlink()
            except OSError:
                pass

        try:
            self._server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self._server_sock.bind(str(self.socket_path))
            # Restrict permissions to owner only (0600)
            os.chmod(self.socket_path, 0o600)
            self._server_sock.listen(5)
            self._server_sock.settimeout(0.5)
            self._is_listening = True
            self.started_listening.emit()
            logger.info("IPC Server bound to %s (permissions 0600)", self.socket_path)
        except Exception as e:
            logger.error("Failed to bind IPC socket %s: %s", self.socket_path, e)
            self._is_listening = False
            return

        while self._running:
            try:
                conn, _ = self._server_sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break

            try:
                conn.settimeout(1.0)
                buffer = b""
                while b"\n" not in buffer:
                    chunk = conn.recv(2048)
                    if not chunk:
                        break
                    buffer += chunk

                if buffer:
                    line = buffer.decode("utf-8").strip()
                    request = json.loads(line)
                    action = request.get("action", "")
                    params = request.get("params", {})

                    # Dispatch to Qt main thread
                    self.action_received.emit(action, params)

                    # Gather current state
                    state = self.state_provider() if self.state_provider else {}

                    response = {
                        "success": True,
                        "action": action,
                        "message": f"Action '{action}' executed successfully",
                        "state": state,
                    }
                    conn.sendall((json.dumps(response) + "\n").encode("utf-8"))
            except Exception as e:
                err_resp = {"success": False, "error": str(e)}
                try:
                    conn.sendall((json.dumps(err_resp) + "\n").encode("utf-8"))
                except Exception:
                    pass
            finally:
                try:
                    conn.close()
                except Exception:
                    pass

        # Cleanup socket on stop
        if self._server_sock:
            try:
                self._server_sock.close()
            except Exception:
                pass
        if self.socket_path.exists():
            try:
                self.socket_path.unlink()
            except Exception:
                pass
        logger.info("IPC Server terminated cleanly.")

    def stop(self) -> None:
        """Stop listening and cleanly unlink socket file."""
        self._running = False
        if self._server_sock:
            try:
                self._server_sock.close()
            except Exception:
                pass
        self.wait(1500)
        if self.socket_path.exists():
            try:
                self.socket_path.unlink()
            except Exception:
                pass
