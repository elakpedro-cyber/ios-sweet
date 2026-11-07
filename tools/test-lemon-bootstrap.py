#!/usr/bin/env python3
"""Run the XNU port's actual mapping macro with MMU on, on QEMU A53/A76."""
import argparse
from pathlib import Path
import struct
import subprocess
import time

ap = argparse.ArgumentParser()
ap.add_argument('--xnu', type=Path, required=True)
args = ap.parse_args()
root = Path(__file__).resolve().parent.parent
out = root / 'shim/out/lemon-mmu-test'
out.mkdir(parents=True, exist_ok=True)
kernel_source = (args.xnu / 'osfmk/arm64/arm_vm_init.c').read_text()
begin = kernel_source.index('static void\nsweet_early_map_final(void)')
end = kernel_source.index('\n}\n', begin) + 3
function = kernel_source[begin:end]
host_source = '''#include <assert.h>
#include <stdint.h>
#define LEMON_4K 1
#include "lemon_fb_map.h"
typedef uint64_t vm_map_address_t;
typedef uint64_t tt_entry_t;
#define SWEET_EARLY_FB_VA 0xffffffe000200000ULL
#define ARM_TT_L2_SIZE 0x200000
#define ARM_TT_L1_INDEX_MASK 0x7fc0000000ULL
#define ARM_TT_L1_SHIFT 30
#define ARM_TT_L2_INDEX_MASK 0x3fe00000
#define ARM_TT_L2_SHIFT 21
#define ARM_TTE_VALID 1
#define ARM_TTE_TYPE_MASK 2
#define ARM_TTE_TYPE_TABLE 2
#define ARM_TTE_TABLE_MASK 0x0000fffffffff000ULL
#define ARM_TTE_EMPTY 0
static tt_entry_t cpu_tte[512], l2[512] __attribute__((aligned(4096)));
static uint64_t gVirtBase = 0xffffffe002000000ULL;
static uintptr_t phystokv(uint64_t address) { return address; }
''' + function.replace('__asm__ volatile("dsb ishst" ::: "memory");', '') + '''
int main(void) {
    cpu_tte[384] = (uintptr_t)l2 | 3;
    cpu_tte[2] = 0x12345603;
    sweet_early_map_final();
    assert(l2[0] == 0 && l2[6] == 0);
    for (unsigned int i=0; i<5; i++)
        assert(l2[i+1] == ((LEMON_FB_BASE + i * 0x200000ULL) | LEMON_FB_BLOCK_FLAGS));
    assert(cpu_tte[2] == 0x12345603);
}
'''
host = out / 'final-map.c'
host.write_text(host_source)
subprocess.run(['gcc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                '-I' + str(args.xnu / 'osfmk/arm64'), str(host),
                '-o', str(out / 'final-map')], check=True)
subprocess.run([str(out / 'final-map')], check=True)
print('Actual XNU final-map C function: all FB blocks and adjacent slots PASS')
subprocess.run(['aarch64-linux-gnu-gcc', '-c', '-DASSEMBLER',
                '-I' + str(args.xnu / 'osfmk'), str(root / 'tools/lemon-mmu-test.S'),
                '-o', str(out / 'test.o')], check=True)
linker = out / 'test.ld'
linker.write_text('ENTRY(_head)\nSECTIONS { . = 0; .text : { *(.text.head) *(.text*) } '
                  '.data : { *(.data*) } .bss : { *(.bss*) } }\n')
subprocess.run(['aarch64-linux-gnu-ld', '-T', str(linker), str(out / 'test.o'),
                '-o', str(out / 'test.elf')], check=True)
symbols = subprocess.check_output(['aarch64-linux-gnu-nm', str(out / 'test.elf')], text=True)
symbols = {line.split()[2]: int(line.split()[0], 16) for line in symbols.splitlines()}
subprocess.run(['aarch64-linux-gnu-objcopy', '-O', 'binary', str(out / 'test.elf'),
                str(out / 'Image')], check=True)
with (out / 'Image').open('r+b') as image:
    image.truncate(symbols['_end'])

load = 0x40200000
fb = 0x5c000000
fb_bytes = 1080 * 2340 * 4
for cpu in ['cortex-a53', 'cortex-a76']:
    paths = [out / f'{cpu}-{name}.bin' for name in ['result', 'tables', 'first', 'last']]
    for path in paths:
        path.unlink(missing_ok=True)
    proc = subprocess.Popen(['qemu-system-aarch64', '-M', 'virt', '-cpu', cpu,
                             '-m', '1024', '-nic', 'none', '-display', 'none',
                             '-serial', 'none', '-monitor', 'stdio',
                             '-kernel', str(out / 'Image'), '-no-reboot'],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True)
    reads = [(load + symbols['result'], 64), (load + symbols['tables'], 34 * 4096),
             (fb, 4), (fb + fb_bytes - 4, 4)]
    commands = 'stop\n' + ''.join(f'pmemsave {addr:#x} {size} "{path}"\n'
                                    for (addr, size), path in zip(reads, paths)) + 'quit\n'
    try:
        time.sleep(1)
        stdout, stderr = proc.communicate(commands, timeout=10)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
    assert proc.returncode == 0, (stdout, stderr)
    result = struct.unpack('<8Q', paths[0].read_bytes())
    assert result[0] == 0x4c454d4f4e4d4d55, (cpu, result, stdout, stderr)
    assert result[2] & 0xfffffffff000 == (fb + fb_bytes - 4) & ~4095
    assert result[3] & 1, 'TTBR0 should be disabled'
    assert struct.unpack('<I', paths[2].read_bytes())[0] == 0x11223344
    assert struct.unpack('<I', paths[3].read_bytes())[0] == 0xaabbccdd
    table = paths[1].read_bytes()
    get = lambda offset: struct.unpack_from('<Q', table, offset)[0]
    pool = load + symbols['tables']
    assert get(8) == pool + 4096 | 3
    assert get(385 * 8) == pool + 4096 | 3
    assert get(384 * 8) == pool + 8192 | 3
    assert get(4096 + 8) == 0x40200701, 'Executable RAM mapping was replaced'
    assert result[4] == pool + 8192, 'Unexpected extra table allocation'
    flags = 0x0060000000000605
    for offset in range(0, (fb_bytes + 0x1fffff) & ~0x1fffff, 0x200000):
        assert get(4096 + ((fb + offset) >> 21 & 511) * 8) == fb + offset | flags
        assert get(8192 + ((0x200000 + offset) >> 21 & 511) * 8) == fb + offset | flags
    print(f'{cpu}: MMU enabled, TTBR0 disabled, all FB blocks and RAM preserved: PASS')
