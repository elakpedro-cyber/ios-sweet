#!/bin/bash
# Package with the DTB from the currently installed, previously booted Linux.
set -euo pipefail
cd "$(dirname "$0")"
mkbootimg=${1:?Pass the path to AOSP mkbootimg.py}
test -s ../dtb/boot-current/dtb
bash build-lemon-probe.sh
gzip -n -c out/lemon-probe/Image > out/lemon-probe/Image.gz
printf '' | cpio -o -H newc --quiet | gzip -n > out/lemon-probe/ramdisk.gz
python3 "$mkbootimg" --header_version 2 --os_version 11.0.0 \
    --os_patch_level 2023-03 --pagesize 4096 --base 0 \
    --kernel_offset 0x8000 --ramdisk_offset 0x1000000 --tags_offset 0x100 \
    --dtb_offset 0x1f00000 --kernel out/lemon-probe/Image.gz \
    --ramdisk out/lemon-probe/ramdisk.gz --dtb ../dtb/boot-current/dtb \
    --cmdline 'console=null' --output out/lemon-probe/boot-lemon-cpu-probe.img
sha256sum out/lemon-probe/boot-lemon-cpu-probe.img
