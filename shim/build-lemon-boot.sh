#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p out/lemon-boot
flags=(-O2 -mcpu=cortex-a53 -march=armv8-a+crypto -ffreestanding -nostdlib
       -fno-pic -mgeneral-regs-only -mstrict-align -fno-stack-protector
       -Wall -Wextra -Werror -DLEMON_BOOT)
objects=()
for src in start.S console.c fdt.c loader.c lemon-boot.c; do
    object="out/lemon-boot/${src%.*}.o"
    aarch64-linux-gnu-gcc "${flags[@]}" -c "$src" -o "$object"
    objects+=("$object")
done
if aarch64-linux-gnu-readelf -r "${objects[@]:1}" | grep -q ABS64; then
    echo 'error: absolute relocation in position-independent loader' >&2
    exit 1
fi
aarch64-linux-gnu-gcc "${flags[@]}" -static -T shim.ld -Wl,--build-id=none \
    -Wl,--no-warn-rwx-segments -Wl,-N "${objects[@]}" -o out/lemon-boot/loader.elf
aarch64-linux-gnu-objcopy -O binary out/lemon-boot/loader.elf out/lemon-boot/Image
size=$(aarch64-linux-gnu-nm out/lemon-boot/loader.elf | awk '$3=="_end"{print "0x"$1}')
truncate -s "$((size))" out/lemon-boot/Image
