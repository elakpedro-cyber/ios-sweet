# iOS 16 on sweet (Redmi Note 10 Pro, SM7150) - working notes

## Local Redmi 9T NFC port handoff (2026-11-07)

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
