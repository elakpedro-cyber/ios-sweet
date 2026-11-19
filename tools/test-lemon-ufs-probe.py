"""Compile the actual opt-in diagnostic with mock read-only controller memory."""
import argparse
from pathlib import Path
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--xnu', type=Path, required=True)
args = parser.parse_args()
source = (args.xnu / 'bsd/dev/sweet_ufs.c').read_text()
start = source.index('#if defined(LEMON_4K)', source.index('sweet_ufs_init(void)'))
body = source[start:source.index('#endif', start)] + '#endif\n'
io = (args.xnu / 'iokit/bsddev/IOKitBSDInit.cpp').read_text()
start = io.index('#if defined(LEMON_4K)', io.index('//\tSWEET: root on a GPT'))
hook = io[start:io.index('#endif', start)] + '#endif\n'
test = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#define LEMON_4K 1
#define REG_CAP 0
#define REG_HCE 0x34
#define REG_HCS 0x30
#define REG_UTRLDBR 0x58
#define REG_UTRLRSR 0x60
typedef uintptr_t vm_offset_t;
typedef int dev_t;
static uint32_t regs[0x3000/4], saved[0x3000/4], option, read_option, root_option;
static int maps, calls, fail_mapping;
static bool lemon_ufs_root;
static void PE_parse_boot_argn(const char *key, uint32_t *p, unsigned size) {
    assert(size == 4);
    if (!strcmp(key, "lemonufsread")) { *p = read_option; return; }
    if (!strcmp(key, "lemonufsroot")) { *p = root_option; return; }
    assert(!strcmp(key, "lemonufsprobe")); *p = option;
}
static vm_offset_t ml_io_map(uintptr_t base, unsigned size) {
    assert(base == 0x04804000 && size == 0x3000);
    maps++; return fail_mapping ? 0 : (uintptr_t)regs;
}
static int probe(void) {
BODY
    return 0;
}
int sweet_ufs_rootdev(dev_t *unused) { (void)unused; calls++; return probe(); }
static void root_hook(void) {
HOOK
}
int main(void) {
    for (unsigned i=0; i<sizeof(regs)/sizeof(*regs); i++) regs[i] = i+1;
    memcpy(saved, regs, sizeof(regs));
    option=0; root_hook(); assert(maps==0 && calls==0);
    option=2; root_hook(); assert(maps==0 && calls==0);
    option=1; root_hook(); assert(maps==1 && calls==1);
    assert(!memcmp(regs, saved, sizeof(regs)));
    fail_mapping=1; root_hook(); assert(maps==2 && calls==2);
    assert(!memcmp(regs, saved, sizeof(regs)));
    option=0; root_option=2; assert(probe()==ENXIO && !lemon_ufs_root);
    root_option=1; assert(probe()==0 && lemon_ufs_root);
    root_option=0; read_option=1; assert(probe()==0 && !lemon_ufs_root);
    assert(maps==2 && !memcmp(regs, saved, sizeof(regs)));
    puts("PASS: opt-in hook, exact MMIO range, no register writes, mapping failure");
}
'''.replace('BODY', body).replace('HOOK', hook)
with tempfile.TemporaryDirectory() as folder:
    c, binary = Path(folder) / 'probe.c', Path(folder) / 'probe'
    c.write_text(test)
    subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=address,undefined', str(c), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
