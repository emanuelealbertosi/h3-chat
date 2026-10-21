# MiniMax H3 PDD 8-step (experimental)

PDD is an optional acceleration adapter, disabled by default. It includes a
rank-64 trunk LoRA **and** a trained video/audio projection bank. A generic
LoRA loader does not implement it correctly.

Choose an original Alibaba PAI `MiniMax-H3-FL2VA-Acc-8Step.safetensors` or
`MiniMax-H3-Ref2VA-Acc-8Step.safetensors` in Video preferences, then enable PDD
for that model. The controls select eight steps, Euler, CFG 1 and shifts 12/3.
Once the adapter is configured, both video modals fill its path automatically,
including when recreating a standard video whose saved adapter path is empty.
Choosing a different model loads that model's own adapter; merely storing the
path does not enable PDD. Pairings must be verified for the actual checkpoint,
rather than inferred solely from filenames.
The sampler receives PDD's exact trained sigma boundaries. Other step counts
and incompatible recipes are rejected before GPU work. Disable PDD before
selecting standard 12/16/20 steps.

FL2VA and Ref2VA have different trained trunks. Hybrid and fine-tuned models
are experimental pairings: trunk fingerprint warnings are logged, all patch
keys must match, and the dense AdaLN LoRA is rebased to the pruned curve basis.
Unknown curve bases fail rather than silently dropping patches. PDD must not
be stacked with another distillation adapter or step-caching system.

Character Swap and VFX Edit can be combined with the matching PDD adapter.
Their ordinary trunk patches remain pending until PDD is added; the combined
patches are merged and requantized once per parameter on the disposable model.
PDD's head bank and trained sigmas remain active. Other ordinary adapters,
including DMD/Turbo distillation, are rejected with PDD until verified.

Source: https://huggingface.co/alibaba-pai/MiniMax-H3-Acc-LoRAs

Implementation: https://github.com/Jalen-Brunson/ComfyUI-MiniMax-H3-PDD-Acc

See `h3chat/vendor_pdd/provenance.json` and `LICENSE` for the pinned revision
and attribution. No custom-node installation or external ComfyUI server is
required. The existing standard generation path is unchanged when disabled.

On low-VRAM systems the disposable worker merges and requantizes trunk patches
once in memory, one module at a time, through Comfy's ordinary quant-aware
setter. Each changed parameter is returned to CPU and its restoration backup
is released before the next module. Sampling keeps quantized matrix operations
and does not repeat LoRA fusion on every MLP chunk. Checkpoint files are never
modified; the prepared diffuser is discarded after sampling, including when
model retention is enabled. `pdd-info.json` records the applied patch count.
