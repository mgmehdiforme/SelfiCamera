"""Tests for Configuration Manager and atomic persistence."""

import json
from pathlib import Path
from selficamera.config import DEFAULT_CONFIG, ConfigManager


def test_default_config_loading(temp_config_file: Path):
    """Verify that default config is returned when file does not exist."""
    assert not temp_config_file.exists()
    mgr = ConfigManager(config_path=temp_config_file)
    assert mgr.get("diameter") == 260
    assert mgr.get("mirror") is True
    assert mgr.get("auto_light") is True
    assert mgr.get("blur_level") == 2
    assert mgr.get("click_through") is False
    assert mgr.get("always_on_top") is True
    assert mgr.get("manual_gamma") == 1.0
    assert mgr.get("target_luminance") == 125.0
    assert mgr.get("blur_intensity") == 50


def test_atomic_save_and_reload(temp_config_file: Path):
    """Verify atomic write persists valid JSON and survives reloading."""
    mgr = ConfigManager(config_path=temp_config_file)
    mgr.set("diameter", 380)
    mgr.set("blur_level", 3)
    mgr.set("click_through", True)

    assert temp_config_file.exists()

    # Create new instance pointing to same file
    mgr2 = ConfigManager(config_path=temp_config_file)
    assert mgr2.get("diameter") == 380
    assert mgr2.get("blur_level") == 3
    assert mgr2.get("click_through") is True


def test_corrupted_config_recovery(temp_config_file: Path):
    """Verify that corrupted or invalid JSON recovers to default state gracefully."""
    temp_config_file.parent.mkdir(parents=True, exist_ok=True)
    temp_config_file.write_text("{ this is corrupted invalid json : [", encoding="utf-8")

    mgr = ConfigManager(config_path=temp_config_file)
    assert mgr.get("diameter") == 260
    assert mgr.get("blur_level") == 2


def test_invalid_value_sanitization(temp_config_file: Path):
    """Verify that out-of-range diameter or blur level are clamped/reverted to valid defaults."""
    temp_config_file.parent.mkdir(parents=True, exist_ok=True)
    bad_data = {
        "diameter": 9999,  # invalid: outside range [120, 600]
        "blur_level": -5,  # invalid: must be 0..3
    }
    temp_config_file.write_text(json.dumps(bad_data), encoding="utf-8")

    mgr = ConfigManager(config_path=temp_config_file)
    assert mgr.get("diameter") == 260
    assert mgr.get("blur_level") == 2

    # Underflow check: diameter < 120
    temp_config_file.write_text(json.dumps({"diameter": 50}), encoding="utf-8")
    mgr_under = ConfigManager(config_path=temp_config_file)
    assert mgr_under.get("diameter") == 260


def test_continuous_diameter_range_persistence(temp_config_file: Path):
    """Verify that any continuous diameter in range [120, 600] is preserved."""
    mgr = ConfigManager(config_path=temp_config_file)
    for test_d in [120, 215, 340, 500, 600]:
        mgr.set("diameter", test_d)
        reloaded = ConfigManager(config_path=temp_config_file)
        assert reloaded.get("diameter") == test_d


def test_update_and_reset(temp_config_file: Path):
    """Verify batch updates and reset to defaults."""
    mgr = ConfigManager(config_path=temp_config_file)
    mgr.update(auto_save=True, diameter=160, mirror=False)
    assert mgr.get("diameter") == 160
    assert mgr.get("mirror") is False

    mgr.reset_to_defaults()
    assert mgr.get("diameter") == DEFAULT_CONFIG["diameter"]
    assert mgr.get("mirror") == DEFAULT_CONFIG["mirror"]

