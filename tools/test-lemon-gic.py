#!/usr/bin/env python3
"""Verify actual EL1 SGI/timer delivery in the standalone lemon probe on A53."""
from pathlib import Path
import struct
import subprocess
import time

root = Path(__file__).resolve().parent.parent
for option, directory in [('--qemu', 'lemon-gic-qemu'), ('--qemu-ppi19', 'lemon-gic-qemu-ppi19')]:
    subprocess.run(['bash', 'build-lemon-gic-probe.sh', option], cwd=root / 'shim', check=True)
    out = root / 'shim/out' / directory
    image = (out / 'Image').read_bytes()
    assert image[56:60] == b'ARM\x64'
    assert struct.unpack_from('<Q', image, 16)[0] == len(image)
    symbols = subprocess.check_output(['aarch64-linux-gnu-nm', str(out / 'probe.elf')], text=True)
    offset = next(int(line.split()[0], 16) for line in symbols.splitlines()
                  if line.endswith(' lemon_gic_result'))
    dump = out / 'result.bin'
    dump.unlink(missing_ok=True)
    p = subprocess.Popen(['qemu-system-aarch64', '-M', 'virt,gic-version=3',
                          '-cpu', 'cortex-a53', '-m', '1024', '-nic', 'none',
                          '-kernel', str(out / 'Image'), '-display', 'none',
                          '-serial', 'none', '-monitor', 'stdio', '-no-reboot'],
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         text=True)
    try:
        time.sleep(2)
        stdout, stderr = p.communicate(
            f'stop\npmemsave {0x40200000 + offset:#x} 80 "{dump}"\nquit\n', timeout=10)
    finally:
        if p.poll() is None:
            p.kill()
            p.wait()
    assert p.returncode == 0, (stdout, stderr)
    result = struct.unpack('<10Q', dump.read_bytes())
    assert result[0] == 0x4c454d4f4e474943, result
    assert result[1] & 0xffff == 0, result
    assert result[2] >= 3 and result[3] == 1, result
    assert result[4] == 0 and result[5] == 27 and result[9] == 27, result
    assert result[6] & 1 and result[7] >= 62500000 // 5, result
    if option == '--qemu-ppi19':
        assert result[8] == 0 and result[7] >= 2 * (62500000 // 5), result
    else:
        assert result[8] >= 3, result
    print(f'A53 {option}: SGI1={result[3]}, timer IRQ27={result[2]}, first-phase={result[8]} PASS')
