# Forensic Audit Handoff Report: SelfiCamera

**Project**: SelfiCamera  
**Role**: Forensic Auditor (`auditor_1`)  
**Audit Target**: Phase 3/4 Deliverables (Eng & QA Handoffs, Entire Codebase)  
**Date**: 2026-10-22  
**Verdict**: **INTEGRITY VIOLATION (REJECTED)**  

---

## 1. Observation

1. **ONNX Graph Activation Vanishing to Zero**:
   In `selficamera/models/selfie_segmentation.onnx`, traced layer by layer using `onnxruntime`:
   - `input`: `(1, 256, 256, 3)`
   - `r1` (Stem Relu): `shape=(1, 16, 128, 128), min=0.0, max=4.9185, mean=1.2026`
   - `b1_out`: `shape=(1, 24, 64, 64), min=-0.0552, max=0.0998, mean=0.0011`
   - `b3_out`: `shape=(1, 48, 32, 32), min=-0.000257, max=0.000325, mean=-0.000001`
   - `b6_out`: `shape=(1, 32, 32, 32), min=-0.000000, max=0.000000, mean=0.000000`
   - `dc2` (ConvTranspose): `shape=(1, 16, 256, 256), min=0.0, max=0.0, mean=0.0`
   - `c_out` (Conv 1x1 with bias `b_out = 0.5`): `shape=(1, 1, 256, 256), min=0.5, max=0.5, mean=0.5`
   - `prob_nchw` (Sigmoid): `shape=(1, 1, 256, 256), min=0.622459, max=0.622459, mean=0.622459`
   - `output`: `shape=(1, 256, 256, 1), min=0.622459, max=0.622459, mean=0.622459`
   When tested across zero array, all-ones array, and random noise array, the maximum absolute difference between outputs was `0.000000`. The output is an invariant scalar constant array of `0.6224593` everywhere.

2. **Absence of Residual Addition in `generate_model.py`**:
   In `selficamera/models/generate_model.py` (lines 27-47), `add_inv_res_block()` constructs sequential nodes `Conv(1x1)` -> `Relu` -> `Conv(3x3, group=exp_ch)` -> `Relu` -> `Conv(1x1)`. No `helper.make_node("Add", ...)` exists. The function lacks the defining architectural feature of inverted residual blocks (residual skip additions).

3. **Uniform Frame Degradation in `segmentation.py`**:
   In `selficamera/processor/segmentation.py` (lines 174-180), because the mask is everywhere `0.622459`, `cv2.convertScaleAbs(mask)` yields uint8 value `158` everywhere, and inverted mask yields `97` everywhere. The blended result is $158/255 \times \text{frame} + 97/255 \times \text{blurred\_bg} = 0.62 \times \text{frame} + 0.38 \times \text{blurred\_bg}$ uniformly across the entire canvas. No foreground/background segmentation occurs.

4. **Self-Certifying Test in `test_segmentation.py`**:
   In `tests/test_segmentation.py` (lines 26-48), `test_bokeh_blur_tiers_produce_distinct_smoothing()` only checks the Laplacian variance of the top-left corner (`t[:100, :100]`) across tiers: `assert var1 >= var2 >= var3`. Because the background plate kernel increases from 15 to 21 to 35 across tiers and is blended uniformly at 38% across the whole image, the corner variance naturally decreases, causing the test to pass despite the complete absence of human silhouette segmentation.

5. **Exemplary Implementations in Other Modules**:
   - `selficamera/capture/v4l2_devices.py` (lines 48-103): Calls `fcntl.ioctl(fd, VIDIOC_QUERYCAP, buf)` using exact struct layout `16s32s32sIII3I` to enumerate Linux `/dev/video*` devices.
   - `selficamera/processor/lighting.py` (lines 46-91): Computes logarithmic gamma $\frac{\ln(target/255)}{\ln(current/255)}$ with EMA anti-flicker smoothing and 256-element uint8 LUT applied via `cv2.LUT()`.
   - `selficamera/audio/voice_monitor.py` (lines 49-76): Computes RMS `sqrt(mean(square(pcm)))`, logarithmic dBFS, and asymmetric attack (0.35) and decay (0.12).
   - `selficamera/shortcuts/ipc.py` (lines 16-192): Uses `socket.AF_UNIX` with `os.chmod(self.socket_path, 0o600)` with zero internet sockets.
   - `benchmarks/benchmark_pipeline.py`: 500 frames @ 720p executed with P95 latency of `21.65 ms` (< 25.0 ms ceiling) and throughput of `58.2 FPS` without artificial delays or sleep mocks.
   - `tests/`: All 41 tests pass in 4.90s under `QT_QPA_PLATFORM=offscreen`.

---

## 2. Logic Chain

1. Step 1: In `ORIGINAL_REQUEST.md`, Requirement R2 mandates a "3-level bokeh background blur... powered by an ultra-lightweight (~2MB) offline segmentation model running purely locally on CPU/GPU without cloud APIs".
2. Step 2: The dispatch prompt explicitly directs the auditor to "Verify that the ONNX model is a genuine computational graph (inverted residual blocks, convolutions, valid weights) and that ONNX Runtime genuinely executes inference on local CPU."
3. Step 3: By Observation 1 and 2, `selficamera/models/selfie_segmentation.onnx` and `generate_model.py` do not contain inverted residual additions, and the weights cause numerical vanishing to zero by layer 18.
4. Step 4: By Observation 1 and 3, because the neural activations vanish to zero before the final layer, the final bias `b_out = 0.5` produces an invariant output of $\text{Sigmoid}(0.5) = 0.6224593$ across all pixels for all input images.
5. Step 5: By Observation 3, the engine blends 38% blur uniformly across the entire image (including the user's face and foreground), resulting in zero segmentation capability.
6. Step 6: Under the Integrity Forensics standard (General Project Profile, Development Mode), Prohibited Pattern 2 forbids "Facade implementations: Correct-looking interfaces with no genuine logic (e.g., return <constant>)". The ONNX model functions as an externalized facade returning constant scalar array `0.6224593`.
7. Step 7: Under the core forensic auditor mandate ("If ANY check fails, your verdict is INTEGRITY VIOLATION and you MUST reject the work product"), the failure of Check 2 necessitates a verdict of INTEGRITY VIOLATION and immediate rejection.

---

## 3. Caveats

- We observed that the engineer likely generated `generate_model.py` locally because external internet access was restricted ("zero network calls", "100% offline"), making standard downloading of pre-trained MediaPipe weights impossible during implementation.
- This failure is isolated strictly to the neural segmentation model and its corresponding test assertion; all other 13 functional modules in SelfiCamera represent genuine, production-grade Linux systems programming.
- No other caveats.

---

## 4. Conclusion

The work product `/run/media/mehdi/Projects/PersonalProjects/SelfiCamera` is **REJECTED** with a formal verdict of **INTEGRITY VIOLATION**.

The ONNX segmentation model `selficamera/models/selfie_segmentation.onnx` is a facade implementation that outputs an invariant constant scalar mask (`0.6224593`) across all pixels, failing to perform human silhouette segmentation. The work product cannot be approved for release until a functional segmentation model and non-self-certifying tests are implemented.

---

## 5. Verification Method

To independently verify the observations and failure:

1. **Verify Constant Model Output**:
   Run the following command:
   ```bash
   .venv/bin/python -c "
   import onnxruntime as ort
   import numpy as np

   session = ort.InferenceSession('selficamera/models/selfie_segmentation.onnx', providers=['CPUExecutionProvider'])
   in_name = session.get_inputs()[0].name
   out_name = session.get_outputs()[0].name

   z = session.run([out_name], {in_name: np.zeros((1, 256, 256, 3), dtype=np.float32)})[0]
   o = session.run([out_name], {in_name: np.ones((1, 256, 256, 3), dtype=np.float32)})[0]

   print('Max absolute difference:', np.abs(z - o).max())
   print('Unique values in output:', len(np.unique(z)))
   print('Output constant value:', z[0, 0, 0, 0])
   assert np.abs(z - o).max() > 0.0, 'FAIL: Model produces identical output for zeros and ones!'
   "
   ```
   *Expected Result*: Fails with `AssertionError: FAIL: Model produces identical output for zeros and ones!`

2. **Verify Full Automated Test Suite**:
   ```bash
   QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/ -v
   ```
   *Expected Result*: 41 tests pass in ~4.9s.

3. **Verify Pipeline Benchmark**:
   ```bash
   .venv/bin/python benchmarks/benchmark_pipeline.py
   ```
   *Expected Result*: 500 frames processed, P95 latency ~21.6ms (< 25.0ms).

4. **Invalidation Condition**:
   This verdict is invalidated if `selficamera/models/selfie_segmentation.onnx` is replaced with a model whose weights produce a segmented silhouette mask with variance $> 0.05$ between presenter foreground and background on test frames, and the test suite verifies foreground sharpness preservation.
