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

Active handoff accepts only the observed FW5/PID5940/1080x2340. It selects the
event pages, reads reports and checks checksum, contact IDs and coordinates;
no chip reset, power change, SRAM firmware/configuration upload or flash write.
Unknown firmware or transport failure stops the worker. Invalid reports release
contacts; initial stale frames do not permanently disable input. Poll20ms, no
GIC interrupt registration. Touch reports use the existing SweetHID service;
LEMON panel height2340 yields a48pixel Y offset into the2436pixel logical display.

First physical test should use snapshot mode and read the small persistent log
after returning TWRP. The same kernel contains active mode for a subsequent
boot; successful offline tests are not proof of physical input support.

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
