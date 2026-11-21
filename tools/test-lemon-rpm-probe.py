"""Test actual read-only RPM TOC/FIFO parser against invalid MMIO layouts."""
import argparse
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--xnu', type=Path, required=True)
tree = parser.parse_args().xnu
source = (tree / 'bsd/dev/lemon_rpm.c').read_text()
assert 'bsd/dev/lemon_rpm.c' in (tree / 'bsd/conf/files').read_text()
source = re.sub(r'^#include <[^>]+>\n', '', source, flags=re.M)
header = '''
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <assert.h>
#include <string.h>
#define ARM64_BOARD_CONFIG_SWEET 1
#define LEMON_4K 1
typedef uintptr_t vm_offset_t, vm_size_t;
extern void delay(int);
'''
test = r'''
static uint32_t memory[LR_SIZE/4], saved[LR_SIZE/4];
static unsigned map_fail;
void delay(int us) {(void)us;assert(!"snapshot must not poll");}
vm_offset_t ml_io_map(vm_offset_t pa,vm_size_t size) {
    assert(pa==LR_PA && size==LR_SIZE);return map_fail?0:(uintptr_t)memory;
}
static void setup(void) {
    memset(memory,0,sizeof(memory));
    memory[LR_TOC/4]=0x67727430;memory[LR_TOC/4+1]=2;
    unsigned t=LR_TOC/4+2;
    memory[t]=LR_TX;memory[t+1]=0x100;memory[t+2]=0x100;
    memory[t+3]=LR_RX;memory[t+4]=0x300;memory[t+5]=0x100;
}
static bool parse(void) {
    struct lr_pipe tx={0},rx={0};return lr_parse((uintptr_t)memory,&tx,&rx);
}
int main(void) {
    setup();assert(parse());
    memcpy(saved,memory,sizeof(memory));lemon_rpm_snapshot();assert(!memcmp(saved,memory,sizeof(memory)));
    memory[LR_TOC/4]=0;assert(!parse());
    setup();memory[LR_TOC/4+1]=21;assert(!parse());
    setup();memory[LR_TOC/4+5]=LR_TX;assert(!parse());
    setup();memory[LR_TOC/4+6]=0x180;assert(!parse());
    setup();memory[LR_TOC/4+3]=0xfffffffc;assert(!parse());
    setup();memory[LR_TOC/4+4]=0xfffffff8;assert(!parse());
    setup();memory[LR_TOC/4+4]=15;assert(!parse());
    setup();memory[LR_TOC/4+3]=LR_TOC-8;assert(!parse());
    setup();
    struct lr_pipe p={0x100,0x100};
    memory[0x100/4]=0xf8;memory[0x104/4]=0x18;
    memcpy(saved,memory,sizeof(memory));assert(lr_snapshot_pipe((uintptr_t)memory,"wrap",p));
    assert(!memcmp(saved,memory,sizeof(memory)));
    memory[0x100/4]=0x100;assert(!lr_snapshot_pipe((uintptr_t)memory,"bad",p));
    memory[0x100/4]=4;assert(!lr_snapshot_pipe((uintptr_t)memory,"bad",p));
    map_fail=1;lemon_rpm_snapshot();
    puts("PASS: RPM TOC bounds/overflow/duplicates/overlap, FIFO indices/wrap, no writes, mapping failure");
}
'''
with tempfile.TemporaryDirectory() as directory:
    folder = Path(directory)
    full = folder / 'full.c'
    full.write_text(header + source)
    mock = re.sub(r'^\s*__asm__ volatile\([^\n]+\);', '', source, flags=re.M)
    (folder / 'test.c').write_text(header + mock + test)
    flags = ['-std=c11', '-Wall', '-Wextra', '-Werror']
    subprocess.run(['cc', *flags, '-fsanitize=address,undefined', str(folder/'test.c'), '-o', str(folder/'test')], check=True)
    subprocess.run([str(folder/'test')], check=True)
    cross = shutil.which('aarch64-linux-gnu-gcc')
    if cross:
        subprocess.run([cross, *flags, '-mcpu=cortex-a53', '-march=armv8-a+crypto', '-mno-outline-atomics',
                        '-c', str(full), '-o', str(folder/'arm64.o')], check=True)
        print('PASS: RPM snapshot ARMv8.0 cross-compile')
