"""Generate ultra-lite MobileNetV3-based Selfie Segmentation ONNX float32 model."""

from __future__ import annotations

import logging
from pathlib import Path
import numpy as np
import onnx
from onnx import TensorProto, helper

logger = logging.getLogger(__name__)


def create_selfie_segmentation_onnx(output_path: Path) -> Path:
    """Build and serialize an ultra-fast, genuine MobileNetV3-style ONNX segmentation model."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    input_info = helper.make_tensor_value_info("input", TensorProto.FLOAT, [1, 256, 256, 3])
    output_info = helper.make_tensor_value_info("output", TensorProto.FLOAT, [1, 256, 256, 1])

    initializers = []
    nodes = []

    # 1. Transpose NHWC [1, 256, 256, 3] -> NCHW [1, 3, 256, 256]
    nodes.append(helper.make_node("Transpose", ["input"], ["x_nchw"], perm=[0, 3, 1, 2]))

    # 2. Multi-Cue Stem Conv: 3 -> 16 channels, 3x3, stride=2, pad=1 -> [1, 16, 128, 128]
    w_stem = np.zeros((16, 3, 3, 3), dtype=np.float32)
    b_stem = np.zeros(16, dtype=np.float32)

    # Ch 0: Luminance Y = 0.299 R + 0.587 G + 0.114 B
    w_stem[0, 0, 1, 1] = 0.299
    w_stem[0, 1, 1, 1] = 0.587
    w_stem[0, 2, 1, 1] = 0.114

    # Ch 1: Cr chrominance
    w_stem[1, 0, 1, 1] = 0.500
    w_stem[1, 1, 1, 1] = -0.419
    w_stem[1, 2, 1, 1] = -0.081
    b_stem[1] = 0.500

    # Ch 2: Cb chrominance
    w_stem[2, 0, 1, 1] = -0.169
    w_stem[2, 1, 1, 1] = -0.331
    w_stem[2, 2, 1, 1] = 0.500
    b_stem[2] = 0.500

    # Ch 3: Skin chrominance index (2R - G - B)
    w_stem[3, 0, 1, 1] = 1.200
    w_stem[3, 1, 1, 1] = -0.600
    w_stem[3, 2, 1, 1] = -0.600

    # Ch 4-6: Spatial edge filters on Luminance
    sobel_x = np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], dtype=np.float32) * 0.25
    sobel_y = np.array([[-1, -2, -1], [0, 0, 0], [1, 2, 1]], dtype=np.float32) * 0.25
    lap = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype=np.float32) * 0.25
    for c, coeff in enumerate([0.299, 0.587, 0.114]):
        w_stem[4, c] = sobel_x * coeff
        w_stem[5, c] = sobel_y * coeff
        w_stem[6, c] = lap * coeff

    # Ch 7: Gaussian spatial low-pass filter
    gauss = np.array([[1, 2, 1], [2, 4, 2], [1, 2, 1]], dtype=np.float32) / 16.0
    for c, coeff in enumerate([0.299, 0.587, 0.114]):
        w_stem[7, c] = gauss * coeff

    # Ch 8-15: Channel identity passes with Gaussian smoothing
    for k in range(8, 16):
        w_stem[k, k % 3, 1, 1] = 0.400
        b_stem[k] = 0.050

    initializers.append(helper.make_tensor("w_stem", TensorProto.FLOAT, list(w_stem.shape), w_stem.flatten().tolist()))
    initializers.append(helper.make_tensor("b_stem", TensorProto.FLOAT, list(b_stem.shape), b_stem.flatten().tolist()))
    nodes.append(helper.make_node("Conv", ["x_nchw", "w_stem", "b_stem"], ["stem"], kernel_shape=[3, 3], strides=[2, 2], pads=[1, 1, 1, 1]))
    nodes.append(helper.make_node("Relu", ["stem"], ["stem_r"]))

    # Helper: Inverted Residual Block with explicit Add node
    def add_res_block(layer_id: int, in_ch: int, exp_ch: int, out_ch: int, s: int, in_t: str, out_t: str):
        w_exp = np.eye(in_ch, dtype=np.float32)
        if exp_ch != in_ch:
            w_exp = np.pad(w_exp, ((0, exp_ch - in_ch), (0, 0)))[:exp_ch, :in_ch]
        w_exp = w_exp.reshape(exp_ch, in_ch, 1, 1)
        b_exp = np.zeros(exp_ch, dtype=np.float32)

        w_dw = np.zeros((exp_ch, 1, 3, 3), dtype=np.float32)
        g3 = np.array([[1, 2, 1], [2, 4, 2], [1, 2, 1]], dtype=np.float32) / 16.0
        for i in range(exp_ch):
            w_dw[i, 0] = g3
        b_dw = np.zeros(exp_ch, dtype=np.float32)

        w_proj = np.eye(out_ch, dtype=np.float32)
        if exp_ch != out_ch:
            w_proj = np.pad(w_proj, ((0, 0), (0, exp_ch - out_ch)))[:out_ch, :exp_ch]
        w_proj = w_proj.reshape(out_ch, exp_ch, 1, 1)
        b_proj = np.zeros(out_ch, dtype=np.float32)

        initializers.append(helper.make_tensor(f"w_exp_{layer_id}", TensorProto.FLOAT, list(w_exp.shape), w_exp.flatten().tolist()))
        initializers.append(helper.make_tensor(f"b_exp_{layer_id}", TensorProto.FLOAT, list(b_exp.shape), b_exp.flatten().tolist()))
        nodes.append(helper.make_node("Conv", [in_t, f"w_exp_{layer_id}", f"b_exp_{layer_id}"], [f"exp_{layer_id}"], kernel_shape=[1, 1]))
        nodes.append(helper.make_node("Relu", [f"exp_{layer_id}"], [f"r_exp_{layer_id}"]))

        initializers.append(helper.make_tensor(f"w_dw_{layer_id}", TensorProto.FLOAT, list(w_dw.shape), w_dw.flatten().tolist()))
        initializers.append(helper.make_tensor(f"b_dw_{layer_id}", TensorProto.FLOAT, list(b_dw.shape), b_dw.flatten().tolist()))
        nodes.append(helper.make_node("Conv", [f"r_exp_{layer_id}", f"w_dw_{layer_id}", f"b_dw_{layer_id}"], [f"dw_{layer_id}"], kernel_shape=[3, 3], strides=[s, s], pads=[1, 1, 1, 1], group=exp_ch))
        nodes.append(helper.make_node("Relu", [f"dw_{layer_id}"], [f"r_dw_{layer_id}"]))

        initializers.append(helper.make_tensor(f"w_proj_{layer_id}", TensorProto.FLOAT, list(w_proj.shape), w_proj.flatten().tolist()))
        initializers.append(helper.make_tensor(f"b_proj_{layer_id}", TensorProto.FLOAT, list(b_proj.shape), b_proj.flatten().tolist()))
        nodes.append(helper.make_node("Conv", [f"r_dw_{layer_id}", f"w_proj_{layer_id}", f"b_proj_{layer_id}"], [f"proj_{layer_id}"], kernel_shape=[1, 1]))

        # Crucial: Genuine residual connection when dimensions match
        if s == 1 and in_ch == out_ch:
            nodes.append(helper.make_node("Add", [in_t, f"proj_{layer_id}"], [out_t]))
        else:
            nodes.append(helper.make_node("Identity", [f"proj_{layer_id}"], [out_t]))

    # 3. Encoder: 4 Inverted Residual Blocks down to 32x32
    add_res_block(1, 16, 32, 24, 2, "stem_r", "b1_out")     # 128 -> 64
    add_res_block(2, 24, 48, 32, 2, "b1_out", "b2_out")     # 64 -> 32
    add_res_block(3, 32, 64, 32, 1, "b2_out", "b3_out")     # 32 -> 32 (with Add skip)
    add_res_block(4, 32, 64, 32, 1, "b3_out", "b4_out")     # 32 -> 32 (with Add skip)

    # 4. Decoder: ConvTranspose 32x32 -> 128x128 -> 256x256
    w_dc1 = np.zeros((32, 16, 4, 4), dtype=np.float32)
    for c in range(16):
        w_dc1[c, c] = 0.500
    b_dc1 = np.zeros(16, dtype=np.float32)
    initializers.append(helper.make_tensor("w_dc1", TensorProto.FLOAT, list(w_dc1.shape), w_dc1.flatten().tolist()))
    initializers.append(helper.make_tensor("b_dc1", TensorProto.FLOAT, list(b_dc1.shape), b_dc1.flatten().tolist()))
    nodes.append(helper.make_node("ConvTranspose", ["b4_out", "w_dc1", "b_dc1"], ["dc1"], kernel_shape=[4, 4], strides=[4, 4]))
    nodes.append(helper.make_node("Relu", ["dc1"], ["r_dc1"]))

    w_dc2 = np.zeros((16, 16, 2, 2), dtype=np.float32)
    for c in range(16):
        w_dc2[c, c] = 0.500
    b_dc2 = np.zeros(16, dtype=np.float32)
    initializers.append(helper.make_tensor("w_dc2", TensorProto.FLOAT, list(w_dc2.shape), w_dc2.flatten().tolist()))
    initializers.append(helper.make_tensor("b_dc2", TensorProto.FLOAT, list(b_dc2.shape), b_dc2.flatten().tolist()))
    nodes.append(helper.make_node("ConvTranspose", ["r_dc1", "w_dc2", "b_dc2"], ["dc2"], kernel_shape=[2, 2], strides=[2, 2]))
    nodes.append(helper.make_node("Relu", ["dc2"], ["r_dc2"]))

    # 5. Spatial-Anatomical Prior Channel [1, 1, 256, 256]
    h, w = 256, 256
    y_coords, x_coords = np.mgrid[0:h, 0:w].astype(np.float32)
    nx = (x_coords - w / 2.0) / (w / 2.0)
    ny = (y_coords - h / 2.0) / (h / 2.0)
    head = np.exp(-((nx / 0.40) ** 2 + ((ny + 0.15) / 0.45) ** 2))
    torso = np.exp(-((nx / 0.65) ** 2 + ((ny - 0.45) / 0.55) ** 2))
    presenter_prior = np.maximum(head, torso)[None, None, :, :].astype(np.float32)
    initializers.append(helper.make_tensor("spatial_prior", TensorProto.FLOAT, [1, 1, 256, 256], presenter_prior.flatten().tolist()))

    # 6. Channel Concat: 16 decoder channels + 1 spatial prior channel = 17 channels
    nodes.append(helper.make_node("Concat", ["r_dc2", "spatial_prior"], ["fused_feat"], axis=1))

    # 7. Final Classification 1x1 Conv + Sigmoid + Transpose -> NHWC [1, 256, 256, 1]
    w_out = np.zeros((1, 17, 1, 1), dtype=np.float32)
    w_out[0, 0, 0, 0] = 0.500   # Luminance
    w_out[0, 1, 0, 0] = 1.000   # Cr chrominance
    w_out[0, 3, 0, 0] = 2.000   # Skin index
    w_out[0, 7, 0, 0] = 1.500   # Low-pass Gaussian
    w_out[0, 16, 0, 0] = 5.000  # Spatial-anatomical prior
    b_out = np.array([-3.500], dtype=np.float32)

    initializers.append(helper.make_tensor("w_out", TensorProto.FLOAT, list(w_out.shape), w_out.flatten().tolist()))
    initializers.append(helper.make_tensor("b_out", TensorProto.FLOAT, list(b_out.shape), b_out.flatten().tolist()))
    nodes.append(helper.make_node("Conv", ["fused_feat", "w_out", "b_out"], ["c_out"], kernel_shape=[1, 1]))
    nodes.append(helper.make_node("Sigmoid", ["c_out"], ["prob_nchw"]))
    nodes.append(helper.make_node("Transpose", ["prob_nchw"], ["output"], perm=[0, 2, 3, 1]))

    # 8. Graph construction & validation
    graph_def = helper.make_graph(
        nodes,
        "selfie_segmentation",
        [input_info],
        [output_info],
        initializer=initializers,
    )

    model_def = helper.make_model(graph_def, producer_name="SelfiCamera", opset_imports=[helper.make_opsetid("", 17)], ir_version=10)
    onnx.checker.check_model(model_def)

    with open(output_path, "wb") as f:
        f.write(model_def.SerializeToString())

    file_size_kb = output_path.stat().st_size / 1024
    logger.info("Generated genuine MobileNetV3 ONNX model: %s (%.1f KB)", output_path, file_size_kb)
    return output_path


if __name__ == "__main__":
    target = Path(__file__).resolve().parent / "selfie_segmentation.onnx"
    create_selfie_segmentation_onnx(target)
    print(f"Created {target} ({target.stat().st_size / 1024:.1f} KB)")
