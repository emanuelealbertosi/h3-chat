# MiniMax H3 standalone

H3-Chat owns a private Python worker (`native/video-worker.py`) and imports the
pinned inference library already distributed with its optional Ming/Qwen
runtime. It starts no ComfyUI server, loads no external custom nodes and has no
dependency on H3-Studio. H3-Studio's generation modes and prompt conventions were
used as the product reference. The worker and inference source are GPL-3.0-or-later;
the downloadable runtime contains the complete upstream source and licenses.

## Setup and original model paths

In **Setup → Video → Sfoglia e collega**, choose **MiniMax H3** and four
`.safetensors` components. Each may live in a different directory:

| Component | Compatible example |
| --- | --- |
| Diffusion model | `minimax_h3_hybrid_fl2va_ref2va_b25-49-int8.safetensors` or a compatible standard H3 FL2VA/REF2VA model |
| Text/image encoder | `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors` |
| Video VAE | `minimax_h3_video_vae_int8_convrot.safetensors` |
| Audio VAE | `minimax_h3_audio_vae_fp32.safetensors` |

The app keeps the absolute paths and never copies or moves model weights. GGUF,
PDD/Turbo banks, model conversion and external workflows are not supported by this
worker. The worker validates the diffusion architecture, standard output heads
and video/audio VAE channels before generation. Select the linked model as the
video default. Hybrid is the preferred model and is selected automatically when linked if no video default exists. Administrators can choose another compatible model and edit each model’s preset; original paths remain local settings and are never embedded in the release. **Installa motore video** downloads the shared private runtime on
first use; an already installed Ming/Qwen runtime is reused. Model license terms
still apply and weights are not included in the application archive.

## Request quality

In the chat's **Video → Impostazioni → Qualità** dialog, **Alta · preset attuale**
is the default and keeps the selected model's saved parameters (normally 0.7 MP
and 12 steps). **Media · più rapida** caps resolution at 0.5 MP and steps at 8;
lower custom values stay lower, except lip-sync still uses at least 8 steps.
Duration, frame rate, aspect handling, references, sampler, scheduler, attention
and loading policies remain unchanged. Media trades detail and refinement for
less generation work; actual time depends on hardware and offload, and model
loading is not made faster by this profile.

The preference belongs to the chat, is captured in each queued request, and is
retained by **Riutilizza** and **Rigenera**. It applies to automatically routed
MiniMax videos too, including every scene of a long video. It never edits the
administrator's per-model preset and does not affect Manim or HTML infographics.
The response displays the selected profile and reported resolution/steps.
Remote H3 video requests apply the same caps; Alta without overrides preserves
the server's defaults. These profiles do not automatically enable VEDA or add
Turbo/LoRA models.

## Per-model defaults

| Setting | Default |
| --- | --- |
| Duration | 15 seconds |
| Resolution | 0.7 MP using H3's 1024² pixels/MP convention |
| Aspect | 16:9, rounded to 1152×640 |
| Frame rate | 24 fps |
| Steps / CFG | 12 / 1 |
| Sampler / scheduler | Res Multistep / Simple |
| Video / audio sigma shift | 12 / 3 |
| Seed | Random |
| Inactive-weight offload | Enabled |

**Avanzate** edits the selected video's preset; a different model retains its
own values. Supported durations are 1–15 seconds and resolutions 0.2–1 MP. The
model uses a 17k+5 frame grid: a 15-second job samples 362 model frames and exports
360 frames, with audio trimmed to the same exact duration. There is one sampling
pass, followed by separate video/audio decode and MP4 encoding stages.

## One chat, automatic or explicit

Use **Video** for an explicit request, or ask to create a video/animate an image.
The router treats music videos as video requests. It keeps questions, tutorials,
code and prompt-only writing in the normal chat. Disable automatic video routing
in Setup if desired; the Video button still works. Explicit image, Music and Video
selections exclude one another. Each queued message captures its own selection,
Assistant switch and per-model settings.

**Assistant On** uses the existing chat LLM to prepare English narrative prompts,
stable Picture/Audio labels, reference roles and keyframe positions. Dialogues and
lyrics retain their supplied wording and language. It uses the chat's mmproj on the selected CPU/GPU device
when Vision is enabled and the LLM supports the number of supplied images. When
images cannot be shown to that LLM, the preparation explicitly states that they
are unseen and does not invent image details. Audio is never presented to the
text/vision LLM as if it had been transcribed. MiniMax H3 receives the actual files.
The maximum Assistant output is saved per chat LLM in its preferences.

An audio-only music video needs no picture: H3 creates its visuals from the
textual description. Both the initial plan and the scene writer receive an
exhaustive list of actual Picture/Audio labels; generated continuity frames are
not user attachments. Every generated scene is validated before video inference.
If the scene writer invents a reference, Assistant rewrites that batch once;
a repeated invalid result stops planning without starting video generation.
Remaining scenes from an older checkpoint are also checked before resuming.

Assistant develops broad requests into concrete actions and a sequence with progression,
including visible comic beats when parody is requested. Returning to a location retains
its cast/style but advances the action instead of copying an earlier scene. An explicit
user storyboard, pacing or intentional repetition takes precedence. Original soundtrack
sections preserve the selected audio without guessing its genre, lyrics or beat timings;
canonical costumes are not assigned unsupported colors. These are direction instructions
for the LLM, not fixed scene templates or an extra planning pass. The existing output
budget, batching, attachment validation, audio offsets and visual-memory mechanism remain.

Attach up to **9 images and 3 audio files** (WAV, MP3, FLAC, OGG). Image limit:
12 MB / 8192 px; audio limit: 64 MB. Numbering is separate by media type and follows
attachment order. For example:

> Crea un video. Usa immagine 1 come frame iniziale, immagine 2 a 7 secondi,
> immagine 3 come riferimento del personaggio. Audio 1 con lip-sync,
> partendo dal secondo 12 della traccia. Mantieni una sola inquadratura.

Image roles may be keyframe (including start, intermediate and end) or reference
(identity, setting, composition or style). Audio roles may be sound/voice reference,
exact reuse or lip-sync. Every attachment must be assigned once; unknown indices,
duplicate keyframes, omitted files and multiple exact master audio tracks are
rejected before inference. A follow-up referring to a preceding image or song can
reuse the latest media from the conversation, including canvas results.

**Assistant Off** passes the prompt directly without loading an LLM. Explicit
timed phrases `immagine 1 a 0 secondi`, `immagine 2 a 7 secondi` assign keyframes;
`start frame`/`frame iniziale` anchors the first image. A single image is a start
frame unless identified as a reference. Other images are references. `lip-sync`
assigns the first audio as the exact source; `audio originale` requests reuse.
Other audio is treated as a sound/voice reference. More complex plans and source
offsets require Assistant On. Advanced details in chat display the resolved plan
and actual generation parameters.

## Audio conditioning and export

H3 samples joint nested video/audio latents. For exact reuse and lip-sync, the
source segment is encoded with H3's audio VAE, inserted into the target audio
latent and locked with an all-zero audio noise mask; video noise remains enabled.
The source is also available as an audio reference in the model conditioning.
Lip-sync uses at least eight standard steps. This is native audio-conditioned
video generation; visual synchronization accuracy still depends on the model,
scene, face visibility and source recording.

An exact source must cover the selected duration from its requested offset;
otherwise the app reports the short input. Short voice/style references are
accepted without padding them into a fake full soundtrack. The source track,
at its original sample rate, becomes the final soundtrack for exact reuse or
lip-sync. The model's audio VAE uses its own resampled representation internally.
Without an exact source, H3's generated audio is decoded.

PyAV/FFmpeg libraries inside the private runtime encode H.264/AAC in MP4; no
external ffmpeg executable is required. AAC is a lossy encoding, so preserved
audio is not a bit-for-bit copy of a source WAV. The same trim is applied to audio
and video. Chat and canvas use a seekable player, byte-range HTTP and MP4 download.
With canvas selected, the media artifact is placed in the canvas and the message
body contains its standard accompanying text.

## Image aspect ratio

The first keyframe in time determines the output ratio, including when the
prompt specifies a different format. In reference-only mode an explicit format
in the original user prompt overrides the reference ratio; otherwise the first
reference determines it. Text-to-video uses the explicit prompt or preset ratio.
EXIF orientation is applied before measuring. Images are resized proportionally
and contained, with neutral padding for mismatched guides. H3's 32-pixel grid is
padded separately and cropped away from the decoded MP4, whose dimensions remain
even. A 4:3 image at 0.7 MP produces 992×744, sampled on a 992×768 grid.

## GPU and memory

Inference requires NVIDIA CUDA. Diffusion, the H3 encoder and both VAEs compute on
the GPU, including when inactive weights are offloaded to RAM. The chat mmproj is
a separate component and follows the chat Vision CPU/GPU choice (default CPU). CUDA Toolkit and H3-Studio are not
required. Compatible NVIDIA drivers are required by the bundled CUDA runtime.

**A richiesta** releases the previous chat/image/music process before loading
the video worker and releases video before switching back. **Residenti** retains
the worker process, but the video preset's offload switch still determines weight
placement. Enabled offload reduces VRAM by transferring inactive weights to RAM;
disabled offload requires all components to fit in GPU memory. Recent model file
pages may be retained by the existing reclaimable file cache, without copying
weights or locking RAM. This can help reloading but cannot remove PCIe transfers.

In on-demand mode the image process is fully closed before local video loading,
including an image worker previously kept warm during chat. The file-cache
preference remains intact. An idle Torch process can retain substantial RAM and
commit allocations even after unloading model objects; these compete with H3
offload and can force Windows paging. Resident mode keeps the selected models.
Returning to images after video therefore requires a fresh image runtime.

With video offload enabled, conditioning is completed first and the encoder and
VAEs are released before reading the diffuser weights. The diffuser is released
before reloading the video VAE for decoding. This ordering applies to the first
generation and to subsequent jobs on the same worker, and prevents the large
encoder and diffuser weight sets from occupying RAM together. A temporary drop
in VRAM between these stages is expected; storing weights in RAM does not switch
inference to CPU. A large 15-second clip can leave little or no VRAM for resident
diffuser weights, requiring repeated RAM-to-GPU transfers during sampling.

Video presets default to `attention: auto`, selecting SageAttention when the
optional accelerator is installed. Advanced preferences also expose `sage`
(requires installation) and `pytorch` for comparison. The backend is logged at
sampling time and recorded in the output's generation details. Masked attention
and unsupported kernel calls retain the core's PyTorch fallback. SageAttention
uses quantized attention and can change the generated output; it is not a
bit-for-bit replacement for PyTorch. Independent attention heads are processed
in groups to bound Sage workspace: automatic uses eight groups up to 20 GiB,
four up to 32 GiB, and one above that. Advanced `attention_chunks` can override
this (0 means automatic, 1 disables grouping). No tokens or frames are removed.

On Windows the worker reads safetensors into owned writable CPU buffers using
`readinto` and `torch.frombuffer`. This avoids the native storage-slicing crash
seen when reopening the large diffuser after CUDA conditioning, as well as
read-only host-registration failures. There is one allocation per tensor and no
second whole-file mapping competing with offloaded weights in RAM. This reader
preserves original quantization metadata and never modifies the model file.

The video engine install button also installs the accelerator in existing
installations. `runtimes.json` pins the upstream SageAttention
`2.2.0+cu130torch2.10.0andhigher.post6` Windows ABI3 wheel, Triton Windows
`3.7.1.post27` for Python 3.13 and the Python 3.13 include/import libraries,
including download sizes and SHA-256 checksums. They live entirely under the
application directory; no ComfyUI installation, system Python, CUDA Toolkit or
Visual Studio is required. Triton's compiled kernel cache stays under
`runtime/vision/cache/triton`. Wheel licenses accompany the installed packages:
SageAttention Apache-2.0, Triton MIT, CPython PSF.

Sources: [SageAttention Windows release](https://github.com/woct0rdho/SageAttention/releases/tag/v2.2.0-windows.post6),
[Triton Windows](https://github.com/woct0rdho/triton-windows), and
[embedded Python setup](https://github.com/woct0rdho/triton-windows#8-special-notes-for-comfyui-with-embeded-python).

H3 weights are much larger than the small chat/image models: memory assessments
include model files, duration, resolution, references and decoded video buffers.
They are estimates, not a guarantee against OOM. Loading, GPU transfers, sampling,
decoding and MP4 saving have distinct status messages. Cancelling the job stops
the owned worker and releases its model process.

Sampling logs record each H3 step duration. Completed generation parameters
include `sampling_seconds` and `step_seconds`. The last step time is shown
during generation; a summary and expandable per-phase timings appear in chat
even when advanced details are disabled. `startup_seconds` measures worker
activation/loading, while `timings` records conditioning, diffuser loading,
sampling, decoder loading, video/audio decoding and MP4 saving.
The first interval includes sampler preparation and GPU transfers; these are
wall-clock measurements, not isolated CUDA-kernel profiling.
