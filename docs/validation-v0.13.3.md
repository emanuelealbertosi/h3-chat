# H3-Chat 0.13.3 validation

Validated on Windows 11, RTX 5070 Ti 16 GiB, approximately 40 GiB system RAM.
The Hybrid diffuser is on a SATA SSD; its encoder and VAEs are on NVMe. All GPU
generation fixtures use a synthetic blue circle on a white background, with no
personal chats or media included in the release.

## Automated and UI checks

- 217 Python tests pass, including request regeneration, HTTP duplicate-submit
  rejection, per-model attention settings, weight-reader bounds/ownership,
  stage memory ordering, image format selection and external H3 media roundtrip.
- Two JavaScript numerical chart/rendering tests pass; UI build passes.
- Native ABI and app-local Microsoft CRT origin check passes.
- Compiler-free clone/bootstrap checks pass.
- Browser regeneration check covers the circular-arrow icon, retained draft,
  no duplicate user message, replacement answer, active-job disabling,
  cancellation/retry, empty chat disabling, desktop/mobile and no page errors.

## Standalone video and acceleration

The app-local runtime contains PyTorch 2.13.0+cu130, the pinned SageAttention
Windows wheel and Triton Windows. A fresh-cache Triton CUDA kernel was compiled
and executed using the application's TCC compiler, CUDA headers and Python
include/import libraries. No system CUDA Toolkit or Visual Studio was selected.

A direct attention benchmark uses 80,000 tokens, 56 heads of dimension 128,
BF16 and the strided Q/K/V layout used by H3. After one warmup and three measured
iterations: PyTorch averages 1.957 s; Sage averages 0.687 s; Sage with eight head
groups averages 0.698 s (2.80× kernel speedup). Peak live allocations are 5,470
MiB for PyTorch and grouped Sage versus 7,112 MiB for ungrouped Sage. Sampled
output cosine similarity is 0.9992. This measures one attention kernel, not the
speed or quality of an entire video, and Sage is not numerically identical.

Real standalone generation with the Hybrid INT8 model, 15 s, 0.7 MP, 24 fps,
CFG 1, res_multistep/simple, shifts 12/3, seed 42, offload enabled and Auto
attention succeeds. This smoke uses two steps rather than the default twelve;
sampling step intervals are 52.5 and 50.3 seconds. A subsequent one-second,
0.2 MP, one-step job on the same worker also succeeds. Logs select Sage with
eight head groups and show no CUDA OOM, pin-registration error or native crash.
The encoder/VAEs are released before reading the diffuser on both jobs, and the
diffuser is released before decode. All inference remains CUDA.

The 320×240 guide resolves to an exact 4:3 output. PyAV verifies the first MP4
as 992×744, 360 frames, 15.0 seconds and 32 kHz audio; the reused worker produces
528×396, 24 frames and 1.0 second. The model canvas padding is removed before
MP4 encoding. The safetensors reader owns writable per-tensor CPU buffers,
preserves quantization metadata and leaves original model files untouched.

## Scope and limitations

The default remains Hybrid, 15 s, 0.7 MP and twelve steps. The smoke establishes
loading, sampling, decode, export, ratio preservation and worker reuse; it does
not certify twelve-step quality, every model/driver configuration or equivalence
to H3-Studio/ComfyUI timings. Lower VRAM still requires repeated weight transfers.
Regeneration replays the saved request snapshot; a fixed seed can repeat output.
Existing installations must reopen the backend to use the new regeneration API.
