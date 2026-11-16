"""Camera worker, IPC, CLI, desktop helpers and audio."""

import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from selficamera.audio.voice_monitor import AudioMonitorWorker
from selficamera.capture.camera import CameraStatus, CameraWorker
from selficamera.desktop import SHORTCUTS, GnomeShortcuts, autostart_enabled, install_model, set_autostart
from selficamera.ipc_client import get_ipc_socket_path, send_command
from selficamera.processor.pipeline import FrameProcessor
from selficamera.shortcuts.ipc import ShortcutIPCServer

ROOT = Path(__file__).resolve().parent.parent


# ----------------------------------------------------------------- camera
def test_mock_camera_publishes_frames(qtbot):
    worker = CameraWorker(FrameProcessor(output_size=(120, 120)), width=640, height=360, fps=30, mock_mode=True)
    with qtbot.waitSignal(worker.frame_available, timeout=3000):
        worker.start()
    img = worker.take_frame()
    assert img is not None and img.width() == 120
    assert worker.take_frame() is None  # mailbox is single-slot
    assert worker.state == CameraStatus.LIVE
    worker.stop()
    assert not worker.isRunning()


def test_missing_camera_reports_friendly_error(qtbot):
    worker = CameraWorker(FrameProcessor(output_size=(64, 64)), device_path="/dev/video-does-not-exist")
    with qtbot.waitSignal(worker.status_changed, timeout=3000) as blocker:
        worker.start()
    state, message = blocker.args
    assert state == CameraStatus.ERROR and "not found" in message.lower()
    worker.stop()


def test_change_source_is_applied(qtbot):
    worker = CameraWorker(FrameProcessor(output_size=(64, 64)), width=320, height=240, mock_mode=True)
    worker.start()
    worker.change_source("/dev/video9", 640, 480, 24)
    qtbot.waitUntil(lambda: worker.width == 640 and worker.fps == 24, timeout=3000)
    worker.stop()


# -------------------------------------------------------------------- IPC
def test_ipc_roundtrip_and_validation(qtbot):
    received = []

    def validator(action, params):
        return (action != "bad", "nope" if action == "bad" else "")

    server = ShortcutIPCServer(state_provider=lambda: {"size": 260}, validator=validator)
    server.action_received.connect(lambda a, p: received.append((a, p)))
    with qtbot.waitSignal(server.started_listening, timeout=3000):
        server.start()
    try:
        assert oct(get_ipc_socket_path().stat().st_mode & 0o777) == "0o600"
        ok = send_command("snap", {"position": 2})
        assert ok["success"] and ok["state"]["size"] == 260
        qtbot.waitUntil(lambda: received == [("snap", {"position": 2})], timeout=2000)
        bad = send_command("bad")
        assert not bad["success"] and bad["error"] == "nope"
        assert send_command("ping")["success"]
        assert len(received) == 1  # ping and rejected actions are not dispatched
    finally:
        server.stop()
    assert not get_ipc_socket_path().exists()
    assert not send_command("ping")["success"]


def test_ipc_client_and_cli_do_not_import_qt():
    code = "import sys, selficamera.__main__, selficamera.ipc_client; print('PySide6' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=ROOT, timeout=30)
    assert out.stdout.strip() == "False", out.stderr


def test_cli_remote_actions_parsing():
    from selficamera.__main__ import build_parser, remote_actions

    args = build_parser().parse_args(["--set", "size=320", "--spotlight", "--snap", "3", "--scene", "Intro"])
    acts = remote_actions(args)
    assert ("set", {"key": "size", "value": 320}) in acts
    assert ("toggle_spotlight", {}) in acts
    assert ("snap", {"position": 3}) in acts
    assert ("scene", {"name": "Intro"}) in acts
    with pytest.raises(SystemExit):
        remote_actions(build_parser().parse_args(["--set", "shape=star"]))


def test_cli_status_without_instance_fails_cleanly():
    out = subprocess.run([sys.executable, "-m", "selficamera", "--status"], capture_output=True, text=True, cwd=ROOT, timeout=30)
    assert out.returncode == 1 and "not running" in out.stderr


# ---------------------------------------------------------------- desktop
class FakeGsettings:
    def __init__(self, existing="['/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom0/']"):
        self.store = {"list": existing}
        self.calls = []

    def __call__(self, cmd, **kw):
        self.calls.append(cmd)
        out = ""
        if cmd[1] == "list-schemas":
            out = "org.gnome.settings-daemon.plugins.media-keys\n"
        elif cmd[1] == "get":
            out = self.store["list"]
        elif cmd[1] == "set" and cmd[3] == "custom-keybindings":
            self.store["list"] = cmd[4]
        return subprocess.CompletedProcess(cmd, 0, stdout=out, stderr="")


def test_gnome_shortcuts_install_preserves_user_bindings():
    fake = FakeGsettings()
    g = GnomeShortcuts(runner=fake, gsettings="gsettings")
    ok, _ = g.install(launcher="/usr/bin/selficamera")
    assert ok and g.installed()
    assert "custom0" in fake.store["list"]
    assert fake.store["list"].count("selficamera-") == len(SHORTCUTS)
    cmds = [c for c in fake.calls if c[-2] == "command"]
    assert [c[-1] for c in cmds].count("/usr/bin/selficamera --toggle") == 1
    # Reinstall does not duplicate.
    g.install(launcher="/usr/bin/selficamera")
    assert fake.store["list"].count("selficamera-") == len(SHORTCUTS)
    ok, _ = g.remove()
    assert ok and not g.installed() and "custom0" in fake.store["list"]


def test_gnome_shortcuts_unavailable():
    g = GnomeShortcuts(runner=lambda *a, **k: subprocess.CompletedProcess(a, 0, stdout="", stderr=""), gsettings="gsettings")
    ok, msg = g.install()
    assert not ok and "gsettings" in msg.lower()


def test_no_default_gnome_conflicts():
    accels = [s[3] for s in SHORTCUTS]
    assert "<Super><Alt>s" not in accels  # GNOME screen reader
    assert "<Super><Alt>8" not in accels  # GNOME zoom
    assert len(set(accels)) == len(accels)


def test_autostart_toggle():
    assert not autostart_enabled()
    assert set_autostart(True) and autostart_enabled()
    assert set_autostart(False) and not autostart_enabled()


class _Resp:
    def __init__(self, data):
        self.data = data

    def read(self):
        return self.data

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_install_model_validates_download(tmp_path):
    good = b"\x1c\x00\x00\x00TFL3" + b"\x00" * 60_000
    ok, _ = install_model(tmp_path, opener=lambda url, timeout: _Resp(good))
    assert ok and (tmp_path / "selfie_segmenter.tflite").exists()
    ok, msg = install_model(tmp_path / "x", opener=lambda url, timeout: _Resp(b"<html>nope</html>"))
    assert not ok and not (tmp_path / "x" / "selfie_segmenter.tflite").exists()


# ------------------------------------------------------------------ audio
def test_audio_energy_envelope():
    mon = AudioMonitorWorker()
    t = np.linspace(0, 1, 512, dtype=np.float32)
    loud = 0.5 * np.sin(2 * np.pi * 220 * t)
    e1 = mon.compute_energy_from_pcm(loud)
    e2 = mon.compute_energy_from_pcm(loud)
    assert 0 < e1 < e2 <= 1.0
    quiet = mon.compute_energy_from_pcm(np.zeros(512, np.float32))
    assert quiet < e2
    assert mon.compute_energy_from_pcm(np.array([], np.float32)) == 0.0


def test_mock_audio_emits(qtbot):
    mon = AudioMonitorWorker(mock_mode=True)
    with qtbot.waitSignal(mon.energy_updated, timeout=2000):
        mon.start()
    mon.stop()


# --------------------------------------------------------------- platform
def test_choose_qt_platform(monkeypatch):
    from selficamera import desktop

    assert desktop.choose_qt_platform({"DISPLAY": ":0"}) == ("xcb", False)
    assert desktop.choose_qt_platform({"QT_QPA_PLATFORM": "offscreen"}) == (None, False)
    assert desktop.choose_qt_platform({"SELFICAMERA_PLATFORM": "wayland"}) == ("wayland", True)
    monkeypatch.setattr(desktop, "xcb_runtime_available", lambda: True)
    assert desktop.choose_qt_platform({"WAYLAND_DISPLAY": "wayland-0", "DISPLAY": ":0"}) == ("xcb;wayland", False)
    monkeypatch.setattr(desktop, "xcb_runtime_available", lambda: False)
    assert desktop.choose_qt_platform({"WAYLAND_DISPLAY": "wayland-0", "DISPLAY": ":0"}) == ("wayland", True)


# ----------------------------------------------------------- shadow extensions
def _shadow_ext_env(tmp_path, monkeypatch, blacklist="@as []", whitelist="false"):
    from selficamera import desktop

    ext = tmp_path / "data" / "gnome-shell" / "extensions" / "rounded-window-corners@fxgn"
    ext.mkdir(parents=True)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_DATA_DIRS", str(tmp_path / "none"))
    state = {"blacklist": blacklist, "whitelist": whitelist, "sets": []}

    def runner(cmd, **_kw):
        if cmd[1] == "get":
            return subprocess.CompletedProcess(cmd, 0, stdout=state[cmd[3]] + "\n", stderr="")
        state["sets"].append(cmd[4])
        state[cmd[3]] = cmd[4]
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    return desktop.ShadowExtensions(runner=runner, gsettings="gsettings"), state


def test_shadow_extension_exclusion_is_idempotent(tmp_path, monkeypatch):
    ext, state = _shadow_ext_env(tmp_path, monkeypatch, blacklist="['firefox']")
    assert ext.exclude() == ["rounded-window-corners@fxgn"]
    assert state["blacklist"] == "['firefox', 'selficamera']"
    assert ext.exclude() == []  # already excluded: no second write
    assert ext.exclude(False) == ["rounded-window-corners@fxgn"]
    assert state["blacklist"] == "['firefox']"


def test_shadow_extension_whitelist_mode_removes_us(tmp_path, monkeypatch):
    ext, state = _shadow_ext_env(tmp_path, monkeypatch, blacklist="['selficamera', 'code']", whitelist="true")
    assert ext.exclude() == ["rounded-window-corners@fxgn"]
    assert state["blacklist"] == "['code']"


def test_shadow_extension_absent_is_noop(tmp_path, monkeypatch):
    from selficamera import desktop

    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setenv("XDG_DATA_DIRS", str(tmp_path / "none"))
    called = []
    ext = desktop.ShadowExtensions(runner=lambda *a, **k: called.append(a), gsettings="gsettings")
    assert ext.exclude() == [] and not called


def test_install_face_model_rejects_bad_download(tmp_path):
    from selficamera.desktop import install_face_model

    ok, msg = install_face_model(tmp_path, opener=lambda url, timeout: _Resp(b"x" * 60_000))
    assert not ok and "not a valid" in msg
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "soname,pkg",
    [
        ("libxcb-cursor.so.0", "libxcb-cursor0"),
        ("libxkbcommon-x11.so.0", "libxkbcommon-x11-0"),
        ("libxcb-icccm.so.4", "libxcb-icccm4"),
        ("libportaudio.so.2", "libportaudio2"),
    ],
)
def test_deb_package_names(soname, pkg):
    from selficamera.desktop import deb_package

    assert deb_package(soname) == pkg


def test_missing_xcb_libs_reads_ldd(monkeypatch, tmp_path):
    from selficamera import desktop

    plugin = tmp_path / "libqxcb.so"
    plugin.write_bytes(b"")
    monkeypatch.setattr(desktop, "_qt_xcb_plugin_files", lambda: [plugin])
    monkeypatch.setattr(desktop.shutil, "which", lambda name: "/usr/bin/ldd")
    out = "\tlibxcb.so.1 => /usr/lib/libxcb.so.1 (0x1)\n\tlibxkbcommon-x11.so.0 => not found\n\tlibxcb-icccm.so.4 => not found\n"
    runner = lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, stdout=out, stderr="")  # noqa: E731
    assert desktop.missing_xcb_libs(runner) == ["libxcb-icccm.so.4", "libxkbcommon-x11.so.0"]
    monkeypatch.setattr(desktop, "missing_xcb_libs", lambda runner=None: ["libxkbcommon-x11.so.0"])
    monkeypatch.setattr(desktop, "_loadable", lambda lib: True)
    assert desktop.apt_hint(desktop.missing_system_packages()) == "sudo apt install libxkbcommon-x11-0"
