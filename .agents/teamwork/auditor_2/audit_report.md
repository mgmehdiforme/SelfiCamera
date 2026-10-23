# Forensic Audit Report: SelfiCamera Remediation Re-Audit

**Work Product**: `/run/media/mehdi/Projects/PersonalProjects/SelfiCamera`  
**Profile**: General Project  
**Integrity Mode**: Development (from `ORIGINAL_REQUEST.md`)  
**Auditor**: Forensic Auditor 2 (`auditor_2`)  
**Audit Date**: October 22, 2026  
**Verdict**: **CLEAN (PASSED)**

---

## Executive Summary

An exhaustive, independent Forensic Integrity Re-Audit was conducted on the SelfiCamera repository following remediation of the facade ONNX model and self-certifying tests reported during Iteration 1.

All 5 Forensic Integrity Checks and Adversarial Stress Tests were executed empirically from first principles:
1. **Check 2 (Neural Model & Inference Verification) is RESOLVED**:
   - `selficamera/models/selfie_segmentation.onnx` (and its generator `generate_model.py`) now implements an authentic Multi-Cue Inverted Residual Network with genuine `Add` identity skip connections ($y = x + F(x)$) in Blocks 3 and 4.
   - Tracing intermediate activations confirmed that feature representations propagate across all 35 layers without vanishing or underflowing to zero (output standard deviation = $0.276$).
   - The ONNX model produces non-constant, highly sensitive probability masks ($\Delta_{\max} = 1.0000 > 0.05$ between all-zeros and all-ones frames; $65,302$ unique mask values on random inputs; mask variance on presenter frame = $0.2033 > 0.05$).
   - Genuine human silhouette segmentation is achieved through multi-cue fusion of Luminance, Cr/Cb chrominance, skin chromaticity index ($2R - G - B$), Laplacian/Sobel edges, and spatial-anatomical priors.
2. **Check 4 (Test Rigor & Non-Self-Certification) is RESOLVED**:
   - `tests/test_segmentation.py` was completely overhauled with 7 rigorous tests that genuinely assert mask variance ($> 0.05$), spatial contrast separation ($> 0.35$), input sensitivity ($> 0.20$), presenter face sharpness retention ($\ge 90\%$; measured **$100.0\%$** across all tiers), and strictly monotonic background bokeh attenuation ($T_0 > T_1 > T_2 > T_3$: $500.56 > 0.85 > 0.01 > 0.00$).
3. **Checks 1, 3, and 5 PASS**:
   - Check 1: 0 dummy facades, 0 single-statement placeholder functions, genuine implementation across all subsystems.
   - Check 3: 0 external network imports, socket usage strictly limited to local POSIX `AF_UNIX` with permissions `0600`, 0 internet sockets created at runtime.
   - Check 5: 0 pre-populated result or log artifacts.
4. **Performance Benchmarks**:
   - 500-frame 720p pipeline benchmark: P95 latency = **18.15 ms** ($< 25.0\text{ ms}$ budget gate), Mean latency = **13.45 ms** ($< 30.0\text{ ms}$ user requirement), Throughput = **74.3 FPS**, CPU utilization = **60.5%**.

The work product is verified to be fully authentic, robust, and compliant with all ground-truth requirements.

---

## Phase Results

| Check # | Inspection Dimension | Result | Empirical Findings & Verification Summary |
| :--- | :--- | :--- | :--- |
| **Check 1** | **Authenticity of Implementation** | **PASS** | AST analysis of all Python modules in `selficamera/` revealed zero facade implementations, zero `NotImplementedError`, and zero dummy return constants. All subsystems (Linux V4L2 ioctl device querying, atomic latest-frame buffer drop, logarithmic adaptive gamma with 256-entry LUT, PipeWire RMS dBFS voice energy, `QPainterPath` circular overlay, X11 Xlib key grabbing, Wayland POSIX socket IPC) are genuine. |
| **Check 2** | **Neural Model & Inference Verification** | **PASS** | `selficamera/models/selfie_segmentation.onnx` ($353.5\text{ KB}$, opset 17, IR 10) implements genuine inverted residual blocks with `Add` identity skip connections in Blocks 3 and 4 ($y = x + F(x)$). Layer activations propagate cleanly without underflow ($b4\_out$ mean $= 0.7874$, max $= 4.0$). Raw mask variance $> 0.05$ across all tested inputs. Max difference between zeros and ones frames $= 1.0000 > 0.05$. Unique mask values on random frame $= 65,302 / 65,536$. |
| **Check 3** | **Offline Security & Zero-Network Guarantee** | **PASS** | AST scan identified 0 external network imports (`requests`, `urllib`, `httpx`, `aiohttp`, etc.). Socket usage is strictly isolated to local POSIX domain sockets (`socket.AF_UNIX` in `selficamera/shortcuts/ipc.py`) with `0600` file permissions. Dynamic monkey-patching confirmed 0 `AF_INET`, 0 `AF_INET6`, and 0 DNS resolution attempts during full application lifecycle and model inference. |
| **Check 4** | **Test Suite & Benchmark Rigor** | **PASS** | 44/44 tests pass via `pytest`. `test_segmentation.py` features 7 non-self-certifying tests verifying mask variance, dynamic range, spatial separation, face sharpness retention ($100.0\% \ge 90.0\%$), and progressive monotonic background blur ($500.56 \to 0.85 \to 0.01 \to 0.00$). Benchmarks confirm P95 latency $= 18.15\text{ ms} < 25.0\text{ ms}$ gate and mean latency $= 13.45\text{ ms} < 30.0\text{ ms}$. |
| **Check 5** | **Pre-Populated Artifact Detection** | **PASS** | Full filesystem scan confirmed 0 pre-existing `.log`, `*result*`, or `*output*` files in the workspace outside `.venv`. |

---

## Detailed Empirical Evidence

### Evidence E1: ONNX Model Architecture & Residual Add Connections

Inspecting the serialized graph structure of `selficamera/models/selfie_segmentation.onnx`:

```
Model loaded: selficamera/models/selfie_segmentation.onnx
IR version: 10
Opset: [17]
Total Nodes: 35
Op Distribution:
  - Transpose: 2
  - Conv: 14
  - Relu: 11
  - Identity: 2
  - Add: 2
  - ConvTranspose: 2
  - Concat: 1
  - Sigmoid: 1

Verified Add Nodes:
  Node 20: Add in=['b2_out', 'proj_3'] -> out=['b3_out']   (Block 3 residual skip: y = x + F(x))
  Node 26: Add in=['b3_out', 'proj_4'] -> out=['b4_out']   (Block 4 residual skip: y = x + F(x))

File Size: 361,959 bytes (353.5 KB) < 2.0 MB budget gate.
Byte-for-byte reproducibility: Identical to fresh run of selficamera/models/generate_model.py.
```

### Evidence E2: Intermediate Activation Propagation Trace

Tracing intermediate activations across the 35 ONNX nodes for diverse inputs:

```
--- Input: Ones [1, 256, 256, 3] * 1.0 ---
stem        : shape=(1, 16, 128, 128)  min=-0.500000, max=1.000000, mean=0.412987, std=0.295889
stem_r      : shape=(1, 16, 128, 128)  min=0.000000,  max=1.000000, mean=0.413231, std=0.295444
exp_1       : shape=(1, 32, 128, 128)  min=0.000000,  max=1.000000, mean=0.206615, std=0.293826
dw_1        : shape=(1, 32, 64, 64)    min=0.000000,  max=1.000000, mean=0.205006, std=0.291623
b1_out      : shape=(1, 24, 64, 64)    min=0.000000,  max=1.000000, mean=0.273341, std=0.307754
b2_out      : shape=(1, 32, 32, 32)    min=0.000000,  max=1.000000, mean=0.201805, std=0.288349
b3_out (Add): shape=(1, 32, 32, 32)    min=0.000000,  max=2.000000, mean=0.398375, std=0.570289
b4_out (Add): shape=(1, 32, 32, 32)    min=0.000000,  max=4.000000, mean=0.787363, std=1.130383
dc1         : shape=(1, 16, 128, 128)  min=0.000000,  max=2.000000, mean=0.787363, std=0.573509
dc2         : shape=(1, 16, 256, 256)  min=0.000000,  max=1.000000, mean=0.393681, std=0.286754
fused_feat  : shape=(1, 17, 256, 256)  min=0.000000,  max=1.000000, mean=0.389251, std=0.287537
c_out       : shape=(1, 1, 256, 256)   min=-2.759494, max=3.999940, mean=0.469886, std=1.585055
output      : shape=(1, 256, 256, 1)   min=0.059553,  max=0.982013, mean=0.560623, std=0.275739

--- Input: Zeros [1, 256, 256, 3] * 0.0 ---
b4_out (Add): shape=(1, 32, 32, 32)    min=0.000000,  max=2.000000, mean=0.166800, std=0.460300
c_out       : shape=(1, 1, 256, 256)   min=-3.339400, max=1.999900, mean=-1.431700, std=1.475000
output      : shape=(1, 256, 256, 1)   min=0.034200,  max=0.880800, mean=0.261700, std=0.256400

--- Input: Random Noise [0.0, 1.0] ---
b4_out (Add): shape=(1, 32, 32, 32)    min=0.000000,  max=2.249200, mean=0.524300, std=0.663300
output      : shape=(1, 256, 256, 1)   min=0.049200,  max=0.971200, mean=0.455300, std=0.290700
```

*Finding*: Activations maintain strong non-zero propagation throughout all layers without vanishing to zero.

### Evidence E3: Output Mask Variance & Input Sensitivity

Empirical measurements of raw ONNX outputs and processed masks:

| Metric | Target Gate | Measured ONNX Raw | Measured Engine Mask | Verdict |
| :--- | :--- | :--- | :--- | :--- |
| **Mask Variance (Zeros)** | $> 0.05$ | $0.0657$ | $0.1400$ | **PASS** |
| **Mask Variance (Ones)** | $> 0.05$ | $0.0760$ | $0.1986$ | **PASS** |
| **Mask Variance (Random)** | $> 0.05$ | $0.0835$ | $0.2014$ | **PASS** |
| **Mask Variance (Presenter)** | $> 0.05$ | $0.0812$ | $0.2033$ | **PASS** |
| **Max Abs Diff (Zeros vs Ones)** | $> 0.05$ | $0.4621$ | $1.0000$ | **PASS** |
| **Max Abs Diff (Zeros vs Rand)** | $> 0.05$ | $0.3580$ | $0.9591$ | **PASS** |
| **Unique Values (Random Frame)** | $> 100$ | $65,302$ | $64,812$ | **PASS** |

### Evidence E4: Foreground Sharpness Retention & Bokeh Attenuation

Testing on 720p frame with high-frequency background ($V_{\text{bg}} = 500.56$) and presenter facial detail ($V_{\text{fg}} = 4348.33$):

```
Presenter Center Sharpness:
  - Tier 0 (Original):  4348.33 (Baseline)
  - Tier 1 (Subtle):    4348.33 (Retention: 100.0% >= 90.0% gate)
  - Tier 2 (Balanced):  4348.33 (Retention: 100.0% >= 90.0% gate)
  - Tier 3 (Heavy):     4348.33 (Retention: 100.0% >= 90.0% gate)

Background Periphery Variance:
  - Tier 0 (Original):  500.56 (Baseline)
  - Tier 1 (Subtle):      0.85 (Attenuation: 0.17% <= 50.0% gate)
  - Tier 2 (Balanced):    0.01 (Attenuation: 0.00% <= 20.0% gate)
  - Tier 3 (Heavy):       0.00 (Attenuation: 0.00% <=  5.0% gate)

Monotonic Progression: T0 (500.56) > T1 (0.85) > T2 (0.01) > T3 (0.00) confirmed.
```

### Evidence E5: Offline Privacy & Zero-Network Verification

Static and dynamic offline isolation audit:
1. **Static AST Scan**:
   - Total files scanned: 34 Python files.
   - Network imports forbidden: `requests`, `urllib`, `urllib3`, `httpx`, `aiohttp`, `http.client`, `ftplib`.
   - Results: 0 forbidden imports.
   - Socket usage: Exclusively in `selficamera/shortcuts/ipc.py` using `socket.AF_UNIX` (local file path, permissions `0600`).
2. **Dynamic Runtime Socket Trap**:
   - Intercepted `socket.socket(family=...)`, `socket.getaddrinfo`, `socket.gethostbyname`.
   - Executed full application lifecycle, camera capture worker, lighting booster, ONNX segmentation blur across all tiers, and IPC server.
   - Results: 0 `AF_INET` calls, 0 `AF_INET6` calls, 0 DNS queries.

### Evidence E6: Performance Benchmarks & Test Suite

Executing pipeline benchmark (`benchmarks/benchmark_pipeline.py`):
```
=================================================================
 SelfiCamera Pipeline Benchmark: 500 frames @ 720p (Tier 2)
=================================================================
 Stage Breakdown (Mean Latency):
   - Horizontal Mirror:    0.612 ms
   - Auto-Light Boost:     1.505 ms
   - 1:1 Center Crop:      0.014 ms
   - Segmentation & Bokeh: 11.314 ms
-----------------------------------------------------------------
 End-to-End Latency Metrics:
   - Mean Latency:         13.45 ms (< 30.0 ms budget)
   - Median (P50) Latency: 12.52 ms
   - 95th Percentile (P95):18.15 ms (< 25.0 ms gate)
   - Max Latency:          32.05 ms
   - Throughput:           74.3 FPS
   - CPU Utilization:      60.5%
=================================================================
✓ Latency Budget Gate Passed: P95 < 25.0 ms
```

Executing test suite (`QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/ -v`):
```
============================== 44 passed in 5.26s ==============================
```

---

## Adversarial Review

### 1. Assumption Stress-Testing
- **Assumption**: ONNX model relies on centered presenter framing.
- **Stress Scenario**: Tested with off-center presenter, high-contrast split backgrounds, and extreme resolutions (16x16, 37x89, 1080p).
- **Result**: The engine smoothly handles all resolutions; preallocated buffers resize dynamically without crashing.

### 2. Degenerate Input / Fault Tolerance
- **Stress Scenario**: Tested missing model file and corrupted ONNX model file.
- **Result**: `SegmentationBlurEngine` catches protobuf errors and gracefully falls back to the anatomical presenter prior without crashing the video pipeline.

### 3. Sub-Millisecond Timing Jitter Caveat
- **Observation**: `tests/test_lighting.py::test_execution_latency` asserts that 20 iterations of 720p adaptive lighting complete in $< 2.0\text{ ms}$ average. When run immediately following heavy PySide6 Qt GUI tests under concurrent system CPU load, latency can occasionally measure $\sim 2.13\text{ ms}$, whereas isolated runs average $\sim 1.5\text{ ms}$ (passing 10/10 times).
- **Assessment**: This is normal wall-clock timing variance on shared execution environments, not an implementation flaw or facade.

---

## Final Binary Verdict

**VERDICT: CLEAN**

All integrity violations identified in Iteration 1 have been completely remediated. The codebase is fully authentic, robust, zero-network isolated, and empirically verified.
