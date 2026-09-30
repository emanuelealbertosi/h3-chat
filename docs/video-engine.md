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
video default. **Installa motore video** downloads the shared private runtime on
first use; an already installed Ming/Qwen runtime is reused. Model license terms
still apply and weights are not included in the application archive.

## Per-model defaults

| Setting | Default |
| --- | --- |
| Duration | 15 seconds |
| Resolution | 0.7 MP using H3's 1024² pixels/MP convention |
| Aspect | 16:9, rounded to 1152×640 |
| Frame rate | 24 fps |
| Steps / CFG | 8 / 1 |
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
lyrics retain their supplied wording and language. It uses the chat's CPU mmproj
when Vision is enabled and the LLM supports the number of supplied images. When
images cannot be shown to that LLM, the preparation explicitly states that they
are unseen and does not invent image details. Audio is never presented to the
text/vision LLM as if it had been transcribed. MiniMax H3 receives the actual files.
The maximum Assistant output is saved per chat LLM in its preferences.

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

## GPU and memory

Inference requires NVIDIA CUDA. Diffusion, the H3 encoder and both VAEs compute on
the GPU, including when inactive weights are offloaded to RAM. The chat mmproj is
a separate component and remains on the CPU. CUDA Toolkit and H3-Studio are not
required. Compatible NVIDIA drivers are required by the bundled CUDA runtime.

**A richiesta** releases the previous chat/image/music process before loading
the video worker and releases video before switching back. **Residenti** retains
the worker process, but the video preset's offload switch still determines weight
placement. Enabled offload reduces VRAM by transferring inactive weights to RAM;
disabled offload requires all components to fit in GPU memory. Recent model file
pages may be retained by the existing reclaimable file cache, without copying
weights or locking RAM. This can help reloading but cannot remove PCIe transfers.

H3 weights are much larger than the small chat/image models: memory assessments
include model files, duration, resolution, references and decoded video buffers.
They are estimates, not a guarantee against OOM. Loading, GPU transfers, sampling,
decoding and MP4 saving have distinct status messages. Cancelling the job stops
the owned worker and releases its model process.
