# SelfiCamera

**A private, offline webcam overlay for Linux screen recordings and live streams.**
Put a shaped, framed, branded camera over VS Code, Blender, slides or a browser, and record
it all with OBS, GNOME's screen recorder, SimpleScreenRecorder or Kazam.

- **Shapes:** circle, rounded square, wide 16:9, tall 9:16 (Shorts/Reels)
- **Background:** blur, solid color (including chroma green for editing), your own image, or **remove** so only you float over the screen
- **Framing:** zoom, pan and **auto-frame**, which follows you and keeps your head in the upper third
- **Light & color:** AI auto light that meters on your face (fixes backlit or washed-out faces, leaves a well-lit face alone), plus brightness, contrast, saturation and warmth
- **Spotlight:** one key grows the camera to the center for intros and outros; the same key sends it back
- **Scenes:** save looks such as "Intro" or "Tutorial corner" and switch with a click, the tray or a hotkey
- **Clean recordings:** controls only on hover (or never), no auto-opening windows, Quit is never on the camera
- **Branding:** border thickness and color, a voice wave that flows around the camera while you talk, drop shadow
- **Private:** no network access at runtime and no telemetry. The AI models run on your CPU.
- **Free and open source** (MIT).

Runs on Ubuntu and other Linux desktops: GNOME (Wayland via XWayland) and X11.

---

## Install

One command, no sudo, nothing system-wide:

```bash
curl -fsSL https://raw.githubusercontent.com/mgmehdiforme/SelfiCamera/main/get.sh | bash
```

Then open **SelfiCamera** from your apps, or run `selficamera`. The installer:

- downloads SelfiCamera to `~/.local/share/selficamera/app`,
- builds an isolated Python 3.12 environment with [uv](https://docs.astral.sh/uv/) (installed to `~/.local/bin` if you don't have it),
- downloads the two offline AI models once (~480 KB, see below),
- adds SelfiCamera to your app menu and the `selficamera` command to `~/.local/bin`.

At the end it prints the exact `sudo apt install …` line if your system is missing libraries
(you can check again any time with `selficamera --check-system`). On a fresh Ubuntu that is:

```bash
sudo apt install libxcb-cursor0 libxkbcommon-x11-0 libxcb-icccm4 libxcb-keysyms1 libxcb-xkb1 libportaudio2
```

**Update:** run the same command again. **Uninstall:** `bash ~/.local/share/selficamera/app/uninstall.sh`
(add `--purge` to also delete settings, models and the app folder).

Add options after `bash -s --`, for example `curl -fsSL …/get.sh | bash -s -- --with-shortcuts --autostart`:

| Option | What it does |
|---|---|
| `--with-shortcuts` | Registers the global shortcuts below as GNOME custom shortcuts. |
| `--autostart` | Starts SelfiCamera when you log in. |

**AI models** (downloaded once, then everything runs offline on your CPU): Google MediaPipe
Selfie Segmenter (Apache-2.0) for background effects, and OpenCV YuNet (MIT) so auto light meters on your face.

<details>
<summary>Install from a git checkout instead</summary>

```bash
git clone https://github.com/mgmehdiforme/SelfiCamera.git && cd SelfiCamera
bash install.sh --with-model --with-shortcuts
```

`install.sh` points the launcher at this checkout. You can also run it without installing: `bash run.sh`.
</details>

> **Why these libraries?** GNOME on Wayland only lets apps stay on top and position themselves
> when they run through XWayland, and Qt's X11 mode needs them. Without it SelfiCamera still
> runs, but in *limited mode*: it can't stay on top or snap to corners, and it tells you so.

## Use it

- **Move:** drag the camera. **Resize:** scroll over it or drag its edge.
- **Hover** for quick controls: Background, Mirror, Spotlight, Settings, Hide.
- **Double-click** for Spotlight. **Right-click** for everything else, including Quit.
- **Tray icon:** click to show or hide; the menu has every quick action.

### Global shortcuts

| Keys | Action |
|---|---|
| `Super+Alt+C` | Show / hide camera |
| `Super+Alt+Z` | Spotlight (big & centered) |
| `Super+Alt+B` | Next background effect |
| `Super+Alt+M` | Mirror |
| `Super+Alt+X` | Click-through on / off |
| `Super+Alt+O` | Settings |
| `Super+Alt+1…4` / `5` | Snap to a corner / center |

On X11 these work immediately. On GNOME Wayland, install them once from Settings → Shortcuts
or with `selficamera --install-shortcuts`.

### Command line and automation

Every action works from a terminal, so you can drive SelfiCamera from a Stream Deck, OBS
scripts or your own hotkeys. Commands reach the running instance in a fraction of a second.

```bash
selficamera --scene "Intro"                   # apply a saved scene
selficamera --spotlight                       # toggle spotlight
selficamera --set background_mode=blur --set blur_strength=70
selficamera --set shape=portrait --set size=320
selficamera --snap 4                          # 1 TL, 2 TR, 3 BL, 4 BR, 5 center
selficamera --status                          # current state as JSON
selficamera --exit
```

Startup options: `--device /dev/video2`, `--width 1920 --height 1080`, `--fps 60`, `--shape`,
`--background`, `--size`, `--no-mirror`, `--ghost`, `--demo` (synthetic camera, no hardware),
`--config PATH`, `--debug`. See `selficamera --help`.

## Recording tips

- **OBS:** add a *Screen Capture (PipeWire)* source. The camera shows up because it's part of the screen.
- **Clean look:** Settings → General → turn off *Show controls on hover*. You can still right-click.
- **Cut-out presenter:** Background → *Remove*, Border → *Off*, Drop shadow off.
- **Chroma key in your editor:** Background → *Color* → green (`#00B140`).
- **Intro to tutorial:** save a big centered scene "Intro" and a small corner scene "Tutorial",
  then switch with `selficamera --scene Tutorial` or press `Super+Alt+Z` for Spotlight.

## Files

| What | Where |
|---|---|
| Settings | `~/.config/selficamera/config.json` (0.1 configs migrate automatically) |
| Log | `~/.local/state/selficamera/selficamera.log` |
| AI models | `~/.local/share/selficamera/models/` (`selfie_segmenter.tflite`, `face_detection_yunet_2023mar.onnx`) |

Custom ONNX models with a `[1,256,256,3] → [1,256,256,1]` signature also work: drop
`selfie_segmenter.onnx` in the models folder or point `SELFICAMERA_MODEL` at the file.

## Develop

```bash
bash run.sh --demo                                     # run from source with a synthetic camera
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest                             # 100+ tests, headless, no camera needed
.venv/bin/python benchmarks/benchmark_pipeline.py      # per-frame latency (budget: p95 ≤ 20 ms)
.venv/bin/python benchmarks/network_privacy_audit.py   # proves no network access at runtime
```

Architecture: `capture/camera.py` captures **and processes** frames on a worker thread and hands
the GUI only the newest frame. `processor/` does framing, light & color, segmentation and
background compositing at the bubble's on-screen size. `app.py` is the single place where
settings are validated, applied and saved (debounced). `ui/` holds the bubble, hover controls,
settings window and tray. `desktop.py` has the GNOME shortcuts, autostart and model install.
Product spec: [docs/PRODUCT.md](docs/PRODUCT.md).

## License

MIT. The optional AI models, Google's MediaPipe Selfie Segmenter (Apache-2.0) and OpenCV's YuNet face detector (MIT), are downloaded on request.
