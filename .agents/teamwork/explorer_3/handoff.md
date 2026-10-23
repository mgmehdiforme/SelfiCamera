# Handoff Report: Anti-Self-Certification Test Specification & Synthetic Fixtures

**Agent**: Explorer 3 (`explorer_3`)  
**Mission**: Investigate `tests/test_segmentation.py` and synthetic test fixtures, and design non-self-certifying test specifications.  
**Date**: 2026-10-22  
**Handoff Type**: Hard (Investigation & Specification Complete)  

---

## 1. Observation

1. **Fixture Flaw in `tests/conftest.py`**:
   In `tests/conftest.py` (lines 25-30), `mock_frame` generates a background with a linear vertical gradient:
   ```python
   for y in range(h):
       val = int(40 + (y / h) * 40)
       frame[y, :, 0] = val
       frame[y, :, 1] = 50
       frame[y, :, 2] = 60
   ```
   Empirical execution in Python revealed:
   ```
   Background Laplacian vars: 0.0 0.0 0.0
   ```
   Because the background is a 1st-degree linear function, its discrete 2nd derivative is identically zero ($\nabla^2 I = 0$), yielding variance of $0.0$ across all blur tiers.

2. **Self-Certifying Assertion in `tests/test_segmentation.py`**:
   In `tests/test_segmentation.py` (lines 37-48):
   ```python
   # Check top-left corner (background region): variance/laplacian should decrease as blur increases
   bg_slice_t1 = cv2.cvtColor(t1[:100, :100], cv2.COLOR_BGR2GRAY)
   bg_slice_t2 = cv2.cvtColor(t2[:100, :100], cv2.COLOR_BGR2GRAY)
   bg_slice_t3 = cv2.cvtColor(t3[:100, :100], cv2.COLOR_BGR2GRAY)

   var1 = cv2.Laplacian(bg_slice_t1, cv2.CV_64F).var()
   var2 = cv2.Laplacian(bg_slice_t2, cv2.CV_64F).var()
   var3 = cv2.Laplacian(bg_slice_t3, cv2.CV_64F).var()

   # Higher blur leads to lower Laplacian variance
   assert var1 >= var2 >= var3
   ```
   `assert var1 >= var2 >= var3` evaluated $0.0 \ge 0.0 \ge 0.0$, passing unconditionally despite zero segmentation occurring.

3. **Presenter Blur Leakage Unmeasured**:
   Empirical measurement of `mock_frame` presenter center $[cy-50:cy+50, cx-50:cx+50]$:
   ```
   Center (Presenter) Laplacian vars: 1115.23 (t0) -> 438.34 (t1) -> 438.34 (t2) -> 438.34 (t3)
   Presenter Sharpness Retention: 39.3% (degradation of 60.7%)
   ```
   The existing test suite had zero assertions on the foreground presenter region.

4. **Zero Mask Verification**:
   Running `engine._infer_mask(frame)`:
   ```
   Mask shape, min, max, var: (256, 256) 0.6224593 0.6224593 3.5527137e-15
   ```
   No test in `tests/test_segmentation.py` asserted mask variance ($>0.05$), dynamic range, or spatial separation.

5. **Current Test Run**:
   Running `QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/test_segmentation.py -v`:
   ```
   tests/test_segmentation.py::test_tier_0_bypass PASSED                    [ 25%]
   tests/test_segmentation.py::test_blur_tier_cycling PASSED                [ 50%]
   tests/test_segmentation.py::test_bokeh_blur_tiers_produce_distinct_smoothing PASSED [ 75%]
   tests/test_segmentation.py::test_zero_network_imports_privacy_audit PASSED [100%]
   4 passed in 0.29s
   ```
   All 4 tests pass today on the broken codebase because of self-certification.

---

## 2. Logic Chain

1. **Step 1 (Observation 1 & 2)**: The background fixture has zero high-frequency energy, producing zero Laplacian variance in all tiers. Therefore, `assert var1 >= var2 >= var3` evaluates `0.0 >= 0.0 >= 0.0 == True`, creating a false-positive test pass.
2. **Step 2 (Observation 3)**: Because `mock_frame` presenter center sharpness drops from $1115.23$ to $438.34$ ($60.7\%$ blur damage), and the existing test does not sample or assert on the presenter region, the test suite is blind to presenter blur degradation.
3. **Step 3 (Observation 4)**: Because the ONNX model emits an invariant scalar constant ($0.6224593$) with variance $3.55 \times 10^{-15}$, but `_infer_mask()` is never tested directly, the test suite conceals the facade model.
4. **Step 4 (Deduction)**: To make tests genuinely non-self-certifying, the test suite must:
   - Provide a synthetic fixture (`synthetic_presenter_frame`) with verifiable high-frequency background texture ($V_{\text{bg}} > 200$) and high-frequency presenter face detail ($V_{\text{fg}} > 1000$).
   - Explicitly assert `np.var(mask) > 0.05`, $\max(M) - \min(M) \ge 0.50$, and spatial contrast $\bar{M}_{\text{fg}} - \bar{M}_{\text{bg}} > 0.35$.
   - Explicitly assert presenter sharpness retention $V_{\text{fg}}^{(t)} / V_{\text{fg}}^{(0)} \ge 0.90$ across all tiers $t \in \{1, 2, 3\}$.
   - Explicitly assert strict monotonic background attenuation $V_{\text{bg}}^{(0)} > V_{\text{bg}}^{(1)} > V_{\text{bg}}^{(2)} > V_{\text{bg}}^{(3)}$ with quantitative caps ($0.50$, $0.20$, $0.05$).
   - Pair static AST checking with a dynamic runtime monkeypatch socket trap intercepting internet connections during inference.
5. **Step 5 (Empirical Verification)**: When the proposed non-self-certifying tests were run against the current codebase in Python, they immediately and unambiguously caught the failure:
   - Mask variance check failed: `Mask variance 3.55e-15 <= 0.05`
   - Presenter retention check failed: `Presenter blurred in tier 2 (retention 0.393 < 0.90)`

---

## 3. Caveats

- The non-self-certifying tests assume a centered presenter layout for the synthetic benchmark fixture (matching typical webcam presenter alignment and SelfiCamera's circular 1:1 viewport).
- The 90% sharpness retention threshold allows for minor boundary feathering at the silhouette perimeter while guaranteeing the presenter's face remains crisp.
- No other caveats.

---

## 4. Conclusion

The existing test `test_bokeh_blur_tiers_produce_distinct_smoothing` was self-certifying due to a flat background gradient fixture and omission of foreground sharpness validation.

We have designed a complete, non-self-certifying test specification comprising:
1. `tests/conftest.py`: New `synthetic_presenter_frame` fixture with high-frequency 8px XOR checkerboard background ($V_{\text{bg}} \approx 500$) and centered facial details ($V_{\text{fg}} \approx 4348$).
2. `tests/test_segmentation.py`: 5 hardened, empirical verification tests:
   - `test_segmentation_mask_variance_and_spatial_contrast` (verifies $\text{Var}(M) > 0.05$, dynamic range $\ge 0.50$, spatial contrast $> 0.35$)
   - `test_foreground_sharpness_strictly_preserved` (verifies $V_{\text{fg}}^{(t)} \ge 0.90 V_{\text{fg}}^{(0)}$)
   - `test_background_bokeh_progression_strict_monotonic_attenuation` (verifies strict monotonic decrease $V_{\text{bg}}^{(0)} > V_{\text{bg}}^{(1)} > V_{\text{bg}}^{(2)} > V_{\text{bg}}^{(3)}$)
   - `test_dual_layer_zero_network_privacy_and_local_isolation` (verifies AST + dynamic runtime socket block)
   - `test_tier_0_bypass_and_tier_cycling` (verifies state machine & bypass identity)

Full technical rationale, mathematical formulas, and exact code implementations are documented in `.agents/teamwork/explorer_3/analysis.md`.

---

## 5. Verification Method

To independently verify the test design and reproduce the failure:

1. **Verify Failure of Non-Self-Certifying Criteria on Current Code**:
   Run:
   ```bash
   .venv/bin/python -c "
   import cv2, numpy as np
   from selficamera.processor.segmentation import SegmentationBlurEngine

   # 1. Check Mask Variance
   engine = SegmentationBlurEngine(tier=2)
   mask = engine._infer_mask(np.zeros((720, 1280, 3), dtype=np.uint8))
   print('Current mask variance:', np.var(mask))
   assert np.var(mask) > 0.05, f'FAIL: Mask variance {np.var(mask)} <= 0.05'
   "
   ```
   *Expected Result*: Fails with `AssertionError: FAIL: Mask variance 3.552713678800501e-15 <= 0.05`.

2. **Verify Full Automated Pytest Execution (Post-Remediation)**:
   ```bash
   QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/test_segmentation.py -v
   ```
   *Expected Result*: All 5 tests pass when a valid model and mask engine are in place.

3. **Invalidation Condition**:
   This specification is invalidated if a test design fails to detect a flat mask ($M = \text{const}$) or allows presenter face sharpness to drop below 90% under background blur.
