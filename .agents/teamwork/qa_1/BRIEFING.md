# QA & Code Reviewer Briefing: SelfiCamera

## Mission Overview
As the QA & Code Reviewer for SelfiCamera, my role is to act as the quality and security gate for Phase 4 of the project delivery lifecycle. I am responsible for rigorously validating the implementation against the authoritative specifications (CTO Architecture Blueprint and PM Product Specifications), verifying zero regressions, auditing thread safety, security, and privacy (zero network calls/sockets), executing the test suite and benchmarks, hardening test coverage with edge-case tests, and providing formal sign-off and defect tracking.

## Authoritative Reference Documents
- **Original User Request**: `.agents/teamwork/ORIGINAL_REQUEST.md`
- **Project Inventory**: `.agents/teamwork/PROJECT.md`
- **CTO Architecture Blueprint**: `.agents/teamwork/cto_1/architecture.md`
- **PM Product Specifications (PRD)**: `.agents/teamwork/pm_1/specifications.md`
- **Engineer Handoff Report**: `.agents/teamwork/eng_1/handoff.md`

## Key Quality Gates & Requirements
1. **Automated Testing Suite**:
   - Headless execution via `QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/ -v`.
   - 100% test pass rate with zero skips/errors.
   - Comprehensive coverage across capture, pipeline, lighting, segmentation, audio, UI/HUD, shortcuts, and config.
2. **Performance Budget Gates**:
   - Frame latency: Strict ceiling < 30.0 ms per frame, P95 < 25.0 ms for 720p processing.
   - Throughput: >= 30 FPS (target 60 FPS).
   - CPU utilization: < 5% on modern multi-core systems / < 90% single core during continuous processing.
3. **Architecture & Specification Audit**:
   - Verification of all 19 User Stories (US-1.1 through US-4.4) and Gherkin Acceptance Criteria.
   - Thread safety: strict separation of QThreads, atomic depth-1 frame dropping queue, main-thread UI operations.
   - Wayland & X11 compatibility, IPC socket permissions (0600 in XDG_RUNTIME_DIR), and single-instance behavior.
   - Zero network imports, zero socket connections, 100% offline privacy guarantee.
   - Graceful degradation: missing webcam, missing microphone, corrupted config file, rapid ghost mode toggling.
4. **Test Hardening**:
   - Write targeted edge-case unit/integration tests to ensure bulletproof resilience.
5. **Formal Deliverables**:
   - `qa_report.md`: Detailed test results, acceptance criteria matrix, code quality & security findings, benchmark telemetry.
   - `handoff.md`: Formal QA verdict and sign-off.
