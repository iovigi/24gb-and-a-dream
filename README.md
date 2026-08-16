# 24GB and a Dream

Local-first Windows desktop pipeline for AI-directed video generation on one 24 GB GPU. It uses
Qwen for scene planning, Piper for Bulgarian/English narration, Wan 2.2 through ComfyUI for T2V or
I2V, and FFmpeg/NVENC for final assembly. No generation data is sent to a cloud service.

## Run the real pipeline

The local machine is configured with:

- Qwen3-8B Q5_K_M in `models/llm/`;
- Bulgarian Dimitar plus English Lessac/Ryan Piper voices in `models/tts/`;
- ComfyUI and Wan 2.2 TI2V-5B under `runtime/ComfyUI/`;
- llama.cpp and FFmpeg under `runtime/`.

Start the application from PowerShell:

```powershell
.\run.ps1
```

The application starts ComfyUI itself when the first scene needs it, so `run.ps1` and the packaged
executable behave identically. An instance that is already running is reused and never stopped — it
belongs to whoever started it. One the app started is shut down with the app, freeing its VRAM.
Both halves are configurable:

```yaml
comfyui:
  autostart: true            # false: require ComfyUI to be running already
  stop_on_exit: true         # false: leave a started instance running between sessions
  startup_timeout_seconds: 180
```

The LLM adapter starts a short-lived local `llama-server`, validates the returned director plan,
and kills its process tree before Wan loads.

Wan defaults to 1280x704, 24 fps, 20 steps, CFG 5, and 5-second scene chunks. Real generation at
that quality can take substantial time. The Bulgarian Piper repository currently provides one
voice (Dimitar), so both Bulgarian voice choices map to it; English female/male map to Lessac/Ryan.

## Mock mode and tests

The deterministic mock pipeline remains available without loading any model:

```powershell
python app.py --config config.mock.yaml
python -m pytest -q
```

## Outputs

Each run creates a recoverable folder under `projects/` containing the request and director JSON,
input image, narration WAV files, scene MP4 files, subtitles, logs, and `output/final.mp4`.
Completed non-empty scene files are retained so interrupted work can be resumed safely.

## Logs and crash diagnostics

Everything the application does is written to `logs/` next to the app, so a silent death always
leaves evidence:

| File | Contents |
| --- | --- |
| `logs/app.log` | Central rotating session log (8 MB x 5): startup environment, package versions, GPU, every pipeline step, ffmpeg commands, Qt warnings. |
| `logs/crash.log` | Native faults (access violation, segfault, abort) with a C-level Python traceback, plus every unhandled exception and all thread stacks. |
| `logs/console.log` | Raw stdout/stderr, including output printed by native libraries that never reaches the logging module. |
| `logs/llama-server.log` | Full llama.cpp server output — the only place a failed model load explains itself. |
| `logs/comfyui.log` | Output of a ComfyUI instance the app started. |
| `logs/launcher.log` | Output and exit code of `run.ps1`. |
| `logs/session.json` | Marker with the last known activity; if it is not `clean_exit` the previous run died. |

A crash is localized by activity: the log records what the app was doing (`video scene 3 chunk 2
attempt 1`, `loading llama model`, `ffmpeg render -> ...`) so even a process killed by the driver
tells you where it died. On the next start the app detects the unclean shutdown and shows a warning
dialog pointing at the crash report; **Open logs** in the UI opens the folder directly.

### GUI thread rule

Generation runs in a `QThread`, so **worker signals must be connected to bound methods of a
GUI-thread `QObject`, never to a lambda**. PySide6 delivers a lambda receiver in the *worker*
thread; touching a widget from there corrupts Qt and kills the process with an access violation
(exit code `-1073741819`) seconds later, in unrelated code. `tests/test_ui_threading.py` pins this
down, `_on_gui_thread()` blocks and logs any offender, and the Qt message handler escalates
"Cannot create children for a parent that is in a different thread" to a full crash report.

Run with `--debug` for verbose logging:

```powershell
python app.py --config config.yaml --debug
```

## Configuration

All project paths in `config.yaml` are relative to the repository. Heavy models and runtimes are
external to the packaged executable and ignored by Git. The main backend switches are:

- `llm.backend: llama_cpp_cli` — local Qwen via a short-lived llama.cpp server;
- `tts.*.backend: local` — local Piper voices;
- `video.backend: wan22` — official ComfyUI Wan 2.2 API workflows;
- `app.mock_mode: false` — real FFmpeg/NVENC rendering.

## Build

```powershell
python -m pip install -r requirements-dev.txt
.\build.ps1
```

The onedir application is created under `dist/24GB and a Dream/`.

`build.ps1` generates the packaged `config.yaml` with `tools/make_dist_config.py` rather than
copying it. Relative paths resolve against the folder holding the config, and `ffmpeg.binary` plus
the TTS command are resolved by `subprocess` against the *current directory*, so a plain copy makes
the packaged app hunt for `runtime/` and `models/` inside `dist/`. The generated config points those
entries at this machine's copies as absolute paths; `app.projects_dir` and `comfyui.workflows_dir`
stay relative so outputs and workflows live with the deployment.

To deploy on another machine, copy `runtime/` and `models/` beside the executable and change those
entries back to relative paths. The app validates every configured backend at startup and again
before generation, listing everything missing at once instead of failing on the first one.

`build.ps1` builds from `24GB and a Dream.spec` — never pass options like `--windowed` on the
command line instead, because PyInstaller then regenerates the spec and drops the DLL collection
described below.

Two things the build guards against:

- **Conda DLLs.** Anaconda/Miniconda keeps the native dependencies of `pyexpat`, `_ctypes`,
  `_lzma`, `_bz2` and `_decimal` in `<prefix>\Library\bin`, which PyInstaller does not search. It
  only warns, then produces an executable that dies during bootstrap with
  `ImportError: DLL load failed while importing pyexpat` — before any logging exists, so the only
  symptom is a bootloader dialog. The spec bundles them, and the build **fails** on any remaining
  `Library not found` warning.
- **A build that cannot start.** After packaging, `build.ps1` runs the executable with
  `--selftest`, which loads every module, the Qt plugins and `config.yaml`, then exits. A non-zero
  exit or a 120 s hang (the startup error dialog) fails the build and prints the packaged log.
