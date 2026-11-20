"""Check Pixel3 CoreAnimation hook targets against an existing local iOS cache."""
import argparse
from pathlib import Path
import re
import struct

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('cache', type=Path)
args = parser.parse_args()
source = (Path(__file__).resolve().parents[1] / 'gpu/pixel3/eagl-ios/src/blueeagl.c').read_text()
constants = {k: int(v, 16) for k, v in re.findall(r'#define\s+(\w+)\s+(0x[0-9a-f]+)UL', source)}
maps = []
for path in sorted(args.cache.glob('dyld_shared_cache_arm64*')):
    if path.name.endswith('.symbols'):
        continue
    with path.open('rb') as f:
        header = f.read(4096)
        assert header[:16] == b'dyld_v1   arm64\0'
        table, count = struct.unpack_from('<II', header, 0x138)
        assert count < 100 and table + count * 56 <= len(header)
        for i in range(count):
            address, size, offset, slide, slide_size, flags, maxprot, prot = struct.unpack_from('<6Q2I', header, table + i*56)
            maps.append((address, size, offset, slide, path))

for name, table, slot, expect in (
    ('renderer', 'VT_EAGL_SERVER', 0x1a0, 'EXPECT_RENDERER'),
    ('render_update', 'VT_EAGL_SERVER', 0x178, 'EXPECT_RENDER_UPDATE'),
    ('function_supported', 'VT_GLES_CONTEXT', 0x378, 'EXPECT_FUNCTION_SUPP'),
    ('function_uniform', 'VT_GLES_CONTEXT', 0x388, 'EXPECT_FUNCTION_UNIF'),
    ('compile_shader', 'VT_GLES_CONTEXT', 0x60, 'EXPECT_COMPILE_SHADER'),
):
    at = constants[table] + 0x10 + slot
    base, size, offset, slide, path = next(m for m in maps if m[0] <= at < m[0] + m[1])
    with path.open('rb') as f:
        f.seek(slide)
        info = f.read(40)
        assert slide and struct.unpack_from('<I', info)[0] == 2, 'only the target arm64 slide-info2 format is supported'
        mask, add = struct.unpack_from('<QQ', info, 24)
        f.seek(offset + at - base)
        raw, = struct.unpack('<Q', f.read(8))
    value = raw & (~mask & ((1 << 64) - 1))
    if value:
        value += add
    assert value == constants[expect], f'{name}: {value:#x} != {constants[expect]:#x}'
    print('MATCH', name, hex(value))
print('PASS: all five donor hook targets match the decoded local cache; no cache files changed')
