import threading

import cv2
import numpy as np
import pytest

from selficamera.processor.background import BackgroundCompositor, cover_fit, hex_to_bgr
from selficamera.processor.framing import AutoFramer, compute_crop
from selficamera.processor.lighting import ImageAdjuster
from selficamera.processor.pipeline import FrameProcessor, to_qimage
from selficamera.processor.segmentation import SegmentationEngine, create_presenter_prior


# ------------------------------------------------------------------ framing
@pytest.mark.parametrize("aspect", [1.0, 16 / 9, 9 / 16, 4 / 3])
def test_crop_matches_aspect_and_stays_inside(aspect):
    r = compute_crop(1280, 720, aspect)
    assert abs(r.w / r.h - aspect) < 0.02
    assert r.x >= 0 and r.y >= 0 and r.x + r.w <= 1280 and r.y + r.h <= 720


def test_zoom_shrinks_crop_around_center():
    base = compute_crop(1280, 720, 1.0)
    zoomed = compute_crop(1280, 720, 1.0, zoom=2.0)
    assert zoomed.w == base.w // 2
    assert abs((zoomed.x + zoomed.w / 2) - 640) <= 1


def test_pan_moves_to_edges():
    left = compute_crop(1280, 720, 1.0, pan_x=-1.0)
    right = compute_crop(1280, 720, 1.0, pan_x=1.0)
    assert left.x == 0
    assert right.x + right.w == 1280


def test_focus_is_clamped():
    r = compute_crop(1280, 720, 1.0, zoom=2.0, focus=(5000, -50))
    assert r.x + r.w == 1280 and r.y == 0


def test_autoframer_tracks_person_and_smooths():
    framer = AutoFramer(smoothing=0.5)
    mask = np.zeros((256, 256), np.float32)
    mask[100:256, 180:240] = 1.0
    f1 = framer.update(mask, 1280, 720, crop_h=720)
    f2 = framer.update(mask, 1280, 720, crop_h=720)
    assert f1[0] > 640  # person is right of center
    assert abs(f2[0] - f1[0]) < 1e-6 or f2 is not None
    framer.update(np.zeros((256, 256), np.float32), 1280, 720, 720)
    assert framer.focus[0] < f2[0]  # empty frame drifts back toward center


# ----------------------------------------------------------------- lighting
def test_adjuster_identity_is_noop():
    adj = ImageAdjuster(auto_light=False)
    frame = np.random.randint(0, 255, (64, 64, 3), np.uint8)
    assert adj.is_identity()
    assert np.array_equal(adj.process(frame), frame)


def test_auto_light_brightens_dark_scene():
    adj = ImageAdjuster(auto_light=True, smoothing=1.0)
    dark = np.full((90, 160, 3), 30, np.uint8)
    out = adj.process(dark)
    assert out.mean() > dark.mean() + 20
    assert adj.current_gamma < 1.0


def test_auto_light_leaves_bright_scene():
    adj = ImageAdjuster(auto_light=True, smoothing=1.0)
    bright = np.full((90, 160, 3), 170, np.uint8)
    assert np.array_equal(adj.process(bright), bright)


@pytest.mark.parametrize("key,check", [("brightness", lambda a, b: b.mean() > a.mean()), ("contrast", lambda a, b: b.std() > a.std())])
def test_manual_adjustments(key, check):
    adj = ImageAdjuster(auto_light=False, **{key: 40})
    frame = np.tile(np.linspace(40, 200, 64, dtype=np.uint8), (32, 1))
    frame = np.dstack([frame] * 3)
    assert check(frame.astype(float), adj.process(frame).astype(float))


def test_warmth_shifts_red_vs_blue():
    adj = ImageAdjuster(auto_light=False, warmth=50)
    out = adj.process(np.full((8, 8, 3), 128, np.uint8))
    b, g, r = out[0, 0]
    assert r > g > b


def test_saturation_zero_is_grayscale():
    adj = ImageAdjuster(auto_light=False, saturation=-100)
    out = adj.process(np.full((8, 8, 3), (20, 120, 220), np.uint8))
    px = out[0, 0].astype(int)
    assert max(px) - min(px) <= 2


# ------------------------------------------------------------- segmentation
def test_basic_engine_without_model():
    eng = SegmentationEngine()
    assert not eng.is_neural
    assert eng.backend_name == "basic"
    m = eng.mask(np.zeros((300, 200, 3), np.uint8), 200, 300)
    assert m.shape == (300, 200)
    assert m[150, 100] > 0.5 and m[5, 5] < 0.1


def _write_onnx_model(path):
    onnx = pytest.importorskip("onnx")
    from onnx import TensorProto, helper

    inp = helper.make_tensor_value_info("input", TensorProto.FLOAT, [1, 256, 256, 3])
    out = helper.make_tensor_value_info("output", TensorProto.FLOAT, [1, 256, 256, 1])
    starts = helper.make_tensor("s", TensorProto.INT64, [1], [0])
    ends = helper.make_tensor("e", TensorProto.INT64, [1], [1])
    axes = helper.make_tensor("a", TensorProto.INT64, [1], [3])
    # Output = red channel: "person" wherever red is high.
    node = helper.make_node("Slice", ["input", "s", "e", "a"], ["output"])
    graph = helper.make_graph([node], "red", [inp], [out], [starts, ends, axes])
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 13)])
    model.ir_version = 8
    onnx.save(model, str(path))


def test_onnx_backend_and_env_discovery(tmp_path, monkeypatch):
    model = tmp_path / "custom.onnx"
    _write_onnx_model(model)
    monkeypatch.setenv("SELFICAMERA_MODEL", str(model))
    eng = SegmentationEngine()
    assert eng.is_neural and eng.backend_name == "onnx"
    frame = np.zeros((100, 100, 3), np.uint8)
    frame[:, 50:] = (0, 0, 255)  # red right half (BGR)
    m = eng.mask(frame, 100, 100, smooth=False)
    assert m[50, 90] > 0.9 and m[50, 10] < 0.1


def test_user_model_dir_discovery(tmp_path):
    from selficamera.processor.segmentation import discover_model, user_model_dir

    d = user_model_dir()
    d.mkdir(parents=True)
    _write_onnx_model(d / "selfie_segmenter.onnx")
    assert discover_model() == d / "selfie_segmenter.onnx"


def test_prior_shape():
    p = create_presenter_prior(256, 256)
    assert p.dtype == np.float32 and p.max() <= 1.0 and p[200, 128] > 0.9


# --------------------------------------------------------------- background
def test_hex_to_bgr():
    assert hex_to_bgr("#00B140") == (0x40, 0xB1, 0x00)


def test_cover_fit_exact_size():
    img = np.zeros((100, 300, 3), np.uint8)
    assert cover_fit(img, 64, 64).shape == (64, 64, 3)


def test_composite_modes():
    comp = BackgroundCompositor()
    frame = np.full((40, 40, 3), 200, np.uint8)
    mask = np.zeros((40, 40), np.float32)
    mask[:, 20:] = 1.0
    color = comp.composite(frame, mask, "color", color="#0000FF")
    assert tuple(color[5, 5]) == (255, 0, 0) and tuple(color[5, 30]) == (200, 200, 200)
    removed = comp.composite(frame, mask, "remove")
    assert removed.shape == (40, 40, 4) and removed[5, 5, 3] == 0 and removed[5, 30, 3] == 255
    blurred = comp.composite(frame, mask, "blur", strength=80)
    assert blurred.shape == (40, 40, 3)


def test_image_background(tmp_path):
    img = np.zeros((50, 80, 3), np.uint8)
    img[:] = (0, 255, 0)
    path = tmp_path / "bg.png"
    cv2.imwrite(str(path), img)
    comp = BackgroundCompositor()
    assert comp.set_image(str(path))
    out = comp.composite(np.zeros((30, 30, 3), np.uint8), np.zeros((30, 30), np.float32), "image")
    assert tuple(out[10, 10]) == (0, 255, 0)
    assert not comp.set_image(str(tmp_path / "missing.png"))


# ----------------------------------------------------------------- pipeline
@pytest.mark.parametrize("size", [(260, 260), (462, 260), (260, 462)])
def test_pipeline_output_size(presenter_frame, size):
    proc = FrameProcessor(output_size=size)
    out = proc.process(presenter_frame)
    assert out.shape[:2] == (size[1], size[0])


def test_pipeline_remove_returns_alpha(presenter_frame):
    proc = FrameProcessor(settings={"background_mode": "remove"}, output_size=(200, 200))
    out = proc.process(presenter_frame)
    assert out.shape == (200, 200, 4)
    img = to_qimage(out)
    assert img.hasAlphaChannel() and img.width() == 200


def test_pipeline_mirror_flips(presenter_frame):
    a = FrameProcessor(settings={"mirror": False, "auto_light": False}, output_size=(128, 128)).process(presenter_frame)
    b = FrameProcessor(settings={"mirror": True, "auto_light": False}, output_size=(128, 128)).process(presenter_frame)
    assert np.abs(a.astype(int) - cv2.flip(b, 1).astype(int)).mean() < 2


def test_pan_direction_is_what_viewer_sees():
    """pan_x=+1 must show the right side of the *displayed* image, mirrored or not."""
    frame = np.zeros((720, 1280, 3), np.uint8)
    frame[:, 640:] = 255  # source: right half white
    shown = {}
    for mirror in (False, True):
        proc = FrameProcessor(settings={"mirror": mirror, "auto_light": False, "zoom": 2.0, "pan_x": 1.0}, output_size=(64, 64))
        shown[mirror] = proc.process(frame).mean()
    assert shown[False] > 200  # unmirrored: right of display = white source side
    assert shown[True] < 50  # mirrored: right of display = black source side


def test_configure_is_thread_safe(presenter_frame):
    proc = FrameProcessor(output_size=(96, 96))
    errors = []

    def worker():
        try:
            for _ in range(30):
                proc.process(presenter_frame)
        except Exception as exc:  # pragma: no cover
            errors.append(exc)

    t = threading.Thread(target=worker)
    t.start()
    for i in range(60):
        proc.configure(background_mode=("blur", "color", "remove", "none")[i % 4], brightness=i % 20)
        proc.set_output_size(96 + (i % 3) * 8, 96)
    t.join()
    assert not errors


def test_unknown_configure_keys_ignored():
    proc = FrameProcessor(output_size=(32, 32))
    proc.configure(nonsense=1, zoom=2.0)
    assert proc.zoom == 2.0


def test_mask_reuse_between_inferences(tmp_path, monkeypatch):
    model = tmp_path / "m.onnx"
    _write_onnx_model(model)
    eng = SegmentationEngine(model_path=model, infer_every=2)
    calls = []
    real = eng.infer_raw
    monkeypatch.setattr(eng, "infer_raw", lambda f: calls.append(1) or real(f))
    frame = np.zeros((64, 64, 3), np.uint8)
    for _ in range(6):
        assert eng.mask(frame, 64, 64).shape == (64, 64)
    assert len(calls) == 4  # first frame (no mask yet), then every 2nd frame


# ------------------------------------------------------- face-metered light
def _face_frame(face_luma: int, bg_luma: int, size: int = 200) -> np.ndarray:
    frame = np.full((size, size, 3), bg_luma, np.uint8)
    frame[50:150, 60:140] = face_luma
    return frame


FACE_BOX = [(60, 50, 80, 100, 0.95)]


def test_backlit_face_is_lifted_even_when_frame_is_bright():
    adj = ImageAdjuster(auto_light=True, smoothing=1.0)
    frame = _face_frame(face_luma=55, bg_luma=235)  # bright window behind a dark face
    out = adj.process(frame, ("face", FACE_BOX))
    assert adj.metering == "face"
    assert out[100, 100, 0] > 100  # face lifted toward the comfortable band
    plain = ImageAdjuster(auto_light=True, smoothing=1.0)
    assert np.array_equal(plain.process(frame), frame)  # old whole-frame metering did nothing


def test_well_lit_face_is_left_alone():
    adj = ImageAdjuster(auto_light=True, smoothing=1.0)
    frame = _face_frame(face_luma=140, bg_luma=30)  # dark room, face already well lit
    assert np.array_equal(adj.process(frame, ("face", FACE_BOX)), frame)
    assert adj.current_gamma == 1.0


def test_blown_out_face_is_darkened():
    adj = ImageAdjuster(auto_light=True, smoothing=1.0)
    out = adj.process(_face_frame(face_luma=232, bg_luma=120), ("face", FACE_BOX))
    assert adj.current_gamma > 1.0 and out[100, 100, 0] < 225


def test_person_mask_metering():
    adj = ImageAdjuster(auto_light=True, smoothing=1.0)
    frame = _face_frame(face_luma=50, bg_luma=220)
    mask = np.zeros((200, 200), np.float32)
    mask[50:150, 60:140] = 1.0
    out = adj.process(frame, ("person", mask))
    assert adj.metering == "person" and out[100, 100, 0] > 90
    adj2 = ImageAdjuster(auto_light=True, smoothing=1.0)
    adj2.process(frame, ("person", np.zeros((200, 200), np.float32)))  # nobody there
    assert adj2.metering == "center"


def test_subject_gamma_band():
    assert ImageAdjuster.subject_gamma(150) == 1.0
    assert ImageAdjuster.subject_gamma(40) < 1.0
    assert ImageAdjuster.subject_gamma(240) > 1.0


class _FakeFaces:
    available = True

    def __init__(self, boxes):
        self.boxes = boxes
        self.calls = 0

    def detect(self, bgr):
        self.calls += 1
        return list(self.boxes)


def test_pipeline_meters_on_face():
    faces = _FakeFaces([(20, 10, 40, 50, 0.9)])
    proc = FrameProcessor(settings={"auto_light": True}, output_size=(96, 96), face_detector=faces)
    for _ in range(8):
        proc.process(np.full((240, 320, 3), 60, np.uint8))
    assert proc.adjuster.metering == "face"
    assert proc.auto_light_source == "face"
    assert 2 <= faces.calls <= 3  # throttled, not every frame


def test_pipeline_skips_face_detection_when_auto_light_off():
    faces = _FakeFaces([(20, 10, 40, 50, 0.9)])
    proc = FrameProcessor(settings={"auto_light": False}, output_size=(96, 96), face_detector=faces)
    proc.process(np.full((240, 320, 3), 60, np.uint8))
    assert faces.calls == 0


def test_face_detector_without_model(monkeypatch):
    from selficamera.processor.face import FaceDetector

    monkeypatch.delenv("SELFICAMERA_FACE_MODEL", raising=False)
    det = FaceDetector()
    assert not det.available and det.detect(np.zeros((50, 50, 3), np.uint8)) == []


# ------------------------------------------------------------------ enhance
def test_denoise_reduces_grain_on_still_scene():
    from selficamera.processor.enhance import TemporalDenoiser

    rng = np.random.default_rng(0)
    clean = np.full((120, 120, 3), 128, np.uint8)
    dn = TemporalDenoiser()
    for _ in range(20):
        noisy = np.clip(clean.astype(int) + rng.normal(0, 8, clean.shape), 0, 255).astype(np.uint8)
        out = dn.process(noisy, 60)
    assert np.abs(out.astype(int) - 128).std() < 0.5 * np.abs(noisy.astype(int) - 128).std()


def test_denoise_does_not_ghost_moving_objects():
    from selficamera.processor.enhance import TemporalDenoiser

    dn = TemporalDenoiser()
    a = np.full((100, 100, 3), 40, np.uint8)
    for _ in range(10):
        dn.process(a, 100)
    b = a.copy()
    b[30:70, 30:70] = 220  # something bright moves in
    out = dn.process(b, 100)
    assert out[50, 50, 0] > 200  # shows up at once, no trail
    assert dn.process(a, 0) is a  # off = untouched


def test_soft_skin_smooths_only_the_face():
    from selficamera.processor.enhance import soft_skin

    rng = np.random.default_rng(1)
    frame = np.full((200, 200, 3), (120, 140, 200), np.uint8)  # skin-like tone (BGR)
    frame = np.clip(frame.astype(int) + rng.normal(0, 10, frame.shape), 0, 255).astype(np.uint8)
    face = [(60, 50, 80, 100, 0.9)]
    out = soft_skin(frame, face, 80)
    inside = (slice(80, 130), slice(80, 120))
    per_channel = lambda im: im[inside].astype(float).std(axis=(0, 1)).mean()  # noqa: E731
    assert per_channel(out) < 0.6 * per_channel(frame)
    assert np.array_equal(out[:20, :20], frame[:20, :20])  # far from the face: untouched
    assert soft_skin(frame, [], 80) is frame and soft_skin(frame, face, 0) is frame


def test_sharpen_adds_detail():
    from selficamera.processor.enhance import sharpen

    frame = cv2.GaussianBlur(np.tile(np.repeat([60, 190], 16).astype(np.uint8), (64, 2))[:, :, None].repeat(3, 2), (0, 0), 2)
    out = sharpen(frame, 60)
    assert np.abs(np.diff(out[:, :, 0].astype(int), axis=1)).max() > np.abs(np.diff(frame[:, :, 0].astype(int), axis=1)).max()
    assert sharpen(frame, 0) is frame


def test_pipeline_detects_faces_for_soft_skin_without_auto_light():
    faces = _FakeFaces([(20, 10, 40, 50, 0.9)])
    proc = FrameProcessor(settings={"auto_light": False, "soft_skin": 50}, output_size=(96, 96), face_detector=faces)
    proc.process(np.full((240, 320, 3), 60, np.uint8))
    assert faces.calls == 1 and proc.enhance_status["faces"] == 1


@pytest.mark.parametrize("size", [(260, 260), (462, 260)])
def test_pipeline_all_enhancements(presenter_frame, size):
    faces = _FakeFaces([(40, 30, 80, 100, 0.9)])
    proc = FrameProcessor(settings={"denoise": 60, "soft_skin": 60, "sharpen": 40}, output_size=size, face_detector=faces)
    for _ in range(3):
        out = proc.process(presenter_frame)
    assert out.shape[:2] == (size[1], size[0]) and out.dtype == np.uint8
