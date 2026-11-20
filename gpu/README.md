# Redmi 9T GPU port: Pixel 3 userspace foundation

Imported from [andyleenz/pixel3-ios](https://github.com/andyleenz/pixel3-ios),
commit `737278ac173883599cfade65627e69b0376083a6`. Original MIT and HakiOS notices
are retained under `pixel3/`. Donor READMEs describe the Pixel 3, not a working
Redmi installation. No Apple binaries, Mesa archive or GPU firmware is included.

The reused path is CoreAnimation -> EAGL shim -> Mesa Freedreno -> IOKit GPU
user client. It does not require Metal or Vulkan. Only userspace was imported;
no Pixel 3 kernel, clock, regulator, SMMU or GMU initialization was copied.

## Lemon adaptations

- The service is `LemonGPU`; the DRM/msm struct layout and selectors stay as in
  the donor. Its old `BLUE_GPU_*` C names are retained to minimize changes.
- Before hooking CoreAnimation, the EAGL loader requires GPU610,
  chip`0x06010000`, GMEM`0x21000`. Missing/incompatible service leaves it off.
  A future kernel must publish this service only once submission is functional.
  `BLUEEAGL_FORCE` remains a donor test override, not a phone activation setting.
- Anonymous BO fallback uses the actual host page size instead of hardcoded
  16KiB rounding, with zero/overflow checks. This supports our 4KiB kernel.
- Build scripts specify Cortex-A53 / ARMv8.0+crypto and no outline atomics.
- The **fake** GPU returns A610 identity/GMEM/bank-bit fixtures. Its synthetic
  clock, VA pool and immediately retired fences are not hardware settings or
  evidence of working GPU execution. It does not render pixels.

## Checks performed

On Linux/WSL (native C compiler, ASan/UBSan), against Linux's DRM UAPI headers:

```sh
python3 tools/test-lemon-gpu.py --linux /path/to/linux
```

Compiles the actual imported DRM bridge and fake IOKit backend, checks their
ABI against Linux, and exercises BO map/close, command submission, fences and
stale handles. Separately executes the actual EAGL identity gate and the actual
BO rounding code for4KiB/16KiB, malformed responses and overflow.
If the AArch64 Linux cross-compiler is installed, the same transport/model and
gate also compile for Cortex-A53 ARMv8.0. That is not an Apple Mach-O build.

Against a local, already prepared iOS cache (read-only):

```sh
python3 tools/check-lemon-gpu-cache.py /path/to/cache-directory
```

All five donor CoreAnimation vtable targets match our iOS16.7.16/20H392 cache
after decoding slide-info2. This confirms address compatibility, not complete
runtime compatibility, rendering correctness or performance.

## What remains before a phone test

Port patch0025 prepares a default-off first kernel checkpoint. `lemongpu=1`
starts a separate snapshot thread after persistent logging is available. It
reads GCC GPU config clocks and, only when both parent paths are clearly on,
the GPUCC power/clock status. It does not access GPU core/SMMU registers or
write hardware registers, load firmware or publish `LemonGPU`. This is a
bring-up diagnostic, not GPU initialization or acceleration. Its actual code
is covered by `tools/test-lemon-gpu-probe.py --xnu PATCHED_XNU` (gated paths,
mapping failures, single start, default off, ARMv8.0 compile). A full XNU build
and a hardware run remain pending.

Patch0026 adds opt-in `lemongpu=2`: synchronously before input workers, require
CFG_AHB already running, set only GCC7900c bit4 (QMIP GPU configuration vote),
verify vote and CLK_OFF for at most200us, then take the guarded snapshot.
On timeout clear only a vote acquired by this code; preserve other bits.
Success retains the config vote. GPU power domains, MEMNOC/SNOC, PLLs,
GPU core/SMMU and firmware remain untouched. This enables register access
only, not rendering. Ordering avoids racing the touch worker's shared vote.
Linux references: [SM6115 GCC](https://github.com/torvalds/linux/blob/master/drivers/clk/qcom/gcc-sm6115.c),
[branch polling](https://github.com/torvalds/linux/blob/master/drivers/clk/qcom/clk-branch.c).

The installed XNU has no `LemonGPU` implementation. GPU initialization, address
translation, memory ownership, command submission/fences, fault handling and
IOSurface sharing must be implemented for A610. Pixel 3's A630 GMU/HFI sequence
is not applicable to A610's GMU-wrapper hardware.

This phone's saved live FDT confirms GPU`0x05900000` (region`0x90000`),
GPUCC`0x05990000`, SMMU`0x059a0000`, chip`0x06010000`, highest bank bit14.
Local Linux `a6xx_catalog.c` confirms132KiB GMEM and the4GiB-VA quirk.
These are source/device-tree facts, not permission to touch unclocked registers.

Read-only TWRP sysfs confirms `Adreno610v1`. Required `a610_zap` components and
`a630_sqe.fw` were found in the earlier personal vendor-firmware extraction;
sizes, hashes and ELF/MDT segment consistency were checked and saved privately
under ignored `research/lemon-gpu-firmware/`. They were not uploaded to GPU RAM.

The complete Mesa/EAGL iOS build still needs macOS/Xcode. It has not been run
here. Before installation, validate its imports and ARMv8.0 instructions, sign
for the4KiB target, and check the actual signature page size and mapping bounds.
No workflow, boot change, library injection or firmware loading is performed
by these host checks. Existing v23 remains unchanged.
