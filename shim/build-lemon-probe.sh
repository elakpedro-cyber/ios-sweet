#!/bin/bash
# Raw ARM64 Image only: packaging/boot route on lemon is not validated yet.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p out/lemon-probe
flags=(-O2 -ffreestanding -nostdlib -fno-pic -mgeneral-regs-only -mstrict-align
       -fno-stack-protector -Wall -Wextra -Werror -DLEMON_PROBE)
for src in start.S console.c lemon-probe.c; do
    aarch64-linux-gnu-gcc "${flags[@]}" -c "$src" -o "out/lemon-probe/${src%.*}.o"
done
if aarch64-linux-gnu-readelf -r out/lemon-probe/console.o out/lemon-probe/lemon-probe.o | grep -q ABS64; then
    echo 'error: absolute relocation in position-independent probe' >&2
    exit 1
fi
aarch64-linux-gnu-gcc "${flags[@]}" -static -T shim.ld -Wl,--build-id=none \
    -Wl,--no-warn-rwx-segments -Wl,-N out/lemon-probe/{start,console,lemon-probe}.o \
    -o out/lemon-probe/probe.elf
aarch64-linux-gnu-objcopy -O binary out/lemon-probe/probe.elf out/lemon-probe/Image
size=$(aarch64-linux-gnu-nm out/lemon-probe/probe.elf | awk '$3=="_end"{print "0x"$1}')
truncate -s "$((size))" out/lemon-probe/Image
sha256sum out/lemon-probe/Image
