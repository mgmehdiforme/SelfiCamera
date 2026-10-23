"""Tests for Unix Domain Socket IPC and ShortcutManager routing."""

import os
from selficamera.shortcuts.ipc import ShortcutIPCClient, ShortcutIPCServer, get_ipc_socket_path
from selficamera.shortcuts.manager import ShortcutManager


def test_ipc_server_permissions_and_lifecycle(qtbot, tmp_path):
    """Verify that IPC server creates socket with 0600 permissions and cleans up on stop."""
    state = {"test_key": "active"}
    sock_file = tmp_path / "test_lifecycle.sock"
    server = ShortcutIPCServer(state_provider=lambda: state, socket_path=sock_file)

    try:
        server.start()
        qtbot.waitUntil(lambda: server.is_listening, timeout=1000)

        # Check file permissions (0600)
        mode = os.stat(server.socket_path).st_mode
        assert (mode & 0o777) == 0o600

        # Test ping/action
        response = ShortcutIPCClient.send_command("ping", socket_path=sock_file)
        assert response.get("success") is True
        assert response.get("state") == state
    finally:
        server.stop()
        qtbot.waitUntil(lambda: not server.socket_path.exists(), timeout=1000)


def test_shortcut_manager_signal_dispatch(qtbot, tmp_path):
    """Verify that ShortcutManager receives actions and emits corresponding Qt signals."""
    sock_file = tmp_path / "test_manager.sock"
    manager = ShortcutManager(state_provider=lambda: {"running": True}, socket_path=sock_file)

    signals_received = {
        "toggle": False,
        "settings": False,
        "snap": None,
        "blur": False,
    }

    manager.toggle_visibility_requested.connect(lambda: signals_received.update(toggle=True))
    manager.toggle_settings_requested.connect(lambda: signals_received.update(settings=True))
    manager.snap_corner_requested.connect(lambda c: signals_received.update(snap=c))
    manager.cycle_blur_requested.connect(lambda: signals_received.update(blur=True))

    try:
        manager.start()
        qtbot.waitUntil(lambda: manager.is_listening, timeout=1000)

        # Trigger toggle
        resp_toggle = ShortcutIPCClient.send_command("toggle_visibility", socket_path=sock_file)
        assert resp_toggle.get("success") is True
        qtbot.waitUntil(lambda: signals_received["toggle"] is True, timeout=1000)

        # Trigger toggle settings
        resp_settings = ShortcutIPCClient.send_command("toggle_settings", socket_path=sock_file)
        assert resp_settings.get("success") is True
        qtbot.waitUntil(lambda: signals_received["settings"] is True, timeout=1000)

        # Trigger snap corner 5 (Center)
        resp_snap = ShortcutIPCClient.send_command("snap_corner", {"corner": 5}, socket_path=sock_file)
        assert resp_snap.get("success") is True
        qtbot.waitUntil(lambda: signals_received["snap"] == 5, timeout=1000)

        # Trigger cycle blur
        resp_blur = ShortcutIPCClient.send_command("cycle_blur", socket_path=sock_file)
        assert resp_blur.get("success") is True
        qtbot.waitUntil(lambda: signals_received["blur"] is True, timeout=1000)
    finally:
        manager.stop()
        qtbot.waitUntil(lambda: not manager.ipc_server.socket_path.exists(), timeout=1000)


def test_toggle_ghost_ipc_dispatch(qtbot, tmp_path):
    """Verify that toggle_ghost IPC command triggers toggle_ghost_requested signal."""
    sock_file = tmp_path / "test_ghost.sock"
    manager = ShortcutManager(state_provider=lambda: {"running": True}, socket_path=sock_file)

    ghost_toggled = []
    manager.toggle_ghost_requested.connect(lambda: ghost_toggled.append(True))

    try:
        manager.start()
        qtbot.waitUntil(lambda: manager.is_listening, timeout=1000)

        resp = ShortcutIPCClient.send_command("toggle_ghost", socket_path=sock_file)
        assert resp.get("success") is True
        qtbot.waitUntil(lambda: len(ghost_toggled) == 1, timeout=1000)
    finally:
        manager.stop()
        qtbot.waitUntil(lambda: not manager.ipc_server.socket_path.exists(), timeout=1000)


def test_stale_socket_auto_cleanup(tmp_path):
    """Verify that stale dead socket files are automatically unlinked upon connect failure."""
    import socket as py_socket
    stale_sock = tmp_path / "stale.sock"

    # Create dummy socket file and immediately close it without listening
    s = py_socket.socket(py_socket.AF_UNIX, py_socket.SOCK_STREAM)
    s.bind(str(stale_sock))
    s.close()

    assert stale_sock.exists()

    # Sending a command to dead socket should clean it up and return failure
    resp = ShortcutIPCClient.send_command("ping", socket_path=stale_sock)
    assert resp.get("success") is False
    assert not stale_sock.exists()


