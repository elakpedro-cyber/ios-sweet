#!/usr/bin/env python3
"""Validate the minimal ADT and, optionally, its RAM against a saved live FDT."""
import argparse
import struct
import subprocess
import mkadt

ap = argparse.ArgumentParser()
ap.add_argument('--fdt', help='saved lemon live FDT, read with fdtget')
args = ap.parse_args()
def child(node, name):
    return next(c for c in node.children if c.name == name)
def qwords(value):
    return struct.unpack('<' + 'Q' * (len(value) // 8), value)

for qemu in [False, True]:
    root = mkadt.build(seed=b'\0' * 64, lemon=True, qemu=qemu)
    chosen = child(root, 'chosen')
    base, = qwords(chosen.prop('dram-base'))
    size, = qwords(chosen.prop('dram-size'))
    assert (base, size) == (0x100000000, 0x1fe00000)
    assert size % 0x200000 == 0
    pram = qwords(child(root, 'pram').prop('reg'))
    assert pram == (base + size, 0x200000)
    cpus = child(root, 'cpus').children
    assert len(cpus) == 1 and cpus[0].prop('reg') == mkadt.u32(0)
    assert not any(n.name == 'sweet-ufs' for n in root.children)
    fb = child(root, 'sweet-fbcon')
    assert qwords(fb.prop('reg')) == (0x5c000000, 0xf00000)
    assert fb.prop('height') == mkadt.u32(2340)
    gic = child(child(root, 'arm-io'), 'gic')
    regs = qwords(gic.prop('reg'))
    expected = (0x08000000, 0x080a0000) if qemu else (0x0f200000, 0x0f300000)
    assert (regs[0] + mkadt.SOC_BASE, regs[2] + mkadt.SOC_BASE) == expected
    assert gic.prop('virtual-timer-intid') == mkadt.u32(27 if qemu else 19)
print('Minimal lemon ADT: RAM, panic region, one CPU, display, GIC and no UFS PASS')

if args.fdt:
    def get(path, property):
        result = subprocess.run(['fdtget', '-tx', args.fdt, path, property],
                                capture_output=True, text=True)
        return [int(v, 16) for v in result.stdout.split()] if result.returncode == 0 else []
    def ranges(cells):
        assert len(cells) % 4 == 0
        return [(cells[i] << 32 | cells[i+1], cells[i+2] << 32 | cells[i+3])
                for i in range(0, len(cells), 4)]
    end = base + size + pram[1]
    assert any(lo <= base and end <= lo + length for lo, length in ranges(get('/memory', 'reg')))
    nodes = subprocess.check_output(['fdtget', '-l', args.fdt, '/reserved-memory'], text=True).split()
    for name in nodes:
        path = '/reserved-memory/' + name
        for lo, length in ranges(get(path, 'reg')):
            assert end <= lo or base >= lo + length, (name, hex(lo), hex(length))
        if get(path, 'size'):
            alloc = ranges(get(path, 'alloc-ranges'))
            assert alloc, f'unbounded dynamic reservation: {name}'
            assert all(end <= lo or base >= lo + length for lo, length in alloc), name
    print('Saved live FDT: selected RAM and panic buffer avoid static/dynamic reservations PASS')
