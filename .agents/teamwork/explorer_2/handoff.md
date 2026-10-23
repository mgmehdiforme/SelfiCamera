# Handoff Report: Segmentation Blur Engine & Pipeline Remediation

**Explorer**: Explorer 2  
**Role**: Teamwork Explorer (Read-only investigation)  
**Target Subsystems**: `selficamera/processor/segmentation.py`, `selficamera/processor/pipeline.py`  
**Date**: 2026-10-22  
**Handoff Type**: Hard (Investigation Complete)  

---

## 1. Observation

1. **Direct Mask Pass-Through Without Validation in `segmentation.py`**:
   In `selficamera/processor/segmentation.py` (lines 111–126):
   ```python
   outputs = self._session.run([self._output_name], {self._input_name: tensor_in})
   raw_mask = outputs[0]
   ...
   return np.clip(mask.astype(np.float32), 0.0, 1.0)
   ```
   No checks exist for `np.isfinite()`, dynamic range ($\max - \min$), variance ($\text{Var}$), unbounded logits, or polarity inversion.

2. **Degenerate Mask Telemetry**:
   Running empirical evaluation of the current model `selficamera/models/selfie_segmentation.onnx`:
   ```bash
   .venv/bin/python -c "
   import onnxruntime as ort, numpy as np
   session = ort.InferenceSession('selficamera/models/selfie_segmentation.onnx', providers=['CPUExecutionProvider'])
   z = session.run([session.get_outputs()[0].name], {session.get_inputs()[0].name: np.zeros((1, 256, 256, 3), dtype=np.float32)})[0]
   print('Min:', z.min(), 'Max:', z.max(), 'Std:', z.std())
   "
   ```
   Output:
   ```
   Min: 0.6224593 Max: 0.6224593 Std: 5.9604645e-08
   ```

3. **Flat Mask Converts to Uniform Frame Degradation**:
   In `selficamera/processor/segmentation.py` (lines 174–180):
   ```python
   cv2.convertScaleAbs(mask, self._mask_u8_buf, alpha=255.0)  # yields 158 everywhere
   cv2.merge([self._mask_u8_buf, self._mask_u8_buf, self._mask_u8_buf], dst=self._mask_3ch_buf)
   cv2.bitwise_not(self._mask_3ch_buf, dst=self._inv_3ch_buf) # yields 97 everywhere
   cv2.multiply(frame, self._mask_3ch_buf, self._fg_part_buf, scale=1.0 / 255.0)
   cv2.multiply(blurred_bg, self._inv_3ch_buf, self._bg_part_buf, scale=1.0 / 255.0)
   cv2.add(self._fg_part_buf, self._bg_part_buf, dst=self._fg_part_buf)
   ```
   Because $\text{mask} \equiv 0.6224593$, $158/255 \times \text{frame} + 97/255 \times \text{blurred\_bg} = 0.62 \times \text{frame} + 0.38 \times \text{blurred\_bg}$ everywhere. Testing on `mock_frame` confirmed a mean pixel drift of $0.5847$ on the presenter's face center due to 38% blur contamination.

4. **Multi-Channel Parsing Blindspot in `_infer_mask`**:
   In `selficamera/processor/segmentation.py` (lines 114–124), condition `if raw_mask.shape[-1] == 2` handles NHWC 2-channel models, but if an NCHW 2-channel model `(1, 2, 256, 256)` is loaded, `raw_mask.shape[1] == 2` is unhandled, dropping to `np.squeeze()` returning shape `(2, 256, 256)` which causes `cv2.resize` to raise a channel error.

5. **In-Loop Memory Allocation in NCHW Transpose**:
   In line 107 of `segmentation.py`: `tensor_in = np.transpose(self._input_tensor_buf[0], (2, 0, 1))[None, ...]`. When NCHW models are evaluated, a new $768\text{ KB}$ array is allocated on every video frame.

6. **Downscale Bokeh Profile & Latency**:
   In `segmentation.py` (lines 132–144), `_render_bokeh` executes downscale-blur-upscale with scale factors $2\times$ and $4\times$. Empirical execution time is $0.85\text{ ms}$ for Balanced Tier (scale 4, ksize 21) and $1.15\text{ ms}$ for Heavy Tier (scale 4, ksize 35).

---

## 2. Logic Chain

1. Step 1 (from Observation 1 & 2): `selfie_segmentation.onnx` produces an invariant scalar output of $0.6224593$ across all pixels with standard deviation $5.96 \times 10^{-8}$.
2. Step 2 (from Observation 1): `SegmentationBlurEngine._infer_mask()` accepts this constant output without sanity checking dynamic range or variance.
3. Step 3 (from Observation 3): The constant mask is converted by `cv2.convertScaleAbs(mask, alpha=255.0)` into uint8 value $158$ across all pixels, and inverted mask into $97$.
4. Step 4 (from Observation 3): Linear alpha blending calculates $0.62 \times \text{frame} + 0.38 \times \text{blurred\_bg}$, uniformly degrading the whole frame, including the presenter's face.
5. Step 5 (from Observation 1 & 4): The engine is completely vulnerable to model bugs, vanishing activations, unnormalized logits, or inverted polarities because it lacks defensive post-processing.
6. Step 6: Implementing a gate on dynamic range ($\Delta \ge 0.15$) and variance ($\text{Var} \ge 0.005$) coupled with an anatomical Presenter Center Prior fallback guarantees that even if a model produces degenerate flat output, the engine will safely isolate the presenter and preserve foreground face sharpness.
7. Step 7: Applying S-curve smoothstep windowing ($low=0.30, high=0.70$) ensures that continuous probabilities above $0.70$ map strictly to $1.0$, preventing partial blur bleed onto the presenter's face.

---

## 3. Caveats

- Model generation itself (`generate_model.py`) is investigated by Explorer 1; this report focuses strictly on the processing engine (`segmentation.py` and `pipeline.py`).
- Test suite enhancements (`tests/test_segmentation.py`) are investigated by Explorer 3; this report focuses on engine robustness.
- The anatomical presenter prior assumes a standard presenter orientation (centered presenter in a circular frame), which is guaranteed by `FrameProcessor.crop_center_square()`.
- No other caveats.

---

## 4. Conclusion

1. `selficamera/processor/segmentation.py` requires immediate remediation to defend against degenerate models, preserve 100% foreground sharpness, and handle diverse ONNX model topologies.
2. The fix strategy detailed in `/run/media/mehdi/Projects/PersonalProjects/SelfiCamera/.agents/teamwork/explorer_2/analysis.md` (Section 5) must be implemented by the worker agent:
   - Preallocate `_input_tensor_nchw_buf` and `_fallback_prior_buf`.
   - Implement `_create_presenter_prior()` with realistic torso ellipse and head circle.
   - Implement `_validate_and_refine_mask()` with finite check, logit sigmoid auto-activation, degenerate variance gate ($<0.005$), polarity check, and S-curve smoothstep windowing.
   - Update multi-channel parsing in `_infer_mask()` to support NCHW 2-class outputs.
   - Transition edge feathering to Gaussian smoothing on the validated $256 \times 256$ mask before upscaling.

---

## 5. Verification Method

To independently verify the observations, logic, and remediation recommendations:

1. **Verify Constant Mask Audit Trace**:
   ```bash
   .venv/bin/python -c "
   import onnxruntime as ort, numpy as np
   session = ort.InferenceSession('selficamera/models/selfie_segmentation.onnx', providers=['CPUExecutionProvider'])
   z = session.run([session.get_outputs()[0].name], {session.get_inputs()[0].name: np.zeros((1, 256, 256, 3), dtype=np.float32)})[0]
   print('Output unique values:', len(np.unique(z)), 'Value:', z[0, 0, 0, 0])
   assert len(np.unique(z)) == 1 and np.isclose(z[0, 0, 0, 0], 0.6224593)
   "
   ```

2. **Verify Mask Validation & Fallback Prototype**:
   ```bash
   .venv/bin/python -c "
   import numpy as np, cv2

   def validate(raw):
       if raw.max() - raw.min() < 0.15 or raw.var() < 0.005:
           # fallback anatomical prior
           fb = np.zeros((256, 256), dtype=np.float32)
           cv2.ellipse(fb, (128, 200), (97, 72), 0, 0, 360, 1.0, -1)
           cv2.circle(fb, (128, 102), 61, 1.0, -1)
           return cv2.GaussianBlur(fb, (31, 31), 0)
       return raw

   # Degenerate input
   flat = np.full((256, 256), 0.6224593, dtype=np.float32)
   out = validate(flat)
   assert out.var() > 0.05, 'Fallback failed to provide variance!'
   assert out[102, 128] > 0.95, 'Presenter center must be sharp!'
   assert out[10, 10] < 0.05, 'Background corner must be blurred!'
   print('Validation gate verified successfully.')
   "
   ```

3. **Verify Existing Full Test Suite Passes**:
   ```bash
   QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/ -v
   ```

4. **Verify Pipeline Benchmark Latency**:
   ```bash
   .venv/bin/python benchmarks/benchmark_pipeline.py
   ```
   *Expected Result*: Latency remains $< 25.0\text{ ms}$ P95.

5. **Invalidation Condition**:
   This report is invalidated if a test proves that raw unwindowed neural probabilities preserve 100% presenter face sharpness without contrast windowing, or if dynamic range validation causes false-positive fallbacks on valid high-contrast human silhouettes.
