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

### v37 first CP/SQE checkpoint (patch0039)

Opt-in `lemongpu=7` extends the existing power and owned-memory gates with a
bounded A610 command-processor test. A private ADT node supplies the stock
`a630_sqe.fw` and A610 chip ID; firmware is not committed. The private local
builder validates its exact identity before embedding it in the boot payload.

The test allocates 76KiB, maps SQE/ring read-only and marker/shadow read-write,
and leaves guard/table pages unmapped. It attaches only user SID0/1 to the
owned context, rejecting overlapping routes. ME_INIT precedes a fixed
NOP/scratch/MEM_WRITE/WAIT_IDLE sequence. Success requires completed ring
consumption, the actual GPU-written marker, matching scratch and no faults.
Execution and cleanup results are logged separately. Buffers remain allocated
until reboot, including on failure; cleanup removes only the owned route and
disables the context only after confirmed halt and detachment.

The actual module passed an independent PM4/PTE host model with 32 fault
cases under ASan/UBSan and an ARMv8.0 compile. The 60 memory cases and outer
power/memory/CP gates also pass. These are software tests, not hardware proof.
Core setup is deliberately a minimal A610 CP subset. No ZAP/PAS, secure-mode
switch, graphics/HWCG/UBWC setup, framebuffer access or GPU user client is
introduced. This checkpoint does not accelerate the iOS interface.
Register/packet references: Linux
[A6xx implementation](https://github.com/torvalds/linux/blob/master/drivers/gpu/drm/msm/adreno/a6xx_gpu.c),
[A610 catalog](https://github.com/torvalds/linux/blob/master/drivers/gpu/drm/msm/adreno/a6xx_catalog.c),
[register definitions](https://github.com/torvalds/linux/blob/master/drivers/gpu/drm/msm/registers/adreno/a6xx.xml).

### v36 FSR field correction (patch0038)

Hardware v36 passed the preparation checkpoint: `prepared=1 owned=1`,20KiB
retained, all configuration readbacks match, FSR400/Format2/faults0/unknown0,
GFSR0, SCTLR.M=0 and no translating GPU stream attached. This proves disabled
context/table preparation only; hardware translation, GPU DMA and rendering
have not been exercised. The phone was then returned to TWRP.

v35 hardware confirms all register readbacks and unchanged SCTLR, but reports
FSR=0x400, GFSR=0. The actual blocker was our full-register zero test: FSR bits
10:9 are Format, and value2 identifies AArch64. No fault bits were set.
Patch0038 separates Format0x600 from fault mask0xc00001fe; unknown remaining
status bits still reject the operation. Snapshots and final/cleanup checks
accept Format-only status. Cleanup writes only owned W1C fault bits, never
the read-only Format field. Logs show raw FSR, decoded format, faults and
unknown bits separately. Existing SCTLR/routing/global-fault gates remain.
Actual-module60-case ASan/UBSan tests and ARMv8.0 compilation pass, with the
model now deriving read-only Format from the programmed context format.
This reproduces v35's0x400 and tests genuine/unknown/unclearable faults too.
Sources: [Linux FSR masks](https://github.com/torvalds/linux/blob/master/drivers/iommu/arm/arm-smmu/arm-smmu.h),
[ARM SMMUv2 FSR definition](https://documentation-service.arm.com/static/5f900d34f86e16515cdc08fb).
Hardware preparation verification of patch0038 passed; no GPU DMA is proven.

### v35 final-state check (patch0037)

v34 hardware matched every programmed register, but failed the final state
guard without printing its current SCTLR/FSR. The exact hardware cause remains
unconfirmed. The guard incorrectly required full raw SCTLR equality even
across the unsupported TYPE0 -> Stage1 change.

For reset-bank preparation only, patch0037 requires SCTLR.M=0 rather than
equality of fields interpreted under different formats. Existing supported
Stage1 contexts keep the strict full-SCTLR requirement. Routing, register
readbacks and local fault checks remain; global faults now also block success
and cleanup without being cleared. Configured/cleanup-begin/cleanup-end logs
always include initial/current SCTLR, FSR/GFSR, CBAR/CBA2R and the guard verdict.
No new SCTLR writes, routing or GPU commands are introduced.

Actual-module56-case ASan/UBSan tests and ARMv8.0 compilation pass, including
a reset-bank non-M change, active M rejection, local/global faults, a supported
Stage1 non-M mismatch, and safe cleanup after a failed write with changed
reset-format bits. This fixes a guard contract, not evidence of GPU DMA.

### v34 register contract (patch0036)

The grouped SMMU correction implements explicit TBI0/TBI1 for the test's
untagged32-bit IOVAs (TCR2=0x38070|OAS, SEP=upstream). Both TTBR regions
have explicit valid4K granules/32-bit sizes; TTBR1 walks remain disabled.
This also avoids sign extension at bit31 for future high32-bit IOVAs.
Every bit still has exact readback;
unexpected PASize/AS or other field changes remain failures, not masked errors.
Every register operation prints requested/returned values.

Snapshot interpretation now starts with CBAR.TYPE, then CBA2R and TCR.EAE.
For an existing Stage1 context, short descriptors use32-bit TTBR accesses;
AArch32 long/AArch64 use64-bit accesses. Only attempted writes are restored,
with format/control restored before table words. Failed control restoration
prevents table writes under the wrong interpretation and retains the allocation.

Important qualification to the earlier audit: CBAR.TYPE0 denotes Stage2, not
Stage1 short descriptors. Stage2 has no TTBR1, CONTEXTIDR, TCR2 or MAIRs and
always uses long descriptors. Therefore the actual initial TYPE0/no-S2 bank
is not a valid context to snapshot as either Stage1 format. Patch0036 reads
only common control/fault/ownership state there; it does not read or restore
the undefined Stage1 registers seen in earlier logs.

Only the exact disabled/unrouted CBAR0/CBA2R0/no-S2/no-ATS case is claimable.
After stable repeated snapshots and successful complete register programming,
the20KiB table/buffer allocation is intentionally retained with a new disabled,
unrouted Stage1 context for this boot. It logs `prepared=1 owned=1 translated=0`.
No SCTLR write, stream attachment, ATS/TLB operation, GPU DMA or service is added.
Re-entry stops before any MMIO. This is ownership/preparation, not restoration
of the initial unsupported TYPE0 or hardware translation success.

Failure never attempts the known-invalid TYPE0 rollback. If pointers were
attempted, clear both under confirmed Stage1/64-bit format before freeing;
otherwise the allocation has never been installed. Fault clearing, unchanged
disabled SCTLR and no routed stream must also be verified. Uncertain cleanup
retains memory and reports failure, rather than claiming exact restoration.
An existing supported Stage1 context follows the reversible test path instead.

Actual-module ASan/UBSan tests cover50 alternate cases, including the observed
TBI normalization/type0 restriction, no reads of undefined Stage2 registers,
short/long/AArch64 widths and restore order, rejected critical/control/table
writes, fault clearing, stream ownership changes, intentional ownership,
duplicate entry and retention on unsafe cleanup. ARMv8.0 module compilation
passes. Full macOS build and real hardware results remain pending.
References: [ARM SMMUv2](https://documentation-service.arm.com/static/5f900d34f86e16515cdc08fb)
(16.5.39/40,17.1/2),
[Qualcomm register programming](https://github.com/MiCode/Xiaomi_Kernel_OpenSource/blob/lime-q-oss/drivers/iommu/arm-smmu.c).

### End-to-end preflight after v33 (2026-11-21)

This is a source/ABI/asset review, not a hardware acceleration result. No new
kernel was built or flashed for this review. Remaining stages are dependencies,
not a promise that each will work on its first hardware run.

| Stage | Evidence now | Known work before it can pass |
| --- | --- | --- |
| Power/clocks | v30-v33 RPM ACKs and stage5 readbacks | Diagnostic retains votes; runtime idle/resume and recovery need a power manager. Nominal320/200MHz is not a frequency measurement. |
| SMMU configuration | v33 stable disabled bank0, buffer and software tables | Resolve TCR2 TBI policy, format-aware register snapshots and ordered restoration; CBAR restoration still fails. Do not route GPU streams yet. |
| GPU-visible memory | Private20KiB table model only | Implement real mappings, free SID/SMR selection without overlap, ASID/TLB lifecycle, fault reporting, cache ownership and allocation lifetime. |
| Firmware/security | Local stock SQE and A610 ZAP hashes verified | Implement metadata/segment loader, relocation/allocation and Qualcomm PAS13 authentication with bounded error handling. File presence is not an authenticated/started GPU. |
| A610 CP/ring | Primary Linux A610 path identified; no local implementation | Port wrapper/core initialization, A610 register values, SQE/ring setup, GPU progress and fence handling. Pixel3 A630 GMU/HFI setup is unsuitable. |
| Kernel/userspace ABI | Actual bridge/fake-backend tests pass | Implement LemonGPU service/user client: BOs/maps/imports, submit, queues, real waits and fence-delayed release. Keep service absent until hardware submission works. |
| Mesa/EAGL build | Existing archive URL responds200; source scripts imported | Build actual iOS arm64 dylibs, validate imports/signing/exports; provide Xcode/Python paths for Intel CI. No Mesa/EAGL Mach-O artifacts have been built here. |
| Display integration | Five hook targets match the prepared iOS cache | Implement writable SweetSurface imports, page pinning, exact row stride/format, GPU-to-CPU visibility and real presentation; test safe hook/loading behavior on this kernel. |

**Immediate SMMU issues found together:**

- TCR2 readback0x71 vs requested0x11 differs in TBI0/TBI1 (bits5/6), which
  have defined address-tag semantics. This is not permission-denied evidence
  and must not be handled by blindly ignoring every differing bit. Establish
  an explicit untagged32-bit-IOVA policy and writable/read-as behavior first.
- Original CBA2R.VA64=0 means the saved context is not AArch64. TTBR access
  width also depends on its original TCR.EAE: short descriptors use32-bit
  accesses. The current unconditional64-bit snapshots/restores are not a
  valid general save/restore contract. UNKNOWN reset fields are not evidence
  that an inactive bank is in use.
- Cleanup currently restores TTBRs before TCR/TCR2 and format state. Restore
  the original interpretation/control before restoring its table registers,
  keeping translation disabled throughout. Only restore fields actually
  modified, with register-specific verification.
- CBAR failed to return from0x1f300 to its initial0. The current test must
  continue to report cleanup failure. Type0 has stage2 semantics, while this
  device advertises no S2 translation; that is a lead, not a proven explanation
  for the failed write. Do not label an acceptable post-test state as an exact
  restoration. A persistent owned context needs an explicit lifecycle instead.
- Extend the MMIO model beyond ordinary read/write arrays: TBI readback,
  rejected CBAR-type restoration, short/long/AArch64 register widths and
  ordering. Existing36-case tests did not model these hardware behaviors.

Reference: [ARM SMMUv2 register definitions](https://documentation-service.arm.com/static/5f900d34f86e16515cdc08fb)
(sections16.5.39/40 and CBAR),
[Qualcomm context write order](https://github.com/MiCode/Xiaomi_Kernel_OpenSource/blob/lime-q-oss/drivers/iommu/arm-smmu.c)
(`arm_smmu_write_context_bank`).

**Constraints for the subsequent implementation:**

- A610 chip06010000 uses132KiB GMEM, a GMU-wrapper path, `a630_sqe.fw`
  and `a610_zap.mdt`; its4GiB quirk concerns GPU virtual addresses, not a ban
  on physical pages above4GiB. Preserve full physical addresses. The current
  user VA window80000000..ffffffff also needs separate non-overlapping BO
  and imported-page ranges. Do not reuse A630 GMEM/clock fixtures as hardware
  capabilities. Linux also selects A610-specific HWCG/GBIF/core values.
- Local ZAP ELF's loadable segment has Qualcomm relocatable flag and PA5000;
  that is not permission to copy firmware to physical address5000. Use the
  authenticated loader's relocation/allocation rules. No A630 GMU firmware
  or HFI channel is required by the identified A610 wrapper path.
- First CP success must be an observed GPU-written scratch/memory marker
  and an actual completion, with an intentional fault/timeout path. The fake
  backend retires work synthetically and cannot validate DMA or pixels.
- CPU writeback/GPU reads and GPU writes/CPU reads need opposite cache
  maintenance, barriers and fences. A pre-submit clean alone is insufficient.
  Do not release imported pages or tables while the GPU can still reference
  them. Raw user pointers need validation and pinned page lists; pass neither
  arbitrary physical addresses nor unbounded commands through the user client.
- The existing SweetSurface implementation is the integration target, not
  the donor's later surface patches. Preserve its stride, offsets, ownership
  and presentation path. Set ABI capabilities from the actual implementation;
  do not advertise unimplemented fences, per-process tables or zero-copy.
- Mesa scripts default to an Apple-silicon Homebrew Python path and old Xcode
  path. CI must supply actual paths. HOST=1 builds/runs macOS arm64 binaries
  and cannot run those binaries on the current macos-15-intel runner.
- Five matching vtable targets do not prove VM_PROT_COPY permissions, loader
  injection, IOSurface coherence, GL completeness or correct presentation.
  Keep the software path available until standalone GPU pixel tests pass.

Sources: [A610 catalog](https://github.com/torvalds/linux/blob/master/drivers/gpu/drm/msm/adreno/a6xx_catalog.c),
[CP/core init and ZAP sequencing](https://github.com/torvalds/linux/blob/master/drivers/gpu/drm/msm/adreno/a6xx_gpu.c),
[Qualcomm loader](https://github.com/torvalds/linux/blob/master/drivers/soc/qcom/mdt_loader.c).

**Batching plan:** prepare the complete SMMU register contract and cleanup
model before another run. In one guarded test collect all relevant original,
requested and returned fields, so a mismatch is diagnosable without rebuilding
just to print the next register. After memory ownership is proven, combine
dependent firmware/core/ring-marker checks behind explicit success gates.
Keep service/standalone GLES and then compositor activation as separate gates;
they cannot safely be declared successful by a register-only boot.

Rechecked actual DRM bridge/fake ABI, identity rejection,4K/16K allocation
rounding and ARMv8.0 cross-compilation: PASS. Local20H392 cache hook target
checks: PASS. Stock firmware manifest sizes/hashes: PASS. Mesa tarball HEAD
was200,91661844 bytes; archive was not downloaded for this review and its
contents/hash/build remain unverified. No real GPU command or pixels tested.

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
   with no translating stream attached. ATS testing still requires empty
   TTBRs/SCTLR; no-ATS register-only testing accepts stable saved values with
   SCTLR.M clear (patch0035). No other/secure banks or streams are modified.
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
Host ASan/UBSan tests use an independent page walker and36 alternate cases,
including stale mappings, ATS failure/bypass, cleanup failure and buffer retention;
mode6 gating and existing power tests also pass. Actual module cross-compiles
for ARMv8.0 with explicit-GPR MMIO stores (Qualcomm HYP zero-register workaround).
v31 full XNU build passed, but hardware stopped before context writes because
ID0=0x4c017e04 advertises ATOSNS. The no-ATS fallback also tests this exact
capability snapshot in the host model, forbidding context enable and unsupported
register accesses. v32 full XNU build passed; fallback stopped on the nonzero
bank state described below.
References: [SMMUv2 definitions](https://github.com/torvalds/linux/blob/master/drivers/iommu/arm/arm-smmu/arm-smmu.h),
[context programming](https://github.com/torvalds/linux/blob/master/drivers/iommu/arm/arm-smmu/arm-smmu.c),
[Adreno user bank0](https://github.com/torvalds/linux/blob/master/drivers/iommu/arm/arm-smmu/arm-smmu-qcom.c).

v32 built and reached bank0: SCTLR=0x14136108 (M=0), FSR=0, CBAR/CBA2R=0,
TTBR0=0x2c087de51242b820, TTBR1=0x110910d908433320. Nonzero values alone do
not prove a live mapping. Live recovery FDT has `qcom,skip-init`, but not
`qcom,enable-static-cb`; the downstream driver skips bank reset and reserves
inherited banks based on valid translating SMR/S2CR entries. Its CB base is
resource base + size/2, matching our 0x59a8000. Secure restore is conditional
on static/slave-side-secure domains, so this evidence does not justify adding
an SCM call. Recovery has arm-smmu bound and separate user/secure IOMMU groups;
no debugfs or /dev/mem register-read interface is available there.

Patch0035 checks bank state three times and rejects unstable snapshots,
active translation, faults, unknown ownership fields or routed streams.
On no-ATS hardware SCTLR is never written, including during cleanup; original
TTBRs and all saved configuration are restored and checked before freeing.
This remains a disabled-context register/table test, not hardware translation.
The host model includes exact v32 register values, active/routed/unstable
refusal and failure to restore the original nonzero TTBR. Full macOS build
and hardware result for patch0035 are pending.
Source: [Xiaomi Qualcomm SMMU driver](https://github.com/MiCode/Xiaomi_Kernel_OpenSource/blob/lime-q-oss/drivers/iommu/arm-smmu.c)
(`arm_smmu_device_reset`, `arm_smmu_handoff_cbs`, `arm_smmu_alloc_cb`,
`arm_smmu_restore_sec_cfg`, `arm_smmu_device_probe`).

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
