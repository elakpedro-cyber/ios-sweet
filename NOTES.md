# iOS 16 on sweet (Redmi Note 10 Pro, SM7150) - working notes

## Local Redmi 9T NFC port handoff (2026-11-07)

### Latest: diagnosis succeeded; authenticated logs required

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
