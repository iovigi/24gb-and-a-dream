# 24GB and a Dream

> **AI video generation for people with no H100, no render farm, and no financial common sense.**

One RTX 3090 Ti.
One Windows machine.
Several local AI models.
A suspicious amount of FFmpeg.
And the unwavering belief that 24 GB of VRAM is basically enterprise infrastructure if you manage memory aggressively enough.

This document is the implementation plan.

Codex: please build this thing before CUDA realizes what we are trying to do.

---

# 1. What Are We Building?

A Windows desktop application that takes:

- a prompt
- optionally a reference image
- optionally custom narration
- a Bulgarian or English voice choice

…and produces a finished AI-generated video.

The basic philosophy:

```text
USER
  |
  | "Make me something cinematic."
  v
LLM pretending to be Spielberg
  |
  v
TTS pretending to be Morgan Freeman
  |
  v
Video model melting the GPU
  |
  v
FFmpeg holding society together
  |
  v
FINAL VIDEO
```

Target machine:

```text
Windows 11
RTX 3090 Ti
24 GB VRAM
Lots of system RAM
No H100
No datacenter
No shame
```

Everything should run locally whenever possible.

---

# 2. The Main Rule

## DO NOT LOAD EVERYTHING INTO VRAM AT ONCE.

This project exists because we have 24 GB, not 240 GB.

Correct strategy:

```text
Load LLM
    ↓
Generate plan
    ↓
Unload LLM

Load TTS
    ↓
Generate narration
    ↓
Unload TTS

Load video model
    ↓
Generate clips
    ↓
Unload / release resources

FFmpeg
    ↓
Profit
```

Incorrect strategy:

```text
LLM + TTS + Wan + VAE + text encoder + hope
```

Expected result of incorrect strategy:

```text
CUDA out of memory
```

---

# 3. User Experience

The application should look simple enough that a normal person can use it without understanding diffusion models, samplers, nodes, quantization, or why VRAM disappears when you look at it.

Main screen:

```text
+------------------------------------------------------+
|               24GB AND A DREAM                       |
|                                                      |
| PROMPT                                               |
| +--------------------------------------------------+ |
| | Make me a cinematic video about...              | |
| |                                                  | |
| +--------------------------------------------------+ |
|                                                      |
| REFERENCE IMAGE                                      |
| [ Upload image - optional ]                          |
| [ preview appears here ]                             |
|                                                      |
| VIDEO                                                |
| Duration:       [ 30 sec      v ]                    |
| Aspect Ratio:   [ 16:9        v ]                    |
| Style:          [ Cinematic   v ]                    |
|                                                      |
| VOICE OVER                                           |
| [x] Enable voice-over                                |
|                                                      |
| Language:       [ Bulgarian   v ]                    |
| Voice:          [ Female      v ]                    |
|                                                      |
| Narration source:                                    |
| (o) Let the AI cook                                  |
| ( ) Use my exact text                                |
|                                                      |
| +--------------------------------------------------+ |
| | Optional custom narration                       | |
| +--------------------------------------------------+ |
|                                                      |
|                   [ GENERATE ]                       |
|                                                      |
| GPU STATUS: probably regretting this                 |
+------------------------------------------------------+
```

The default experience should be:

```text
Prompt
Optional image
BG / EN
Generate
```

Everything else belongs in Advanced Settings.

---

# 4. What the LLM Does

The LLM is the director.

It receives:

- the user prompt
- desired duration
- aspect ratio
- video style
- whether a reference image exists
- selected narration language
- whether narration is auto or manual
- video model constraints

The LLM must decide:

```text
What happens visually?
How many scenes?
What should each scene look like?
How should the camera move?
What should move?
What must remain unchanged?
What should the narrator say?
How long should each scene last?
```

The LLM must NOT return random prose and vibes.

It must return valid structured JSON.

Because parsing:

```text
"Then perhaps the camera slowly glides..."
```

is how software projects become crimes.

---

# 5. The Sacred JSON Contract

The LLM must produce something like:

```json
{
  "project": {
    "title": "Castle Storm",
    "duration_seconds": 30,
    "aspect_ratio": "16:9",
    "style": "cinematic",
    "language": "bg"
  },

  "voice_over": {
    "enabled": true,
    "language": "bg",
    "voice": "female",
    "narration_mode": "auto"
  },

  "scenes": [
    {
      "id": 1,
      "duration_seconds": 6,

      "director": {
        "visual_prompt": "A cinematic medieval castle during a thunderstorm",
        "negative_prompt": "",
        "camera_motion": "slow push-in",
        "motion": [
          "flags moving in strong wind",
          "clouds moving rapidly",
          "fog drifting",
          "lightning flashes"
        ],
        "preserve": [
          "castle architecture",
          "main composition"
        ]
      },

      "narrator": {
        "text": "Над древния замък се надига буря.",
        "emotion": "dramatic",
        "pace": "medium"
      }
    }
  ]
}
```

That JSON is the law.

Not a suggestion.

Not a creative interpretation.

The law.

---

# 6. Validate Everything

Use Pydantic.

Suggested hierarchy:

```text
ProjectPlan
    ProjectSettings
    VoiceOverSettings
    List[Scene]

Scene
    DirectorInstructions
    NarratorInstructions
```

Pipeline:

```text
LLM response
    ↓
Parse JSON
    ↓
Pydantic validation
    ↓
Valid?
   /   \
 yes    no
 |       |
continue ask LLM once to repair it
         |
         v
      validate again
         |
         v
   if still broken:
   fail loudly and politely
```

Never silently invent missing critical values.

The computer is already hallucinating enough.

---

# 7. Tech Stack

Use:

```text
Python 3.11+
PySide6
Pydantic
PyYAML
llama.cpp / llama-cpp-python
ComfyUI API
FFmpeg
Pillow
requests
websocket-client
```

Do NOT use Tkinter.

We are broke, not uncivilized.

---

# 8. LLM Backend

Recommended starting point:

```text
Qwen family
GGUF
llama.cpp
```

Example:

```text
Qwen3 8B
Q5_K_M or Q6_K
```

The exact model must live in config, not in seventeen Python files.

The app should be able to replace the LLM later without collapsing like a badly-written startup backend.

Interface:

```python
class LLMEngine:
    def create_director_plan(self, request):
        raise NotImplementedError
```

Possible implementations:

```text
QwenLlamaCppEngine
FutureLocalModelEngine
FutureCloudEngine
```

---

# 9. Video Backend

Use ComfyUI as the GPU basement.

The user should never need to see the node graph unless they explicitly want to.

Architecture:

```text
PySide6 App
      |
      v
Python Controller
      |
      v
ComfyUI API
      |
      v
Workflow JSON
      |
      v
Wan / MiniMax / Whatever survives this week
      |
      v
MP4
```

Create a generic video interface:

```python
class VideoGenerator:
    def text_to_video(self, request):
        raise NotImplementedError

    def image_to_video(self, request):
        raise NotImplementedError
```

Possible implementations:

```text
WanVideoGenerator
MiniMaxVideoGenerator
HunyuanVideoGenerator
```

First backend:

```text
Wan 2.2 through ComfyUI
```

Because one disaster at a time.

---

# 10. Optional Reference Image

This is important.

If the user does NOT provide an image:

```text
TEXT TO VIDEO
```

If the user DOES provide an image:

```text
IMAGE TO VIDEO
```

The user should not have to choose.

Logic:

```python
if reference_image:
    mode = "image_to_video"
else:
    mode = "text_to_video"
```

Simple.

No dropdown asking the user to understand model architecture.

---

# 11. What the Image Means

The image is a visual foundation.

Example:

```text
User uploads:
castle.jpg

Prompt:
"Make the castle feel alive during a violent storm."
```

The LLM should NOT decide:

```text
Great, let's replace the castle with a cyberpunk frog.
```

Instead:

```text
PRESERVE:
- castle identity
- architecture
- major composition
- important colors

ANIMATE:
- clouds
- rain
- flags
- fog
- lightning
- camera

CAMERA:
- slow push-in
```

The image is the boss.

The motion prompt works around it.

---

# 12. Voice-over

Voice-over must be optional.

UI:

```text
[x] Enable voice-over
```

Languages:

```text
Bulgarian
English
```

Internal:

```text
bg
en
```

Because somewhere, eventually, a config file will care.

---

# 13. Narration Modes

Two modes.

## Mode A — Let the AI Cook

The LLM writes narration.

Example:

```text
Prompt:
Make a premium sports car commercial.

Language:
BG
```

Narration:

```text
"Създадена за онези, които отказват да намалят скоростта."
```

## Mode B — Hands Off My Copy

The user writes narration manually.

Example:

```text
"The future does not wait. Neither should you."
```

The LLM may arrange scenes around the text.

It must NOT rewrite the text.

Logic:

```python
if narration_mode == "manual":
    narration = user_narration
else:
    narration = llm_generated_narration
```

No "helpful improvements."

No surprise poetry.

---

# 14. TTS Architecture

Create a generic interface:

```python
class TTSEngine:
    def synthesize(
        self,
        text: str,
        output_path: str,
        voice: str,
        speed: float = 1.0
    ):
        raise NotImplementedError
```

Implement:

```python
class BulgarianTTSEngine(TTSEngine):
    pass


class EnglishTTSEngine(TTSEngine):
    pass
```

The exact model must be configurable.

Example:

```yaml
tts:
  bg:
    backend: local_bg
    model_path: "./models/tts/bg"

  en:
    backend: local_en
    model_path: "./models/tts/en"
```

Do not tattoo model names into the application.

Models change.

Repos disappear.

Dependencies break.

Nature heals.

---

# 15. Narration Controls the Timeline

This is one of the most important architecture decisions.

Wrong:

```text
Generate random amount of video
    ↓
Try to squeeze narration on top
    ↓
Why is the voice still talking over a black screen?
```

Correct:

```text
Generate narration
    ↓
Measure narration duration
    ↓
Calculate visual duration
    ↓
Generate enough video
    ↓
Trim precisely
```

Example:

```text
Scene 1 narration = 7.4 sec
Scene 2 narration = 11.2 sec
Scene 3 narration = 5.8 sec
```

If video clips are generated in 5-second chunks:

```text
Scene 1 -> 2 clips
Scene 2 -> 3 clips
Scene 3 -> 2 clips
```

Then trim the final clip.

This is engineering.

The alternative is prayer.

---

# 16. FFmpeg: The Adult in the Room

FFmpeg handles final assembly.

Responsibilities:

```text
concatenate video
trim clips
mux narration
normalize audio
mix background music later
add subtitles
encode MP4
```

Create:

```python
class VideoRenderer:
    def render(self, project):
        ...
```

Preferred output:

```text
MP4
H.264
AAC
```

If NVENC is available:

```text
h264_nvenc
```

Because after making the 3090 Ti generate the video, we might as well ask it to encode the corpse too.

---

# 17. Subtitles

We already know the narration text.

Therefore:

```text
DO NOT RUN SPEECH RECOGNITION JUST TO REDISCOVER THE TEXT WE ALREADY HAVE.
```

Generate:

```text
subtitles.srt
```

from scene timings.

MVP:

```text
normal SRT
```

Future:

```text
burned captions
animated TikTok subtitles
word highlighting
karaoke mode
```

But not today.

---

# 18. VRAM Survival Protocol

Target:

```text
RTX 3090 Ti
24 GB
```

Rule:

```text
Only one heavy AI subsystem gets to feel important at a time.
```

Pipeline:

```text
1. LLM loads
2. Director plan generated
3. LLM unloaded

4. TTS loads
5. Narration generated
6. TTS unloaded

7. Video backend loads / runs
8. Scenes generated
9. Video resources released

10. FFmpeg renders
```

Use:

```python
del model
gc.collect()
torch.cuda.empty_cache()
```

where appropriate.

But do not pretend:

```python
torch.cuda.empty_cache()
```

is an exorcism.

Models must actually be unloaded.

---

# 19. ComfyUI Client

Create:

```python
class ComfyUIClient:
    def health_check(self):
        ...

    def submit_workflow(self, workflow, parameters):
        ...

    def wait_for_completion(self, prompt_id):
        ...

    def get_outputs(self, prompt_id):
        ...
```

Support:

- workflow submission
- WebSocket progress if useful
- dynamic node parameter replacement
- output discovery
- errors
- retries
- cancellation if possible

ComfyUI is the engine room.

The GUI is the steering wheel.

Do not let the steering wheel know how the reactor works.

---

# 20. Workflow Templates

Store workflows separately:

```text
workflows/
    wan22_t2v.json
    wan22_i2v.json
```

Never paste 4,000 lines of workflow JSON into a Python module.

The controller should modify fields like:

```text
prompt
negative prompt
seed
reference image
width
height
frames
steps
CFG
```

and leave everything else alone.

---

# 21. Repository Structure

Use something like:

```text
24gb-and-a-dream/
|
|-- app.py
|-- requirements.txt
|-- config.yaml
|-- README.md
|
|-- ui/
|   |-- main_window.py
|   |-- widgets/
|   |   |-- prompt_panel.py
|   |   |-- image_picker.py
|   |   |-- voice_panel.py
|   |   |-- progress_panel.py
|   |
|   |-- dialogs/
|       |-- settings_dialog.py
|
|-- core/
|   |-- controller.py
|   |-- project.py
|   |-- pipeline.py
|   |-- events.py
|
|-- llm/
|   |-- base.py
|   |-- qwen_llama_cpp.py
|   |-- prompts.py
|   |-- schemas.py
|
|-- tts/
|   |-- base.py
|   |-- bulgarian.py
|   |-- english.py
|
|-- video/
|   |-- base.py
|   |-- comfyui_client.py
|   |-- wan.py
|   |-- minimax.py
|
|-- render/
|   |-- ffmpeg.py
|   |-- subtitles.py
|   |-- timeline.py
|
|-- workflows/
|   |-- wan22_t2v.json
|   |-- wan22_i2v.json
|
|-- models/
|   |-- .gitkeep
|
|-- projects/
|   |-- .gitkeep
|
|-- utils/
|   |-- paths.py
|   |-- process.py
|   |-- gpu.py
|   |-- logging.py
|
|-- tests/
    |-- test_schema.py
    |-- test_timeline.py
    |-- test_project.py
```

Do not create:

```text
main.py
```

with 8,700 lines and three classes called Manager.

---

# 22. Project Folder Structure

Every generation gets its own project folder:

```text
projects/
    2026-08-15_castle_storm/
        project.json
        director_plan.json

        input/
            reference.png

        audio/
            narration.wav

        scenes/
            scene_001.mp4
            scene_002.mp4
            scene_003.mp4

        subtitles/
            subtitles.srt

        output/
            final.mp4

        logs/
            generation.log
```

Why?

Because when scene 8 fails after 45 minutes, deleting everything and starting again is how monitors get punched.

---

# 23. Project State

Create a project object:

```python
class VideoProject:
    id: str
    prompt: str
    reference_image: str | None

    requested_duration: float
    aspect_ratio: str
    style: str

    voice_enabled: bool
    voice_language: str
    voice_name: str

    narration_mode: str
    narration_text: str | None

    director_plan: ProjectPlan | None
    project_directory: str
```

Persist:

```text
project.json
```

The app should always know what happened before Windows decides it is Update Time.

---

# 24. Background Jobs

Never run AI generation on the UI thread.

Ever.

Use:

```text
QThread
```

or:

```text
QThreadPool + QRunnable
```

Signals:

```text
status_changed
progress_changed
scene_started
scene_completed
generation_completed
generation_failed
```

If the window freezes for 20 minutes, users will assume the application is dead.

They will be correct emotionally, even if Python disagrees technically.

---

# 25. Progress UI

Show useful status.

Example:

```text
Analyzing prompt...
████████████████████ 100%

Convincing the TTS model to speak Bulgarian...
████████████████████ 100%

Scene 1 / 5 — GPU still alive
██████████---------- 50%

Scene 2 / 5 — fans have achieved flight
████████████-------- 60%

Rendering final video...
██████████████------ 70%
```

Humorous status messages are allowed.

But logs should remain professional enough to debug.

---

# 26. Cancellation

Add:

```text
[ CANCEL ]
```

Cancellation should:

- stop future scenes
- stop child processes where safe
- keep completed outputs
- mark project cancelled
- avoid destroying evidence

Do not delete everything because the user changed their mind.

Disk space is cheaper than emotional recovery.

---

# 27. Configuration

Use:

```text
config.yaml
```

Example:

```yaml
app:
  projects_dir: "./projects"

gpu:
  auto_unload: true
  preferred_device: "cuda"

llm:
  backend: "llama_cpp"
  model_path: "./models/qwen.gguf"
  context_size: 16384

comfyui:
  host: "127.0.0.1"
  port: 8188
  workflows_dir: "./workflows"

video:
  backend: "wan22"
  default_width: 1280
  default_height: 720
  default_fps: 24

tts:
  default_language: "bg"

  bg:
    backend: "bulgarian_local"
    model_path: "./models/tts/bg"

  en:
    backend: "english_local"
    model_path: "./models/tts/en"

ffmpeg:
  binary: "ffmpeg"
  encoder: "h264_nvenc"
```

No absolute paths like:

```text
C:\Users\Ivan\Desktop\final_final_REAL\models\
```

Use `pathlib.Path`.

We are professionals now.

Mostly.

---

# 28. Settings Screen

Later add:

```text
GENERAL
GPU
LLM
VIDEO MODEL
TTS
COMFYUI
FFMPEG
```

Allow configuration of:

- LLM model
- TTS models
- video backend
- ComfyUI address
- FFmpeg
- project folder

Optional diagnostic section:

```text
CUDA detected: yes
GPU: RTX 3090 Ti
VRAM: 24 GB
H100 detected: lol no
```

---

# 29. Advanced Settings

Hide by default.

Button:

```text
Advanced >
```

Options:

```text
Seed
Steps
CFG
Resolution
FPS
Negative prompt
Camera motion strength
Image preservation strength
TTS speed
Voice
Video model
```

Default users should not need to know what CFG means.

Advanced users absolutely will complain if CFG is missing.

This satisfies both tribes.

---

# 30. Image Handling

Supported MVP formats:

```text
PNG
JPG
JPEG
WEBP
```

When selected:

- validate image
- preview image
- copy it into project folder
- automatically switch to image-to-video

Add:

```text
[ Remove image ]
```

Removing it switches back to text-to-video.

No drama.

No modal confirmation asking:

```text
Are you sure you wish to remove image?
```

Yes.

They clicked Remove.

---

# 31. LLM Prompt Rules

The internal system prompt must tell the director:

1. Output JSON only.
2. Follow the schema exactly.
3. Respect requested duration.
4. Respect selected narration language.
5. Keep video prompts in English where useful for model compatibility.
6. If a reference image exists, preserve it rather than reinventing reality.
7. If narration is manual, do not rewrite it.
8. Keep scenes short and practical.
9. Do not invent unsupported features.
10. Optimize for the configured video model.

And perhaps spiritually:

```text
You are not writing a novel.
You are operating a financially constrained video pipeline.
Act accordingly.
```

---

# 32. Example: Text-to-Video

User:

```text
Create a 20-second cinematic video about the fall of the Roman Empire.
```

Settings:

```text
Voice: Bulgarian
Image: none
```

Pipeline:

```text
Prompt
    ↓
Qwen
    ↓
Director JSON
    ↓
Bulgarian narration
    ↓
TTS
    ↓
Wan T2V
    ↓
FFmpeg
    ↓
final.mp4
```

Somewhere during this process:

```text
GPU fans: 100%
User confidence: 83%
CUDA stability: unknowable
```

---

# 33. Example: Image-to-Video

User uploads:

```text
car.jpg
```

Prompt:

```text
Create a premium nighttime advertisement for this car.
```

LLM:

```text
PRESERVE:
- car identity
- body shape
- paint color

ANIMATE:
- reflections
- city lights
- fog
- environment

CAMERA:
- slow dolly
- wheel close-up
```

Backend:

```text
Wan I2V
```

Output:

```text
Scene 1
Scene 2
Scene 3
```

FFmpeg:

```text
"Fine, I'll do everything."
```

---

# 34. Example: Manual Narration

Prompt:

```text
Create a futuristic reveal.
```

Voice:

```text
English
```

Narration:

```text
"The future does not wait. Neither should you."
```

The LLM may adjust scenes around that exact text.

It may not turn it into:

```text
"In a world where tomorrow waits for no one..."
```

No.

Bad LLM.

---

# 35. Logging

Use Python logging.

Store:

```text
timestamps
pipeline stages
model load/unload
scene IDs
ComfyUI job IDs
FFmpeg commands
durations
errors
```

Project log:

```text
projects/.../logs/generation.log
```

Humor belongs in UI status.

Logs should tell us why everything exploded.

---

# 36. Error Messages

UI errors should be understandable.

Examples:

```text
Could not load the LLM model.

ComfyUI is not reachable.

TTS generation failed.

The reference image is invalid.

Scene 3 failed after 2 retries.

FFmpeg was not found.

Not enough disk space.

CUDA ran out of memory.
The 24 GB dream has temporarily ended.
```

Raw stack traces belong in logs.

Not in giant popup windows.

---

# 37. Retry Strategy

Video models occasionally decide not to cooperate.

Use:

```text
max_scene_retries = 2
```

Flow:

```text
Generate scene
    ↓
failed?
    ↓
retry
    ↓
failed again?
    ↓
retry
    ↓
still dead?
    ↓
stop pipeline
keep completed work
show useful error
```

Do not regenerate seven successful scenes because scene eight had feelings.

---

# 38. Resume Support

Design for resumability immediately.

Scene state:

```json
{
  "scene_001": "completed",
  "scene_002": "completed",
  "scene_003": "pending"
}
```

Before generation:

```python
if valid_scene_output_exists:
    skip_generation
```

This feature is not optional philosophically.

Video generation takes too long to trust fate.

---

# 39. Factories and Interfaces

Use factories:

```python
video_generator = VideoGeneratorFactory.create(config.video.backend)
tts_engine = TTSEngineFactory.create(language)
llm = LLMFactory.create(config.llm.backend)
```

Why?

Today:

```text
Wan
```

Tomorrow:

```text
MiniMax
```

Next month:

```text
ModelWithANameThatRequiresSixHyphens-v3.7-distilled-fp8
```

The rest of the application should not care.

---

# 40. Local-First

MVP should be local-first.

Do not upload:

- prompts
- images
- narration
- video

to random cloud services.

Future cloud integrations can be explicit adapters.

But default behavior should be:

```text
What happens on the 3090 Ti
stays on the 3090 Ti.
```

---

# 41. Windows Packaging

Final app:

```text
24GB and a Dream.exe
```

Use something like:

```text
PyInstaller
```

Do NOT bundle 50+ GB of models into the EXE.

Use external folders:

```text
24GB and a Dream/
    24GB and a Dream.exe
    config.yaml
    workflows/
    models/
    runtime/
```

The executable should launch the app.

It should not contain the Library of Alexandria.

---

# 42. MVP Scope

## v0.1 MUST HAVE

- PySide6 Windows GUI
- prompt field
- optional reference image
- duration
- aspect ratio
- voice-over enable/disable
- Bulgarian / English
- auto narration
- manual narration
- LLM director
- JSON validation
- TTS abstraction
- BG TTS
- EN TTS
- ComfyUI API client
- Wan T2V
- Wan I2V
- FFmpeg rendering
- subtitles
- project folders
- progress reporting
- logs
- model unload logic
- errors
- retries

This is already plenty.

Do not suddenly invent a social network.

---

# 43. Things We Are NOT Building Yet

Not in v0.1:

```text
accounts
payments
cloud sync
timeline editor
voice cloning
lip sync
multi-GPU orchestration
distributed rendering
plugin marketplace
mobile app
NFT export
blockchain
AI girlfriend
```

Stay focused.

---

# 44. Future v0.2

Potential:

```text
background music
audio ducking
more voices
MiniMax backend
Hunyuan backend
scene regeneration
project resume UI
prompt presets
model manager
scene preview
```

---

# 45. Future v0.3

Potential:

```text
storyboard editor
drag-and-drop scenes
per-scene reference images
voice cloning
music generation
automatic image generation
animated captions
logos
brand templates
intro/outro
```

By then the 3090 Ti may have achieved consciousness.

---

# 46. Development Order

Codex should implement the project in phases.

Do not attempt the entire stack in one commit titled:

```text
initial
```

---

## Phase 1 — Skeleton

Create:

```text
repository structure
config loader
logging
project model
Pydantic schemas
tests
```

Acceptance:

```text
imports work
config loads
tests pass
nothing catches fire
```

---

## Phase 2 — LLM Director

Implement:

```text
LLM interface
llama.cpp adapter
director prompt
JSON parser
Pydantic validation
one repair attempt
```

Acceptance:

```text
Prompt -> valid ProjectPlan
```

No video yet.

The GPU deserves one problem at a time.

---

## Phase 3 — UI

Implement:

```text
prompt
image picker
duration
aspect ratio
voice checkbox
BG / EN
auto/manual narration
Generate button
progress
status
```

Acceptance:

```text
UI creates a valid generation request
```

---

## Phase 4 — TTS

Implement:

```text
TTS interface
Bulgarian adapter
English adapter
WAV output
duration measurement
```

Acceptance:

```text
BG -> WAV
EN -> WAV
```

If Bulgarian sounds like a haunted GPS, that is a model-quality problem, not an architecture problem.

---

## Phase 5 — ComfyUI Client

Implement:

```text
health check
submit workflow
track job
find outputs
handle errors
```

Acceptance:

```text
test workflow successfully runs
```

---

## Phase 6 — Wan T2V

Implement:

```python
WanVideoGenerator.text_to_video()
```

Acceptance:

```text
prompt -> MP4
```

---

## Phase 7 — Wan I2V

Implement:

```python
WanVideoGenerator.image_to_video()
```

Acceptance:

```text
image + prompt -> animated MP4
```

---

## Phase 8 — Timeline

Implement:

```text
audio duration
scene timings
clip count
trim logic
subtitle timings
```

Acceptance:

```text
video length follows narration length
```

---

## Phase 9 — Renderer

Implement:

```text
FFmpeg concat
audio mux
subtitle generation
final encode
```

Acceptance:

```text
scenes + voice -> final.mp4
```

---

## Phase 10 — Full Pipeline

Connect:

```text
UI
 ↓
LLM
 ↓
TTS
 ↓
Video
 ↓
FFmpeg
```

Acceptance:

```text
one Generate button
one final video
one exhausted GPU
```

---

## Phase 11 — Stability

Add:

```text
retries
cancel
resume foundations
GPU unload
disk checks
better logs
better errors
```

---

## Phase 12 — Windows Build

Create:

```text
PyInstaller build
README
setup instructions
launcher
```

Acceptance:

```text
24GB and a Dream.exe launches
```

Preferably without opening twelve command windows.

---

# 47. Codex Rules

Codex, please observe the following.

## Rule 1

Do not build a monolith.

## Rule 2

Use type hints.

## Rule 3

Use Pydantic.

## Rule 4

Use interfaces around model-specific code.

## Rule 5

Never block the GUI thread.

## Rule 6

No absolute paths.

## Rule 7

Use `pathlib.Path`.

## Rule 8

Log important stages.

## Rule 9

Save project state.

## Rule 10

Keep data local.

## Rule 11

Readable code beats wizardry.

## Rule 12

Test non-GPU logic.

## Rule 13

If tempted to create `utils2.py`, reconsider your life choices.

---

# 48. Minimum Tests

Write tests for:

```text
config loading
director schema
manual narration preservation
BG / EN selection
T2V / I2V mode selection
timeline calculation
subtitle timestamps
project directory creation
scene state persistence
```

Do not unit-test whether Wan can generate a castle.

That is between Wan and God.

---

# 49. Definition of Done

MVP is done when the user can:

1. Launch the Windows app.
2. Enter a prompt.
3. Optionally upload an image.
4. Select video duration.
5. Enable/disable voice-over.
6. Select Bulgarian or English.
7. Auto-generate narration or enter exact narration.
8. Click Generate.
9. Watch progress.
10. Receive a final MP4.
11. Hear the correct narration language.
12. Get I2V when an image exists.
13. Get T2V when it does not.
14. Find all intermediate project assets.
15. Read useful logs when CUDA betrays us.

---

# 50. First Milestone

Before real video generation, build this:

```text
Prompt
    ↓
LLM
    ↓
Director JSON
    ↓
UI shows scene plan
    ↓
TTS creates BG / EN narration
    ↓
Project files saved
```

This must work reliably first.

Do not debug:

```text
PySide
+
Qwen
+
TTS
+
ComfyUI
+
Wan
+
FFmpeg
```

all at once unless suffering is a product requirement.

---

# 51. First Deliverable from Codex

Start by creating:

```text
1. repository structure
2. requirements.txt
3. config.yaml
4. Pydantic schemas
5. project persistence
6. PySide6 main window
7. LLM base interface
8. mock LLM
9. mock TTS
10. mock video generator
11. pipeline controller
12. FFmpeg wrapper skeleton
13. tests
14. README
```

Mocks are important.

The entire application should work end-to-end with fake generation before touching real GPU models.

Example fake pipeline:

```text
Prompt
 ↓
Mock Director JSON
 ↓
Fake narration.wav
 ↓
Fake scene.mp4
 ↓
Fake final result
```

Once that works:

```text
Replace mock LLM
Replace mock TTS
Replace mock video
```

one module at a time.

This drastically reduces the probability of spending four hours debugging CUDA when the actual bug is a missing comma in a signal handler.

---

# 52. Final Architecture

```text
+---------------------------------------------------------+
|                 24GB AND A DREAM                        |
|                     PySide6                             |
+-----------------------------+---------------------------+
                              |
                              v
                     Pipeline Controller
                              |
          +-------------------+-------------------+
          |                   |                   |
          v                   v                   v
     LLM Director           TTS Engine        Video Engine
     llama.cpp             BG / EN            ComfyUI
          |                   |                   |
          |                   |             +-----+-----+
          |                   |             |           |
          |                   |            T2V         I2V
          |                   |             |           |
          +-------------------+-------------+-----------+
                              |
                              v
                           Timeline
                              |
                              v
                            FFmpeg
                              |
                              v
                        FINAL MP4
                              |
                              v
                    unreasonable satisfaction
```

---

# 53. Project Philosophy

This project is not about having the biggest model.

It is not about having an H100.

It is not about pretending one consumer GPU is a datacenter.

It is about building a sane orchestration layer that gets useful results from hardware normal humans can actually own.

The application should be modular.

The models should be replaceable.

The workflow should be resumable.

The UI should be simple.

The VRAM should be respected.

And when everything finally renders:

```text
Hollywood has millions.

We have 24 GB,
FFmpeg,
duct tape,
and a dream.
```

---

# Codex: Start Here

Implement **Phase 1** first.

Do not skip directly to real model integration.

Build the project skeleton, schemas, config, logging, project persistence, tests, and mock interfaces.

Then proceed phase by phase.

If a design decision is unclear, prefer:

```text
modular
local-first
recoverable
configurable
24GB-VRAM-friendly
```

over:

```text
clever
hardcoded
monolithic
"works on my machine"
```

Good luck.

The GPU has no idea what is coming.
