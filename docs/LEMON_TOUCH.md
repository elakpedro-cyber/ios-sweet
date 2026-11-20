# Redmi 9T NT36672A touch bring-up

TWRP identifies event5 as NVTCapacitiveTouchScreen, ten slots, X0..1079,
Y0..2339. SPI1.1 binds NVT-ts. Recovery reports firmware5, PID5940 and a
successful SRAM firmware upload. These observations do not prove that the
firmware survives the next boot.

The stock driver overrides the DT chip-select1 to runtime CS0. GENI SE2 is
0x04a88000; SM6115 GCC is 0x01400000; GPIO6/7/71/80/93 are in the WEST tile
0x00500000, not the flat DT TLMM base. GPIO103 reset is in SOUTH. The IO and
LCD bias supplies are shared with the display. Do not enable Sweet's Goodix
I2C, PM6150 regulators or reset sequence on this board.

Patch0017 adds a separate SPI polling driver, guarded by LEMON_4K:

- Default/other `lemontouch` values: disabled, no mapping or hardware access.
- `lemontouch=1`: read-only GCC/pin snapshot, SE reads only if clocks run.
- `lemontouch=2`: narrow wrapper0/SE2 clock vote, XO clock, stock pin settings,
  SPI mode0/8bit/CS0, raw CS delay200. Requires retained GENI SPI firmware and
  idle/empty FIFOs. Reads NT36672A FW info/PID before accepting any contacts.

Active handoff requires known PID5940. Readable metadata must match the observed
FW5/1080x2340. If metadata is unavailable, patch0020 permits the vendor-style
known panel dimensions after stable PID, but withholds HID until two checksummed
frames with the same active contacts show actual movement. A first slow swipe
confirms this path; static/corrupt replies do not activate it. It selects the
event pages, reads reports and checks checksum, contact IDs and coordinates;
no chip reset, power change, SRAM firmware/configuration upload or flash write.
Readable unsupported firmware or transport failure stops the worker. Invalid reports
are discarded; patch0021 releases stale contacts after100ms without a valid report,
while valid finger-up remains immediate. Initial stale frames do not permanently disable input. Poll20ms, no
GIC interrupt registration. Touch reports use the existing SweetHID service;
LEMON panel height2340 yields a48pixel Y offset into the2436pixel logical display.

First physical test should use snapshot mode and read the small persistent log
after returning TWRP. The same kernel contains active mode for a subsequent
boot; successful offline tests are not proof of physical input support.

Physical v15: wrapper clocks run, SE2 is gated and SPI pins are not selected.
v16: narrow setup starts GENI SPI (FW register0x102), transport returns success
and PID5940, but FW info is invalid (a0:04, geometry35584x0). The worker stops
and the user reports no touch. This does not establish that SRAM firmware is
missing: even TWRP's later version query fails while the user confirms its touch
works. Initial recovery firmware upload does report FW5/PID5940. Actual recovery
binary trim-table/map confirm event base0x21c00. Do not guess a new base or upload
the available Truly image (file metadata6, observed runtime5; mismatch unresolved).

Patch0018 checks readiness at most20times,100ms apart, and logs reset-state bytes,
short and full FW-info reads and PID. It retains all version/complement/geometry/
PID gates and additionally requires short/full version agreement. SPI transport
failure still stops immediately. This is a bounded diagnostic/retry change,
not a demonstrated fix or permission to reset/upload firmware.

v17 physical result: all20 readiness attempts complete without transport errors,
but short FW bytes mostlya1:06, full info mostly ninezeros/ff/a0:04:a7:cf:8b:00,
PID usually5940 (oneffff). Reset read is also inconsistent. Delay alone did not
produce valid identity. This still does not identify missing firmware as cause.

Patch0019 completes GENI packing setup with SE_GENI_BYTE_GRAN(0x254)=0 for
four8bit words per FIFO entry, matching geni_se_config_packing(8,4,...).
Earlier code set packing vectors but omitted this register. It logs inherited
granularity and reads back the configured granularity, word length, packing,
clock divisor and CS. Whether the inherited value was wrong is not yet measured.
Host MMIO test begins with granularity2 and verifies setup clears it to0.

v18 physical result: inherited granularity already0, configured0/word4/packing
7f8fe,ffefe/MCLK101/CS0. Identity fails like v17; this register was not the cause.
User corrected their initial positive touch reply: there is NO iOS touch success.

Direct recovery validation then captured actual event5 movement and30 raw
checksummed contact packets. The actual XNU decoder accepted all12 saved samples
with matching IDs/coordinates. TWRP touch works despite its metadata query failing.
Longer raw reads expose FW5/1080x2340 at an unexpected offset; that observation
does not justify changing offsets or scanning arbitrary memory to bypass checks.

Vendor nvt_get_fw_info defaults to panel dimensions when metadata is broken;
nvt_update_firmware logs that failure without making the input path contingent
on a valid version response. Patch0020 follows this distinction, preserving
rejection of readable wrong geometry/version and SPI failures. Metadata fallback
also requires the last two PID reads5940 and live motion before HID. Both decoder
and live-motion gate were exercised on real recorded reports locally (dumps
remain ignored). Source:
https://github.com/MiCode/Xiaomi_Kernel_OpenSource/blob/02ca1a919564a9b176a79cce09c40977f833e9ac/drivers/input/touchscreen/NT36672A/nt36xxx_fw_update.c

v19 confirms physical iOS touch delivery: log contains checked movement enabled,
then real SWEET HID finger down/movement/up. First monotonic upward swipe from
(477,2292) to(696,483) splits into7 down segments: invalid packets caused6 early
finger-ups before the valid release at frame126. This explains unreliable swipes;
reliable unlock is not established. Patch0021 discards invalid samples without
ending the gesture, using a100ms absolute-clock deadline to prevent stale held
contacts. Any valid frame refreshes it; valid no-touch and transport failure
still release immediately. Tests exercise short gaps, refreshed deadline,
exact timeout, one release only and immediate real release.

The photographed fade to black is separately consistent with RequestPowerChange0:
v19 logs display off and existing framebuffer code halves pixels on successive
vsyncs while leaving panel power on. No kernel panic or SpringBoard/backboardd
crash appears in the saved log (existing driverkitd sig9 occurs earlier). This
does not identify the exact userspace reason for the power-off request. Test the
next swipe promptly when the clock appears; physical power-key wake remains unported.

v20 physical result (2026-11-20): user confirms the upward swipe opened the next
screen, and explicitly identifies it as the home screen with icons. Basic touch
navigation to the iOS desktop is therefore user-confirmed. Phone remains running
the working v20; no new log/photo was requested at this milestone. This test is
a warm boot from TWRP, not validation of firmware loading after power loss.

Primary register/protocol references (read locally during implementation):
Xiaomi NT36672A and spi-geni-qcom sources, commit
02ca1a919564a9b176a79cce09c40977f833e9ac in
https://github.com/MiCode/Xiaomi_Kernel_OpenSource ; mainline sm6115 pinctrl/GCC
and GENI definitions from Linux05441d697f7f9a927264f4058cbbc6a03dfcac9d.
Local sibling project's corrected stage1-r2 notes also corroborate CS0, pins
and shared rails. Its Linux driver was not evidence of functioning iOS touch.

Validation: `python3 tools/test-lemon-touch.py --xnu <patched-xnu>` compiles
the actual decoder/FIFO/setup/gates with mocked MMIO and ASan/UBSan. It covers
1..67byte duplex and TX-only transfers, partial FIFO words, delayed RX at DONE,
late errors, timeout, malformed/duplicate/out-of-range contacts, all ten contacts,
release, read-only snapshot with gated SE, CS0 setup and default-off initialization.
