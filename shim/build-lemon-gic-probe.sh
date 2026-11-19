#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
out=out/lemon-gic
flags=(-O2 -mcpu=cortex-a53 -march=armv8-a+crypto -ffreestanding -nostdlib
       -fno-pic -mgeneral-regs-only -mstrict-align -fno-stack-protector
       -Wall -Wextra -Werror -DLEMON_PROBE)
if [ "${1:-}" = --qemu ] || [ "${1:-}" = --qemu-ppi19 ]; then
    out=out/lemon-gic-qemu
    flags+=(-DLEMON_GIC_QEMU)
    if [ "$1" = --qemu-ppi19 ]; then
        out=out/lemon-gic-qemu-ppi19
        flags+=(-DLEMON_GIC_TEST_PPI19)
    fi
fi
mkdir -p "$out"
for src in start.S console.c lemon-gic-probe.c; do
    aarch64-linux-gnu-gcc "${flags[@]}" -c "$src" -o "$out/${src%.*}.o"
done
if aarch64-linux-gnu-readelf -r "$out/console.o" "$out/lemon-gic-probe.o" | grep -q ABS64; then
    echo 'error: absolute relocation in GIC probe' >&2
    exit 1
fi
aarch64-linux-gnu-gcc "${flags[@]}" -static -T shim.ld -Wl,--build-id=none \
    -Wl,--no-warn-rwx-segments -Wl,-N "$out"/{start,console,lemon-gic-probe}.o -o "$out/probe.elf"
aarch64-linux-gnu-objcopy -O binary "$out/probe.elf" "$out/Image"
size=$(aarch64-linux-gnu-nm "$out/probe.elf" | awk '$3=="_end"{print "0x"$1}')
truncate -s "$((size))" "$out/Image"
