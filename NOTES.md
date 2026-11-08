# iOS 16 on sweet (Redmi Note 10 Pro, SM7150) - working notes

## Local Redmi 9T NFC port handoff (2026-11-07)

### ACTIVE PHYSICAL TEST: boot replaced; restoration REQUIRED (2026-11-08)

User explicitly approved temporary write ONLY boot and restoration after test.
Pre-write live boot/recovery/dtbo and local 134217728-byte boot backup hashes
matched known good copies. Wrote 16977920 bytes of b3e70be6... image to boot
using TWRP dd bs=4096 conv=fsync, then sync. Read-back image-prefix SHA256
exactly matches b3e70be6ecabab6cd48be7aed8ce274483df096efcc9e83c1b5796a3be74998d.
Recovery/dtbo full hashes remain unchanged. Next reboot system and get screen
observation; the test has no USB. User must return with Power + Volume Up.
Then push backup/boot-current.img again (TWRP /tmp is volatile), verify its
hash and restore ALL 134217728 bytes ONLY boot; verify full boot/recovery/dtbo
hashes. Do not leave the temporary image installed after this test.

### Latest: physical test image prepared; waiting for boot-write approval (2026-11-08)

User asked to prepare the physical test. New lemon-boot.c only runs loader_boot
then halts; it links no UFS, old 16K MMU probes, PSCI/reset or SMP test code.
Loader validates source/destination/segment bounds and requires lemon RAM
0x100000000 + 0x1fe00000, with no loader/initrd overlap. Existing 16K boot_args
alignment is also valid for 4K and stays inside the reserved topOfKernelData.
build/package-lemon-boot.sh produce an experimental Android boot v2 image:
shim/out/lemon-boot/boot-lemon-xnu-test.img, 16977920 bytes, SHA256
b3e70be6ecabab6cd48be7aed8ce274483df096efcc9e83c1b5796a3be74998d.
Kernel is the verified 077246e3... combined kernel; phone ADT is --lemon
without --qemu, one CPU, test init on RAMDisk. Original previously booted DTB
is byte-identical. DTB load address moved from 31 to 48 MiB to avoid overlap
with the 16 MiB-offset payload. Image decompression/header/load-range checks PASS.
QEMU --shim now tests real start.S, FDT/initrd parsing and segment copies,
not just the direct payload entry. A53 55s run prints PID1 and four alive lines.
Evidence: /home/hadirpc/lemon-real-loader-a53/. Decoder has 4 unrelated old
unknown glyphs; exact PID1/alive lines decode completely.
Repository syntax: 81 base patches, 22 Python, 11 shell PASS.

Phone was in TWRP, 31% Charging. All three partition hashes matched backups.
adb reboot bootloader exposed missing Windows driver (PnP code 28). User
manually selected existing signed Google Android Bootloader Interface.
Fastboot reports unlocked=yes. fastboot boot sent the image successfully but
Booting FAILED (remote: 'unknown command'). No partition was written.
fastboot reboot recovery succeeded; ADB recovery is available again.
After return, full boot/recovery/dtbo hashes still match the recorded backups.
Local backup copies' full hashes also match. Image pushed to
/tmp/boot-lemon-xnu-test.img in TWRP and SHA256 verified. Boot size 134217728.
NEXT REQUIRES explicit approval for temporary write ONLY boot, as repo AGENTS
requires confirmation of each destructive step. Then verify image prefix and
unchanged recovery/dtbo before reboot. Test has no USB/ADB; user must return to
TWRP with buttons; restore ALL boot bytes from backup/boot-current.img and
verify full hash f5ee6f406dc2a923dae167b9d45287daa0cba3c051484ce6e03536894b6c868f.
Do not write recovery, dtbo, userdata or other partitions. Current state TWRP.

### Latest: full 4K XNU boots our PID1 on QEMU Cortex-A53 (2026-11-08)

CI 42449737397 SUCCESS, job 128636447719, 7m57s, source commit 280dd5e.
https://github.com/elakpedro-cyber/ios-sweet/actions/runs/42449737397
Build, baseline atomic assembly, RPC and ADT checks passed. Kernel in ignored
xnu/out-lemon-combined/kernel.development.sweet; SHA256 matches SHA256SUMS:
077246e379fa23634291be97f699b4f77ccf1c39e9faabf22eac7159298faaa9.
Full QEMU A53 boot, 55 seconds, unmodified combined kernel and normal lemon
QEMU ADT (kryo260, no diagnostic compatibility fallback or GDB overrides):
BSD root md0 -> /sbin/launchd -> our static sweet-init.S prints
"*** SWEET userspace: init running as PID 1 ***" and FOUR "still alive" lines.
This demonstrates 4K VM, CPU0/SGI/timer/scheduler, RAMDisk/mockfs, exec,
user/kernel transitions and console syscalls in QEMU; it is not iOS userland
or proof of operation on physical Redmi 9T. Hardware remains untouched.
Final whole-section disassembly has one apparent LSE opcode at 7b2c3b4,
inside SHA-256 K256 constants (symbol starts 7b2c2d0), not executable code.
The 12 real dependency LSE instructions are gone after Firehose A53 flags.
Framebuffer decoder reports 5 unknown glyphs in older overwritten lines and
returns incomplete_decode; the complete PID1 marker and all four alive lines
decode exactly. Do not describe decoder exit status as a clean automated pass.
WSL evidence: /home/hadirpc/lemon-qemu-combined-a53/{fb.txt,fb.png,regs.txt,
qemu.log,result.json}; copied to ignored research/qemu-combined-a53/.
Local PFZ, actual pmap reservation, 4K/16K constants, ADT/FDT and bootstrap
MMU tests passed. Changes committed/pushed on lemon-bringup without force.
Current milestone complete. Next is physical lemon loader/boot-image review
and hardware-specific bring-up; no phone write/reboot is authorized by this
QEMU milestone. Preserve TWRP, Android and all backups.

### Latest: minimal lemon board preparation (2026-11-08)

CI 42446940840 succeeded (job 128627753961, 8m16s), including RPC/ADT checks.
Kernel SHA256 eb0b9431afcbca75188c3d51ffede625e3fa42ac237dace7dc0651a8cb600f1d,
stored in ignored xnu/out-minimal-kernel/. Link VA now fffffff007004000.
Full-kernel QEMU A53 reaches arm_init, PE_init_platform, CPU bootstrap then
panics on LSE ldadd in lck_grp_reference. Explicit cortex-a53 compiler target
and an assembly check are added; -march alone did not exclude LSE in this build.
A76 diagnostic run passes that point and reaches VM bootstrap (123304 pages),
then kmem_range_init fails to place kmem_ptr_range. Patch 0006 logs claim sizes
and addresses to diagnose this next; it does not bypass the allocator.
Test PID1 is our own tools/sweet-init.S, packaged as a signed static Mach-O
using mkinit.build_code after GNU cross-linking, entirely in the RAM disk.
QEMU output uses /home/hadirpc/lemon-qemu-minimal-{a53,a76} in WSL because
QMP sockets cannot live on /mnt/c. No device commands or writes.
QEMU HMP inspection confirms the zones claim is 0x2000000000 (128 GiB) and
ptr_range_size has wrapped to 0x7ff4604e0000. zalloc.c uses the macOS 128 GiB
zone VA reservation even though lemon now uses the mobile 48 GiB heap window.
Patch 0007 selects the existing mobile 24 GiB zone VA / 8 GiB physical cap.
The physical cap remains further constrained to half sane_size by XNU.
Run 42447975067 passed the ARMv8 baseline atomic assembly check; next push
includes the concrete zone fix and supersedes its diagnostic-only build.
Run 42448044675 failed at two explicit CASA instructions in commpage_asm.s
(lines 276/326). Patch 0008 substitutes a bounded LDAXR/STXR trylock for
lemon; a lost exclusive reservation reports contention, as allowed by these
trylock helper contracts. No loop or general CAS emulation is introduced.
tools/test-lemon-pfz.py executes the actual helper bodies on QEMU Cortex-A53;
empty/two-element FIFO, both held-lock failures and release checks PASS.
Only function prologue/epilogue macros are replaced in this freestanding test.
Run 42448627969 (7daa382, job 128632844836) SUCCESS. Kernel SHA256
6d83ea7904c13bf0222332644c6e9cfb8f7d49c22f6c74dcc2529c83c06fb8d9,
stored in xnu/out-a53-kernel/. QEMU A53 now completes kmem/zone/VM bootstrap,
then panics on CAS in __firehose_buffer_tracepoint_reserve, PC fffffff007a687fc.
LSE scan finds 13 remaining instructions (previous kernel: 873), all still
requiring audit. Firehose is NOT a closed KDK binary: darwin-xnu-build builds
libdispatch/libfirehose_kernel separately with xcodebuild, without XNU CFLAGS.
Workflow now passes an arch=arm64 xcconfig to build that dependency for A53.
QEMU output: /home/hadirpc/lemon-qemu-a53-fixed/. No hardware activity.
A76 run bypassing LSE reveals a separate IOCPU match issue: ADT has kryo260,
but KernelConfigTables matches only kryo470. A temporary diagnostic ADT fallback
to kryo470 unblocks CPU0 processor_start, SGI1 verification and BSD initialization.
Patch 0009 fixes the personality conditionally for lemon, preserving the real
kryo260 ADT identity. Diagnostic fallback ADT stays ignored and is not a release
profile. Output /home/hadirpc/lemon-qemu-cpu-match-test/.
Longer matching-CPU A76 run reaches BSD, then pmap_ttne panics on attempted L2
demotion at fffffff00087e000 (FB PA block 5c600000). The alias spans lowglobals
+2 MiB through +12 MiB, but pmap_virtual_region reserves only the first 8 MiB.
Patch 0010 reserves MAX(existing, ARM_TT_L2_SIZE + LEMON_FB_MAP_BYTES).
Regression executes actual pmap_virtual_region body and checks whole alias
coverage. This is a real permanent VA reservation fix, not a pmap panic bypass.
Run 42449287530 was superseded/cancelled by combined fixes; current build
42449737397 targets commit 280dd5e. A temporary GDB diagnostic on the older
A76 binary returns the corrected 12 MiB region for pmap_virtual_region(2),
with the temporary CPU matching ADT, and reaches BSD root md0 and exec launchd.
This is diagnostic evidence only, not a boot of the final patched kernel.
It then repeatedly faults in copyin at user VA 0x1000004c0; A76 PSTATE has PAN
set while lemon is compiled without PAN support. This may be an A76-only test
artifact; verify on A53 before changing code. Output in WSL
/home/hadirpc/lemon-qemu-reservation-diagnostic/. No PID1 success claimed.
Bootstrap host test now uses the actual mobile final-map VA/root slot (448).

Found macOS CFLAGS still force ARM_LARGE_MEMORY and link at -2 TiB, outside
4K/39-bit bootstrap TTBR1. Optional patch 0005 selects the existing mobile
link addresses and -UARM_LARGE_MEMORY, moves final FB alias relative to
LOW_GLOBAL_BASE_ADDRESS, and blocks unported Sweet UFS/keys/touch/USB/SPMI/RPMh
entry points before MMIO. This is required before a full-kernel QEMU boot.
mkadt --lemon emits one CPU, no UFS, 510 MiB managed RAM + 2 MiB panic region
at 0x100000000..0x120000000, display 0x5c000000/1080x2340, lemon GIC or QEMU GIC.
Saved live FDT confirms this range is RAM and avoids fixed reservations and
all dynamically allocated pools (whose alloc-ranges are below 4 GiB).
QEMU tool --lemon uses matching framebuffer and reads Mach-O symbols directly,
so llvm-nm is no longer required. No native boot image or phone command here.
Next: complete CI, inspect linked VA, then minimal full-kernel QEMU on A53.

### Latest: RPC compatibility fix and full CI verified (2026-11-08)

Pushed commit `b515ae75dfa248dc6c08ee7761fcc8c760b15d6e` without force.
New run `42445948818`:
https://github.com/elakpedro-cyber/ios-sweet/actions/runs/42445948818
Run completed SUCCESS, job `128624793329`, in 6m37s. Build and the new
Verify RPC runtime compatibility step both succeeded. Log confirms all
lemon patches 0082-0085 applied and 1109 lines contain -DLEMON_4K.
Kernel downloaded to ignored `xnu/out-rpc-fixed/kernel.development.sweet`:
16278960 bytes, SHA256
`503bf1c2112e63b1b348ba7eddb45fb9745557493499e0e8b353846c37a72a44`.
Hash matches the artifact SHA256SUMS. Full log in ignored research/ci-rpc-fixed/run.log.

Continued Claude's work. Prior successful build confirmed remotely; no local
changes were discarded. Optional patch 0004 sets kernelContent in both manually
constructed RPC paths (incoming IPC and trap), and normalizes it from the
validated Mach payload in OSMetaClassBase::Invoke and IOUserServer::kernelDispatch.
The generated modern iig dispatcher otherwise dereferences null/stale content.
Regression test uses actual entry function bodies and actual OSObject.iig.cpp
from CI 42411427607, with mocked IOKit/Mach parser/TLS and ASan+UBSan.
Unpatched CI source fails with null-member access; patched source passes local,
remote, IPC, trap, instantiate, stale content, and invalid-parser-result cases.
This does not exercise the real kernel Mach parser or prove an iOS boot.
Workflow applies patch 0085 and runs the test after a successful kernel build.
Repository syntax validation passed (81 base patches, 20 Python, 9 shell).
RPC regression milestone complete. Next: adapt lemon RAM/ADT/GIC and isolate
unported Sweet storage/USB/touch drivers before a minimal full-kernel QEMU boot.
Current binary is not a validated Redmi 9T boot image; no phone test proposed.
No device commands, writes or reboot in this work.

### Previous: kernel builds; generated RPC has an unresolved runtime defect

CI run `42411427607` succeeded on commit `6db1c4214c977b99515e20359c540c3f645d676b`.
Job `128520207843` applied lemon patches 0082-0084, compiler commands included
`-DLEMON_4K -march=armv8-a+crypto`, and installed arm64
`kernel.development.sweet` (16,278,960 bytes). GitHub artifacts `xnu-kernel`
and `xnu-buildtree` were uploaded; buildtree downloaded locally under ignored
`research/ci-42411427607/`. This is a compile/link result, not a boot test.
Generated `OSObject.iig.cpp` reads `rpc.kernelContent`, while the old
`iokit/Kernel/IOUserServer.cpp:3212` initializer omits it before dispatching;
thus this path passes a null pointer to generated code, a runtime incompatibility
requiring analysis and fix. No device boot/flash. Sweet board drivers and other
hardware assumptions are also not yet validated for lemon. Next fix/audit the
RPC compatibility and remaining board-specific assumptions before any phone test.

### Previous: IOKit generator compatibility patch prepared

GitHub CLI authenticated as the fork owner. Merged the divergent histories
without force-pushing in `6db1c4214c977b99515e20359c540c3f645d676b`, then
pushed `lemon-bringup`. Push started XNU run `42411427607`:
https://github.com/elakpedro-cyber/ios-sweet/actions/runs/42411427607
It was in progress at handoff; inspect result and generated iig sources. Full
previous job log was accessible: apart from kernelContent failures, observed
matches were skipped optional patches and source lines containing error text;
interleaving can hide individual errors. No phone commands or writes.

User supplied diagnosis from `42407989137`: Xcode 16.4 iig-generated sources
fail because XNU 8796's `IORPC` lacks `kernelContent`. Added optional lemon
patch 0003, mirroring the `#if KERNEL` trailing `IORPCMessage *kernelContent`
field in Apple's current IORPC header; workflow copies it as patch 0084. This
is a compile-compatibility attempt, NOT proof that modern generated RPC code
works correctly at runtime: kernelContent initialization and semantics must
be examined with generated sources before any hardware test. Diagnosis listed
166 distinct matches, including interleaved lines and skipped optional patches;
other compiler errors may remain. Patch `git apply --check` passed against the
local XNU source and repository validation passed (81 base patches, 19 Python,
9 shell). 4K payload test passed but its header-preprocessing portion could not
run: clang is unavailable in this Windows environment. No full XNU build or
new CI run, no device commands. Local/remote histories differ but their trees
matched apart from handoff notes before this change; do not force-push.
Next: authenticate GitHub CLI, safely integrate remote branch, run CI, inspect
remaining errors and generated iig source. No phone or partition changes.

### Previous: diagnosis succeeded; authenticated logs required

First XNU build run `42407194318` failed. Diagnostic run `42407989137`,
job `128509745819`, succeeded and produced artifact `ci-diagnosis` (ID
`13588805052`), but its output and artifact require GitHub authentication.
GitHub CLI is not installed or not on PATH in this environment, and Git
Credential Manager has no available noninteractive GitHub credentials. The
actual compiler error remains unknown; do not guess at a fix or claim a build.
The remote `fork/lemon-bringup` is at `be6156da0db37742da2c4274bde9adcf8653b221`
and has a different history from local `lemon-bringup` (last pre-handoff local
commit `5369aa61cb1a3a667a1a18f5b503112c22f01a34`); preserve both histories,
never force-push. Next: obtain authenticated diagnosis output, investigate the
first concrete compiler error, then reconcile the branches safely before CI.
No device command, flash or reboot performed in this milestone.

### Latest: early 4K framebuffer verified, fork CI setup in progress

Fork access granted by user. Remote branch lemon-bringup created at
`cb3ecc4e959f7c4203f288d11c8052d1ca3edbde` (same tree as local 6b91a59).
First Actions run `42407194318`, build job `128507328097`, in progress.
https://github.com/elakpedro-cyber/ios-sweet/actions/runs/42407194318
Checkout, build-script fetch and dependencies passed. Await actual Build result;
then inspect logs and fix compile failures. No phone changes.

User provided fork https://github.com/elakpedro-cyber/ios-sweet and authorized
GitHub Actions setup. Fork HEAD matches upstream 45263bee51df4a0f55cdf9c649af886399488ddb.
New optional patch 0002-early-framebuffer covers all five 2 MiB FB blocks,
allocates missing L2 tables without replacing RAM mappings, checks pool/collisions,
uses lemon geometry in stage0/early console and final kernel alias.
Increased bootstrap pool to 34 pages for this config only.
QEMU A53/A76 ran the actual mapping macro with MMU enabled, switched code to
high KVA, disabled TTBR0, accessed first/last FB pixels successfully.
Tests also verify collision/capacity rejection, repeated map reuse, all block
descriptors and preserved executable RAM. Extracted actual final-map C logic
passed host checks (types mocked, memory barrier omitted; not full XNU compile).
Next CI: macos-15 / Xcode 16.4, because macos-14 retired on 2026-11-02.
Modern iig compatibility may need a follow-up fix; do not claim kernel built.
No device commands, writes or reboot in this milestone; original boot/TWRP preserved.

### Previous: offline 4K feasibility and first configuration completed

Read `docs/LEMON_4K.md`. Native 4K pmap and PAGE_RATIO=4 already exist in
Apple XNU; 16K logical pages do not require 16K hardware granules.
Prepared OPTIONAL `xnu/ports/lemon/0001-4k-config.patch` after the 81 Sweet
patches. Enables 4K/ARMv8-A/no assumed PAN and mobile user VA limit when
LEMON_4K=1, MACHINE_CONFIG=SWEET. Not wired into workflow; not a full board port.
Added mkpayload --page-size 4096 (2 MiB L2); default Sweet behavior preserved.
Tests passed: synthetic payload + ramdisk + default compatibility and real
XNU header preprocessing for 4K/16K geometry, TCR and user VA ranges.
All 81 upstream patches plus optional config applied in ignored research tree.
Repository validation passed (81 patches, 17 Python, 9 shell), diff check passed.
NO full XNU compilation/link/boot: no macOS SDK/buildtree on this host.
Next: replace Sweet-specific early framebuffer table assumptions with correct
4K L1/L2 allocation, then lemon RAM/ADT/GIC and minimal QEMU kernel build.
Existing Sweet drivers and early physical addresses are NOT safe for lemon.
No device command, flash, or reboot performed in this offline milestone.

### Previous: real CPU test completed; original boot RESTORED

User explicitly approved starting now while charging from PC, in response to
the concrete request for temporary boot-only write, test, and restoration.
Preflight: lemon in TWRP/root; boot=/dev/block/sde49,
recovery=/dev/block/sda9. All three partition hashes still match backups.
Battery 11%; user instructed proceeding now. Recovery must stay untouched.
Test and full original boot staged in recovery /tmp and hashes checked.
Probe written to boot: dd 315392 bytes succeeded, prefix SHA256 matched.
Recovery and dtbo full hashes unchanged. Executed adb reboot; after 8 seconds
neither ADB nor fastboot enumerated, as expected for this halted probe.
User observed blue CPU-test screen: MMFR0 ends in 1122 (leading zeroes),
TGran16 all zeroes. Real EL1 readout therefore indicates no 16K granule on
the boot CPU. User returned to TWRP with hardware keys; ADB confirmed recovery.
Restored the complete 134217728-byte boot-current.img using dd + sync.
Post-restore full SHA256: boot=f5ee6f406dc2a923dae167b9d45287daa0cba3c051484ce6e03536894b6c868f,
recovery=1737005c5d9452d3238fcd0a2430956e7232937b35e9df427edc114f0dacd2eb,
dtbo=6fd8b752c9a64bc77ccb43a43834b38a2a61e0499c44de01c6d1a349d73ce9a6.
All match pre-test backups. Device left in TWRP; no probe remains in boot.
Current Sweet kernel cannot run unchanged on the tested CPU (requires 16K).
Next software task: audit feasibility of a 4K XNU configuration and iOS userland
compatibility. Do not blindly replace __ARM_16K_PG__: loader, early mappings
and pmap must agree. No further hardware test is needed for this milestone.

### Previous update: packaged probe

Boot image `shim/out/lemon-probe/boot-lemon-cpu-probe.img` is now prepared:
315392 bytes, SHA256 `3e3b20d8fcaae8ce542c9f5eba2683231215eba34a9d85e4e66ca0d5c8d25f73`.
Raw Image now SHA256 `350667d2c65e2c3b7f99c6060b59aeff94286aad6833e0162e4b2849b1f3e917`.
QEMU CPU probe tests passed for A53 (TGran16=0) and A76 (TGran16=1);
these are emulator results, NOT phone results. Header/kernel/DTB checks passed.
Repository validation passed: 81 patches, 16 Python, 9 shell scripts.
Current boot/recovery/dtbo backups are complete and hashes match device reads.
Recovery kernel has no kexec/kcore/devmem/kallsyms; modules require signatures.
Device still in TWRP, charging at 11%; no reboot or partition write performed.
Prepared exact test/rollback sequence is in docs/LEMON_BRINGUP.md.
Next: obtain explicit approval for temporary boot-only write and restoration,
let phone charge, then test. User must physically return the halted probe to
TWRP with hardware keys. Never flash recovery. No test result from real hardware yet.

### Previous milestone

This checkout now starts a separate **lemon** port. Current local work takes
precedence over the historical Sweet handoff below. Read
`docs/LEMON_BRINGUP.md` for observed hardware, build command and next steps.
User explicitly requires keeping the installed TWRP: do not replace or flash recovery.
Base upstream: `45263bee51df4a0f55cdf9c649af886399488ddb`.
Live recovery FDT and current boot were pulled into gitignored `dtb/`, `backup/`.
EL0 CPU check ran successfully, but Linux hides the MMFR0 granule fields;
16K support remains UNKNOWN. Do not treat `0xff000000` as raw hardware data.
Bare-metal EL1 CPU probe uses upstream entry/console, lemon splash address
and dimensions, and has no storage driver. Offline ARM64 build passed;
no CI run and no device boot of this probe. Raw Image is not a boot.img.
Final raw Image: 77824 bytes, SHA256
`102c35dbf0628383bf364f93c0444716031ceab434e0582d3df22e9c3ee996a3`.
Repository validation passed (81 patches, 15 Python, 8 shell scripts) after
local LF normalization; probe compiles with -Werror and no undefined symbols.
Temporary EL0 checker was removed from recovery /tmp after the readout.
Next: establish a recoverable boot route, then read hardware MMFR0 before
porting XNU memory mappings. Existing ABL research suggests no fastboot boot.
No flashing, reboot, userdata changes or Apple downloads in this session.
Historical upstream approvals and host paths below DO NOT apply to this user.

## Historical Sweet notes

The original board-specific handoff remains in the upstream repository:
https://github.com/dipa-studio/ios-sweet/blob/45263bee51df4a0f55cdf9c649af886399488ddb/NOTES.md
