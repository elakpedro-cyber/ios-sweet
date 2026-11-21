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

v25 hardware verified the config vote and GPUCC reads; CX/GX remain collapsed.
Before powering them, SM6115 needs RPM-SMD voltage votes transported by RPM
GLINK, not the SM7150 RPMh implementation. Patch0027 adds `lemongpu=3`:
retain mode2 config setup, then inspect RPM message RAM0x045f0000/0x7000.
The read-only parser validates TOC, pipe bounds/overlap and indices, and logs
up to64 pending bytes per direction without opening a channel or advancing
pointers. It makes no voltage or CX/GX requests. This is a prerequisite
diagnostic; it does not enable GPU power or rendering.

v26 verified the RPM TOC and empty zeroed FIFO pointers on hardware.
Patch0028 adds opt-in `lemongpu=4`: negotiate version1/features0, send OPEN
for `rpm_requests` (local channel1), validate remote OPEN and matching local
OPEN_ACK, then acknowledge the remote channel. A single bounded poll loop
allows at most5 seconds. Only fresh zeroed FIFOs are accepted; no resets or
stale queue adoption. Writes are limited to TX data/head, RX tail and APCS
mailbox0 BIT0 at0x0f111008. No RPM data/voltage requests are sent. Success means
the OPEN handshake completed, not that voltage control or GPU power works.
The peer model tests both OPEN orders, wrong version/channel/name, timeout,
partial frames, full/wrapped FIFOs, mapping failures and the write whitelist.
See [GLINK protocol](https://github.com/torvalds/linux/blob/master/drivers/rpmsg/qcom_glink_native.c)
and [SM6115 mailbox](https://github.com/torvalds/linux/blob/master/drivers/mailbox/qcom-apcs-ipc-mailbox.c).

v27 hardware negotiated version1/features0 and received the remote OPEN for
`rpm_requests` with remote channel2, but exited with result0 before completing
the handshake. The rejected header was not logged, so its exact cause is
unknown. Patch0029 removes the extra OPEN_ACK param2==0 requirement (Linux
matches the local channel ID only), retaining the local ID and state checks.
It logs rejected RX headers and TX space/index errors. Host tests reproduce
the old rejection with nonzero OPEN_ACK param2 and pass after the fix in both
OPEN/ACK orders. Hardware verification remains pending; no rail requests.

Patches0030/0031 combine the next bring-up in one opt-in `lemongpu=5` boot:

1. Reuse checked configuration clocks and negotiate GLINK. Consume bounded,
   valid OPENs for other channels without binding/acknowledging them; log names,
   continue for multiple channels. Keep strict matching for `rpm_requests`.
2. Send four sequential ACTIVE RPM-SMD KVP requests: MX floor256, CX floor128,
   MX enable1, CX enable1. These are corner enums, not microvolts. Normal `vlvl`
   and SLEEP requests remain unchanged. Each request needs a matching `msg#`
   ACK with no `err`; malformed/mismatched/fragmented ACK or timeout stops.
3. Only after all four ACKs: validate configuration access and retained shared
   GPLL0 at600MHz, require cold GX/disabled consumers, power CX then GX using
   SM6115's documented reset/clamp sequence. Poll CX via hardware status1540,
   GX via100c (the old GDSCR-only snapshot was insufficient for CX status).
4. Configure dedicated GPU PLL1 at640MHz only if off. A running PLL must
   already match; unknown FSM/rate is rejected. Program core320MHz/GMU200MHz
   roots and enable GPU/bus branches with bounded readbacks. Shared PLLs are
   never retuned. The frequencies are inferred from configuration, not measured.

No core/SMMU/firmware/command submission or drawing is attempted. Each stage
logs progress and final register status. A failure retains the reached power
state and acknowledged floors rather than dropping voltage below an enabled
domain. Recovery must reinitialize power afterwards; clearing retained RPM
votes across a reboot has not been verified. This is a short boot diagnostic,
not a runtime power manager.
GLINK/RPM replies are restricted to single-frame ACKs up to256 bytes; unsupported
reply forms stop the sequence. Actual voltage, domain and clock results remain
unverified until the combined boot is tested on the phone.

Host ASan/UBSan peer tests cover multiple extra channels, good/error/stale ACKs,
partial requests/timeouts and stop-before-power gating. Separate actual-module
MMIO tests check power order, register masks, rate readback, status failures,
unknown retained states and absence of shared PLL/core/SMMU writes.
References: [RPM wire format](https://github.com/torvalds/linux/blob/master/drivers/soc/qcom/smd-rpm.c),
[corner votes](https://github.com/torvalds/linux/blob/master/drivers/pmdomain/qcom/rpmpd.c),
[SM6115 clocks](https://github.com/torvalds/linux/blob/master/drivers/clk/qcom/gpucc-sm6115.c),
[power domain sequence](https://github.com/torvalds/linux/blob/master/drivers/clk/qcom/gdsc.c).

v29 hardware confirmed the GLINK endpoint, all four RPM ACKs and CX/GX ON.
It stopped when optional GPUCC CX_SNOC_DVM108c read back0 after an enable
request. Xiaomi's lime-q-oss driver labels this branch HALT_DELAY; its enable
path waits10us and does not require an enable-bit readback. The live phone's
GPU/SMMU clock consumer lists do not request this branch or GPUCC CX_GFX3D10a4;
they use the separate GCC SNOC36018 for SMMU interfacing. Patch0032 therefore
leaves both optional GPUCC branches unchanged, logs them, and retains the
required GCC bus, GMU1098 and GX_GFX3D1054 clock checks. It does not conclude
that108c is broken or that readback0 means a stopped clock.

The MMIO model now uses the observed108c=0 and forbids writes to both optional
branches, while requiring the final clocks to succeed and testing that a stuck
required GMU still stops. No hardware result for this fix yet. Full memory/SMMU
setup is not included: the live qsmmu-v500 node has skip-init/dynamic properties,
and its inherited stream/context ownership has not been inspected on XNU.
References: [Xiaomi clocks](https://github.com/MiCode/Xiaomi_Kernel_OpenSource/blob/lime-q-oss/drivers/clk/qcom/gpucc-bengal.c),
[Xiaomi branch policy](https://github.com/MiCode/Xiaomi_Kernel_OpenSource/blob/lime-q-oss/drivers/clk/qcom/clk-branch.c).

v30 hardware reached power stage5: required GPU/GMU clocks enabled, RPM ACKs
and CX/GX ON verified. Patch0033 adds one combined memory test, `lemongpu=6`:

1. Complete the existing RPM/power/clock sequence first; otherwise no memory
   probe runs. Verify CX, AHB/GCC buses and enable/read back SMMU HLOS vote5000.
2. Inspect only non-secure globals and known GPU-user bank0. Require SMMUv2,
   4KiB layout, stage1 support, supported OAS and an idle, unrouted bank0
   with empty TTBRs. No other/secure banks or inherited streams are modified.
3. Allocate20KiB contiguous kernel memory, verify physical contiguity/address
   width, construct three4KiB table pages and map two private data pages at
   IOVA0x20000000. Clean CPU caches before table walking. No GPU stream is
   attached to the test context and no DMA is submitted.
4. Validate both mappings and the unmapped following page with a bounded
   software table walk. Save bank configuration, verify register writability
   and program AArch64 stage1 registers. If ATS is available, enable the
   context, synchronize its TLB and test those addresses using ATS1PR.
   Patch0034 handles ATOSNS=1 by keeping the context disabled: only software
   tables and configuration readback are tested. No ATS/PAR/ATSR or TLB
   operations occur on this path; it does not prove hardware translation.
5. Disable/drain and restore the context, clear only test-owned bank faults,
   and free memory only after restoration is verified. On uncertain disable,
   ATS/TLB timeout or restoration, retain the allocation and log it. No global
   reset, SMR/S2CR routing, other banks or secure state writes are performed.

This mode stops on unknown/occupied/protected state; it does not take over an
existing mapping. Unsupported/fragmented capabilities are not treated as test
success. As before, clock/rail votes are retained for recovery reinitialization.
Host ASan/UBSan tests use an independent page walker and31 alternate cases,
including stale mappings, ATS failure/bypass, cleanup failure and buffer retention;
mode6 gating and existing power tests also pass. Actual module cross-compiles
for ARMv8.0 with explicit-GPR MMIO stores (Qualcomm HYP zero-register workaround).
v31 full XNU build passed, but hardware stopped before context writes because
ID0=0x4c017e04 advertises ATOSNS. The no-ATS fallback also tests this exact
capability snapshot in the host model, forbidding context enable and unsupported
register accesses. Patch0034 full XNU build/hardware readback remain pending.
References: [SMMUv2 definitions](https://github.com/torvalds/linux/blob/master/drivers/iommu/arm/arm-smmu/arm-smmu.h),
[context programming](https://github.com/torvalds/linux/blob/master/drivers/iommu/arm/arm-smmu/arm-smmu.c),
[Adreno user bank0](https://github.com/torvalds/linux/blob/master/drivers/iommu/arm/arm-smmu/arm-smmu-qcom.c).

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
