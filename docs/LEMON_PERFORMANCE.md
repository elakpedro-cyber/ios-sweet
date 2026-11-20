# Temporary CPU-rendering performance profile

v20 reaches the iOS home screen with working touch, but the user reports severe
lag. There is no measured baseline frame rate yet. This profile reduces work
and memory pressure without a GPU/Metal driver or userspace-file modification.

- Keep the physical panel and logical1125x2436 canvas, formats and touch mapping.
- Set `sweetfb_vsync_hz=15 sweetfb_hz=15`: notify CoreAnimation once per intended
  software presentation instead of sending60notifications while copying at15Hz.
  Existing profiles retain their60Hz notifications by default.
- Set `sweetsample=- sweetnull=-` explicitly. Omitting these arguments would
  enable default process stack sampling and SpringBoard/backboardd stderr tee.
- Expose766MiB usable RAM instead of510, preserving physical base0x100000000.
  Total768MiB includes a2MiB panic buffer at0x12fe00000. End0x130000000 stays
  within live System RAM and below observed reservations starting0x13b546000.
  The loader accepts only the original and this exact larger profile. Do not
  move the physical base or expose the whole upper bank without rechecking it.
- Retain the working v20 touch implementation, root, recovery, CPU count1 and
  existing clocks. No CPU/DDR voltage or GPU registers are changed.

`sweetfb_stats=1` adds one short `LEMON PERF` line per at-least5s active interval:
vsync notifications, presentation calls, elapsed milliseconds and time spent
inside presentation. `frames *1000/elapsed_ms` estimates presented frames/s.
`present_ms` is wall time, including preemption/locking; it is not a CPU profiler.
Display-off intervals reset the counters. This helps separate kernel copying
from userspace rendering on the next test; it does not establish a speedup yet.

Host validation: `tools/test-lemon-perf.py --xnu <patched-source>` tests actual
pacing/stats code, preserves default timing, checks exact loader profiles, and
proves the ADT changes only RAM size and panic-buffer address. With
`--iomem <recovery-dump>` it also checks the entire selected physical interval
against live RAM and every listed reserved range. Device dumps stay ignored.

Local loader build: `bash shim/build-lemon-boot.sh out/lemon-perf`. It preserves
the old loader outputs. The real-product ADT is cloned from the working v20
assets; Apple identity files and generated boot images are not committed.
Framebuffer patch0022 is built in GitHub Actions; packaging helper is the ignored
`research/build_perf_boot.py`. Before installation, verify the artifact checksum,
boot layout, staged image and protected partitions. Obtain boot-write approval.

Practical limits remain: one CPU and CPU-only graphics. Lower notification rate
and more RAM may help responsiveness, but15Hz is a cap rather than a guaranteed
frame rate. Measure and test the resulting image before calling it improved.
