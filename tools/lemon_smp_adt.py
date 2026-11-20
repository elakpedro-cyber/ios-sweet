"""Expand a single-CPU lemon ADT to all eight SM6115 cores.

Only /cpus changes. Node order decides which cores cpus=N selects:
cpu0 is the boot Cortex-A53 (MPIDR 0x000), cpu1-4 the Cortex-A73 cluster
(0x100-0x103), cpu5-7 the other A53s (0x001-0x003). cpus=5 therefore runs
the boot core plus the four big cores. The kernel still defaults to cpus=1.
"""
import struct

import adt

# SM6115 live FDT cpu@ reg values in the order exposed to XNU.
LEMON_SMP_MPIDRS = (0x000, 0x100, 0x101, 0x102, 0x103, 0x001, 0x002, 0x003)
A53_HZ, A73_HZ = 1804800000, 2000000000


def _u32(value):
    return struct.pack('<I', value)


def _max_phandle(node):
    value = node.prop('AAPL,phandle')
    best = struct.unpack('<I', value)[0] if value is not None else 0
    for child in node.children:
        best = max(best, _max_phandle(child))
    return best


def expand(tree):
    """Return a new ADT byte string; tree is modified in place."""
    cpus = next(n for n in tree.children if n.name == 'cpus')
    if len(cpus.children) != 1:
        raise ValueError('expected the single-CPU lemon /cpus node')
    boot = cpus.children[0]
    if boot.prop('reg') != _u32(0) or boot.prop('compatible') != b'qcom,kryo260\0ARM,v8\0':
        raise ValueError('cpu0 is not the lemon boot A53 (MPIDR 0)')
    phandle = _max_phandle(tree)
    nodes = []
    for index, mpidr in enumerate(LEMON_SMP_MPIDRS):
        node = adt.Node()
        overrides = {
            'name': f'cpu{index}'.encode() + b'\0',
            'reg': _u32(mpidr),
            'cpu-id': _u32(index),
            'cluster-core-id': _u32(mpidr & 0xff),
            'l2-cache-id': _u32(mpidr >> 8),
            'state': b'running\0' if index == 0 else b'stopped\0',
            'clock-frequency': _u32(A73_HZ if mpidr >> 8 else A53_HZ),
        }
        if index:
            phandle += 1
            overrides['AAPL,phandle'] = _u32(phandle)
        node.props = [(k, f, overrides.get(k, v)) for k, f, v in boot.props]
        nodes.append(node)
    if adt.serialize(nodes[0]) != adt.serialize(boot):
        raise AssertionError('boot CPU node must stay byte-identical')
    cpus.children = nodes
    return adt.serialize(tree)
