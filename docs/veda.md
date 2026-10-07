# Optional VEDA video attention

In **Preferenze → Avanzate → Video → Avanzate**, choose **VEDA** under
**Accelerazione attenzione** for the selected local MiniMax H3 model. Existing
presets keep **Auto**, which selects SageAttention when available. No duration,
resolution, step count, sampler or model default changes.

Install the existing video engine/accelerator first, then **Installa VEDA**. The
optional installer adds a pinned MIT implementation and a verified 275 MB FP8
predictor in H3-Chat's own directories. It neither installs a ComfyUI server nor
modifies another application's installation. All downloads resume and verify
their SHA-256 before use. Weights retain the MiniMax H3 Community License.

The predictor field may point to an existing `.safetensors` file on any local
drive; it is used in place, without copying. Leave it empty for the downloaded
predictor. Video/reference sparsity default to 90%, the predictor's training
setting. Setting reference sparsity to 0% preserves full attention for reference
images/keyframes. These parameters are saved per model and captured per request.

VEDA uses its own head grouping for sparse and dense calls, retaining the
app's automatic low-VRAM grouping limit. Unsupported shapes/kernels and runtime
errors use the existing dense Sage/PyTorch path. Chat reports whether VEDA
actually ran, including partial fallback, and advanced generation details contain
call counts and the upstream summary. The predictor and GPU workspaces are
released before VAE decode in offload mode, and when switching back to Sage in
resident mode. Switching modes restores the original patcher; overrides do not
accumulate across requests.

Verification on Windows / RTX 5070 Ti: 58 video/queue/provider tests, browser
checks for per-model selection and sidebar activity, and a native adapter smoke
with the real predictor and MiniMax packed layout. The actual Triton INT8 SM120
kernel passed its GPU self-test and one synthetic sparse call; switching and
offload cleanup are covered independently. This is not a full 15-second render,
a visual-quality comparison, or an end-to-end performance benchmark. The
repeatable optional check is `tests/smoke_veda_runtime.py --gpu`; its default CPU
reference is for testing only and does not enable CPU video generation.

The first GPU use compiles and self-tests the Triton INT8 kernel using H3-Chat's
bundled compiler/headers. NVIDIA SM80+ is supported by the upstream kernel.
Sparse attention changes the result: compare the same seed/prompt and check
references, motion, audio and lipsync. The predictor was trained with Turbo at
eight steps and a limited set of sizes/durations; our default Hybrid, 12 steps,
15 seconds and arbitrary image ratios require comparison. Weight transfers and
RAM pressure can still dominate generation. No end-to-end speedup is promised.

Sources:
- [Pinned VEDA source](https://github.com/veda-sparse/Veda-on-ComfyUI/tree/60bfae688897dc41bc8685ca9f3130d7ed8f3b0c)
- [Predictor](https://huggingface.co/Veda-Sparse/Minimax-H3-T2VA-Veda-8NFE-600Step-Preview)

The sidebar shows a rotating indicator for a running chat and a clock for a
queued request. Both disappear after completion, cancellation or failure, and
remain visible when another conversation is open.
