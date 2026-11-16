import json

import pytest

from selficamera.config import (
    DEFAULT_CONFIG,
    MAX_SIZE,
    MIN_SIZE,
    SCHEMA_VERSION,
    ConfigManager,
    migrate,
    parse_cli_value,
    validate_value,
)


def test_defaults_when_missing(config_path):
    cfg = ConfigManager(config_path)
    assert cfg.as_dict() == DEFAULT_CONFIG
    assert not config_path.exists()


def test_save_and_reload_roundtrip(config_path):
    cfg = ConfigManager(config_path)
    cfg.set("shape", "landscape")
    cfg.set("size", 333)
    assert cfg.dirty
    assert cfg.save()
    assert not cfg.dirty
    again = ConfigManager(config_path)
    assert again.get("shape") == "landscape"
    assert again.get("size") == 333


def test_set_does_not_write_until_save(config_path):
    cfg = ConfigManager(config_path)
    cfg.set("brightness", 10)
    assert not config_path.exists()
    cfg.save_if_dirty()
    assert config_path.exists()


@pytest.mark.parametrize(
    "key,value,expected",
    [
        ("size", 50, MIN_SIZE),
        ("size", 5000, MAX_SIZE),
        ("zoom", 9, 3.0),
        ("pan_x", -4, -1.0),
        ("border_color", "#7c5cff", "#7C5CFF"),
        ("mirror", "off", False),
        ("resolution", "1920x1080", [1920, 1080]),
        ("x", None, None),
    ],
)
def test_validation_normalises(key, value, expected):
    assert validate_value(key, value) == expected


@pytest.mark.parametrize(
    "key,value",
    [("shape", "hexagon"), ("border_color", "red"), ("background_mode", "sparkles"), ("size", True), ("resolution", [1])],
)
def test_validation_rejects(key, value):
    with pytest.raises(ValueError):
        validate_value(key, value)


def test_unknown_key_rejected():
    with pytest.raises(KeyError):
        validate_value("nope", 1)


def test_corrupted_file_falls_back(config_path):
    config_path.parent.mkdir(parents=True)
    config_path.write_text("{not json")
    assert ConfigManager(config_path).get("size") == DEFAULT_CONFIG["size"]


def test_bad_values_are_dropped_per_key(config_path):
    config_path.parent.mkdir(parents=True)
    config_path.write_text(json.dumps({"version": 2, "shape": "triangle", "size": 300}))
    cfg = ConfigManager(config_path)
    assert cfg.get("shape") == "circle"
    assert cfg.get("size") == 300


def test_migrates_v1_config(config_path):
    config_path.parent.mkdir(parents=True)
    legacy = {"diameter": 380, "x": 100, "y": 200, "blur_level": 3, "blur_intensity": 85, "aura_enabled": False, "manual_gamma": 1.4}
    config_path.write_text(json.dumps(legacy))
    cfg = ConfigManager(config_path)
    assert cfg.get("size") == 380
    assert cfg.get("background_mode") == "blur"
    assert cfg.get("blur_strength") == 85
    assert cfg.get("voice_glow") is False
    # v1 stored the window's top-left; v2 stores the bubble center.
    assert cfg.get("x") == 100 + (380 + 32) // 2
    assert cfg.get("first_run") is False
    assert "manual_gamma" not in cfg.as_dict()


def test_migrate_noop_for_current_schema():
    data = {"version": SCHEMA_VERSION, "size": 200}
    assert migrate(data) == data


def test_scenes_save_apply_delete(config_path):
    cfg = ConfigManager(config_path)
    cfg.update(shape="portrait", size=300, x=10, y=20)
    snap = cfg.save_scene("  Shorts  ")
    assert snap["shape"] == "portrait"
    assert cfg.scene_names() == ["Shorts"]
    cfg.set("shape", "circle")
    assert cfg.get_scene("Shorts")["shape"] == "portrait"
    assert cfg.delete_scene("Shorts")
    assert not cfg.delete_scene("Shorts")
    with pytest.raises(ValueError):
        cfg.save_scene("   ")


def test_reset_keeps_scenes(config_path):
    cfg = ConfigManager(config_path)
    cfg.save_scene("Intro")
    cfg.set("size", 500)
    cfg.reset_to_defaults()
    assert cfg.get("size") == DEFAULT_CONFIG["size"]
    assert cfg.scene_names() == ["Intro"]


def test_parse_cli_value_types():
    assert parse_cli_value("size", "320") == 320
    assert parse_cli_value("mirror", "false") is False
    assert parse_cli_value("background_mode", "blur") == "blur"
    assert parse_cli_value("zoom", "1.5") == 1.5
    with pytest.raises(ValueError):
        parse_cli_value("shape", "star")
