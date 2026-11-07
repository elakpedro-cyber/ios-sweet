#!/usr/bin/env python3
"""Check the raw probe in QEMU; this does not establish phone CPU support."""
import gzip
from pathlib import Path
import struct
import subprocess
import time

root = Path(__file__).resolve().parent.parent
out = root / 'shim/out/lemon-probe'
image = (out / 'Image').read_bytes()
assert image[56:60] == b'ARM\x64'
assert struct.unpack_from('<Q', image, 16)[0] == len(image)
assert gzip.decompress((out / 'unpacked/kernel').read_bytes()) == image
assert (out / 'unpacked/dtb').read_bytes() == (root / 'dtb/boot-current/dtb').read_bytes()
symbols = subprocess.check_output(
    ['aarch64-linux-gnu-nm', str(out / 'probe.elf')], text=True)
offset = next(int(line.split()[0], 16) for line in symbols.splitlines()
              if line.endswith(' lemon_mmfr0'))
for cpu, expected in [('cortex-a53', 0), ('cortex-a76', 1)]:
    dump = out / f'{cpu}-mmfr0.bin'
    dump.unlink(missing_ok=True)
    proc = subprocess.Popen(
        ['qemu-system-aarch64', '-M', 'virt', '-cpu', cpu, '-m', '1024', '-nic', 'none',
         '-kernel', str(out / 'Image'), '-display', 'none', '-serial', 'none',
         '-monitor', 'stdio', '-no-reboot'],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True)
    try:
        time.sleep(2)
        stdout, stderr = proc.communicate(
            # QEMU virt places this text_offset=0 Image at the next 2 MiB boundary.
            f'stop\npmemsave {0x40200000 + offset:#x} 8 "{dump}"\nquit\n',
            timeout=10)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
    assert proc.returncode == 0, (stdout, stderr)
    mmfr0, = struct.unpack('<Q', dump.read_bytes())
    assert mmfr0 != 0, 'Probe did not save a register value'
    gran16 = (mmfr0 >> 20) & 15
    assert gran16 == expected, (cpu, hex(mmfr0), gran16)
    print(f'{cpu}: MMFR0={mmfr0:#x}, TGran16={gran16}: PASS')
print('Image header, packaged kernel and DTB: PASS')
