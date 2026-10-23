"""Configuration management subsystem with atomic JSON persistence."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

DEFAULT_CONFIG: Dict[str, Any] = {
    "diameter": 260,
    "x": 1600,
    "y": 760,
    "device_path": "/dev/video0",
    "resolution": [1280, 720],
    "fps": 30,
    "mirror": True,
    "auto_light": True,
    "blur_level": 2,
    "click_through": False,
    "mic_device": "default",
    "aura_enabled": True,
    "always_on_top": True,
    "manual_gamma": 1.0,
    "target_luminance": 125.0,
    "blur_intensity": 50,
}

MIN_DIAMETER = 120
MAX_DIAMETER = 600
PRESET_DIAMETERS = (160, 260, 380)
VALID_DIAMETERS = PRESET_DIAMETERS
VALID_BLUR_LEVELS = (0, 1, 2, 3)


class ConfigManager:
    """Manages application configuration with atomic JSON file persistence."""

    def __init__(self, config_path: str | Path | None = None) -> None:
        if config_path is not None:
            self._path = Path(config_path).resolve()
        else:
            config_dir = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "selficamera"
            self._path = config_dir / "config.json"

        self._data: Dict[str, Any] = dict(DEFAULT_CONFIG)
        self.load()

    @property
    def path(self) -> Path:
        """Return the active configuration file path."""
        return self._path

    def load(self) -> Dict[str, Any]:
        """Load configuration from disk. Falls back to defaults if missing or corrupted."""
        if not self._path.exists():
            self._data = dict(DEFAULT_CONFIG)
            return dict(self._data)

        try:
            with open(self._path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                # Validate & merge
                merged = dict(DEFAULT_CONFIG)
                merged.update(loaded)
                # Sanitize constraints
                d = merged.get("diameter")
                if not (isinstance(d, (int, float)) and MIN_DIAMETER <= d <= MAX_DIAMETER):
                    merged["diameter"] = DEFAULT_CONFIG["diameter"]
                else:
                    merged["diameter"] = int(round(d))

                if merged.get("blur_level") not in VALID_BLUR_LEVELS:
                    merged["blur_level"] = DEFAULT_CONFIG["blur_level"]
                self._data = merged
            else:
                logger.warning("Config file root is not an object. Reverting to defaults.")
                self._data = dict(DEFAULT_CONFIG)
        except Exception as e:
            logger.warning("Failed to load config from %s: %s. Reverting to defaults.", self._path, e)
            self._data = dict(DEFAULT_CONFIG)

        return dict(self._data)

    def save(self) -> bool:
        """Atomically persist configuration to disk."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self._path.parent / f"{self._path.name}.tmp.{os.getpid()}"
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())

            os.replace(temp_path, self._path)
            return True
        except Exception as e:
            logger.error("Failed to save config atomically to %s: %s", self._path, e)
            return False

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve a configuration value."""
        return self._data.get(key, default)

    def set(self, key: str, value: Any, auto_save: bool = True) -> None:
        """Set a configuration value and optionally persist immediately."""
        self._data[key] = value
        if auto_save:
            self.save()

    def update(self, auto_save: bool = True, **kwargs: Any) -> None:
        """Update multiple configuration keys and optionally persist."""
        self._data.update(kwargs)
        if auto_save:
            self.save()

    def reset_to_defaults(self, auto_save: bool = True) -> None:
        """Reset configuration back to standard defaults."""
        self._data = dict(DEFAULT_CONFIG)
        if auto_save:
            self.save()

    def as_dict(self) -> Dict[str, Any]:
        """Return a copy of the configuration dictionary."""
        return dict(self._data)
