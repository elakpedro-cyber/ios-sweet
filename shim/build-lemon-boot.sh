#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
out=${1:-out/lemon-boot}
mkdir -p "$out"
flags=(-O2 -mcpu=cortex-a53 -march=armv8-a+crypto -ffreestanding -nostdlib
       -fno-pic -mgeneral-regs-only -mstrict-align -fno-stack-protector
       -Wall -Wextra -Werror -DLEMON_BOOT)
objects=()
for src in start.S console.c fdt.c loader.c lemon-boot.c; do
    object="$out/${src%.*}.o"
    aarch64-linux-gnu-gcc "${flags[@]}" -c "$src" -o "$object"
    objects+=("$object")
done
if aarch64-linux-gnu-readelf -r "${objects[@]:1}" | grep -q ABS64; then
    echo 'error: absolute relocation in position-independent loader' >&2
    exit 1
fi
aarch64-linux-gnu-gcc "${flags[@]}" -static -T shim.ld -Wl,--build-id=none \
    -Wl,--no-warn-rwx-segments -Wl,-N "${objects[@]}" -o "$out/loader.elf"
aarch64-linux-gnu-objcopy -O binary "$out/loader.elf" "$out/Image"
size=$(aarch64-linux-gnu-nm "$out/loader.elf" | awk '$3=="_end"{print "0x"$1}')
truncate -s "$((size))" "$out/Image"
