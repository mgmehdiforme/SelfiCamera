# SelfiCamera 📸

> **Ultra-lightweight, zero-bloat, 100% offline circular presenter camera overlay for Ubuntu Linux (Wayland and X11).**

SelfiCamera is built for software engineers, keynote presenters, educators, and live streamers who need a persistent, modern, circular webcam bubble floating above full-screen IDEs, slides, terminals, and browsers without battery drain or privacy compromises.

---

## Key Features

- **Frameless Circular Viewport**: 1:1 aspect-ratio locked video feed clipped cleanly with anti-aliasing and a soft Gaussian drop shadow.
- **Direct UI Controls & Floating Settings Panel**:
  - **Auto-Docked Settings Panel**: Starts docked alongside the bubble for effortless mouse-driven configuration without memorizing shortcuts.
  - **Pinned HUD Capsule (`📌`)**: Quick pill overlay with a 1-click Pin toggle to keep controls permanently visible on screen without fading out.
  - **Fluid Drag & 1-Click Snapping**: Effortlessly reposition anywhere on screen with automatic desktop boundary clamping and visual cursor feedback (`OpenHand` / `ClosedHand`). 1-click spatial snapping to desktop corners or center (`[↖ TL]`, `[↗ TR]`, `[⏺ Center]`, `[↙ BL]`, `[↘ BR]`).
  - **Stepped & Continuous Resizing**: Continuous diameter slider (`120px` to `600px`), on-bubble step buttons (`[−]` and `[+]`), mouse scroll-wheel scaling, and standard presets:
    - **Compact**: 160 px (IDE & terminal walkthroughs)
    - **Standard**: 260 px (default meeting & presentation mode)
    - **Focus**: 380 px (keynotes & introductions)
- **Always-on-Top Persistence**: Stays pinned above active fullscreen applications on both Wayland and X11.
- **Click-Through Ghost Mode (`Super+Alt+X`)**: Passes all mouse clicks directly through the camera bubble to the code editor underneath.
- **Offline 4-Tier AI Bokeh Blur**:
  - **Tier 0 (Off)**: 0ms overhead, bypasses model
  - **Tier 1 (Subtle)**: ~12px Gaussian blur
  - **Tier 2 (Balanced)**: ~28px photographic bokeh (downscale-blur-upscale)
  - **Tier 3 (Heavy)**: ~56px heavy bokeh
  - Fine-grained intensity slider (0% to 100%) and quick cycling directly from the HUD.
  - Powered by a local MediaPipe Selfie Segmentation ONNX float32 model (~353KB) running on CPU SIMD with zero cloud dependencies.
- **Real-Time Light Control**: Quick toggle button on HUD, adaptive Auto-Light Boost, manual Brightness/Gamma slider (`0.40x` to `2.20x`) with `↺ Reset`, and Target Luminance tuning (<1.5ms).
- **Dynamic Voice Aura Border**: Pulses and glows in real time to speech activity captured via PipeWire / PulseAudio (silence cyan $\rightarrow$ speech blue $\rightarrow$ peak magenta).
- **Ubuntu System Tray & AppIndicator**: Comprehensive menu for camera device picking, resolution switching (480p, 720p, 1080p), mirror toggle, and clean exit.

---

## Presenter Shortcuts & Desktop Integration

| Shortcut | Action | Description |
| :--- | :--- | :--- |
| `Super+Alt+C` | Toggle Overlay | Show / Hide circular bubble |
| `Super+Alt+X` | Ghost Mode | Toggle click-through mode |
| `Super+Alt+1` | Snap Top-Left | Snap bubble to Top-Left desktop corner |
| `Super+Alt+2` | Snap Top-Right | Snap bubble to Top-Right desktop corner |
| `Super+Alt+3` | Snap Bottom-Left | Snap bubble to Bottom-Left desktop corner |
| `Super+Alt+4` | Snap Bottom-Right | Snap bubble to Bottom-Right desktop corner |
| `Super+Alt+B` | Cycle Blur | Cycle blur tier (Off $\rightarrow$ Subtle $\rightarrow$ Balanced $\rightarrow$ Heavy) |

### GNOME Wayland Shortcut Setup
On GNOME Wayland sessions, global shortcuts are routed via the local Unix Domain Socket IPC client:
1. Open **Ubuntu Settings $\rightarrow$ Keyboard $\rightarrow$ Keyboard Shortcuts $\rightarrow$ Custom Shortcuts**.
2. Add new shortcuts invoking the client:
   - Name: `SelfiCamera Toggle` | Command: `/path/to/run.sh --toggle` | Shortcut: `Super+Alt+C`
   - Name: `SelfiCamera Ghost` | Command: `/path/to/run.sh --toggle-ghost` | Shortcut: `Super+Alt+X`
   - Name: `SelfiCamera Blur Cycle` | Command: `/path/to/run.sh --blur-cycle` | Shortcut: `Super+Alt+B`
   - Name: `SelfiCamera Snap BR` | Command: `/path/to/run.sh --snap 4` | Shortcut: `Super+Alt+4`

---

## Quickstart & Launch

SelfiCamera adheres strictly to Ubuntu standards and isolates all dependencies in a local `.venv`.

### Automated Bootstrap & Run
```bash
git clone https://github.com/your-repo/SelfiCamera.git
cd SelfiCamera

# Automated one-command bootstrap: provisions .venv and starts application
./run.sh
```

### CLI Options
```bash
# Launch with synthetic mock video & audio (zero camera/mic hardware required)
./run.sh --headless-mock

# Launch on a specific V4L2 device at 1080p
./run.sh --device /dev/video2 --width 1920 --height 1080

# Launch with balanced blur and ghost mode
./run.sh --blur 2 --ghost
```

---

## Automated Testing & Benchmarks

Run the complete test suite headlessly (no physical display or camera needed):
```bash
# Activate virtual environment
source .venv/bin/activate

# Run full pytest suite with headless Qt
QT_QPA_PLATFORM=offscreen pytest tests/ -v

# Run 500-frame latency & CPU benchmark
python benchmarks/benchmark_pipeline.py
```

---

## License

MIT License. Built for offline presentation perfection on Ubuntu Linux.
