# iOS 16 on sweet (Redmi Note 10 Pro, SM7150) - working notes

## Local Redmi 9T NFC port handoff (2026-11-07)

### ACTIVE: v16 SPI responds but FW info invalid; readiness patch0018 (2026-11-20)

User returned TWRP; read ONLY4198400byte tail to research/lemon-v16-log.bin/.txt,
SWEETLOG total170993/flush13. Active setup succeeded: awake FW register0x102,
status0; retained read err0, version160/complement04, PID5940, geometry35584x0,
IRQ40000001. Worker refused input as designed. Actual touch still not working.
User confirms TWRP touch works. Its fresh initial firmware update logs FW5/PID5940,
but later /proc/nvt_fw_version also fails (FF/FF), while PID query5940 succeeds.
Thus invalid metadata is not proof of lost sensor SRAM firmware.

Read local recovery backup into ignored research/twrp-Image,30978064bytes SHA
4e9946d0160031469fe1d664e75d1e282539ca92dddd21349bd34188154ccdba.
Binary trim0Axxxx726603 at16c1d48 points to map16c1f9c, event base21c00;
get_fw_info code7f8b70 uses offset78/read17. CTP read7f7de0 clears bit7.
Actual vendor Truly file pulled118784bytes, SHA36dccc95785b40bb5bc0cc4764bc80dc066ce358dd7fb3c1afebaca670b9276f;
metadata at1a000 is06/f9, unlike runtime5. Do not upload this based on name alone.

DIAGNOSTIC ERROR/RECOVERY: ignored research/nvt-read-info.c initially inverted
NVTSPI direction flag. Source enum is WRITE0/READ1; first helper inadvertently
sent zero writes to volatile sensor event memory instead of reads (no phone
partition write or firmware-flash command). Disclosed to user immediately,
corrected direction, executed adb reboot recovery; fresh TWRP initialized/reset
and successfully reloaded its firmware (FW5/PID5940). Tested helper on host;
live page-only counter delta messages1/RX0/TX3 confirms corrected WRITE flag.
Later corrected bounded reads (only page-select writes) still returned unstable
metadata; not reliable evidence of firmware absence. No more NVTSPI probing
needed; use driver single-owner diagnostics. Helper is temporary/ignored.

Patch0018 adds bounded20x100ms readiness, reset-state/short+full metadata/PID logs,
keeps strict FW5/complement/PID/geometry gates, requires short/full agreement,
stops immediately on SPI error. No reset/power/upload. Actual helper tests pass
ASan/UBSan: delayed readiness, disagreement, wrong PID/geometry/complement,
bounded invalid state, transport error, restored event page. Whole worker also
passes native syntax/type check with kernel interface stubs. Final14ce591 CI
44617296656 in progress; supersedes cancelled547e156 run44617175805 (caught
removed report-loop err declaration locally before the first build completed).
Packaging prepared: research/build_touch_boot.py ready, kernel expected in
xnu/out-touch-ready-kernel. Produces boot-lemon-touch-ready-v17.img and
payload-touch-ready-phone.bin with unchanged identityADT/settings +lemontouch2.
NEXT push/build, package same v14 ADT with new kernel+lemontouch2 as v17, verify,
stage /tmp then obtain explicit boot-only write/reboot approval. Installed v16
full boot remains e975d1e1...; recovery/root preserved. No new boot written.

### v16 RESULT: user reports no touch; waiting TWRP/log (2026-11-20)

User selected "Касания не работают" after v16 swipe test. No claim of working
physical input. Failure stage unknown until log is collected; do not guess
DFS, GENI firmware, sensor SRAM or HID as established cause. ADB currently
has no devices, consistent with XNU running. Asked user to return TWRP without
formatting Data. No device write/reboot this turn. NEXT read ONLY4198400byte
tail to research/lemon-v16-log.bin/.txt and inspect LEMON TOUCH mode2 output.
Keep v16 installed, preserve root/recovery; new boot requires concrete approval.

### INSTALLED: v16 active touch handoff, awaiting physical result (2026-11-19)

User approved concrete active v16 boot-only write/reboot: "да".
Preflight recovery, boot sde49/134217728bytes, staged v16 SHA, current v15 full
boot and original recovery/dtbo hashes matched. Wrote ONLY16998400bytes boot
using dd4096 conv=fsync+sync. Readback4150block prefix SHA matched
1839c1ec9b31e9c7ef6e88ec2a11ce5dc7709a8266080653df3202f096a44b43.
Full boot SHA256 now
e975d1e1bc7f3b61db84da6f388745659c2d17fe5b3b457ddbf068d5284a1739.
Recovery/dtbo unchanged. No manual userdata write. Issued adb reboot successfully.
v16 lemontouch=2 attempts narrow SPI setup and retainedFW validation; actual
input NOT yet confirmed. NEXT allow UI to load and user try swipe-up. If no
response, return TWRP and pull ONLY4.2MiB log tail, inspect LEMON TOUCH lines
for DFS/protocol/FW/report result. No reset/power/firmware upload implemented.

### v15 RESULT: SE2 clock gated/pins unconfigured; active v16 staged (2026-11-19)

User returned TWRP. Read ONLY4198400byte tail to research/lemon-v15-log.bin/.txt,
SWEETLOG total164315, flush11. Actual LEMON TOUCH snapshot:
vote0x4be0 rcg0x80000000 cfg0x100000 dfs0x21;
branches1f004=0,1f008=8,1f00c=4220,1f014=4220,1f3a4=80004220.
GPIO6/7 cfg0/io0;71 cfg200/io3;80 cfg0/io1;93 cfg1/io1.
Driver correctly skipped SE reads because SE2 branch halted, then stopped.
No proof yet of GENI protocol/SRAM firmware retention. SPI pins not qup2.
Existing v16 active mode can narrow-vote clocks, require DFS level0 XO, read
protocol/idle state, configure SPI and validate retained FW5/PID5940. It may
stop safely if those conditions fail. No new build needed, same tested kernel.
Staged /tmp/boot-lemon-touch-active-v16.img; SHA matches
1839c1ec9b31e9c7ef6e88ec2a11ce5dc7709a8266080653df3202f096a44b43.
Current full boot remains v15 c5f381ce9def49c6eb1b0bec0cc6a9c6d5822c6fe034fcd24d882d378b6c381f;
recovery/dtbo match originals. NO partition write/reboot this turn.
NEXT obtain concrete v16 boot-only write/reboot approval. Then readback and
protected hashes, reboot, test swipe if UI appears. If no touch, return TWRP
and read tail for LEMON TOUCH awake/DFS/FW/report diagnostics. No reset/upload.

### INSTALLED: v15 snapshot boot, rebooted; awaiting physical result (2026-11-19)

User explicitly approved concrete v15 boot-only write/reboot: "делай".
Preflight recovery, boot link /dev/block/sde49 size134217728, staged SHA,
old v14 full boot and original recovery/dtbo hashes all matched.
Wrote ONLY16998400bytes boot via dd4096 conv=fsync+sync. Prefix4150blocks SHA
3d607568355c7dd577cb7cac703b9b2701f3daff2e65b63d8b9e07364576c104 matches.
New full boot SHA256
c5f381ce9def49c6eb1b0bec0cc6a9c6d5822c6fe034fcd24d882d378b6c381f.
Recovery/dtbo full hashes remain original. No manual userdata writes.
Issued adb reboot successfully. v15 lemontouch=1 is read-only hardware snapshot;
physical touch is still disabled. NEXT user allow normal GUI boot, return TWRP
via Power+VolumeUp, then read small persistent4.2MiB tail and LEMON TOUCH lines.
Do not flash active v16 before interpreting clock/protocol snapshot and obtaining
separate concrete boot-write approval. Keep installed root/recovery intact.

### READY: touch CI SUCCESS; v15 snapshot staged, awaiting boot approval (2026-11-19)

CI44609929903 for70642f3 SUCCESS, including full XNU link and actual touch
decoder/FIFO/gate tests. Kernel downloaded ONLY xnu-kernel (not buildtree) to
xnu/out-touch-kernel/kernel.development.sweet, SHA256
9fe189b564ca1e497efc7b56c5688094e87261131c7b77b943c9cdf16f0fb73e,
matches artifact SHA256SUMS. Linked driver strings/boot flag present.
research/build_touch_boot.py packaged two16998400byte Androidv2 images:
- shim/out/lemon-boot/boot-lemon-touch-probe-v15.img, lemontouch=1,
  SHA2563d607568355c7dd577cb7cac703b9b2701f3daff2e65b63d8b9e07364576c104.
- shim/out/lemon-boot/boot-lemon-touch-active-v16.img, lemontouch=2,
  SHA2561839c1ec9b31e9c7ef6e88ec2a11ce5dc7709a8266080653df3202f096a44b43.
Payloads payload-touch-probe-phone.bin/payload-touch-active-phone.bin retain
exact v14 identityADT and cmdline plus ONLY lemontouch flag; new kernel. Boot
header/load addresses/known DTB/gzip shim/4K payload/ranges/timer19 all verified.
Staged ONLY v15 in recovery /tmp/boot-lemon-touch-probe-v15.img, device SHA
matches. ADB recovery, boot link /dev/block/sde49, battery56. No partition write
or reboot. Latest full boot hash remainscf01389b... (v14); recovery/dtbo match
original full hashes (read this turn). All changes committed/pushed to fork.

NEXT obtain explicit approval for concrete boot-only v15 write/reboot per
AGENTS.md. Write dd4096 conv=fsync+sync only boot; verify16998400byte prefix
and protected hashes before reboot. First test is read-only MMIO snapshot,
not yet expected functional touch. ReturnTWRP/read4.2MiB tail, grep LEMON TOUCH
to assess SE clocks/protocol before choosing same-kernel active v16. No firmware
upload/reset implemented; hardware input still UNPROVEN. Keep root/recovery.

### ACTIVE: NT36672A touch driver prepared; phone in TWRP (2026-11-19)

User requested actual touchscreen after v14 lock-screen success, returned TWRP.
ADB connected. Fresh recovery input/sysfs/dmesg confirms NT36672A, SPI1.1 NVT-ts,
FW5/PID5940, 1080x2340, ten slots. Stock runtime CS0, despite DT address1.
Read local primary Xiaomi/mainline sources and sibling corrected stage1-r2 notes.
GCC0x01400000, GENI SE2 0x04a88000, TLMM WEST0x00500000 (GPIO6/7/71/80/93).
Reset103 and display-shared regulators deliberately untouched. No device writes,
reboots, raw SPI commands or new boot flashed during preparation.

Patch0017 adds lemon_touch.c, guarded default-off lemontouch=0. Mode1 snapshots
GCC/pins and clock-safe SE without writes. Mode2 narrow clock/pin/FIFO setup,
CS0, retainedFW-only validation, checksummed reports -> existing SweetHID.
No firmware upload/reset/PMIC; no assumption SRAM survives ABL. HID height fixed
to2340 for LEMON only. See docs/LEMON_TOUCH.md. Actual decoder/FIFO1..67byte,
errors/timeouts/gates/setup/HID release tests pass ASan+UBSan on local Linux.
Workflow applies0098 and runs tests. Commit70642f3 pushed to fork; CI44609929903
in progress (compiling). Patch dry-run against prior patched XNU passes. Full
repo validation passes under WSL. Read-only v14 log pulled:4198400bytes,
ring total241422bytes/flush47 to research/lemon-v14-log.bin/.txt.
Prepared ignored research/build_touch_boot.py for v15 snapshot/v16 active packaging.
NEXT build CI, prepare concrete v15 snapshot boot, verify layout, obtain explicit
boot-write/reboot confirmation per AGENTS.md. Then collect LEMON TOUCH log from
4.2MiB tail after returnTWRP; same kernel can test active mode later. Do not
claim working touch before a physical successful test. Installed boot remainsv14.

### MILESTONE: v14 iOS LOCK SCREEN CONFIRMED BY PHOTO; touch disabled (2026-11-19)

User supplied clear photo: Wednesday, December31,4:06, charging battery icon,
camera affordance, actual iOS lock-screen layout. First GUI on Redmi9TNFC now
VISUALLY CONFIRMED, beyond earlier user report. Preserved original unedited photo
in ignored research/lemon-v14-lockscreen-confirmed.png (not committed/published).
This milestone validates real Apple userspace/display after4K cache signatures
and chosen MAC identity properties; does NOT establish home navigation or input.
Phone still running v14. No device reads/writes/reboots this photo-confirmation
turn. Touch hardware polling remains disabled; performance and RTC still pending.

### Previous: v14 user reports iOS LOCK SCREEN; physical touch disabled (2026-11-19)

Physical v14: user reported Apple logo disappeared very slowly (~1fps), black
screen, then "ЕСТЬ ЕСТЬ Я ВИЖУ ЧАСЫ ВРЕМЯ 4:04 ДЕКАБРЬ 31". This is reported
iOS lock-screen UI after identity fix, NOT yet verified by a new photo/log pull.
No home-screen navigation established. Wrong date consistent with unset RTC/
epoch0 seen in prior boot logs. Current phone still running v14, not in TWRP.

Assistant prematurely asked user to swipe; user reports no response, suspects
lag. Corrected that request: physical touch is NOT ported/enabled. Confirmed
0005-minimal-board.patch makes sweet_touch_init() and sweet_keys_init() return
immediately under LEMON_4K. SweetHIDTouch/Buttons IOKit services can register
without actual hardware events. Do NOT attribute no swipe response solely to
lag or enable the Sweet Goodix/PM6150 path on lemon blindly.
Saved live lemon DTS has focaltech@0 and novatek@1 (NVT-ts-spi) alternatives;
active boot panel nt36672d_xinli_v2 suggests Novatek, but actual bound controller
MUST be confirmed in TWRP /proc/bus/input/devices/sysfs before driver work.
No MMIO/driver/partition write this turn. Performance still oneCPU + CPU display
copy, but actual lag cause not measured yet. Need photo of first lock screen,
then collect v14 small tail log when user returns TWRP; preserve running UI for
photo first. Future stages: input port and measured performance work. Could use
existing sweethidtest fake-Home for a bounded diagnostic if separately approved;
that would not be real touch support. Don't promise touch/USB/Wi-Fi functioning.

### Previous: identity v14 INSTALLED/VERIFIED, rebooted; awaiting screen/log (2026-11-19)

User explicitly approved "делаем" for concrete v14 boot-only write/reboot.
Preflight ADB recovery, boot /dev/block/sde49 size134217728, staged SHA, old v13
and protected hashes matched. Wrote16982016 bytes ONLY boot, dd4096 conv=fsync
and sync. Readback prefix SHA exactly
ccafcfa6f5827861163ef4265196f3362e04be3c24342f8393adf6426413863e.
Full boot SHA256cf01389ba2e079701fba9fc6e9e55025b1cf457ca809b83096d375c19b6e5f25.
Recovery/dtbo original hashes unchanged. No manual userdata/cache/persist write.
Issued adb reboot successfully. NEXT allow~2min and collect display result;
if still logo, return TWRP and read ONLY4.2MiB tail to research/lemon-v14-log.bin
and decode .txt. Check lsd seeding/MobileGestalt wait resolved versus new blocker,
SpringBoard/backboardd exec/crash/sample state and framebuffer swaps. Keep root.
This is the physical test of ADT identity fix; GUI success not assumed yet.

### Previous: v13 pinpoints missing Wi-Fi identity; ADT-only v14 staged (2026-11-19)

User returned TWRP after same logo/static tiny line. Read ONLY4.2MiB tail to
research/lemon-v13-log.bin/.txt: SWEETLOG v1,total148895,flush30,no wrap.
Samples0/1 have same lsd wait; no new core crashes (only driverkitd sig9 again).
Genericized ignored research/symbolicate_v12.py to accept log path/regex and
infer cache slide; v13 slide0x4b0c4000, lsd99 mh0x100308000.
lsd t0 _LSInstallProgressService performJournalRecovery -> dispatch_sync,
t2 restoreInactiveInstalls -> dispatch_group_wait, t4 clients waiting DB seeding.
Worker t1: MIInstalledInfoGatherer -> MIExecutableBundle installationIdentity ->
MIInstallationIdentity -> _GenerateBuiltInAppInstallSessionID+0x30 -> MobileGestalt
deep callbacks -> dispatch_semaphore_wait forever. cfprefsd idle, not blocker.

Disassembled exact PC cache (read-only) with aarch64 objdump, helper cache_read.py:
InstalledContentLibrary _GenerateBuiltInAppInstallSessionID at0x1b11b9ee0 passes
CFString0x1d8bc7708 to MGCopyAnswer: "re6Zb+zwFKJNlkQTUeT+/w" = UniqueDeviceID.
Confirmed MD5/Base64("MGCopyAnswer"+"UniqueDeviceID") and primary key table
https://github.com/PoomSmart/MGKeys/blob/master/deobfuscated.py .
MG UniqueDeviceID callback then requests WifiAddress (hashgI6iODv8MZuiP0IA+efJCw),
which requests WifiAddressData (hasheZS2J+wspyGxqNYZeZ/sbA). Current stack contains
0x19c568938,0x19c571770,0x19c57c0f8,0x19c57c6e8,0x19c57c4bc (unslid).
MGIOKitSupport.c worker is waiting for IOServiceMatched IONetworkController,
walking IOService parents looking for local-mac-address. No networking driver.
Read actual getter0x19c5716e8: BEFORE network-controller fallback it reads
IODeviceTree:/chosen "mac-address-wifi0". BluetoothAddressData getter0x19c56883c
likewise first reads chosen "mac-address-bluetooth0". Both absent in our ADT.
Thus a minimal ADT identity supply can avoid hardware-service wait, no kernel patch.

tools/mkadt.py now adds TWO6-byte locally administered unicast TEST identities
to chosen for LEMON ONLY (including its QEMU profile), analogous to synthetic ECID.
They are placeholders for userspace identity, NOT real Redmi MACs or network
drivers; no Wi-Fi/BT hardware support claimed. Sweet profile unchanged.
test-lemon-adt.py PASS6-byte binary type/length, unicast+local bits, distinctness,
lemon hardware/QEMU profiles and no change to Sweet; existing RAM/GIC/etc PASS.

Prepared boot-lemon-identity-v14.img16982016 bytes SHA256
ccafcfa6f5827861163ef4265196f3362e04be3c24342f8393adf6426413863e.
ADT shim/out/lemon-boot/lemon-identity-phone.adt (cloned OLD exact real-product
ADT, appends only2 properties), payload-identity-phone.bin. Kernel SAME ca32...,
v13 command line unchanged (keeps lsd sampler/null tee/quiet display/tail log).
research/build_identity_boot_v14.py proves pruning2 properties restores exact
old ADT; all kernel segments and cmdline unchanged. Boot header differs only
payload size/Android checksum. Existing v2/gzip/DTB/load ranges/timer19 PASS.
No kernel rebuild/CI needed for this ADT-only change. No actual phone success yet.
Staged ONLY /tmp/boot-lemon-identity-v14.img, device SHA matches. Current v13 full
boot9e4ace85... and original recovery/dtbo hashes verified. NO partition writes
or reboot this turn. NEXT explicit approval for v14 boot-only write/reboot;
collect screen and then tail log to see whether lsd passes identity/seeding.
Keep4K root caches; do not reinstall root or change real network/persist data.

### Previous: v13 lsd sampler INSTALLED/VERIFIED, rebooted; wait120s then collect log (2026-11-19)

User explicitly approved "делай" for reviewed v13 boot-only write/reboot.
Preflight TWRP, boot /dev/block/sde49 size134217728, staged SHA and old v12/
protected hashes matched. Wrote16982016 bytes ONLY boot, dd4096 conv=fsync+sync.
Readback prefix SHA exactly85e89ee91d2f9ff3aeb4c3acb1c4619f53d63087277d1d1fd9fd5cb0d961c652.
Full boot SHA2569e4ace850d6f4c26dc09fce9a3aa2430fca004674c788393fd795ac3db45b088.
Recovery/dtbo original hashes unchanged. No manual rootfs/cache/userdata writes.
Issued adb reboot successfully. NEXT wait~120s (first sampler90s + logger10s),
then if still Apple logo return TWRP, replug only if ADB absent. Read ONLY tail
4198400 bytes (skip12346082 count1025 bs4096) into research/lemon-v13-log.bin,
decode to .txt with tools/sweet-log.py. Inspect SMP lsd/cfprefsd/installd along
with SpringBoard/backboardd, then symbolicate using matching cache .symbols.
v12 complete log retained in research; v13 will overwrite device tail normally.
No GUI fix claimed: this run diagnoses observed LaunchServices synchronous wait.

### Previous: v12 log identifies LaunchServices wait; v13 lsd sampler staged (2026-11-19)

User saw Apple logo with tiny stationary element, waited, returned TWRP.
ADB recovery connected. Read ONLY4198400 bytes userdata tail block12346082;
ignored research/lemon-v12-log.bin + .txt. SWEETLOG v1, ring4MiB, total152707,
flush51, NO wrap: full saved log. Kernel remained alive ~510s; samples0..3.
exec counts: SpringBoard1,backboardd1,lsd1,cfprefsd1,datamigrator3,installd0;
bluetoothd49,fairplayd.H2 50. No CRASH SpringBoard/backboardd or panic/OOM in log.
Only reported CRASH is driverkitd sig9. Actual backboardd IOSurface2/3 created
1125x2436,BGRA,bpr4608,4 framebuffer swaps (2..5), then static display.
Thus graphics pipeline works, but no home screen observed.

Read phone preferences via READ-ONLY NBD (research/read_v12_prefs.py), no writes:
/home/hadirpc/lemon-v12-prefs/{migration,springboard,purplebuddy,SystemVersion}.plist.
Migration file uid/gid501,mode0600, LastSystemVersion20H392, disposition build20H392,
SyntheticDidUpgradeFalse. SystemVersion20H392/16.7.16, SetupDone/etc true,
BKNoWatchdogs true, migration sentinel /private/var/datamigrator/migrate ABSENT.
ADT already includes synthetic unique-chip-id/chip-id and display-scale3.
Do NOT blindly repeat old upstream migration fixes or add com.apple.DataMigration
domain: old notes explicitly say that domain did not work; com.apple.migration
is correct and present. Current stack gate is LaunchServices, not proven migration.

Extracted .symbols592101376 bytes from pristine PC root READ-ONLY into
/home/hadirpc/lemon-cache-4k/dyld_shared_cache_arm64.symbols. No downloads required.
research/symbolicate_v12.py uses mmap/nlist64/strings, validates symbolFileUUID
against main header offset400, resolves nearest local symbols (global syscall
symbols absent: large-offset syscall names are approximate, don't overinterpret).
Exact relevant SpringBoard t0 frames (subtract slide0x33238000):
0x181cb0f34 ___LAUNCH_SERVICES_WAS_ASKED_TO_PERFORM_BLOCKING_IO_ON_THE_MAIN_QUEUE__+0x10
0x181bf98d8 __LSCopyServerStore+0x300
0x181c898e4 _LSContextInitCommon+0x200
0x181bdfbb8 -[LSApplicationRecord _initWithNode:...]+0x8c.
backboardd t2: 0x181cb0f4c ___LAUNCH_SERVICES_IS_RESEEDING_ITS_DATABASE_AND_MAY_BLOCK__+0x10,
__LSCopyServerStore+0x310. Both wait synchronous XPC; lsd launched once but default
sampler only collected SpringBoard/backboardd, so lsd internal blocker unknown.
Do NOT call lsd corrupt or delete its database without evidence.

Prepared v13 SAME kernel/ADT/boot layout as v12, only adds:
sweetsample=lsd,SpringBoard,backboardd,cfprefsd,installd
sweetnull=lsd,SpringBoard,backboardd (stderr/stdout null tee diagnostics).
Keeps quiet graphics, tail logger10s,4K caches,root flags,510MiB and oneCPU.
shim/out/lemon-boot/boot-lemon-lsd-sample-v13.img16982016 bytes SHA256
85e89ee91d2f9ff3aeb4c3acb1c4619f53d63087277d1d1fd9fd5cb0d961c652.
Payload payload-lsd-sample-phone.bin; build research/build_lsd_boot_v13.py.
Matching mkpayload rebuild + byte comparison outside608-byte cmdline PASS;
v2 header/gzip/known DTB/load ranges/timer19 validation PASS. No kernel CI needed.
Staged ONLY /tmp/boot-lemon-lsd-sample-v13.img, device SHA matches.
Current boot still v12 fullb700159c..., recovery/dtbo original hashes verified.
NO partition write/reboot this turn. Tail log v12 preserved on PC before next boot.
NEXT explicit approval for boot-only v13 write/reboot, then wait~120s (sampler
first90s + next10s log flush), return TWRP, read same small tail, inspect lsd
and cfprefsd stacks. This is targeted diagnostic, not a claimed fix. Keep root.

### Previous: quiet/logging v12 INSTALLED/VERIFIED, rebooted; awaiting display (2026-11-19)

User explicitly approved "делай" for concrete v12 boot/reboot + logger proposal.
Preflight ADB recovery, boot /dev/block/sde49 size134217728, staged v12 SHA,
current v11/protected hashes matched. Wrote ONLY16982016 bytes to boot with
dd4096 conv=fsync + sync. Readback prefix SHA exactly
f9ee563f00ec0adbf0734f9925cd7e045cd4779d01a5adc220a7ecd02b44e259.
Full boot SHA256b700159cf7c413637a530ada54cd6a3220dcd50893549b2e0c81bdea557a90ef.
Recovery/dtbo original hashes unchanged. No manual userdata/rootfs writes;
v12 will save logs in the approved backed-up unused tail (details below).
Issued adb reboot successfully. NEXT wait30-60s, user reports/photo unobscured
display (logo/progress/UI/black). Do not assume GUI success. If no UI after a
short bounded wait, return TWRP, replug USB if needed, read ONLY last1025*4096
bytes of userdata at byte offset50569551872 (block12346082), decode with
tools/sweet-log.py, inspect SpringBoard/backboardd/CRASH/panic/VM pressure.
No new kernel CI required for current flags-only v12; installed4K caches preserved.

### Previous: real services running; quiet/logging v12 staged, awaiting boot approval (2026-11-19)

After installed4K caches user reports Apple logo behind console, then repeated
exec messages/slowing. Photo rotated upright in ignored research/phone-cache-boot-
upright.png: repeated bluetoothd/fairplayd.H2/xpcproxy; other processes contactsd,
privacyaccountingd,suggestd,assetsd,adid,medialibraryd. SWEET AKS (NOT RAS/RMS)
selector17/0/7 calls return0x0 success; "suggestd" was initially misread as
"suppressed". This photo has no panic/CRASH or proof SpringBoard/backboardd died.
Peripheral loops alone do NOT establish GUI failure; upstream Sweet also saw
bluetoothd/fairplayd.H2 relaunch with working GUI. Apple logo is user's observation,
not visible in supplied photo. Need unobscured image and full log next.

Prepared boot-lemon-quiet-log-v12.img16982016 bytes, SHA256
f9ee563f00ec0adbf0734f9925cd7e045cd4779d01a5adc220a7ecd02b44e259.
Same matching ca32dfac... v11 kernel/real-product ADT/loader/DTB/510MiB/oneCPU.
Byte comparison proves ONLY608-byte payload command-line field changes:
sweetfb_noconsole0->1 (mute panel text after first graphics presentation),
sweetlog0->1, explicit ufslogsecs=10; removed -enable_kprintf_spam. Keeps root
flags, sweetfb_hz15 and lemonpid1hold1. Header/layout/load addresses and known
gzipImage/payload/DTB/timer19 tests PASS. No new kernel build/QEMU required:
unchanged kernel already tested, hardware currently executing actual iOS services.
Build reproducible ignored research/build_quiet_boot_v12.py.

Logger is existing sweet_log_thread: writes ring+header ONLY last4198400 bytes
of userdata, offset50569551872 (device block12346082), every10sec under UFS lock.
Pinned userdata50573750272 bytes; HFS volume header confirms logical16GiB.
Log area is beyond HFS, within existing userdata, no GPT/partition geometry change.
Saved exact ORIGINAL area to ignored backup/lemon-pre-v12-log-tail.bin, SHA256
06955cde7f98b9503653b906e9634732d59a17a6dc2cb1a0e453fbdd4adaab86.
If needed, after next return TWRP read ONLY that4.2MiB and decode with
tools/sweet-log.py (no full filesystem scan needed). Console muting does not
disable ring append, and logger starts for lemon root mode when su.writable=true.

User returned TWRP on request; ADB recovery connected without replug this time.
research/stage_quiet_v12.py exit0: staged ONLY /tmp/boot-lemon-quiet-log-v12.img,
device SHA matches; current v11 full boot7ced79c0... and original recovery/dtbo
hashes verified. NO partition write/reboot in this preparation. Installed4K caches
preserved. NEXT explicit approval for v12 boot write/reboot + enabling logger in
unused userdata tail (AGENTS each-step rule). Verify boot prefix/protected hashes
then reboot. Await unobscured image; if still logo, return TWRP and retrieve small
saved log to locate actual SpringBoard/backboardd faults. Do NOT reinstall root.

### Previous: 4K cache update INSTALLED/VERIFIED, rebooted; awaiting screen (2026-11-19)

User explicitly approved "да" after reviewing21MiB userdata-cache update/reboot.
Ran python research/install_cache_update.py --flash, exit0. Before ANY write:
all113 exact physical preimages, backup/replacement hashes, TWRP, unmounted Data,
userdata device/size and boot/recovery/dtbo hashes matched. Staged bundle SHA
729bd5940ed5a64ae92171fbdb2786fa9d68b843e60eda2a5ff760f4d757d08d matched.
Wrote ONLY113 bounded existing userdata ranges, total21573632 bytes (4K aligned),
dd skip/seek/count conv=notrunc,fsync + sync. EACH range readback SHA matched;
second COMPLETE113-range readback verification also passed. Original rollback
bundle research/cache-phone-update/before.bin + manifest retained unchanged.
Boot remains v11 full7ced79c0a4d1c14e62729257a6854ef4423a39961ada7964c8516e51438269b5;
recovery/dtbo original hashes unchanged. No boot image replaced or recovery write.
Physical HFSX attributes0x80002100, free4637523968 bytes, journal0x82000,
start=end0x1f200 EMPTY verified. Root cache now has4K signatures.
Issued adb reboot successfully after ALL checks. NEXT photo/last lines after
30-60s, especially dyld/shared cache, launchd, panic or PID1 HOLD. This fixes
the observed signature-registration blocker; GUI/next-stage success NOT assumed.
DO NOT rerun installer (preimages now intentionally differ), format Data or
restore original root. TWRP remains available via Power+VolumeUp if next boot fails.

### Previous: 4K cache update staged/verified, awaiting userdata-write approval (2026-11-19)

User resumed: "давай делай новый boot я вернул телефон в тврп", then replugged
USB on request. ADB recovery connected. Explained current v11 boot/kernel already
supports verified4K signatures; the observed failure requires CACHE update,
not another kernel build. NO new boot image/build needed for this fix.
No userdata cache-write approval yet: current request explicitly names boot.

Completed FAST identity checks: ALL43 phone files match pristine PC root in
size, full4096-byte header and complete original signature table. No repeated
2.6GiB body checksum scans. This verifies identity metadata/signature hashes,
not complete integrity of every phone payload byte (user requested faster checks).
ALL86 canonical/preboot-alias paths in local phone-backed overlay have exact
expected new sizes, headers and signature tables. Full local converter4K hashes
and QEMU/HFS tests from d6ecb65 remain valid; not repeated unnecessarily.

Corrected journal handling: Linux fsck540.1 -fy does NOT checkpoint it. Actual
pending journal consists of ONE transaction, one4096-byte block at root offset0,
and that data ALREADY MATCHES physical phone disk byte-for-byte. Validated Apple
journal header44-byte and transaction32-byte checksums, descriptor/data bounds;
only then changed LOCAL overlay journal start to end and recalculated checksum.
No transaction payload replay or phone write. New journal start=end0x1f200.
research/checkpoint_journal.py refuses any unapplied block or corrupt checksum;
test_checkpoint_journal.py PASS read-only planning + positive/corrupt/unapplied
cases. Actual checkpoint validated independently by reading updated journal.
After cache edits fsck -fn says iOSRoot appears OK, journal still empty.

Successful overlay: /home/hadirpc/lemon-cache-phone-next2.qcow2 (~27MiB), backed
by read-only phone nbd+unix:///?socket=/home/hadirpc/lemon-cache-next2.sock.
Preparation research/prepare_cache_fast.py completed exit0; all servers stopped
and its socket cleaned. Do NOT rerun preparation over completed overlay.
Metadata snapshots /home/hadirpc/lemon-cache-fast2/{original,phone-original,
updated-canonical,updated-alias}. Source phone remains untouched v11/old caches.

Fixed range export: research/nbd_read.py is a read-only fixed-newstyle NBD client,
tested against4MiB random raw image (whole, offset130, unaligned and first reads
match exactly). Export uses read-only qemu-nbd instead of broken qemu-img dd.
Successful research/export_cache_overlay.py exported exact changed4K sectors,
FRESH original preimages from phone, bounded to first16GiB userdata only.
Ignored research/cache-phone-update/: 113 ranges,21573632 bytes (~20.57MiB).
before.bin SHA2561b48566ff67f56b2be0fab32ddeafe696aa4b4d52a63d3fa0497792092b3e10a
after.bin SHA256729bd5940ed5a64ae92171fbdb2786fa9d68b843e60eda2a5ff760f4d757d08d
manifest.json SHA25608593cf70901ba1aa2bc9d9074be9cf21d5a0f675125b498655098dbf0daf110.

Ran research/install_cache_update.py WITHOUT --flash, exit0: validated local
backup/replacement hashes, sorted/bounded/aligned113 ranges, userdata geometry,
TWRP+unmounted Data, ALL fresh physical preimage hashes, v11 boot/original recovery
and dtbo hashes. Staged ONLY /tmp/lemon-cache-update.bin, device SHA matches
after.bin. NO userdata/boot writes, NO reboot. This is concrete and ready.
NEXT obtain explicit approval for userdata cache+completed-journal update and
reboot (AGENTS rule). Then python research/install_cache_update.py --flash;
it rechecks all originals before writing, writes only bounded sectors with fsync,
verifies readback+protected hashes+empty journal. Reboot only after success.
After installation DO NOT rerun installer: preimages intentionally no longer match.
Keep v11 boot; preserve TWRP and full rootfs, no formatting/reinstallation.

### Previous pause: no phone writes; 4K cache fix prepared locally (2026-11-19)

User explicitly requested stop now, continue later: "ладно всё закончи быстро
вот прям щас быстро закончи потом продолжим". Stopped phone preparation/checksum
processes (session24172, Python2233, guestfish3420/3441, NBD2231 SIGTERM).
Phone remains TWRP, installed v11 boot, ORIGINAL installed16K-signature root cache.
NO userdata/boot writes this turn, no flashing/reboot approved for cache update.

Original full-cache phone checksum pass was too slow (~6MiB/s). User asked for
faster file identity checks: on resume compare sizes/headers/signature tables
instead of re-reading all file payloads (we already verified pristine source
and original installation readback). Explain this is narrower than full integrity
verification. Local converted43 files, full independent hashes and QEMU/HFS tests
already PASS; do not repeat them unnecessarily.

IMPORTANT NEW SAFETY FINDING: phone HFS journal pending (raw journal0x82000,
start0x1c200,end0x1f200, volume attrs0x80002000). Must replay/checkpoint in LOCAL
phone-backed overlay BEFORE Linux force RW edits, then ensure journal empty
before applying sectors, or stale replay can overwrite filesystem edits.
research/probe_hfs_journal.py reads/prints and currently ASSERTS empty (fails on
untouched phone, expected). guestfish appliance CAN run host /usr/sbin/fsck.hfsplus:
run; debug-upload /usr/sbin/fsck.hfsplus /tmp/fsck.hfsplus 0755;
debug sh "/tmp/fsck.hfsplus -f -y /dev/sda". Use --rw LOCAL qcow2 only, backing
NBD stays read-only. NO need install packages. Then -f -n check after edits.
Confirmed fsck -fn on PC test overlay: volume appears OK. Phone-v2 fsck -fy
also says volume appears OK, but journal header after replay NOT YET verified.

Local phone overlays: /home/hadirpc/lemon-cache-4k-phone.qcow2 (read-only attempt,
no cache edits); /home/hadirpc/lemon-cache-4k-phone-v2.qcow2 (~324KiB after fsck,
no cache edits). Backing nbd+unix:///?socket=/home/hadirpc/lemon-cache-phone.sock.
These require restarting read-only NBD server; stale socket may remain after
shutdown, remove only socket after confirming no server/fuser. Never apply PC
test-overlay sectors to phone. User pause overrides pending preparation.

Optimized tools/lemon-adb-nbd.py to8MiB reads,8-entryLRU (still64MiB total).
Actual8MiB binary read matches independently read first+last1MiB,0.74s for3reads.
Change committed with pause notes in1a4fc48. New server was restarted with8MiB reads.

Ignored helper scripts now available: research/test_cache_overlay.py (optional
--base,--overlay,--existing-overlay,--replay-journal; BEFORE full source hashes,
then tail/size writes ONLY local overlay, then full86 path hashes and hardlink
checks, fsck -fn), prepare_phone_cache_overlay.sh wrapper, export_cache_overlay.py,
install_cache_update.py. Exporter NOT successfully run; no bundle/staging exists.
BUG TO FIX BEFORE USING EXPORTER: qemu-img dd -f qcow2 if=... of=... bs=4096
skip=130 count=1 FAILED "cannot skip to specified offset". Do not trust range
extraction until tested (use qemu-io read export or NBD client/libnbd instead).
Also add explicit post-fsck journal-empty check to preparation/export before
any approval/write. install_cache_update.py default only preflight+/tmp staging,
--flash writes bounded exact userdata sectors with preimage/protected/readback
checks, then journal-empty assertion. Script NOT run, requires review/completed
export first and explicit user approval. Do not execute while paused.

### Previous: v11 exposes 16K signature rejection; prepare 4K cache update (2026-11-19)

Physical v11 photo finally preserves the actual error: libignition opens
/System/Library/Caches/com.apple.dyld, then kernel says "disallowing unsupported
code signature page shift: 14", "unable to create a validated cs_blob object: 85",
dyld reports shared-cache signature registration failure and missing libSystem.
PID1 HOLD works physically. This is NOT a missing cache/directory or GUI success.
ubc_subr.c accepts PAGE_SHIFT_4K or PAGE_SHIFT (both12 here). Simply accepting14
is unsafe: cs_validate_hash hashes16K from a4K page and asserts on other offsets.
Do not implement that blind kernel acceptance or fake successful validation.

Added tools/lemon-cache-4k.py: SOURCE read-only, OUTPUT separate; limited to
the actual ad-hoc SHA256 v0x20400 cache format with empty CMS and no scatter.
Verifies ALL original page hashes and requirements special hash, rebuilds4K
CodeDirectory, changes ONLY header codeSignatureSize8 bytes and signature tail.
UUID/mappings/library payload preserved. Rejects real CMS instead of stripping it.
Unit tests verify hashes, unchanged source/body, idempotence, corrupt payload,
CMS rejection and existing output preservation. Syntax/diff checks PASS.

Prepared ALL43 non-symbol cache files in /home/hadirpc/lemon-cache-4k (~2.6GiB).
Original source /home/hadirpc/lemon-ios16-root.img was mounted read-only only.
Independent full4K hash + payload-byte digest checks PASS for all43.
Manifest SHA256 fb089409647b9319a1b98c9b9fc6011d83de5a2037b07b13b4b1a4eda6f74a58.
Signature/8-byte-size patches /home/hadirpc/lemon-cache-4k-patches (~22MiB),
total file growth16039936 bytes. Original main SHA76874e83... matches phone.

Actual unchanged v11 XNU/QEMU Cortex-A53 + HFS test of REAL main cache:
original16K returns EBADEXEC85 (negative control), converted4K F_ADDFILESIGS_RETURN
succeeds with correct full coverage, executable mmap succeeds, reads ALL signed
pages: "LEMON CACHE4K: ALL SIGNED PAGES READ OK". No panic/fail markers.
Framebuffer decoder incomplete_decode/4 unknown old glyphs; targeted markers
verified, not a clean entire-screen claim. /home/hadirpc/lemon-cache-sign-test.
Fixture research/cache-sign-probe.S built with aarch64-linux-gnu-as, no relocations,
objcopy .text, mkinit.build_code (no clang present in current WSL).

Local filesystem integration /home/hadirpc/lemon-cache-4k-root-test.qcow2 backed
by pristine PC root: only signature tails/size uploaded in-place, hard links
preserved. ALL86 canonical/preboot-alias paths match new full-file checksums;
main inode identical,nlink2. PC source image NOT modified. This overlay is ONLY
a test: NEVER apply its sectors to the phone (phone HFS metadata differs).

User returned TWRP then replugged USB; ADB recovery connected, userdata unmounted,
boot remains v11 full7ced79c0..., recovery/dtbo originals verified. No phone write.
Preparing FRESH phone-backed read-only NBD + LOCAL qcow2 overlay using
research/prepare_phone_cache_overlay.sh (exec session4058). It checks all original
file hashes before local overlay writes, then all86 updated path checksums,
hard links. research/export_cache_overlay.py will export ONLY changed4K sectors
with exact preimages in ignored research/cache-phone-update/{before,after}.bin
and manifest.json. NBD server auto-stops after export. Phone always read-only.
NEXT collect preparation result, inspect/verify bounded sector bundle + backup,
then request explicit approval for userdata cache update/reboot (AGENTS rule).
Boot/kernel/recovery unchanged; no new CI needed for this rootfs-only solution.
Do NOT format Data or rerun entire root installer. No phone cache write approved yet.

### Previous: v11 installed and rebooted; awaiting held diagnostic screen (2026-11-19)

User explicitly approved "делаем" for prepared v11 boot-only write/reboot.
Preflight TWRP, boot target /dev/block/sde49 size134217728, staged SHA and
old v10/protected hashes matched. Wrote exactly16982016 bytes with dd4096
conv=fsync, sync. Readback prefix SHA matches v11
c09d893d7ada8c85676a35509e686d70326678f104bb47999cbe32320acee0c2.
Full boot SHA7ced79c0a4d1c14e62729257a6854ef4423a39961ada7964c8516e51438269b5.
Recovery/dtbo original hashes unchanged. No userdata write or root reinstall.
Issued adb reboot successfully. NEXT collect photo after30-60s, especially
messages immediately preceding LEMON PID1 HOLD; this is diagnostic, no GUI fix.

### Previous: v11 diagnostic ready, staged; awaiting boot-only approval (2026-11-19)

CI44555149569 for a464e2fe51271a8086d4eae6aea3713938cf6e1c succeeded.
Matching kernel SHA256 ca32dfac654912a448ea2dbf7fa69297bfdfba11d28a2b0e4cbd256398788f22.
QEMU Cortex-A53 real-shim deliberately-exiting PID1: option0 gives original
initproc panic, exit status0; option1 preserves exit message and LEMON PID1 HOLD
marker with no panic string. Snapshot decoder reports5 unknown glyphs on ON
screen (incomplete_decode), so this is targeted marker verification, not a
claim of clean full-screen decode. Outputs /home/hadirpc/lemon-pid1-hold-{0,1}.

Prepared boot-lemon-pid1-hold-v11.img16982016 bytes, SHA256
c09d893d7ada8c85676a35509e686d70326678f104bb47999cbe32320acee0c2.
Baselinev9 root flags plus lemonpid1hold=1; unsuccessful v10 dyld_flags removed.
Matching kernel/payload/ADT/root flags and boot header/load ranges validated.
Staged only /tmp/boot-lemon-pid1-hold-v11.img; device SHA matches local.
ADB sees TWRP. Boot remains v10 full SHA4c4d7e70419b4a0e270685be9131acd2c2d8934e12859082fd6f8571be3e1bed;
recovery/dtbo original hashes verified unchanged. NO boot/userdata writes.
Next: obtain explicit approval for v11 boot-only write/reboot, verify readback
and protected hashes, then collect preceding dyld cache error from held screen.
Preserve existing iOS root; do not run root installer or format Data.

### Previous: v10 same dyld cache failure; prepare PID1 pre-panic hold diagnostic (2026-11-19)

Photo v10 repeats namespace6/subcode1 Library not loaded libSystem.B.dylib,
no such file/no dyld cache. dyld_flags0x19 did NOT resolve it. Root intact;
no GUI/main launchd reached. User returned TWRP ("вернуо"), device check next.

Optional0016 adds lemonpid1hold=1 to preserve preceding dyld/kernel messages
instead of overwriting screen with panic dump. Hook in proc_handle_critical_exit
AFTER existing sync(), only p==initproc; helper defaultoff/2 returns normally,
exact1 prints marker and loops delay1s (no device IO). Original panic unchanged
when off or for other critical processes. Not a fix or continuation after failure.
Actual helper/hook ASan/UBSan PASS option0/2/1, onlyPID1, delayiteration.
Workflow applies0097 and tests helper. Repo31Python/12shell/81basepatches PASS.
Next full CI, QEMU own deliberately-exiting PID1 with hold ON/OFF to verify
preserved marker versus original panic, then root v11 with baselinev9 command
line plus lemonpid1hold=1 (remove unsuccessfuldyld_flags0x19), no rootfs change.
Before new boot write get approval for concrete image. Preserve installed HFS.

### Latest: v10 boot-only installed/verified; next cache-path boot result (2026-11-19)

User approved "делаем" for staged v10 boot-only retry. TWRP/staged v10 and
current v9 boot/protected hashes matched. Wrote16982016 bytes ONLY boot,
dd4096 conv=fsync+sync. Read-back prefix SHA exactly
3cbf15273f788a0959c556b6dc6d970d8b5aac20f249021c61161613d859cdde.
Full boot SHA256 4c4d7e70419b4a0e270685be9131acd2c2d8934e12859082fd6f8571be3e1bed.
Recovery/dtbo original hashes unchanged. Existing iOS rootfs preserved;
no userdata write this step. Next reboot, photo/last lines after30-60s;
look for dyld/cache failure versus launchd progress. No assumed fix yet.

### Latest: v9 Apple dyld fails shared-cache load; v10 cache-path test staged (2026-11-19)

Physical photo v9: initproc failed to start, exit namespace6/subcode1,
Library not loaded /usr/lib/libSystem.B.dylib, referenced /sbin/launchd,
reason no such file/no dyld cache. This is real Apple launchd/dyld reaching
loader, NOT proof of GUI. Cache failure cause not yet established.
User returned TWRP, replugged USB when ADB absent; recovery now connected.
Do NOT reinstall root image: it is intact and writable HFS state changed normally.

Added tools/lemon-adb-nbd.py, read-only nbdkit Python2 API proxy of first16GiB
userdata through adb exec-out1MiB reads,64-block cache. Requires TWRP and exact
userdata device/size, rejects non-readonly opens, no pwrite callback. Installed
nbdkit + python plugin (8.8MB downloads), server socket only in WSL home.
Actual Windows binary capture returned1MiB with HFSX header; guestfish --ro
--format=raw via NBD mounted PHONE filesystem. /cores empty. ALL44 cache files
exist at /System/Library/Caches/com.apple.dyld. Main384KiB cache: UID0,GID80,
mode0755,nlink2,inode318416, SHA256
76874e8375252ee643011ff8063f0cce12355f05cf5f9897a34e5679667a65aa.
No partition writes. Stopped nbdkit PID719 after clients closed; discard cache
between boots. Reproduce command in tool docstring, use --format=raw (initial
automatic format probe failed). Read-only proxy useful for future logs/files.

Read Apple dyld1066.10 source at /home/hadirpc/lemon-dyld-1066,
commit3e5ba1a2d04c3a221eab66b99e0e0dd90a470150. DyldDelegates.h bits:
forceCustomerCache1,skipIgnition8,useSystemCache0x10. v10 adds dyld_flags=0x19
to test direct system-cache lookup, bypass ignition directory selection.
This is a bounded TEST, not a confirmed fix. No kernel patch or FS change.
Kernel/ADT/loader/DTB match v9; payload byte comparison verifies ONLY608-byte
command-line field differs. Header/payload/ranges/timer19/root flags validated.
No repeated QEMU needed: unchanged kernel passed HFS test already.
shim/out/lemon-boot/boot-lemon-cache-path-v10.img16982016 bytes SHA256
3cbf15273f788a0959c556b6dc6d970d8b5aac20f249021c61161613d859cdde.
Staged ONLY /tmp/boot-lemon-cache-path-v10.img; device SHA matches.
Current boot remains v9 fullcf155ee3...; recovery/dtbo original hashes.
Syntax30Python/12shell/81basepatches PASS. NEXT approval for v10 boot-only
write/reboot; preserve existing rootfs. If cache still fails, obtain earlier
dyld/cache diagnostic (e.g. PID1-exit hold before panic wipes console), do not
assume a 4K/16K fix: PAGE_SIZE_FOR_SR_SLIDE is fixed4096 even upstreamSweet.
Upstream ignition cache failure history saved research/upstream-notes-current.md;
v9 ADT already has /chosen/asmb lp-sip0=0x6f,lp-sip1=1, so don't blindly repeat SIP.

### Latest: REAL ROOTFS + V9 INSTALLED AND VERIFIED; next first boot (2026-11-19)

User explicitly said "запускай" after reviewing userdata+boot+launch proposal.
Completed python research/install_ios_root.py --flash, exit0. Unmounted/data,
wrote exactly16GiB to verified /dev/block/sda11 in64MiB chunks with fsync.
FULL16GiB device prefix SHA matched original root image
c783b998c83c0a7b3d7920fd665fdd8a84fa5b20d5165c605c633c82abb3328a.
Script rechecked unchanged v8 boot + original recovery/dtbo, then cleaned temps.
No GPT/bootloader/modem/persist write. Userdata NOW CONTAINS HFS+ iOS root;
old Android/data filesystem replaced as explicitly authorized (phone empty).

Then checked local/staged v9 SHA and v8/protected hashes again. Wrote ONLY
boot16982016 bytes, dd4096 conv=fsync+sync. Read-back prefix SHA matches
58e6ae6a54681bd5ffb5f03431ea4cbf6d8e932ac2f66112336ac19b954dbeac.
Full boot SHA cf155ee3fe372b61014ac0ee234e741bd1fa3fafc9d30c5f79df4de81b3425cb.
Recovery/dtbo retain original hashes. No original boot restoration.
NEXT reboot to first REAL Apple userspace attempt, ask screen/photo after30-60s;
if text continues, allow boot more time. Actual Apple launchd/UI still unobserved.
Do not run initial installer again merely because HFS hash changes after RW boot;
normal journal/daemon writes will change image. TWRP/data is no longer F2FS;
do NOT format it if recovery cannot mount it. Preserve installed root for debugging.

### Previous: user authorized installation; transfer started (2026-11-19)

User replied "запускай" to concrete userdata+boot+launch proposal. Previous
wait-for-confirmation boundary is revoked for these reviewed actions.
Started python research/install_ios_root.py --flash, exec session57553.
Preflight passed source SHA/HFSX, device/extent and protected hashes; /data
unmounted and checked by script. Transfer subsequently completed and verified
as recorded above. No new approval needed for the already-authorized first launch.

### Latest: ALL PREPARATION COMPLETE; wait for user's install/launch confirmation (2026-11-19)

User away and explicitly wants to confirm phone launch on return. Do NOT
write userdata/boot or reboot until that confirmation. Phone in TWRP.
ONLY /tmp files written in this stage; current boot remains v8 full
11abe53dc2ad5a644d709777d6f40eefa43e4593c56fec288df1fcb747b4d2c1;
recovery/dtbo original hashes rechecked. User says phone completely empty.

CI44543155402 ef6664a SUCCESS. SHA256SUMS verified kernel
xnu/out-ufs-root-kernel/kernel.development.sweet:
ee90c84170f9003e418d1d00e59ce6b1ca6ae10319e64ad027414962ed7a4167.
New kernel actual HFS-root integration on real shim/Cortex-A53 QEMU55s:
"hfs: mounted LemonTest on device b(1,0)", own PID1 + FOUR alive messages.
No visible panic. Decoder unknown5 old glyphs, not clean-decoder pass.
Output /home/hadirpc/lemon-hfs-root-kernel-a53. No Apple launchd run yet.

V9 for REAL root (not own RAMDisk init):
shim/out/lemon-boot/boot-lemon-ios-root-v9.img16982016 bytes SHA256
58e6ae6a54681bd5ffb5f03431ea4cbf6d8e932ac2f66112336ac19b954dbeac.
Staged /tmp/boot-lemon-ios-root-v9.img; device SHA matches. Known loader/DTB,
fresh lemon-root-phone.adt with real D22AP /product. SAME510MiB managed RAM,
one CPU, timer19. No XNU chosen/memory-map RAMDisk, payload exactly rebuilt
from matching kernel/ADT; header/gzip/payload/DTB/ranges all validated.
Command line: debug=0xc serial=3 cpus=1 keepsyms=1 rd=ufsroot0 lemonufsroot=1
ufsroot=userdata ufsrw=1 rootrw=1 unentitled_ios_sim_launch=1 ignition_level=1
launchd_unsecure_cache=1 wdt=-1 wdt_test=no_user_checkin sweetlog=0
sweetfb_noconsole=0 sweetfb_hz=15 -enable_kprintf_spam
Console intentionally left visible for first real Apple bootstrap diagnostics.

Root image /home/hadirpc/lemon-ios16-root.img16GiB is prepared, fsck clean,
SHA c783b998c83c0a7b3d7920fd665fdd8a84fa5b20d5165c605c633c82abb3328a.
research/install_ios_root.py READ-ONLY preflight PASSED, --flash NOT run.
It is the tested64MiB chunk transfer helper; do NOT use failed stdin gzip route.
It pins userdata block/size/extent, unmounts/data and verifies before writing,
does complete16GiB prefix hash + protected partition hashes, never reboots.
Installer expects current v8 boot hash and therefore MUST run BEFORE boot-v9
installation. If phone restarted TWRP, re-push volatile /tmp v9 as needed.

After user's explicit approval covering userdata+boot+launch:
1) python research/install_ios_root.py --flash (monitor until verified success).
2) Recheck/stage v9, write ONLY boot dd4096 conv=fsync+sync, verify16982016-byte
prefix SHA and unchanged recovery/dtbo. Record new full boot hash.
3) Reboot, ask user for last screen lines/photo. Actual Apple launchd/dyld/
SpringBoard first run may need fixes; UI not yet proven. No automatic restore.
Do not widen RAM blindly: TWRP /proc/iomem shows reserved allocations around
0x13b546000..0x13fffffff despite broad System RAM range. Kept proven510MiB.
Some GitHub status requests had transient TLS timeouts; artifact hashes and
final success were verified. No active local preparation process remains.

### Active: user away; finish preparation ONLY, await install/launch approval (2026-11-19)

User: "я отойду от пк так что доделай там что надо и дождись меня я подтвержу
запуск на телефоне". Agreed: prepare/verify PC artifacts, leave phone in TWRP;
NO userdata/boot writes or reboot until user returns and confirms.
CI44543155402 (ef6664a) building0015; full result pending.

Meaningful HFS integration test with EXISTING v8 kernel: built32MiB case-sensitive
journaled HFS+ in guestfish containing our static init at /sbin/launchd + /dev.
Booted real shim/A53 QEMU55s: "hfs: mounted LemonTest on device b(1,0)",
PID1 + FOUR still-alive messages. No visible panic. Decoder unknown4glyphs in
older text, not clean-decoder pass. Output /home/hadirpc/lemon-hfs-a53;
image /home/hadirpc/lemon-test-hfs.img; ignored research/make_hfs_test.sh.
Thus actual HFS mount + exec works on4K, independently of physical UFS DMA.

Prepared ignored research/install_ios_root.py: default READ-ONLY preflight
passes original16GiB SHA/HFSX signature, current v8 boot+recovery+dtbo hashes,
pinned userdata device /dev/block/sda11 size50573750272 and sysfs extent.
--flash intentionally NOT run. It would unmount /data via TWRP and verify,
copy64MiB raw chunks via adb push + bounded dd seek/notrunc/fsync, then verify
full16GiB prefix SHA and unchanged protected partitions; never reboots.
--flash needs explicit user authorization for rootfs install.
Actual transfer helper tested with binary1MiB+7bytes at two offsets into
/tmp ONLY: SHA readback exact, seek/notrunc/short-final-write pass. Cleaned temp.
research/test_root_stream.py reproduces. No user partition writes.
An attempted stdin gzip/exec-in route failed TEMP-only tests (empty/short data,
gzip Illegal seek); abandoned. Do NOT reuse it for installation. Chunked
adb push helper is the verified path. /data currently mounted f2fs in TWRP;
must unmount and verify immediately before any explicitly approved root write.

Optional host backup compressed (not used by installer):
/home/hadirpc/lemon-ios16-root.img.gz,~5.8GiB, gzip-t passed, SHA256
6d310b1605ed24609dc206b08cf3422decf3c92195dfb63181a8b1fbcf75d3da.
Raw SHA remains c783b998...; host~46GiB free. No extra network download.
Next await CI; repeat actual HFS QEMU on new kernel; build real-product ADT
and boot-v9 ROOT payload (NO RAMDisk/init, rd=ufsroot0 lemonufsroot=1,
ufsroot=userdata ufsrw=1 rootrw=1 sweetlog=0 etc). Validate/stage ONLY /tmp,
record exact checksums and ask concrete userdata+boot installation approval.

### Active: PHYSICAL v8 reads correct GPT; preparing real UFS root mode (2026-11-19)

Photo v8: LEMON UFS READ result=0,LUN=0,first=0x20d918,blocks=12347107,
then own PID1/still-alive. EXACT match to TWRP GPT/sysfs. XNU DMA/SCSI READ
on this phone is now proven. User returned to TWRP and clarified phone is
completely empty (no Android personal data to preserve). No userdata write yet.

Optional0015 prepares root on verified userdata, gated lemonufsroot=1.
Default/diagnostic stays read-only. Kernel permits WRITE10 + SYNCHRONIZE_CACHE
only in root mode AND after su.writable enabled with exact ufsrw=1, after disk
registration and pinned LUN0/first0x20d918/count12347107 geometry check.
Any other named partition rejected before controller use; existing writer
checks all write ranges against partition bounds. Nonlemon behavior preserved.
Actual-function ASan/UBSan tests PASS: opt-in0/2/1, all256 command opcodes and
directions in diagnostic/RO/RW modes, wrong LUN/extent, valid first/last writes,
outside/crossing/zero/oversized/overflow writes rejected without mock transport,
rootmode/ufsrw0/1/2 gating. Full CI next. Prepare actual HFS-root QEMU test
and a concrete PC rootfs installation script before asking approval to write
userdata + new boot. Do not write until that explicit confirmation.

### Latest: v8 installed and verified; next reboot/read GPT result (2026-11-19)

After reviewing prepared v8, user instructed "продолжи". Continued with v8
boot-only installation. TWRP ADB confirmed, current v7 boot/recovery/dtbo
hashes matched. Volatile /tmp image was absent; re-pushed exact local v8,
verified SHA before write. Wrote16977920 bytes ONLY boot, dd conv=fsync+sync.
Read-back prefix SHA256 matches
4cb98e0e4bf09b3034ce67119a519b39fa78fb610ab68164c2031f1d13dc0b68.
Full boot SHA256 11abe53dc2ad5a644d709777d6f40eefa43e4593c56fec288df1fcb747b4d2c1.
Recovery/dtbo unchanged; no userdata write and no original boot restore.
Next reboot/read LEMON UFS READ result/LUN/first/blocks or timeout/panic.
Expected result0,LUN0,first0x20d918,blocks12347107. No physical DMA result yet.

### Latest: v8 read-only GPT test built/checked/staged, approval pending (2026-11-19)

CI44514064375 (051b6ed) SUCCESS, including actual command guard/GPT parser
ASan/UBSan and prior diagnostic tests. Kernel artifact SHA256SUMS verified:
xnu/out-ufs-read-kernel/kernel.development.sweet SHA256
1433d24419ac89128a095e1a474224d57d653203699dff252ea6786edca61cac.
Real-shim A53 QEMU55s, physical UFS options OFF: PID1 and SIX still-alive
messages, no visible panic. Two unknown old glyphs remain; automated clean
decode criterion did not pass. /home/hadirpc/lemon-xnu-ufs-read-a53.
This does not test physical DMA; next phone run is the first such test.

shim/out/lemon-boot/boot-lemon-ufs-read-v8.img16977920 bytes, SHA256
4cb98e0e4bf09b3034ce67119a519b39fa78fb610ab68164c2031f1d13dc0b68.
Same v6/v7 ADT/loader/DTB/test init/RAM, new kernel and command line includes
lemonufsprobe=1 lemonufsread=1, still rd=md0 sweetlog=0. Validated header,
gzip Image, payload, DTB, load ranges, timer19. Staged ONLY
/tmp/boot-lemon-ufs-read-v8.img; device SHA matches.
Current TWRP boot remains v7 full6137965e...; recovery/dtbo original.
No device partition write this turn. NEXT explicit v8 boot-only approval,
verified dd/fsync/readback then reboot and photograph LEMON UFS READ line.
Success must show result=0,LUN=0,first=0x20d918,blocks=12347107 matching
TWRP GPT/sysfs. Test returns before disk registration, forbids all data-out
and non-TUR/READ10 SCSI commands. No userdata write/rootfs install yet.

### Active: physical v7 UFS ready; opt-in GPT read test prepared (2026-11-19)

Photo clearly shows CAP=0x1587031f, VER=0x300, HCE=1, HCS=0x10f,
DBR=0, RSR=1 and PID1/still-alive. CAP bit24 supports64-bit DMA;
HCS DP/UTRLRDY set, no outstanding transfer doorbell. This verifies register
handoff only; no XNU DMA/SCSI read has yet run. User returned to TWRP ("готово").

Optional0014 enables existing host takeover + TUR/READ(10) GPT lookup ONLY
when lemonufsread=1. Uses verified0x04804000 MMIO base; LUN0, known4KiB blocks.
LEMON build command guard permits ONLY TUR/READ(10) with data-in/no-data;
all data-out and other opcodes return EROFS before descriptor/MMIO access.
After reporting result/LUN/first/blocks it returns BEFORE disk registration,
writable enable, log/input/USB services. rd=md0 test init remains root.
GPT count bounds changed to division to avoid uint32 multiplication overflow.
Actual guard/parser ASan/UBSan: all256 opcodes/data-out, known partition,
missing partition, invalid extent/count, overflow count and read-error PASS.
Existing0013 diagnostic/hook test updated for read-test-off default, PASS.
Repo syntax29Python/12shell/81basepatches PASS. Next full CI, A53 QEMU default
OFF, concrete v8 phone image with explicit approval before boot-only write.
Rootfs remains PC-only; no userdata writes. Existing v7 remains installed.
CI44514064375 (051b6ed) started; ADB confirms recovery. Await full build result.

### Latest: v7 written and verified; collect physical UFS registers (2026-11-19)

Physical user report: some "framework" startup text, then repeating
SWEET init: still alive. Kernel/test userspace survived v7, but no UFS
register values transcribed yet. Do NOT infer controller readiness from this.
Hook is before rd=md0 branch in IOFindBSDRoot; inspect screen/photo first,
lines may have been overwritten by repeated init output. No new write planned.

User explicitly approved v7 boot-only write. Staged image and current v6
boot/recovery/dtbo hashes rechecked before writing. Wrote16977920 bytes ONLY
boot using dd conv=fsync + sync. Prefix SHA256 matches
829a62ad4bb6873fc1af9f4ea2ea4cdf43abee44e02099bd886b82ae4828615f.
Full boot SHA256 6137965e4b0c2df85da9143511c9a820b3791c441564904b7a139806eddce419.
Recovery/dtbo hashes unchanged. No userdata write or original boot restore.
Next reboot and read LEMON UFS CAP/VER/HCE/HCS plus DBR/RSR, or panic/last line.
Probe only reads controller registers; no DMA/SCSI/controller writes enabled.

### Latest: iOS rootfs prepared + v7 UFS register diagnostic staged (2026-11-19)

Rootfs preparation COMPLETED, not XNU-boot-tested:
/home/hadirpc/lemon-ios16-root.img, logical17179869184 bytes (16GiB), about12GiB
allocated. SHA256 c783b998c83c0a7b3d7920fd665fdd8a84fa5b20d5165c605c633c82abb3328a
(also adjacent .sha256). OS/SystemOS/AppOS streamed successfully into HFS+
using IOSROOT_GUESTFS=1; script exit0, fsck clean. Applied existing
sweet-root-tweaks.py, verified unchanged SHA256 of Apple launchd/dyld and
root ownership, SpringBoard executable exists, SetupDone/BKNoWatchdogs and
mobile501 ownership. Final read-only fsck clean; finish script exit0.
Logs /home/hadirpc/lemon-ios16-root-{build,finish}.log.
Host guestmount gives different synthetic per-path st_ino for hard links:
initial host ino equality assertion was wrong. Appliance guestfish statns
shows SAME inode318416,nlink2,size393216 for both shared-cache aliases.
Host content/nlink checks pass. No actual link repair was needed.
Ignored research/{finish_ios_root.sh,verify_prepared_root.py} reproduce finishing.

CI44510231343 (66f53f0) SUCCESS including new UFS diagnostic host test.
xnu/out-ufs-probe-kernel/kernel.development.sweet SHA256
8f5166d1ce69fb77be876bb842e1f11419c3e9238276b95bc2622604c03d209c.
Real-shim A53 QEMU55s, diagnostic OFF (physical MMIO absent on virt):
PID1 and SIX still-alive messages, no visible panic. Decoder still has2unknown
glyphs in an older line; clean-decode criterion did not pass.
Output /home/hadirpc/lemon-xnu-ufs-probe-a53. Probe opt-in/no-write path covered
by actual-function ASan/UBSan host test and CI; hardware result pending.

Prepared shim/out/lemon-boot/boot-lemon-ufs-probe-v7.img16977920 bytes SHA256
829a62ad4bb6873fc1af9f4ea2ea4cdf43abee44e02099bd886b82ae4828615f.
Same loader, DTB, v6 phone ADT and own test init; only new kernel and added
lemonufsprobe=1 command line. Validated v2/gzip/payload/DTB/ranges/timer19.
Staged ONLY /tmp/boot-lemon-ufs-probe-v7.img; device SHA matches.
Current TWRP boot remains v6 full hash0ca20d0b...; recovery/dtbo original.
NO partition writes during rootfs stage. NEXT specific v7 boot-only approval,
then verified write/reboot and collect LEMON UFS CAP/VER/HCE/HCS/DBR/RSR.
Do NOT write userdata yet: UFS driver still disabled before DMA/SCSI and
register-only diagnostic is the next physical step. Rootfs is PC-only.

### Active: downloaded iOS verified, rootfs building, UFS diagnostic prepared (2026-11-19)

User finished download and resumed. All four components SHA384 match Apple
BuildManifest 20H392/d22ap erase identity. OS=4730814044 bytes,
SystemOS=2743074816, AppOS=10485760, DeviceTree=33719. Read-only OS APFS mount
works, real arm64 launchd/dyld present. Extracted LZFSE d22ap ADT into ignored
research/ipsw-x/d22ap.adt, mkadt with real /product succeeds.
TWRP ADB confirmed. READ ONLY storage facts: Micron MT064GASAO2U21, LUN0,
4096-byte logical blocks, userdata=/dev/block/sda11. GPT header/entry CRCs
validated against local backup/lemon-ufs-gpt.bin; userdata first0x20d918,
12347107 blocks,47.10GiB; matches sysfs first17221824/size98776856 512b sectors.
UFS controller live DT base0x04804000,size0x3000. No device partition writes.

WSL lacks HFS+ and KVM. Installed libguestfs-tools, Linux6.8.0-149 image/modules
and modules-extra (about212MB downloads total, no recommended firmware).
mkiosroot.sh IOSROOT_GUESTFS=1 streams tar into appliance HFS+ instead of slow
per-file guestmount rsync; then guestmount for existing link/metadata setup.
Waits guestmount PID exit before fsck to avoid image flush races.
First slow build stopped cleanly, partial kept at
/home/hadirpc/lemon-ios16-root-initial-copy.img (~250MB allocated).
Current build /home/hadirpc/lemon-ios16-root.img16G running, log
/home/hadirpc/lemon-ios16-root-build.log; exec session55691. Must finish and
fsck, then apply sweet-root-tweaks.py before declaring ready.

Optional0013 adds lemonufsprobe=1 register-only CAP/VER/HCE/HCS/DBR/RSR
diagnostic; hook in IOFindBSDRoot works even rd=md0. Default remains off,
lemon driver still returns ENXIO before DMA/SCSI/host writes. Nonlemon unchanged.
Actual diagnostic+hook host ASan/UBSan PASS opt-in0/2/1, no register mutations,
mapping failure. Workflow applies0094 and runs test. Next CI, QEMU without
physical MMIO option, then prepare concrete v7 boot for explicit approval.
This is preparation for storage access; full iOS UI still needs storage driver.
CI44510231343 (66f53f0) now building0013 on macos-15-intel.
OS tar import completed; SystemOS import in progress, image~9.4GiB allocated.
Apparent source sizes: OS7937213671, SystemOS3359797050, AppOS7846405 bytes
(~10.53GiB before HFS allocation/metadata). No need to fill entire16GiB image.
Standalone actual Apple launchd scan: no LSE opcodes in instruction sections;
dyld scan's sole match0x66274 is SHA256 constant0x78a5636f, verified nearby K
constants. This is static inspection only, not proof of runtime compatibility.

### Latest: user-operated resumable downloader ready; NOT started (2026-11-19)

User wants to change VPN server before downloading. Added download-ios.cmd
for double-click on this Windows PC, invoking tools/download-lemon-ios.py.
Uses existing WSL source folder via UNC so complete AppOS/SystemOS/DeviceTree
and manifest are CRC-checked and skipped. Fetches only selected ZIP members
from pinned Apple CDN IPSW, not whole archive. Shows percent/MiB/s/ETA.
Compressed .zip.part cache allows resume even for ZIP_DEFLATED; final files
are extracted and CRC/size verified. Old downloader's decompressed OS .part
cannot supply compressed resume state; first OS run with new script starts
from zero, but subsequent interruptions resume. Existing .part left intact.
Offline stored/deflated half-download resume + output integrity + skip tests
passed (research/test_ios_download.py); help and UNC directory checked.
No new download started, no phone operations. User will run after VPN switch.

### Paused by explicit user STOP during iOS rootfs preparation (2026-11-19)

User requested actual iOS screen next, then explicitly STOP. Download process
and child curl terminated, verified absent. No device writes in this stage;
phone last known running successful v6 test init. Do not resume until asked.
WSL /home/hadirpc/lemon-ios16-source contains BuildManifest, components.json,
complete AppOS/SystemOS/DeviceTree with ZIP CRC checks, partial OS dmg (.part).
Ignored research/ios-firmware.json and fetch_ios_components.py hold exact Apple
CDN URL and resumable extraction. iPhone X 16.7.16/20H392 manifest verified.
apfs-fuse built at /home/hadirpc/lemon-apfs-fuse commit66b86bd525e8cb90f9012543be89b1f092b75cf3
and installed /usr/local/bin/apfs-fuse. Root-owned read-only FUSE mounts remain
at lemon-ios16-source/mount-system and mount-app (host paths only).
Installed cmake/pkg-config/libfuse-dev/libbz2-dev/libattr1-dev/hfsprogs.
Host WSL kernel lacks CONFIG_HFSPLUS_FS; mkiosroot.sh cannot mount target HFS+
as-is. guestfs alternative only simulated, NOT installed (882MB packages).
No root image created, Apple launchd/SpringBoard not yet attempted.

### Latest: PHYSICAL XNU v6 reaches test userspace and stays alive (2026-11-19)

User read on phone: "SWEET CPU: cpu=0 mpidr=0x0 came alive; SGI1 OK",
copyright lines, then repeating "SWEET init: still alive".
This is the first physical full XNU success on lemon: the bundled test init
runs beyond the former initCPU hang and repeatedly resumes after sleep.
It is our small test userspace, not an iOS UI/root filesystem. No physical
PID1 banner was transcribed, but repeating text comes from our test init.
Phone currently running v6; no TWRP return requested, no further device write.
Recovery remains preserved by pre/post-write hash checks. Keep v6 installed
per user preference. Next port milestone: assess real userspace/rootfs and
remaining unimplemented hardware drivers; do not infer those work from init.

### Previous: XNU v6 written and verified (2026-11-19)

User explicitly approved v6. Rechecked staged image and v5/current boot,
recovery/dtbo before writing. Wrote 16977920 bytes ONLY boot, dd conv=fsync
and sync. Read-back image prefix SHA256 matches exactly
7e0846f3385edc533aee0a0ed71d5ba662ba4b650c80439d961136a1e652b323.
Full boot SHA256 0ca20d0bca5a202e3a42f38e7530aa580777f8190978e71368fe4cb1acb0cd93.
Recovery/dtbo retain original hashes. No original restore per user preference.
Reboot completed; physical result recorded above.

### Previous: full XNU v6 built, QEMU PID1 verified, staged pending approval (2026-11-19)

CI44501956040 (af86cea) completed SUCCESS, including actual GIC order test.
Downloaded xnu/out-gic-fixed-kernel/kernel.development.sweet; SHA256SUMS OK.
Kernel SHA256 c3311f0e7a518928af2b24b0e0a06eab66846bf299e51de07f6c4374e735feaa.
Real-shim Cortex-A53 QEMU 55s: PID1 + two still-alive messages, SGI1 verified,
no visible panic. Decoder reports two unknown glyphs in an older overwritten
network-init line; automated clean-decode criterion did not pass. Exact PID1
and liveness messages decoded fully. Output /home/hadirpc/lemon-xnu-gic-fixed-a53.
Phone image uses same loader/known DTB, timer19 and verbose v3 command line.
shim/out/lemon-boot/boot-lemon-gic-fixed-v6.img: 16977920 bytes, SHA256
7e0846f3385edc533aee0a0ed71d5ba662ba4b650c80439d961136a1e652b323.
Verified v2 header, decompressed Image, payload identity, DTB, load ranges,
managed RAM and embedded timer19 (research/verify_v6.py, ignored).
Staged ONLY /tmp/boot-lemon-gic-fixed-v6.img; device SHA matches.
TWRP current boot remains v5 hash6bd4276e...; recovery/dtbo original hashes.
NEXT: specific approval for v6 boot-only write, then dd/fsync readback and reboot.
No automatic original restoration per user. Physical full XNU v6 untested.

### Previous: physical v5 confirms SGI1 + IRQ19; XNU order fix prepared (2026-11-19)

User-read v5: SGI CNT=1; TMR A=0x13; TMR CNT=0x13; TMR IRQ=0x13;
END EN=0x80002; D AFTER=0x12; RESULT="both IRQs delivered".
Hex 0x13 is decimal 19: 19 timer deliveries on INTID19, no IRQ27 fallback.
This confirms ordered affinity setup fixes hardware delivery; leave timer19.
User returned to TWRP. V5 left installed per preference; full boot hash
6bd4276e4bbbe62d6072f159505a6583b1f55fb0a43a984cbc4e4935a879f1fd;
recovery/dtbo still original. No restore or further device write.

Optional XNU patch 0012 initializes distributor ARE_NS before GICR configuration
on lemon only, preserving already-set ARE and disabling group forwarding during
the mode transition. Adds bounded distributor RWP waits and verifies ARE_NS.
Existing tail then enables groups after per-CPU setup. No timer, ASID, RAM or
allocator changes. Non-lemon Sweet path remains unchanged.
tools/test-lemon-xnu-gic.py compiles actual pe_init_fiq plus its helper with
mock DT/sysregs and architectural GICR RAZ/WI behavior; actual probe NS readback
bit0=0 is modeled. Reset states 0/0x10/0x12 and stuck-RWP timeout PASS.
Workflow applies patch0093 and runs this test. Next full CI and real-loader
A53 QEMU, then prepare a concrete new XNU image before another boot-write.
Run 44500809386 remained queued on macos-15 with no assigned runner/steps.
Official runner-images currently identifies macos-15 as arm64 and the standard
macos-15-intel as x64; the Intel macOS15 image still includes Xcode16.4 at the
same path. Switched ONLY runs-on to macos-15-intel to try its separate queue.
Kernel target remains ARM64/SWEET/LEMON_4K and all checks remain enabled.
Reference: https://github.com/actions/runner-images/blob/main/images/macos/macos-15-Readme.md
Intel run 44501956040 (af86cea00b3f90687f4b45bce09cc163a8ef96de)
started successfully; dependency setup and ARMv8 atomics check passed, kernel
build in progress. Superseded ARM run 44500809386 was cancelled. No device write.

### Previous: ordered GIC probe v5 installed (2026-11-19)

User specifically approved replacing boot with v5. Pre-write v4 full hash and
recovery/dtbo matched recorded values; staged image verified. Wrote 315392 bytes
ONLY boot with dd/fsync + sync; read-back prefix SHA256 exactly matches
86cdec55cadb51219b55acea4c275a73bf8dba0742bd99b728e8bc7f53333611.
Recovery/dtbo unchanged. Reboot and obtain SGI CNT, TMR A, TMR CNT, TMR IRQ,
END EN, D AFTER and RESULT (or STOP/FAULT). Leave test boot installed per user
preference. Return to TWRP with buttons after result before subsequent work.

### Latest: v4 shows no enabled IRQs; ordered GIC probe v5 prepared (2026-11-19)

Physical v4 user-read results: SGI CNT=0, TMR CNT=0, OTHER=0, RESULT="IRQ
delivery missing". D CTLR(before setup)=0; D TYPER=0x7904f4; R EN=0;
R PEND=0x08200002; R ACTIVE=0; ICC PMR=0xf0; ICC GRP1=1; TMR CTL=5.
User separately confirmed R GROUP=0, R EN=0 (not PRE EN), PRE PEND=0.
Thus SGI1 becomes pending and CNTV expires, but interrupt forwarding is not
enabled. Cause of zero enable is consistent with an actual ordering bug:
both probe v4 and XNU configure GICR before enabling GICD ARE_NS. GICR SGI/PPI
enable writes are RAZ/WI when affinity routing is off. QEMU masked this case.
Primary architecture source: Arm IHI0069C,
https://documentation-service.arm.com/static/6012f442773bb020e3de7aa5 .
Linux driver reference: android.googlesource.com/kernel/msm/+/866b728388bc6a1d774e8433482a08f11e8245d4/drivers/irqchip/irq-gic-v3.c
(gic_dist_init precedes CPU/redistributor config). No secure-world changes.

User returned to TWRP, v4 still installed by request. Current full boot hash
aef97b71958b53dace14d73b5912d8ef0c7dc64d691c10aeacc639abb2c71781;
recovery/dtbo retain original hashes. No original boot restore performed.
V5 masks distributor group enables while preserving an already-set ARE bit,
enables ARE_NS, verifies it, THEN programs GICR and enables groups. Never
transitions ARE 1->0. New post-setup CTLR/enable prints provide readback.
Phone-only second phase tests IRQ27 only when IRQ19 delivered no timer and
CNTV caused pending bit27 before the timer was disabled; ISR follows chosen ID.
Do not change XNU's timer ID based only on pending state; await physical counts.
tools/test-lemon-gic-order.py executes actual setup against architectural
ARE-off RAZ/WI semantics. Old v4 source FAILS ignored-write assertion; new
code PASSES reset states 0/0x10/0x13. A53 QEMU SGI1=1, timer27=19 PASS;
alternate candidate19->27 path: first phase=0, then timer27=19 PASS.
Phone build and Image/gzip/cpio/DTB/load-range checks PASS. Syntax: 25 Python,
12 shell, 81 base patches PASS. XNU kernel not changed yet.
shim/out/lemon-gic/boot-lemon-gic-probe-v5.img: 315392 bytes, SHA256
86cdec55cadb51219b55acea4c275a73bf8dba0742bd99b728e8bc7f53333611.
Staged ONLY /tmp/boot-lemon-gic-probe-v5.img, device hash verified.
NEXT requires approval for replacing ONLY boot with v5; no automatic restore.

### Previous: standalone GIC probe v4 installed (2026-11-19)

User specifically approved writing v4. Verified staged image and current v3
boot/recovery/dtbo hashes before write. Wrote 315392 bytes ONLY boot with
dd bs=4096 conv=fsync + sync. Read-back prefix hash matches
2a4a408911658dcf8d643f3277f543bc55a49a2122573ea99f6c6f2624c6c267.
Recovery/dtbo remain original. Boot tail still contains v3/original bytes;
header sizes select only the v4 probe. Reboot and collect SGI CNT, TMR CNT,
OTHER, RESULT plus fault/status registers if either interrupt is missing.
Per user preference leave test boot installed, no automatic original restore.
User button return to TWRP is necessary after probe halts.

### Latest: physical v3 reaches CPU0 init; GIC probe v4 prepared (2026-11-19)

User-read final lines: "cpu_start() cpu:0" and
"SWEET CPU: cpu=0 entered initCPU mpidr=0x0 EL1 IRQs=1"; unchanged after a
further 20-30s. No SGI1 OK, CPU initialized, timeout/panic or PID1 reported.
Thus the older kmem[3] line was not the full progress observable with verbose
logging. This narrows attention to CPU start / IRQ delivery; cause unproven.
User returned to TWRP. Per explicit preference v3 remains installed; no restore.
Full current boot hash cf2334b8bb20a49963c7d322037af915b4db2e9c77efe76c9d0080c4bc82708e;
recovery/dtbo remain original 1737005c... / 6fd8b752... .
Live TWRP DT confirms arm,gic-v3, GICD f200000+10000, GICR f300000+100000,
timer interrupts PPIs 1/2/3/0 and frequency 19200000. Virtual PPI3 => INTID19.

Prepared standalone shim/lemon-gic-probe.c; no XNU, storage, PSCI or extra CPUs.
Uses same Group1 NS/SRE/PMR/BPR/EOI setup as XNU, bounded GIC wake/RWP waits,
self SGI1 and 200ms periodic CNTV test. Displays pre/post pending/active/enable,
CPU interface and IRQ counters. Unexpected inherited sources are disabled in
GIC before EOI to prevent a level-triggered interrupt storm in the probe.
MMU stays off. No persistent device state or partition writes by probe code.
Separate --qemu build substitutes virt GIC bases and INTID27 only.
tools/test-lemon-gic.py executes actual vectors/ISR on Cortex-A53: SGI1=1,
timer IRQ27=19, other=0 PASS; raw Image header/size and position independence PASS.
Phone probe package Image/empty cpio/unchanged DTB/load-range checks PASS.
Repository validation: 81 base patches, 24 Python, 12 shell PASS.
shim/out/lemon-gic/boot-lemon-gic-probe-v4.img: 315392 bytes, SHA256
2a4a408911658dcf8d643f3277f543bc55a49a2122573ea99f6c6f2624c6c267.
Staged ONLY at /tmp/boot-lemon-gic-probe-v4.img; device SHA256 verified.
NEXT needs specific approval for writing this new diagnostic to ONLY boot.
Keep v3 installed until approval; do not restore original automatically.

### ACTIVE V3 TEST: v3 installed; user explicitly waived automatic boot restore (2026-11-19)

User explicitly approved writing v3 and said original boot need NOT be restored
between tests to save time. This user instruction overrides older restoration
requirements below. Keep the verified original backup; preserve recovery/dtbo,
userdata and every other partition. Future destructive writes still need the
specific authorization required by AGENTS unless already authorized in session.
Rechecked original boot/recovery/dtbo, staged v3 image and local backup hashes.
Wrote 16977920 bytes ONLY boot with dd/fsync + sync. Read-back prefix SHA256
matches 3f707deafbc2dc15f2bb4adbcfa03a00da5c2bcd17ebca147c5b8986a3816937.
Recovery/dtbo hashes unchanged. Reboot system and get last startup trace lines.
V3 remains installed after the test unless user requests restoration; returning
to TWRP with buttons is still required for USB/ADB and subsequent work.

### Latest: resumed v2 physical test completed; original boot RESTORED (2026-11-19)

User returned and explicitly resumed work; phone already in TWRP, battery 41%.
V2 was left installed during the pause. Prefix hash matches e116b925...;
full boot SHA256 6dd41d973b9aa6aabb0d84038e00a4420fc28fda494ef1dab0268b9b4ae273c0
matches an offline overlay of v2 on the verified original 128 MiB backup.
Recovery/dtbo retain original full hashes. Local original boot and v2 hashes
also reverified. Rebooted the existing v2 without rewriting it. User reports
last visible line "kmem_large_ranges[3] : 0 - 0 (0B)", unchanged after another
30 seconds. Normal console now visibly advances beyond EARLY20 into kmem;
no panic or PID1 reported. Observation is user-read text, not a saved image.
User returned with buttons to TWRP. Re-pushed verified original backup and
restored ALL 134217728 bytes of boot. Full boot hash matches f5ee6f40... and
recovery/dtbo match 1737005c... / 6fd8b752... respectively. Phone left in TWRP.
No userdata/recovery/dtbo writes. V2 is no longer installed.
Prepared v3 diagnostic using built-in startup_debug=1 and -enable_kprintf_spam
with the SAME verified d59ad404... kernel. Only the 608-byte payload command
line slot changed; kernel code, ADT, test init and loader are byte-identical to
v2. No speculative allocator changes or new kernel build needed.
Real-loader A53 QEMU 55s reaches PID1 with THREE alive messages; no visible
panic. Decoder reports 2 unknown glyphs in older log text. A separate read-only
hardware breakpoint at kmem_range_init captures actual verbose startup trace
and KMEM phase/function-pointer lines. Native outputs in WSL:
/home/hadirpc/lemon-startup-trace-a53/ and lemon-startup-trace-markers/.
Image shim/out/lemon-boot/boot-lemon-startup-trace-v3.img: 16977920 bytes,
SHA256 3f707deafbc2dc15f2bb4adbcfa03a00da5c2bcd17ebca147c5b8986a3816937.
Unpacked v3 kernel/DTB exactly match v2; payload differs ONLY in command line;
boot load addresses/sizes unchanged and non-overlapping. Staged ONLY at
/tmp/boot-lemon-startup-trace-v3.img in TWRP; device image SHA256 verified.
NEXT requires specific approval for another temporary write ONLY boot, then
screen capture, user button return to TWRP and full original boot restoration.
Current original boot is restored; do not repeat a new write without approval.

### Previous interrupted v2 physical test (2026-11-08; restored 2026-11-19)

User approved v2 temporary boot replacement and restoration. Pre-write live
boot/recovery/dtbo hashes and local full 134217728-byte boot backup match known
good copies. Wrote 16977920 bytes of console v2 to boot using TWRP dd/fsync.
Read-back prefix SHA256 e116b925c381895868bb901ee5862ae1bb8aa52cb886a72ab47db0c05a40d950
matches image. Recovery/dtbo unchanged. Reboot system next, record screen,
then user returns to TWRP with buttons. Push backup/boot-current.img anew,
verify and restore ALL 134217728 bytes ONLY boot; verify full boot/recovery/dtbo
hashes. No userdata/recovery/dtbo writes. Do not leave v2 installed after test.

### Latest: console v2 built, QEMU verified, physical approval pending (2026-11-08)

CI 42452145524 SUCCESS on 3b0a203, job 128643452833, 8m33s.
https://github.com/elakpedro-cyber/ios-sweet/actions/runs/42452145524
Build, RPC, ADT and actual framebuffer-console sanitizer checks passed.
Kernel xnu/out-console-kernel/kernel.development.sweet SHA256 matches artifact:
d59ad404d7760078ed7d5caf8f9d9c89f3bdbd6e9d4ca5ae59ee14edfcfb59ed.
Real-loader A53 QEMU 55s run reaches our PID1 and FOUR alive lines, no visible
panic; decoder has 4 unknown glyphs in older overwritten log rows.
Time-based early capture missed markers (already overwritten); the wrapper's
marker assertion failed, although its PID1 checks passed. A separate read-only
GDB hardware breakpoint at machine_startup captures all FOUR exact console
markers, without changing code/registers/mappings. Both checks now evidenced.
WSL outputs /home/hadirpc/lemon-console-a53/ and lemon-console-markers/.
Local copies research/console-v2/{final.txt,markers.txt,fb.png,regs.txt}.

Packaged image shim/out/lemon-boot/boot-lemon-console-v2.img, 16977920 bytes,
SHA256 e116b925c381895868bb901ee5862ae1bb8aa52cb886a72ab47db0c05a40d950.
Image decompression, exact payload/DTB and nonoverlapping load ranges PASS.
Old b3e70be6 image retained as boot-lemon-xnu-test-v1.img in the same directory.
Phone checked in TWRP: full boot/recovery/dtbo hashes match known good backups.
V2 pushed ONLY to /tmp/boot-lemon-console-v2.img and exact SHA256 verified.
No physical writes or reboot during this phase. Next requires new specific
approval for temporary boot replacement, followed by full original boot restore.
Actual physical effect on the EARLY20 stall is still unverified.

### Previous: console handoff diagnostic prepared (2026-11-08)

Patch 0011 gives fbcon the existing sweet_early_framebuffer() permanent Normal-NC
alias instead of creating a second ml_io_map_wcomb alias. The physical stall's
cause is still unproven; this removes an unnecessary mapping/attribute change.
It validates the lemon FB base/dimensions before reusing that alias and drains
framebuffer stores on newline. arm_init emits direct PE_kputc markers after
handoff, PE_create_console, platform init and CPU PIO mapping, independent of
DEVELOPMENT kprintf spam settings. Original Sweet path remains unchanged.
tools/test-lemon-console.py compiles actual getter/probe/render functions with
mock DT and guarded framebuffer under ASan/UBSan: alias/no extra map, glyph,
newline/wrap, buffer guards and invalid-display rejection PASS on Linux.
Workflow applies 0011 and runs this check. Next full CI and real-loader A53
QEMU, then package a concrete new image before asking for another physical
boot-write approval. Phone remains in TWRP with original boot restored.
CI 42451650642 failed: pexpert/arm/pe_serial.c cannot find arm64/lemon_fb_map.h.
The new cross-component include needs EXPORT_MD_LIST in osfmk/arm64/Makefile;
0011 now exports it alongside sweet_early.h. No device commands this phase.

### Latest: physical XNU reaches EARLY 20; original boot RESTORED (2026-11-08)

User explicitly approved temporary write ONLY boot and restoration after test.
Pre-write live boot/recovery/dtbo and local 134217728-byte boot backup hashes
matched known good copies. Wrote 16977920 bytes of b3e70be6... image to boot
using TWRP dd bs=4096 conv=fsync, then sync. Read-back image-prefix SHA256
exactly matches b3e70be6ecabab6cd48be7aed8ce274483df096efcc9e83c1b5796a3be74998d.
Recovery/dtbo full hashes remained unchanged before reboot. Rebooted system.
User reports "SWEET EARLY 20: kprintf startup complete", unchanged after a
further 20-30 seconds. This is a physical XNU entry/MMU/arm_vm_init/serial-init
milestone. NO physical PID1 or complete kernel boot claimed. No USB/ADB from
test, as expected. Observation is user-read text, not a saved screenshot.
Source places stage20 just before sweet_early_disable and normal serial
console setup. A console handoff/visibility issue is plausible, not confirmed;
absence of further visible text does not prove a CPU hang.
User returned to TWRP with buttons. Re-pushed and verified boot-current.img,
then restored ALL 134217728 bytes to boot using dd bs=4096 conv=fsync + sync.
Full post-restore hashes match known good backups:
boot f5ee6f406dc2a923dae167b9d45287daa0cba3c051484ce6e03536894b6c868f
recovery 1737005c5d9452d3238fcd0a2430956e7232937b35e9df427edc114f0dacd2eb
dtbo 6fd8b752c9a64bc77ccb43a43834b38a2a61e0499c44de01c6d1a349d73ce9a6
Phone left in TWRP. Temporary test boot is no longer installed. No userdata
or other partition writes. Next investigate logging handoff after EARLY20,
preserve early diagnostic output and test changes in QEMU before proposing
another separately approved physical boot replacement.

### Previous: physical test image prepared; boot-write approval pending (2026-11-08)

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
