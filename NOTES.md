# iOS 16 on sweet (Redmi Note 10 Pro, SM7150) - working notes

## Local Redmi 9T NFC port handoff (2026-11-07)

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
