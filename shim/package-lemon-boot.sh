#!/bin/bash
set -euo pipefail
mkbootimg=$(realpath "${1:?Pass AOSP mkbootimg.py}")
payload=$(realpath "${2:?Pass the lemon phone payload}")
cd "$(dirname "$0")"
test -s ../dtb/boot-current/dtb
bash build-lemon-boot.sh
gzip -n -c out/lemon-boot/Image > out/lemon-boot/Image.gz
# The payload nearly fills 16 MiB: the old 31 MiB DTB address would overlap it.
python3 "$mkbootimg" --header_version 2 --os_version 11.0.0 \
    --os_patch_level 2023-03 --pagesize 4096 --base 0 \
    --kernel_offset 0x8000 --ramdisk_offset 0x1000000 --tags_offset 0x100 \
    --dtb_offset 0x3000000 --kernel out/lemon-boot/Image.gz \
    --ramdisk "$payload" --dtb ../dtb/boot-current/dtb \
    --cmdline 'console=null' --output out/lemon-boot/boot-lemon-xnu-test.img
sha256sum out/lemon-boot/boot-lemon-xnu-test.img
