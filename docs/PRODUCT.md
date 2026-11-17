# SelfiCamera 1.0 — Product Review & Specification

_Status: implemented in 1.0.0 · Owner: Mehdi · Last updated: 2026-11-15_

## 1. Why a redesign

SelfiCamera 0.1 was specified as a "presenter bubble for engineers". A review of the PRD
(`.agents/teamwork/pm_1/specifications.md`), the three change requests and the code found
that the product works as a demo but is not ready for creators who record and stream every day.

### 1.1 Review findings (0.1.0)

| # | Finding | Impact for a YouTuber | Severity |
|---|---------|-----------------------|----------|
| F1 | The bundled `selfie_segmentation.onnx` is **not a trained model**. `generate_model.py` hand-sets conv weights and multiplies a fixed head/torso ellipse by 5.0, so "AI blur" blurs everything outside a static oval. | Blur cuts through hair, shoulders and hands, and fails whenever you move. | Blocker |
| F2 | All frame processing ran on the GUI thread at full camera resolution (720×720 crop per frame for a 260 px bubble). Capture signals were queued with no back-pressure. | Dragging and hovering stutter; latency grows under load. | High |
| F3 | Settings were written to disk with `fsync` on **every slider tick**. | Disk churn, UI hitches while adjusting. | High |
| F4 | The settings panel auto-opened on every launch, and the hover HUD (with a Quit `✕`) sat on top of the video. | Controls get recorded; one mis-click ends the recording. | High |
| F5 | Only a circle. No zoom, framing or pan; the camera crop was always dead-center. | Creators need a rectangle for talking-head and Shorts layouts and need to frame their face. | High |
| F6 | Engineer-facing controls ("Gamma 0.40x–2.20x", "Target luminance 125", "B:Bal"). No contrast, saturation or warmth. | Not understandable without reading code. | Medium |
| F7 | `run.sh` re-installed dependencies on every launch; GNOME Wayland shortcuts had to be created manually; the IPC client imported Qt. | Slow start, hard setup, sluggish hotkeys. | Medium |
| F8 | `aura_enabled` existed in config but did nothing; no ring color or thickness; no mic selection. | No brand styling. | Medium |
| F9 | No camera-reconnect logic; failures painted a red "Camera Unavailable" frame forever. | Unplugging a USB cam mid-session kills the bubble. | Medium |
| F10 | No logs on disk, no config schema/versioning, test deps shipped as runtime deps. | Hard to support and package. | Low |

## 2. Product definition

**One-liner:** A private, offline webcam overlay for Linux that makes screen recordings and streams
look like they were edited — shaped, framed, branded camera, background effects, one-key scene changes.

**Primary persona — "Sam", tutorial YouTuber.** Records VS Code / Blender / browser walkthroughs
with OBS or GNOME's screen recorder. Wants their face in a corner, no visible UI in the recording,
a clean background without a green screen, a big "intro" shot that shrinks into the corner, and
vertical framing for Shorts re-cuts.

**Secondary personas:** live streamer (Twitch/YouTube Live), course creator, remote presenter.

### 2.1 Product principles
1. **Nothing but you in the recording.** Controls appear only on hover (optional), never auto-open, and never put a destructive action on the bubble.
2. **Offline and private.** No network calls at runtime. Models ship with the app.
3. **One key per moment.** Every recording-time action (spotlight, background, scene, hide) is a global shortcut and a CLI/IPC verb.
4. **Plain words.** Brightness, Contrast, Warmth, not gamma.
5. **Smooth first.** The GUI thread never processes video; frames are processed at display size.

## 3. Feature specification

### 3.1 Camera bubble
| Feature | Spec |
|---|---|
| Shapes | Circle, Rounded square, Wide 16:9, Tall 9:16. |
| Size | Short side 120–800 px. Scroll wheel, edge-drag, S/M/L presets (180/260/380), slider. Resizes anchor on the center. |
| Move | Drag anywhere; snap to 4 corners or center (24 px margin, respects panels/docks); position persists. |
| Border | Width 0–16 px, color presets + picker. Optional voice wave (layered waves flow around the edge and ripple outward while you talk; nothing is drawn while you are quiet). Optional drop shadow. |
| Spotlight | One toggle animates the bubble to the screen center at a large size; toggling again returns it. Used for intros/outros. |
| Hover controls | Icon toolbar: Background, Mirror, Spotlight, Settings, Hide. Can be disabled ("clean mode"). |
| Right-click menu | All quick actions, including Quit (never on the bubble itself). |
| Click-through | Bubble ignores the mouse. A toast explains how to turn it off (tray / shortcut). |
| Status | Friendly in-bubble messages: "Starting camera…", "Camera not found", "Camera in use or disconnected — retrying". |

### 3.2 Framing
- Digital zoom 1.0–3.0×, horizontal and vertical pan.
- **Auto-frame**: tracks the person and keeps the head in the upper third, smoothed so it looks like a camera operator. Requires the AI model.
- Mirror (on by default for natural self-view).

### 3.3 Background
Modes: **None, Blur** (strength 0–100), **Color** (any color; includes chroma green for post-production keying), **Image** (any PNG/JPG, cover-fit), **Remove** (transparent — only you float over the desktop).
Masks are temporally smoothed to avoid flicker.

**Model:** Google MediaPipe *Selfie Segmenter* (Apache-2.0, 256×256, ≈250 KB) run with LiteRT
(`ai-edge-litert`), or any ONNX model with a `[1,256,256,3] → [1,256,256,1]` signature placed in
`selficamera/models/`. When no trained model is installed the app falls back to a basic center prior
and says so in Settings → Background ("Basic mode — install the AI model for accurate edges").

### 3.4 Light & color
Auto light meters on the **face** (OpenCV YuNet, MIT, ~230 KB, every 4th frame, ~2 ms), falling back to the person mask, then the frame center. A face outside the comfortable band (luma 98–172) is moved to the nearest target; a well-lit face is left alone, so skin tones are not normalised. Manual controls: Brightness, Contrast, Saturation, Warmth (−50…+50 each,
double-click a slider to reset). Applied as one per-channel lookup table plus an optional saturation blend.

### 3.4.1 Enhance
All three run at the bubble's on-screen size and add at most ~5 ms per frame at 380 px.

| Option | Default | How |
|---|---|---|
| Denoise (0–100) | 30 | Motion-adaptive temporal filter: still pixels are averaged over frames, moving pixels pass through, so there is no ghosting. |
| Soft skin (0–100) | Off | Edge-preserving (bilateral) smoothing restricted to skin inside the detected face (YuNet box × skin-tone mask × feathered ellipse), with fine texture added back. Needs the face model. |
| Sharpen (0–100) | Off | Small-radius unsharp mask, applied after denoise and soft skin so it doesn't amplify grain. |

Order per frame: denoise → auto light & manual color → soft skin → sharpen → background.

**Researched and deliberately not included (Nov 2026):**

| Candidate | Why not |
|---|---|
| Face restoration: GFPGAN, CodeFormer, GPEN, RestoreFormer | 280–470 MB ONNX models, seconds per frame on a CPU, frame-to-frame flicker and identity drift. CodeFormer (S-Lab) and GPEN are non-commercial. Built for restoring old photos, not live video. |
| Low-light: Zero-DCE / Zero-DCE++, SCI | CC BY-NC (non-commercial): a monetised channel is commercial use. |
| IAT exposure/color (Apache-2.0, 90K params) | Converted to ONNX and made ~10× faster for CPU, then tested on real webcam frames. Its brightness decisions depend on input size (it darkened an already-dark frame at 224 px) and crushed shadows; once bounded to be safe, the visible gain was a few levels of color at ~17 % of a CPU core. The useful part of its result (taming a washed-out face) is now done by face-metered auto light at no cost. |
| Super-resolution (FSRCNN, Real-ESRGAN) | The camera already delivers more pixels than the bubble shows in normal use; only extreme zoom on a 480p camera would benefit. |

### 3.5 Scenes
Save the current look and position (shape, size, position, background, border, framing) under a name.
Apply from Settings, tray, right-click menu, or `selficamera --scene "Intro"`.

### 3.6 Shortcuts & automation
| Shortcut | Action | CLI |
|---|---|---|
| Super+Alt+C | Show / hide camera | `--toggle` |
| Super+Alt+Z | Spotlight | `--spotlight` |
| Super+Alt+B | Next background mode | `--background-cycle` |
| Super+Alt+M | Mirror | `--mirror-toggle` |
| Super+Alt+X | Click-through | `--toggle-ghost` |
| Super+Alt+O | Settings | `--settings` |
| Super+Alt+1…5 | Snap TL / TR / BL / BR / center | `--snap N` |
| — | Apply scene | `--scene NAME` |
| — | Set any setting | `--set key=value` |

On X11 the keys are grabbed directly. On GNOME Wayland, Settings → Shortcuts → **Install GNOME
shortcuts** (or `selficamera --install-shortcuts`) registers them as GNOME custom keybindings.
The IPC client does not import Qt, so a hotkey round trip stays fast.

### 3.7 Desktop integration
Tray menu, `.desktop` launcher, optional **Start at login**, single instance (second launch shows the
bubble), logs at `~/.local/state/selficamera/selficamera.log`, config at
`~/.config/selficamera/config.json` (schema v2, migrates 0.1 configs automatically, saves debounced).

## 4. Non-functional requirements
| Area | Target |
|---|---|
| Latency | Processing p95 ≤ 20 ms per frame with the AI model on a 4-core laptop CPU (frame time at 30 fps is 33 ms); the model runs on every second frame to halve CPU use. |
| GUI | Video processing never runs on the GUI thread; at most one frame in flight to the UI. |
| Privacy | No network access at runtime (verified by `benchmarks/network_privacy_audit.py`). |
| Resilience | Camera unplug/replug recovers without restart (retry every 2 s). |
| Tests | Full suite passes headless (`QT_QPA_PLATFORM=offscreen`), no camera or mic required. |

## 5. Out of scope for 1.0
Virtual camera output (v4l2loopback) for Zoom/Meet, built-in recording, generative face restoration, multi-camera
layouts, macOS/Windows builds. Virtual camera output is the recommended next feature.
