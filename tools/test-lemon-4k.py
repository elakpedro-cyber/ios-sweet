#!/usr/bin/env python3
"""Check payload layout and XNU page-table constants; not a kernel boot test."""
import argparse
from pathlib import Path
import struct
import subprocess
import tempfile

import adt
import mkadt
import mkpayload

ap = argparse.ArgumentParser()
ap.add_argument('--xnu', type=Path, required=True,
                help='xnu-8796.141.3 with Sweet patches and optional lemon patch')
args = ap.parse_args()

with tempfile.TemporaryDirectory() as temp:
    directory = Path(temp)
    kernel = directory / 'kernel'
    tree = directory / 'test.adt'
    disk = directory / 'root.img'
    vmaddr = 0xfffffff007004000
    macho = bytearray(4096)
    struct.pack_into('<8I', macho, 0, 0xfeedfacf, 0x100000c, 0, 2, 2, 360, 0, 0)
    struct.pack_into('<II16s4Q4I', macho, 32, 0x19, 72, b'__TEXT',
                     vmaddr, 0x5000, 0, len(macho), 7, 5, 0, 0)
    struct.pack_into('<4I', macho, 104, 5, 288, 6, 68)
    struct.pack_into('<Q', macho, 104 + 16 + 32 * 8, vmaddr + 0x1000)
    kernel.write_bytes(macho)
    disk.write_bytes(b'R' * 4097)
    tree.write_bytes(adt.serialize(mkadt.node('device-tree', children=[
        mkadt.node('chosen', [('dram-base', mkadt.u64(0xb0000000)),
                             ('dram-size', mkadt.u64(0x20000000))],
                   [mkadt.node('memory-map')])
    ])))
    default, _ = mkpayload.build(kernel, tree, 'rd=md0', disk)
    explicit, _ = mkpayload.build(kernel, tree, 'rd=md0', disk, 16384)
    assert default == explicit, 'Default Sweet payload changed'
    for page, block in [(4096, 0x200000), (16384, 0x2000000)]:
        blob, info = mkpayload.build(kernel, tree, 'rd=md0', disk, page)
        base, = struct.unpack_from('<Q', blob, 0x10)
        assert base == vmaddr & ~(block - 1)
        assert int(info['kernel_end'], 16) % page == 0
        rd_pa, rd_size = (int(value, 16) for value in info['ramdisk'])
        assert rd_pa % page == 0
        assert rd_size == (4097 + page - 1) & ~(page - 1)
        off, size = struct.unpack_from('<2Q', blob, 0x20)
        parsed, _ = adt.parse(blob[off:off + size])
        mmap = parsed.children[0].children[0]
        assert struct.unpack('<2Q', mmap.prop('RAMDisk')) == (rd_pa, rd_size)
    print('Payload: 4K/16K layout, RAMDisk ADT and default compatibility PASS')

for page, shift, block, tg0, tg1 in [(4096, 12, 0x200000, 0, 2 << 30),
                                    (16384, 14, 0x2000000, 2 << 14, 1 << 30)]:
    source = ('#include <arm64/proc_reg.h>\n#undef __ASSEMBLER__\n'
              '#define KERNEL 1\n#define __has_feature(x) 0\n'
              '#include <mach/arm/vm_param.h>\n')
    for macro, value in [('ARM_PGSHIFT', shift), ('ARM_TT_L2_SIZE', block),
                         ('TCR_TG0_GRANULE_SIZE', tg0), ('TCR_TG1_GRANULE_SIZE', tg1)]:
        source += f'#if {macro} != {value}\n#error wrong {macro}\n#endif\n'
    if page == 4096:
        source += '#include <arm64/lemon_fb_map.h>\n'
        source += ('#if LEMON_FB_BLOCK_FLAGS != (ARM_TTE_TYPE_BLOCK | ARM_TTE_VALID | '
                   'ARM_TTE_BLOCK_SH(SH_OUTER_MEMORY) | '
                   'ARM_TTE_BLOCK_ATTRINDX(CACHE_ATTRINDX_WRITECOMB) | '
                   'ARM_TTE_BLOCK_AF | ARM_TTE_BLOCK_PNX | ARM_TTE_BLOCK_NX)\n'
                   '#error framebuffer attributes differ from XNU\n#endif\n')
        source += '#ifdef __ARM_16K_PG__\n#error 16K macro must be undefined\n#endif\n'
        source += '#if __ARM_PAN_AVAILABLE__\n#error PAN requires separate CPU validation\n#endif\n'
        source += '#if MACH_VM_MAX_ADDRESS_RAW != 0xfc0000000ULL\n#error incorrect mobile VA limit\n#endif\n'
    else:
        source += '#if MACH_VM_MAX_ADDRESS_RAW != 0x7ffffe000000ULL\n#error Sweet VA limit changed\n#endif\n'
    cmd = ['aarch64-linux-gnu-gcc', '-E', '-P', '-x', 'assembler-with-cpp',
           '-D__arm64__', '-D__ASSEMBLER__', '-DASSEMBLER', '-DARM64_BOARD_CONFIG_SWEET',
           '-DXNU_PLATFORM_MacOSX',
           '-I' + str(args.xnu / 'osfmk'), '-I' + str(args.xnu / 'pexpert')]
    if page == 4096:
        cmd.append('-DLEMON_4K')
    subprocess.run(cmd + ['-'], input=source, text=True, stdout=subprocess.DEVNULL, check=True)
    print(f'XNU hardware constants: {page}-byte pages PASS')
