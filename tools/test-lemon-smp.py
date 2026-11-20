"""Test the opt-in lemon SMP topology: kernel MPIDR rule and 8-CPU ADT."""
import argparse
from pathlib import Path
import re
import struct

import adt
import lemon_smp_adt
import mkadt

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--xnu', type=Path, help='patched XNU source tree')
parser.add_argument('--adt', type=Path, help='real single-CPU phone ADT to expand')
args = parser.parse_args()

# Kernel: the lemon validation accepts exactly SM6115's eight MPIDRs.
lemon_ok = lambda mpidr: (mpidr & ~0x103) == 0
assert [m for m in range(0x10000) if lemon_ok(m)] == sorted(lemon_smp_adt.LEMON_SMP_MPIDRS)
if args.xnu:
    x = args.xnu
    cpu = (x / 'iokit/Kernel/arm/SweetCPU.cpp').read_text()
    rule = re.search(r'#if defined\(LEMON_4K\)\s*/\*.*?\*/\s*if \(\(cpu->phys_id & ~0x103U\) != 0 \|\|', cpu, re.S)
    assert rule, 'lemon MPIDR rule missing'
    assert 'withCStringNoCopy("Kryo 260")' in cpu
    assert '(((mpidr >> 8) & 0xff) << 16)' in cpu, 'SGI must route by target Aff1'
    start = (x / 'osfmk/arm64/start.s').read_text()
    assert re.search(r'#if HAS_CLUSTER \|\| defined\(SWEET\)\s*and\s+x0, x15, #0xFFFF', start)
    mr = (x / 'osfmk/arm64/machine_routines.c').read_text()
    assert re.search(r'if \(!cpus_boot_arg_present \|\| cpu_boot_arg == 0\) \{\s*cpu_boot_arg = 1;', mr), \
        'SMP must stay opt-in'
    assert 'phys_id &= MPIDR_AFF1_MASK | MPIDR_AFF0_MASK;' in mr
    fiq = (x / 'pexpert/arm/pe_fiq.c').read_text()
    assert '& (MPIDR_AFF1_MASK | MPIDR_AFF0_MASK);' in fiq, 'GICR lookup must match Aff1:Aff0'
    assert '#define SWEET_SMP_MAX_CPUS         8' in (x / 'pexpert/pexpert/arm64/SWEET.h').read_text()

# ADT: only /cpus changes, order is boot A53, four A73s, three A53s.
sources = [adt.serialize(mkadt.build(seed=b'x' * 64, lemon=True, lemon_perf=True))]
if args.adt:
    sources.append(args.adt.read_bytes())
for original in sources:
    tree, _ = adt.parse(original)
    expanded = lemon_smp_adt.expand(tree)
    new, _ = adt.parse(expanded)
    old, _ = adt.parse(original)
    cpus = next(n for n in new.children if n.name == 'cpus')
    regs = [struct.unpack('<I', n.prop('reg'))[0] for n in cpus.children]
    assert tuple(regs) == lemon_smp_adt.LEMON_SMP_MPIDRS
    assert [n.name for n in cpus.children] == [f'cpu{i}' for i in range(8)]
    states = [n.prop('state') for n in cpus.children]
    assert states == [b'running\0'] + [b'stopped\0'] * 7
    handles = []
    def walk(node):
        handles.append(node.prop('AAPL,phandle'))
        for child in node.children:
            walk(child)
    walk(new)
    assert len(handles) == len(set(handles)), 'duplicate phandles'
    old_cpus = next(n for n in old.children if n.name == 'cpus')
    assert adt.serialize(cpus.children[0]) == adt.serialize(old_cpus.children[0])
    cpus.children = old_cpus.children
    assert adt.serialize(new) == original, 'only /cpus may change'
print('PASS: lemon MPIDR rule, opt-in SMP, Aff1:Aff0 routing, 8-CPU ADT (only /cpus changed)')
