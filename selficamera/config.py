"""Configuration schema, validation, migration and atomic JSON persistence.

The config module is intentionally Qt-free so it can be used by the lightweight IPC
client and by tests.  Saving is explicit: the application debounces writes with a
timer instead of fsync-ing on every slider tick.
"""

from __future__ import annotations

import copy
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 2

MIN_SIZE = 120
MAX_SIZE = 800
SIZE_PRESETS: Dict[str, int] = {"S": 180, "M": 260, "L": 380}

SHAPES: Tuple[str, ...] = ("circle", "rounded", "landscape", "portrait")
SHAPE_LABELS: Dict[str, str] = {
    "circle": "Circle",
    "rounded": "Rounded",
    "landscape": "Wide 16:9",
    "portrait": "Tall 9:16",
}

BACKGROUND_MODES: Tuple[str, ...] = ("none", "blur", "color", "image", "remove")
BACKGROUND_LABELS: Dict[str, str] = {
    "none": "None",
    "blur": "Blur",
    "color": "Color",
    "image": "Image",
    "remove": "Remove",
}

RESOLUTIONS: Tuple[Tuple[int, int], ...] = ((640, 480), (1280, 720), (1920, 1080))
FPS_CHOICES: Tuple[int, ...] = (24, 30, 60)

BORDER_COLOR_PRESETS: Tuple[str, ...] = (
    "#FFFFFF",
    "#7C5CFF",
    "#00D1FF",
    "#22C55E",
    "#FACC15",
    "#FF5C8A",
    "#FF3B30",
    "#111111",
)
BACKGROUND_COLOR_PRESETS: Tuple[str, ...] = ("#00B140", "#0047BB", "#111111", "#F5F5F5", "#7C5CFF", "#1E293B")

# Keys that a "scene" captures.
SCENE_KEYS: Tuple[str, ...] = (
    "shape",
    "size",
    "x",
    "y",
    "border_width",
    "border_color",
    "voice_glow",
    "shadow",
    "background_mode",
    "blur_strength",
    "background_color",
    "background_image",
    "zoom",
    "pan_x",
    "pan_y",
    "auto_frame",
    "mirror",
)

DEFAULT_CONFIG: Dict[str, Any] = {
    "version": SCHEMA_VERSION,
    "first_run": True,
    # Camera
    "device_path": "/dev/video0",
    "resolution": [1280, 720],
    "fps": 30,
    "mirror": True,
    # Bubble
    "shape": "circle",
    "size": 260,
    "x": None,
    "y": None,
    "border_width": 3,
    "border_color": "#FFFFFF",
    "voice_glow": True,
    "shadow": True,
    "mic_device": None,
    "spotlight_scale": 0.62,
    # Framing
    "zoom": 1.0,
    "pan_x": 0.0,
    "pan_y": 0.0,
    "auto_frame": False,
    # Light & color
    "auto_light": True,
    "brightness": 0,
    "contrast": 0,
    "saturation": 0,
    "warmth": 0,
    # Background
    "background_mode": "none",
    "blur_strength": 60,
    "background_color": "#00B140",
    "background_image": "",
    # Behaviour
    "always_on_top": True,
    "click_through": False,
    "show_controls_on_hover": True,
    "visible": True,
    # Scenes
    "scenes": {},
}

_HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


def _clamp_num(lo: float, hi: float, cast: Callable[[Any], Any]) -> Callable[[Any], Any]:
    def _v(value: Any) -> Any:
        if isinstance(value, bool):
            raise ValueError("boolean is not a number")
        num = cast(float(value))
        return cast(max(lo, min(hi, num)))

    return _v


def _int_round(value: float) -> int:
    return int(round(value))


def _choice(options: Iterable[str]) -> Callable[[Any], str]:
    allowed = tuple(options)

    def _v(value: Any) -> str:
        if value not in allowed:
            raise ValueError(f"must be one of {allowed}")
        return str(value)

    return _v


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        low = value.strip().lower()
        if low in ("1", "true", "yes", "on"):
            return True
        if low in ("0", "false", "no", "off"):
            return False
    raise ValueError("not a boolean")


def _color(value: Any) -> str:
    if isinstance(value, str) and _HEX_COLOR.match(value.strip()):
        return value.strip().upper()
    raise ValueError("expected #RRGGBB color")


def _resolution(value: Any) -> List[int]:
    if isinstance(value, str) and "x" in value.lower():
        value = [int(p) for p in value.lower().split("x", 1)]
    if isinstance(value, (list, tuple)) and len(value) == 2:
        w, h = int(value[0]), int(value[1])
        if 160 <= w <= 7680 and 120 <= h <= 4320:
            return [w, h]
    raise ValueError("expected [width, height]")


def _optional_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise ValueError("boolean is not a coordinate")
    return int(round(float(value)))


def _optional_str(value: Any) -> Optional[str]:
    if value is None or value == "":
        return None
    return str(value)


def _path_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _scenes(value: Any) -> Dict[str, Dict[str, Any]]:
    if not isinstance(value, dict):
        raise ValueError("scenes must be an object")
    out: Dict[str, Dict[str, Any]] = {}
    for name, scene in value.items():
        if not isinstance(scene, dict) or not str(name).strip():
            continue
        clean: Dict[str, Any] = {}
        for key, val in scene.items():
            if key in SCENE_KEYS:
                try:
                    clean[key] = VALIDATORS[key](val)
                except (ValueError, TypeError):
                    continue
        out[str(name).strip()[:40]] = clean
    return out


VALIDATORS: Dict[str, Callable[[Any], Any]] = {
    "version": lambda v: SCHEMA_VERSION,
    "first_run": _bool,
    "device_path": lambda v: str(v),
    "resolution": _resolution,
    "fps": _clamp_num(5, 120, _int_round),
    "mirror": _bool,
    "shape": _choice(SHAPES),
    "size": _clamp_num(MIN_SIZE, MAX_SIZE, _int_round),
    "x": _optional_int,
    "y": _optional_int,
    "border_width": _clamp_num(0, 16, _int_round),
    "border_color": _color,
    "voice_glow": _bool,
    "shadow": _bool,
    "mic_device": _optional_str,
    "spotlight_scale": _clamp_num(0.3, 0.9, float),
    "zoom": _clamp_num(1.0, 3.0, float),
    "pan_x": _clamp_num(-1.0, 1.0, float),
    "pan_y": _clamp_num(-1.0, 1.0, float),
    "auto_frame": _bool,
    "auto_light": _bool,
    "brightness": _clamp_num(-50, 50, _int_round),
    "contrast": _clamp_num(-50, 50, _int_round),
    "saturation": _clamp_num(-100, 100, _int_round),
    "warmth": _clamp_num(-50, 50, _int_round),
    "background_mode": _choice(BACKGROUND_MODES),
    "blur_strength": _clamp_num(0, 100, _int_round),
    "background_color": _color,
    "background_image": _path_str,
    "always_on_top": _bool,
    "click_through": _bool,
    "show_controls_on_hover": _bool,
    "visible": _bool,
    "scenes": _scenes,
}


def validate_value(key: str, value: Any) -> Any:
    """Validate and normalise a single setting value. Raises KeyError / ValueError."""
    if key not in VALIDATORS:
        raise KeyError(f"Unknown setting '{key}'")
    return VALIDATORS[key](value)


def parse_cli_value(key: str, raw: str) -> Any:
    """Parse a `--set key=value` string into a typed, validated value."""
    if key not in VALIDATORS:
        raise KeyError(f"Unknown setting '{key}'")
    candidate: Any = raw
    try:
        candidate = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        candidate = raw
    return validate_value(key, candidate)


def migrate(data: Dict[str, Any]) -> Dict[str, Any]:
    """Migrate a 0.1.x (schema 1) config dict to the current schema."""
    version = data.get("version", 1)
    if not isinstance(version, int) or version >= SCHEMA_VERSION:
        return data

    migrated = dict(data)
    if "diameter" in migrated and "size" not in migrated:
        migrated["size"] = migrated.pop("diameter")
    # 0.1 stored the window's top-left corner (window = diameter + 2*16 px shadow margin);
    # 1.0 stores the bubble center so position survives shape and size changes.
    try:
        d = float(migrated.get("size", 260))
        if isinstance(migrated.get("x"), (int, float)) and isinstance(migrated.get("y"), (int, float)):
            migrated["x"] = int(migrated["x"] + (d + 32) / 2)
            migrated["y"] = int(migrated["y"] + (d + 32) / 2)
    except (TypeError, ValueError):
        migrated.pop("x", None)
        migrated.pop("y", None)
    blur_level = migrated.pop("blur_level", None)
    intensity = migrated.pop("blur_intensity", None)
    if "background_mode" not in migrated and blur_level is not None:
        migrated["background_mode"] = "blur" if blur_level in (1, 2, 3) else "none"
        if isinstance(intensity, (int, float)) and intensity > 0:
            migrated["blur_strength"] = int(intensity)
        else:
            migrated["blur_strength"] = {1: 35, 2: 60, 3: 90}.get(blur_level, 60)
    if "aura_enabled" in migrated:
        migrated["voice_glow"] = migrated.pop("aura_enabled")
    if migrated.get("mic_device") == "default":
        migrated["mic_device"] = None
    for legacy in ("manual_gamma", "target_luminance"):
        migrated.pop(legacy, None)
    migrated["first_run"] = False
    migrated["version"] = SCHEMA_VERSION
    logger.info("Migrated configuration from schema %s to %s", version, SCHEMA_VERSION)
    return migrated


def default_config_path() -> Path:
    base = Path(os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config"))
    return base / "selficamera" / "config.json"


class ConfigManager:
    """Validated configuration store with atomic JSON persistence."""

    def __init__(self, config_path: str | Path | None = None) -> None:
        self._path = Path(config_path).expanduser().resolve() if config_path else default_config_path()
        self._data: Dict[str, Any] = copy.deepcopy(DEFAULT_CONFIG)
        self._dirty = False
        self.load()

    @property
    def path(self) -> Path:
        return self._path

    @property
    def dirty(self) -> bool:
        return self._dirty

    def load(self) -> Dict[str, Any]:
        """Load configuration from disk, falling back to defaults per key on bad values."""
        self._data = copy.deepcopy(DEFAULT_CONFIG)
        if not self._path.exists():
            return self.as_dict()
        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                loaded = json.load(fh)
        except Exception as exc:  # corrupted or unreadable file
            logger.warning("Could not read config %s (%s). Using defaults.", self._path, exc)
            return self.as_dict()
        if not isinstance(loaded, dict):
            logger.warning("Config root is not an object. Using defaults.")
            return self.as_dict()

        loaded = migrate(loaded)
        for key, value in loaded.items():
            if key not in VALIDATORS:
                continue
            try:
                self._data[key] = validate_value(key, value)
            except (ValueError, TypeError) as exc:
                logger.warning("Ignoring invalid config value %s=%r (%s)", key, value, exc)
        self._dirty = False
        return self.as_dict()

    def save(self) -> bool:
        """Atomically persist the configuration."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._path.parent / f".{self._path.name}.{os.getpid()}.tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(self._data, fh, indent=2, sort_keys=True)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, self._path)
            self._dirty = False
            return True
        except Exception as exc:
            logger.error("Failed to save config to %s: %s", self._path, exc)
            return False

    def save_if_dirty(self) -> bool:
        return self.save() if self._dirty else True

    def get(self, key: str, default: Any = None) -> Any:
        value = self._data.get(key, default)
        return copy.deepcopy(value) if isinstance(value, (dict, list)) else value

    def set(self, key: str, value: Any, auto_save: bool = False) -> Any:
        """Validate and store a value. Returns the normalised value."""
        clean = validate_value(key, value)
        if self._data.get(key) != clean:
            self._data[key] = clean
            self._dirty = True
        if auto_save:
            self.save()
        return clean

    def update(self, auto_save: bool = False, **kwargs: Any) -> Dict[str, Any]:
        out = {k: self.set(k, v) for k, v in kwargs.items()}
        if auto_save:
            self.save()
        return out

    def reset_to_defaults(self, keep: Iterable[str] = ("scenes", "first_run"), auto_save: bool = True) -> None:
        preserved = {k: self._data.get(k) for k in keep}
        self._data = copy.deepcopy(DEFAULT_CONFIG)
        self._data.update(preserved)
        self._dirty = True
        if auto_save:
            self.save()

    def as_dict(self) -> Dict[str, Any]:
        return copy.deepcopy(self._data)

    # --- Scenes -------------------------------------------------------------
    def scene_names(self) -> List[str]:
        return list(self._data.get("scenes", {}).keys())

    def save_scene(self, name: str) -> Dict[str, Any]:
        name = name.strip()[:40]
        if not name:
            raise ValueError("Scene name cannot be empty")
        snapshot = {k: copy.deepcopy(self._data.get(k)) for k in SCENE_KEYS}
        scenes = dict(self._data.get("scenes", {}))
        scenes[name] = snapshot
        self._data["scenes"] = scenes
        self._dirty = True
        return snapshot

    def delete_scene(self, name: str) -> bool:
        scenes = dict(self._data.get("scenes", {}))
        if name not in scenes:
            return False
        del scenes[name]
        self._data["scenes"] = scenes
        self._dirty = True
        return True

    def get_scene(self, name: str) -> Optional[Dict[str, Any]]:
        scene = self._data.get("scenes", {}).get(name)
        return copy.deepcopy(scene) if scene is not None else None
