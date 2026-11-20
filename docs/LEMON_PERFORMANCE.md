# Temporary CPU-rendering performance profile

## v22 investigation (2026-11-20)

This section records measured results; the original v21 profile below is kept
for reproduction. v22 uses five CPUs and 30Hz notifications/copies, not the
single CPU and 15Hz described below. See `LEMON_SMP.md`.

- All five requested CPUs start and pass SGI1 verification. Actual frequency,
  per-core load and scheduler placement have not been measured.
- Across 59 five-second intervals with presentation calls, `present()` consumed
  7149ms out of 296036ms wall time (2.4%). This includes preemption and locking;
  it is not a CPU utilization measurement. The timer is rearmed after copying,
  so a copy does also delay the next notification. Nevertheless, copying alone
  cannot account for the low number of frames in these intervals. Idle screen
  intervals must not be interpreted as failed frames or used as a benchmark.
- Full-canvas surfaces are 1125x2436 BGRA (~11MB with 4608-byte row stride).
  The copy crops to the 1080x2340 panel; it does not reduce the userspace render
  canvas. Switching to native resolution would reduce pixel count by only
  7.8%, so it is not a likely order-of-magnitude fix.
- `exec bluetoothd` occurs 55 times and `exec fairplayd.H2` 56 times; there are
  381 xpcproxy executions. Similar retry activity predates SMP (v20: 52 and
  54 respectively). Counts cover different session lengths/activity and are
  not directly comparable rates. The extra process churn is confirmed; its
  CPU/I/O cost and exit reasons are not. Do not disable FairPlay blindly.
- Captured crashes: driverkitd once (SIGKILL), PosterBoard once (SIGTRAP),
  assetsd twice (SIGABRT, same backtrace). There is no captured kernel panic.
  Local cache symbols place PosterBoard frames near initial switcher setup /
  extension prewarming. Nearest local-symbol matches do not establish the
  exact failing instruction or assertion. These are userspace failures, not
  evidence that the framebuffer or SMP crashed.
- Touch reads run every 20ms plus transfer/scheduling time; the vendor driver
  instead reads in a threaded IRQ handler. v22 logs 21 stale-contact releases
  after 100ms without a valid sample (v20 had 9, v21 had 5). This mechanism can
  split a gesture, but current logs cannot tell whether each release occurred
  during motion or after a real finger-up whose report was missed.
  `first=00:00` describes only two bytes, not an all-zero packet; error22 may
  be checksum failure or invalid contact IDs. No SPI worker-stop is logged.

Next bounded test: distinguish invalid packet reasons and count valid reports,
transfer time and scheduling gaps per interval; sample backboardd/SpringBoard
work and daemon exit reasons. Keep checksum validation and the 100ms release
limit. Temporary UI candidates are Reduce Motion/Transparency; verify the
installed preference schema before changing it. Avoid arbitrary clock writes,
blindly extending contact grace, or enabling eight CPUs as an assumed cure.

## Original v21 profile

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
