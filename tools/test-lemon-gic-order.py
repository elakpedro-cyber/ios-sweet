#!/usr/bin/env python3
"""Run actual setup code against GICR RAZ/WI semantics while ARE_NS is off."""
import argparse
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser()
ap.add_argument('--source', type=Path, default=root / 'shim/lemon-gic-probe.c')
args = ap.parse_args()
text = args.source.read_text()
begin = text.index('\tstage = "GIC setup";')
end = text.index('\tcon_hex("R GROUP"', begin)
setup = text[begin:end].replace('__asm__ volatile("dsb sy; isb" ::: "memory");', '(void)0;')
setup = setup.replace('__asm__ volatile("isb" ::: "memory");', '(void)0;')
source = r'''#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#define GICD 0x0f200000UL
#define SGI 1
#define VTIMER 19
static uintptr_t redistributor = 0x0f300000UL;
static const char *stage;
static uint32_t ctl, enabled, ignored;
static uint32_t rd32(uintptr_t address) {
    if (address == GICD) return ctl;
    return 0;
}
static void wr32(uintptr_t address, uint32_t value) {
    if (address == GICD) {
        /* Never transition ARE_NS 1 -> 0, or change it while groups enabled. */
        assert(!(ctl & 0x10) || (value & 0x10));
        assert(!((ctl ^ value) & 0x10) || !(ctl & 3));
        ctl = value;
    } else if (address == redistributor + 0x10080 || address == redistributor + 0x10100) {
        if (!(ctl & 0x10)) ignored++;
        else if (address == redistributor + 0x10100) enabled |= value;
    }
}
static int wait_clear(uintptr_t address, uint32_t mask) {
    return !(rd32(address) & mask);
}
static uint64_t rsr(const char *name) { (void)name; return 0; }
static void wsr(const char *name, uint64_t value) { (void)name; (void)value; }
static void con_str(const char *label, const char *message) { (void)label; (void)message; }
static void halt(void) { abort(); }
int main(void) {
    const unsigned states[] = {0, 0x10, 0x13};
    for (unsigned i = 0; i < 3; i++) {
        ctl = states[i]; enabled = ignored = 0;
''' + setup + r'''
        assert(stage != 0);
        assert(ignored == 0);
        assert(enabled == ((1U << SGI) | (1U << VTIMER)));
        assert((ctl & 0x13) == 0x13);
    }
}
'''
with tempfile.TemporaryDirectory() as directory:
    path = Path(directory)
    (path / 'order.c').write_text(source)
    subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                    str(path / 'order.c'), '-o', str(path / 'order')], check=True)
    subprocess.run([str(path / 'order')], check=True)
print('Actual GIC setup: ARE-off, ARE-on and groups-enabled reset states PASS')
