# H3-Chat 0.14.0 validation

Full Python Manim uses Community 0.21.0 and the existing pinned private wheels;
TinyTeX 2026.10 and dvisvgm 3.6 are optional hash-locked downloads. Their setup
runs inside the app directory without system installation. The dvisvgm addon
was matched byte-for-byte to the CTAN Windows package and its published SHA-512.
The public addon download was independently verified against the runtime manifest.

Synthetic real CPU/Cairo rendering exercised ThreeDScene, camera rotation,
Sphere, animation, Text, ImageMobject and actual MathTex/LaTeX compilation. Private
file read/write and networking were denied. A separate real three-dimensional
scene produced exactly 30.0 seconds (150 frames at 5 fps). GPU/OpenGL also
rendered a real 3D scene successfully on RTX 5070 Ti.

AppContainer keeps a unique SID per job; only runtime libraries and copied
assets are accessible. The renderer receives only NUL/log handles and inherits
a Job Object with a memory cap, child-process cap and kill-on-close. Killing a
broker after a scene spawned a Python descendant stopped both descendants;
parent cleanup removed the job folder, ACLs and temporary drive alias. TeX Live
requires an app-folder-only temporary Windows drive alias for its legacy name
lookup; it is removed after rendering/cancellation and grants no new file rights.
No volume-root permissions or GLOBALROOT PATH changes are used.

Regression tests cover Python/3D syntax, helper classes, selected scene names,
legacy JSON, prompt duration, 10s→30s correction, unchanged preset defaults,
manual-code errors with preserved source and canvas-only delivery. The existing
PDF→Manim flow now validates Python scene output. Video requests have a distinct
1–15s limit and explicitly reject 30s rather than using an old 10s preset.

The full 228 Python tests and two JavaScript tests pass. Optional full rendering
and isolation/cancellation checks run in the Windows release workflow. The UI
build and compiler-free bootstrap manifest were refreshed. Real LLM output is
still model-dependent; correction is bounded to two attempts and a configured
time limit. Cairo supports 3D; OpenGL availability depends on installed drivers.
