"""Read-only userdata HFS image through TWRP ADB (run nbdkit -r in WSL).

nbdkit -r -f -U /home/hadirpc/lemon-root.sock python tools/lemon-adb-nbd.py
guestfish --ro --format=raw -a 'nbd://?socket=/home/hadirpc/lemon-root.sock' -m /dev/sda:/:ro:hfsplus
"""
from functools import lru_cache
from pathlib import Path
import subprocess

API_VERSION = 2
SIZE = 16 << 30
BLOCK = 8 << 20
ADB = str(Path(__file__).resolve().parents[2] / 'platform-tools/adb.exe')


def command(serial, *args):
    return subprocess.check_output([ADB, '-s', serial, *args])


def open(readonly):
    if not readonly:
        raise RuntimeError('This export must be opened read-only (nbdkit -r)')
    serial = subprocess.check_output([ADB, 'get-serialno']).decode().strip()
    if command(serial, 'get-state').decode().strip() != 'recovery':
        raise RuntimeError('TWRP required')
    if command(serial, 'shell', 'readlink -f /dev/block/by-name/userdata').decode().strip() != '/dev/block/sda11':
        raise RuntimeError('Unexpected userdata device')
    if command(serial, 'shell', 'blockdev --getsize64 /dev/block/by-name/userdata').decode().strip() != '50573750272':
        raise RuntimeError('Unexpected userdata size')
    return serial


def get_size(handle):
    return SIZE


@lru_cache(maxsize=8)
def block(serial, index):
    sectors = BLOCK // 4096
    data = command(serial, 'exec-out',
                   f'dd if=/dev/block/sda11 bs=4096 skip={index*sectors} count={sectors} status=none')
    if len(data) != BLOCK:
        raise RuntimeError(f'Short binary ADB read: {len(data)} bytes')
    return data


def pread(handle, buf, offset, flags):
    if offset < 0 or offset+len(buf) > SIZE:
        raise ValueError('Read outside installed root image')
    done = 0
    while done < len(buf):
        index, inside = divmod(offset+done, BLOCK)
        count = min(len(buf)-done, BLOCK-inside)
        buf[done:done+count] = block(handle, index)[inside:inside+count]
        done += count
