# Briefing: SelfiCamera Remediation Worker

## Objective
Remediate the integrity violation identified by `auditor_1`:
1. Replace the facade ONNX segmentation model with a genuine, functional Multi-Cue Inverted Residual Network with residual `Add` skip connections, perceptual color/edge stem filters, and spatial-anatomical prior fusion.
2. Upgrade `SegmentationBlurEngine` in `selficamera/processor/segmentation.py` with preallocated NCHW buffers, finite validation, degenerate mask detection, presenter polarity checking, S-curve smoothstep windowing, and anatomical center-prior fallback.
3. Harden the test suite in `tests/test_segmentation.py` and `tests/conftest.py` with non-self-certifying tests:
   - Mask variance > 0.05 & contrast separation > 0.35.
   - Foreground presenter sharpness strictly preserved (>= 90% retention).
   - Background bokeh progression strictly monotonic with quantitative attenuation targets.
   - Dual-layer static AST and runtime socket interception for zero-network privacy verification.
4. Verify complete test suite (`QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/ -v`) and pipeline benchmark (`.venv/bin/python benchmarks/benchmark_pipeline.py`).
5. Deliver handoff report and notify orchestrator.

## References
- Auditor Report: `.agents/teamwork/auditor_1/audit_report.md`
- Explorer 1 Blueprint: `.agents/teamwork/explorer_1/analysis.md`
- Explorer 2 Blueprint: `.agents/teamwork/explorer_2/analysis.md`
- Explorer 3 Blueprint: `.agents/teamwork/explorer_3/analysis.md`
