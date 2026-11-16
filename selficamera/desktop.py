"""Desktop integration helpers (Qt-free): GNOME keybindings, autostart, logging, model install."""

from __future__ import annotations

import ast
import logging
import logging.handlers
import os
import shlex
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

GNOME_SCHEMA = "org.gnome.settings-daemon.plugins.media-keys"
GNOME_KEY = "custom-keybindings"
GNOME_BASE = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/"
GNOME_PREFIX = "selficamera-"

# (id, label, CLI args, GNOME accelerator)
SHORTCUTS: Tuple[Tuple[str, str, str, str], ...] = (
    ("toggle", "SelfiCamera: show / hide", "--toggle", "<Super><Alt>c"),
    ("spotlight", "SelfiCamera: spotlight", "--spotlight", "<Super><Alt>z"),
    ("background", "SelfiCamera: next background", "--background-cycle", "<Super><Alt>b"),
    ("mirror", "SelfiCamera: mirror", "--mirror-toggle", "<Super><Alt>m"),
    ("ghost", "SelfiCamera: click-through", "--toggle-ghost", "<Super><Alt>x"),
    ("settings", "SelfiCamera: settings", "--settings", "<Super><Alt>o"),
    ("snap1", "SelfiCamera: top left", "--snap 1", "<Super><Alt>1"),
    ("snap2", "SelfiCamera: top right", "--snap 2", "<Super><Alt>2"),
    ("snap3", "SelfiCamera: bottom left", "--snap 3", "<Super><Alt>3"),
    ("snap4", "SelfiCamera: bottom right", "--snap 4", "<Super><Alt>4"),
    ("snap5", "SelfiCamera: center", "--snap 5", "<Super><Alt>5"),
)

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_segmenter/float16/latest/selfie_segmenter.tflite"
)

# OpenCV Zoo YuNet face detector (MIT license, ~230 KB). Used by auto light to meter on your face.
FACE_MODEL_URL = (
    "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
)

Runner = Callable[..., subprocess.CompletedProcess]


# --------------------------------------------------------------------- paths
def state_dir() -> Path:
    return Path(os.environ.get("XDG_STATE_HOME") or (Path.home() / ".local" / "state")) / "selficamera"


def log_path() -> Path:
    return state_dir() / "selficamera.log"


def autostart_path() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config")) / "autostart" / "selficamera.desktop"


def launcher_command() -> str:
    """Best command to start SelfiCamera from a keybinding or autostart entry."""
    installed = shutil.which("selficamera")
    if installed:
        return shlex.quote(installed)
    run_sh = PROJECT_ROOT / "run.sh"
    if run_sh.exists():
        # Invoke through bash: the checkout may live on a filesystem without exec bits (NTFS, exFAT).
        return f"bash {shlex.quote(str(run_sh))}"
    return f"{shlex.quote(sys.executable)} -m selficamera"


# ------------------------------------------------------------------- logging
def setup_logging(debug: bool = False) -> Path:
    level = logging.DEBUG if debug else logging.INFO
    root = logging.getLogger()
    root.setLevel(level)
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S")
    if not any(isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler) for h in root.handlers):
        stream = logging.StreamHandler()
        stream.setFormatter(fmt)
        root.addHandler(stream)
    path = log_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.handlers.RotatingFileHandler(path, maxBytes=1_000_000, backupCount=2, encoding="utf-8")
        fh.setFormatter(fmt)
        root.addHandler(fh)
    except OSError as exc:
        logger.warning("File logging disabled: %s", exc)
    return path


# ------------------------------------------------------------------ platform
# Libraries Qt's X11 (xcb) plugin needs beyond a standard desktop. Ubuntu doesn't install
# all of them by default. Used when ``ldd`` is unavailable.
XCB_LIBS = (
    "libxcb-cursor.so.0",
    "libxkbcommon-x11.so.0",
    "libxcb-icccm.so.4",
    "libxcb-keysyms.so.1",
    "libxcb-xkb.so.1",
    "libxcb-image.so.0",
    "libxcb-render-util.so.0",
    "libxcb-randr.so.0",
    "libxcb-shape.so.0",
    "libxcb-xinerama.so.0",
    "libxcb-xinput.so.0",
)
AUDIO_LIBS = ("libportaudio.so.2",)


def deb_package(soname: str) -> str:
    """Debian/Ubuntu package for a library soname: libxcb-icccm.so.4 -> libxcb-icccm4."""
    name, _, version = soname.partition(".so.")
    version = version.split(".")[0]
    if not version:
        return name
    return f"{name}-{version}" if name[-1:].isdigit() else f"{name}{version}"


def _qt_xcb_plugin_files() -> List[Path]:
    try:
        import PySide6  # noqa: F401 - only to locate the Qt directory
    except ImportError:
        return []
    qt = Path(PySide6.__file__).resolve().parent / "Qt"
    return [f for f in (qt / "plugins" / "platforms" / "libqxcb.so", qt / "lib" / "libQt6XcbQpa.so.6") if f.exists()]


def _loadable(soname: str) -> bool:
    import ctypes

    try:
        ctypes.CDLL(soname)
        return True
    except OSError:
        return False


def missing_xcb_libs(runner: Optional[Runner] = None) -> List[str]:
    """Sonames Qt's X11 plugin needs but this system lacks (empty = X11 mode will start)."""
    files = _qt_xcb_plugin_files()
    ldd = shutil.which("ldd")
    if files and ldd:
        run = runner or subprocess.run
        missing = set()
        try:
            for f in files:
                res = run([ldd, str(f)], capture_output=True, text=True, timeout=10)
                for line in res.stdout.splitlines():
                    if "not found" in line:
                        missing.add(line.split("=>")[0].strip())
            return sorted(missing)
        except (OSError, subprocess.SubprocessError):
            pass
    return [lib for lib in XCB_LIBS if not _loadable(lib)]


def missing_system_packages() -> List[str]:
    """apt packages to install for the full experience (X11 mode + voice wave)."""
    libs = missing_xcb_libs() + [lib for lib in AUDIO_LIBS if not _loadable(lib)]
    return sorted({deb_package(lib) for lib in libs})


def apt_hint(packages: Sequence[str]) -> str:
    return "sudo apt install " + " ".join(packages) if packages else ""


def xcb_runtime_available() -> bool:
    """True when every library Qt's X11 plugin needs is installed."""
    return not missing_xcb_libs()


def choose_qt_platform(env: Optional[Dict[str, str]] = None) -> Tuple[Optional[str], bool]:
    """Return (QT_QPA_PLATFORM to set or None to keep, limited_wayland_mode).

    The bubble needs XWayland on GNOME: native Wayland clients cannot position
    themselves or stay on top. If the user set QT_QPA_PLATFORM we respect it.
    """
    env = dict(os.environ if env is None else env)
    if env.get("SELFICAMERA_PLATFORM"):
        return env["SELFICAMERA_PLATFORM"], env["SELFICAMERA_PLATFORM"].startswith("wayland")
    if env.get("QT_QPA_PLATFORM"):
        return None, env["QT_QPA_PLATFORM"].startswith("wayland")
    wayland = bool(env.get("WAYLAND_DISPLAY")) or env.get("XDG_SESSION_TYPE", "").lower() == "wayland"
    if not wayland:
        return "xcb", False  # pure X11 session: there is nothing to fall back to
    if env.get("DISPLAY") and xcb_runtime_available():
        # Fallback list: if the X11 plugin still fails to start, Qt uses Wayland instead of aborting.
        return "xcb;wayland", False
    return "wayland", True


# ----------------------------------------------------------------- autostart
def autostart_enabled() -> bool:
    return autostart_path().exists()


def set_autostart(enabled: bool) -> bool:
    path = autostart_path()
    try:
        if enabled:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                "[Desktop Entry]\nType=Application\nName=SelfiCamera\nComment=Camera overlay for screen recording\n"
                f"Exec={launcher_command()}\nIcon=selficamera\nTerminal=false\nX-GNOME-Autostart-enabled=true\n"
                "X-GNOME-Autostart-Delay=3\n",
                encoding="utf-8",
            )
        elif path.exists():
            path.unlink()
        return True
    except OSError as exc:
        logger.error("Could not update autostart entry: %s", exc)
        return False


# ------------------------------------------------------------ GNOME bindings
def _parse_gvariant_strv(text: str) -> List[str]:
    text = text.strip()
    if text.startswith("@as"):
        text = text[3:].strip()
    try:
        value = ast.literal_eval(text)
    except (ValueError, SyntaxError):
        return []
    return [str(v) for v in value] if isinstance(value, (list, tuple)) else []


class GnomeShortcuts:
    """Installs SelfiCamera hotkeys as GNOME custom keybindings via ``gsettings``."""

    def __init__(self, runner: Optional[Runner] = None, gsettings: Optional[str] = None) -> None:
        self._run = runner or subprocess.run
        self._gsettings = gsettings or shutil.which("gsettings")

    @property
    def available(self) -> bool:
        if not self._gsettings:
            return False
        try:
            out = self._run([self._gsettings, "list-schemas"], capture_output=True, text=True, timeout=5)
            return GNOME_SCHEMA in (out.stdout or "")
        except Exception:
            return False

    def _get_list(self) -> List[str]:
        out = self._run([self._gsettings, "get", GNOME_SCHEMA, GNOME_KEY], capture_output=True, text=True, timeout=5)
        return _parse_gvariant_strv(out.stdout or "[]")

    def _set_list(self, paths: Sequence[str]) -> None:
        value = "[" + ", ".join(f"'{p}'" for p in paths) + "]"
        self._run([self._gsettings, "set", GNOME_SCHEMA, GNOME_KEY, value], check=True, capture_output=True, text=True, timeout=5)

    def _set_binding(self, path: str, name: str, command: str, accel: str) -> None:
        schema = f"{GNOME_SCHEMA}.custom-keybinding:{path}"
        for key, val in (("name", name), ("command", command), ("binding", accel)):
            self._run([self._gsettings, "set", schema, key, val], check=True, capture_output=True, text=True, timeout=5)

    def installed(self) -> bool:
        if not self._gsettings:
            return False
        try:
            return any(GNOME_PREFIX in p for p in self._get_list())
        except Exception:
            return False

    def install(self, launcher: Optional[str] = None) -> Tuple[bool, str]:
        if not self.available:
            return False, "GNOME settings (gsettings) not found. Add the shortcuts in your desktop's keyboard settings."
        launcher = launcher or launcher_command()
        try:
            current = [p for p in self._get_list() if GNOME_PREFIX not in p]
            ours: List[str] = []
            for sid, label, args, accel in SHORTCUTS:
                path = f"{GNOME_BASE}{GNOME_PREFIX}{sid}/"
                self._set_binding(path, label, f"{launcher} {args}", accel)
                ours.append(path)
            self._set_list(current + ours)
            return True, f"Installed {len(ours)} shortcuts. They work right away."
        except Exception as exc:
            logger.error("Installing GNOME shortcuts failed: %s", exc)
            return False, f"Could not install shortcuts: {exc}"

    def remove(self) -> Tuple[bool, str]:
        if not self._gsettings:
            return False, "gsettings not found."
        try:
            current = self._get_list()
            keep = [p for p in current if GNOME_PREFIX not in p]
            for p in current:
                if GNOME_PREFIX in p:
                    self._run(
                        [self._gsettings, "reset-recursively", f"{GNOME_SCHEMA}.custom-keybinding:{p}"],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
            self._set_list(keep)
            return True, "Shortcuts removed."
        except Exception as exc:
            return False, f"Could not remove shortcuts: {exc}"

    def state(self) -> Tuple[bool, bool, str]:
        """(available, installed, message) for the settings UI."""
        if not self.available:
            return False, False, "Not a GNOME session. Use your desktop's keyboard settings with the commands below."
        if self.installed():
            return True, True, "Installed. Change keys in Settings → Keyboard → Custom Shortcuts."
        return True, False, "Not installed yet."


# ------------------------------------------------------- shadow extensions
# GNOME extensions that draw their own rounded corners + box shadow around every
# normal window. On native Wayland the bubble is a normal window, so they paint a
# rectangle shadow around the transparent margin. Each one has an app blacklist:
# (extension uuid, schema id, list key, "list is a whitelist" flag key or None).
SHADOW_EXTENSIONS: Tuple[Tuple[str, str, str, Optional[str]], ...] = (
    ("rounded-window-corners@fxgn", "org.gnome.shell.extensions.rounded-window-corners-reborn", "blacklist", "whitelist"),
    ("rounded-window-corners@yilozt", "org.gnome.shell.extensions.rounded-window-corners", "black-list", None),
)
APP_WM_CLASS = "selficamera"  # Wayland app id / X11 WM_CLASS (QGuiApplication.desktopFileName)


def _extension_dirs(uuid: str) -> List[Path]:
    data = Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share"))
    roots = [data] + [Path(d) for d in (os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share").split(":") if d]
    return [r / "gnome-shell" / "extensions" / uuid for r in roots if (r / "gnome-shell" / "extensions" / uuid).is_dir()]


class ShadowExtensions:
    """Keeps the bubble out of GNOME extensions that add window shadows."""

    def __init__(self, runner: Optional[Runner] = None, gsettings: Optional[str] = None) -> None:
        self._run = runner or subprocess.run
        self._gsettings = gsettings if gsettings is not None else shutil.which("gsettings")

    def _cmd(self, ext_dir: Path, *args: str) -> Optional[str]:
        cmd = [self._gsettings or "gsettings"]
        schemas = ext_dir / "schemas"
        if (schemas / "gschemas.compiled").exists():
            cmd += ["--schemadir", str(schemas)]
        res = self._run(cmd + list(args), capture_output=True, text=True, timeout=5)
        return res.stdout.strip() if res.returncode == 0 else None

    def found(self) -> List[Tuple[str, Path, str, str, Optional[str]]]:
        out = []
        for uuid, schema, key, wl_key in SHADOW_EXTENSIONS:
            for d in _extension_dirs(uuid):
                out.append((uuid, d, schema, key, wl_key))
                break
        return out

    def exclude(self, enable: bool = True) -> List[str]:
        """Add (or with ``enable=False`` remove) SelfiCamera from each extension's exclusion list.

        Returns the uuids that were changed. Never raises.
        """
        if not self._gsettings:
            return []
        changed = []
        for uuid, ext_dir, schema, key, wl_key in self.found():
            try:
                current_raw = self._cmd(ext_dir, "get", schema, key)
                if current_raw is None:
                    continue
                current = _parse_gvariant_strv(current_raw)
                whitelist = wl_key is not None and self._cmd(ext_dir, "get", schema, wl_key) == "true"
                # In whitelist mode the list names apps that DO get the effect.
                want_listed = enable != whitelist
                listed = APP_WM_CLASS in current
                if want_listed == listed:
                    continue
                new = current + [APP_WM_CLASS] if want_listed else [c for c in current if c != APP_WM_CLASS]
                if self._cmd(ext_dir, "set", schema, key, str(new)) is not None:
                    changed.append(uuid)
                    logger.info("%s SelfiCamera in %s so it does not draw a box shadow", "Excluded" if enable else "Restored", uuid)
            except Exception as exc:  # pragma: no cover - defensive, desktop specific
                logger.debug("Could not update %s: %s", uuid, exc)
        return changed


# ---------------------------------------------------------------- AI model
def litert_available() -> bool:
    for mod in ("ai_edge_litert.interpreter", "tflite_runtime.interpreter"):
        try:
            __import__(mod)
            return True
        except ImportError:
            continue
    return False


def install_model(dest_dir: Optional[Path] = None, url: str = MODEL_URL, opener: Callable = urllib.request.urlopen) -> Tuple[bool, str]:
    """Download the MediaPipe Selfie Segmenter (Apache-2.0) once, for offline use."""
    from selficamera.processor.segmentation import user_model_dir

    dest_dir = dest_dir or user_model_dir()
    dest = dest_dir / "selfie_segmenter.tflite"
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
        with opener(url, timeout=30) as resp:
            data = resp.read()
        if len(data) < 50_000 or data[4:8] != b"TFL3":
            return False, "Downloaded file is not a TFLite model; nothing was installed."
        tmp = dest.with_suffix(".part")
        tmp.write_bytes(data)
        os.replace(tmp, dest)
    except Exception as exc:
        return False, f"Download failed: {exc}"
    msg = f"Model installed to {dest} ({len(data) // 1024} KB)."
    if not litert_available():
        msg += " Also install the runtime:  pip install ai-edge-litert  (run.sh does this automatically)."
    return True, msg


def install_face_model(dest_dir: Optional[Path] = None, url: str = FACE_MODEL_URL, opener: Callable = urllib.request.urlopen) -> Tuple[bool, str]:
    """Download the YuNet face detector (MIT) once, for face-based auto light."""
    import cv2

    from selficamera.processor.face import FACE_MODEL_FILENAME
    from selficamera.processor.segmentation import user_model_dir

    dest_dir = dest_dir or user_model_dir()
    dest = dest_dir / FACE_MODEL_FILENAME
    tmp = dest.with_suffix(".part.onnx")
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
        with opener(url, timeout=30) as resp:
            data = resp.read()
        if len(data) < 50_000:
            return False, "Downloaded file is not the face model; nothing was installed."
        tmp.write_bytes(data)
        try:
            cv2.FaceDetectorYN.create(str(tmp), "", (320, 320))
        except cv2.error:
            tmp.unlink(missing_ok=True)
            return False, "Downloaded file is not a valid face model; nothing was installed."
        os.replace(tmp, dest)
    except Exception as exc:
        tmp.unlink(missing_ok=True)
        return False, f"Face model download failed: {exc}"
    return True, f"Face model installed to {dest} ({len(data) // 1024} KB)."
