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

`run.ps1` starts ComfyUI in a hidden process when necessary, waits for its health endpoint, and
then opens the desktop UI with `config.yaml`. The LLM adapter starts a short-lived local
`llama-server`, validates the returned director plan, and kills its process tree before Wan loads.

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

The onedir application is created under `dist/24GB and a Dream/`. Keep `config.yaml`, `workflows/`,
`models/`, and `runtime/` beside the application when deploying it.
