# H3-Chat 0.13.4 validation

## Memory transition fix

The 0.13.3 application was running SageAttention on RTX 5070 Ti 16 GiB,
with Hybrid, 15 seconds, 0.7 MP and twelve steps. An image runtime had been
kept alive after unloading image models, using about 5 GB working set while
the video worker was active. Windows reported approximately 85 GB committed
against an 86 GB commit limit and about 9 GB pagefile usage.

Closing only the verified inactive image process, without interrupting the
video worker, raised available physical memory from approximately 4.6 GB to
8.6 GB and reduced committed bytes by about 10.4 GB. The video reached decode
and produced a valid MP4 container. This is evidence of avoided memory pressure,
not a claim of a measured per-step speedup from closing that process.

On-demand transitions now fully terminate image workers before local video,
including previously warmed image workers. Direct image-to-video switching
skips the unload/keep-warm roundtrip. Resident mode preserves selected models;
file-cache settings remain intact. A subsequent image request cold-starts its
runtime, trading image startup time for H3 memory headroom.

## Verification

Regression checks cover direct image-to-video shutdown, an already warmed
image worker, cache preservation, resident retention and the existing cancel/
reuse paths. Video logging now records each sampling interval and completion
parameters include sampling_seconds and step_seconds for advanced chat details.
Sampling itself, duration, resolution and default twelve steps are unchanged.

The full 220-test Python suite passes, as do the two JavaScript tests, UI build,
native-runtime origin check and compiler-free bootstrap checks. Existing video
lifetime tests also verify that timings reset per job and the progress protocol
remains intact. GPU performance and
standalone runtime verification from 0.13.3 remain documented in
[validation-v0.13.3.md](validation-v0.13.3.md).
