#!/usr/bin/env python3
"""Exercise actual pe_init_fiq against ARE-gated private interrupt registers."""
import argparse
from pathlib import Path
import subprocess
import tempfile

ap = argparse.ArgumentParser()
ap.add_argument('--xnu', type=Path, required=True)
args = ap.parse_args()
text = (args.xnu / 'pexpert/arm/pe_fiq.c').read_text()

def function(signature):
    start = text.index(signature)
    return text[start:text.index('\n}\n', start) + 3]

helper = function('static void\nlemon_gicd_write_ctlr(') if 'lemon_gicd_write_ctlr' in text else ''
setup = function('void\npe_init_fiq()')
source = r'''#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <setjmp.h>
#define LEMON_4K 1
#include <pexpert/arm64/SWEET.h>
#define GICR_WAKE_TIMEOUT_NS 1000000000ULL
#define DSB_SY 15
#define ISB_SY 15
#define kSuccess 0
#define os_atomic_load(p, order) (*(p))
typedef uintptr_t vm_offset_t;
typedef int DTEntry;
static vm_offset_t gicd_base, gicr_base, gicr_size;
static uint64_t gicr_wake_timeout_ns = GICR_WAKE_TIMEOUT_NS;
static uint32_t sweet_vtimer_intid = SWEET_VTIMER_INTID;
static uint32_t ctl, enabled, ignored, group1;
static int stuck, expect_panic;
static uint64_t clock_value;
static jmp_buf panic_target;
static uint32_t read32(uintptr_t address) {
    assert(address == gicd_base);
    return ctl | (stuck ? GICD_CTLR_RWP : 0);
}
static void write32(uintptr_t address, uint32_t value) {
    assert(address == gicd_base);
    assert(!(ctl & GICD_CTLR_ARE_NS) || (value & GICD_CTLR_ARE_NS));
    assert(!((ctl ^ value) & GICD_CTLR_ARE_NS) || !(ctl & 3));
    ctl = value & ~1U; /* observed NS view: bit0 reads zero, bit1 enables Group1 */
}
#define gicd_read32(off) read32(gicd_base + (off))
#define gicd_write32(off, val) write32(gicd_base + (off), (val))
static uint32_t read_r(uintptr_t base, unsigned off) {
    assert(base == gicr_base && off == GICR_WAKER);
    return 0;
}
static void write_r(uintptr_t base, unsigned off, uint32_t value) {
    assert(base == gicr_base);
    if (off == GICR_IGROUPR0 || off == GICR_ISENABLER0) {
        if (!(ctl & GICD_CTLR_ARE_NS)) ignored++;
        else if (off == GICR_ISENABLER0) enabled |= value;
    }
}
#define gicr_read32(off) read_r(gicr_pe_base, (off))
#define gicr_write32(off, value) write_r(gicr_pe_base, (off), (value))
static vm_offset_t find_gicr_pe_base(void) { return gicr_base; }
static vm_offset_t pe_arm_get_soc_base_phys(void) { return 0x1000000; }
static vm_offset_t ml_io_map(uint64_t base, uint64_t size) { (void)size; return base; }
#define ml_get_cpu_number_local() 0
static int SecureDTLookupEntry(void *root, const char *path, DTEntry *entry) {
    (void)root; assert(!strcmp(path, "/arm-io/gic")); *entry = 1; return kSuccess;
}
static int SecureDTGetProperty(DTEntry entry, const char *key, const void **value, unsigned *size) {
    static const uint64_t reg[] = {0xe200000, 0x10000, 0xe300000, 0x100000};
    static const uint32_t timer = 19;
    assert(entry == 1);
    if (!strcmp(key, "reg")) { *value = reg; *size = sizeof(reg); }
    else { assert(!strcmp(key, "virtual-timer-intid")); *value = &timer; *size = sizeof(timer); }
    return kSuccess;
}
static void nanoseconds_to_deadline(uint64_t ns, uint64_t *deadline) { *deadline = clock_value + ns; }
static uint64_t mach_absolute_time(void) { return clock_value += GICR_WAKE_TIMEOUT_NS + 1; }
static void panic(const char *format, ...) {
    (void)format;
    if (!expect_panic) abort();
    longjmp(panic_target, 1);
}
static void kprintf(const char *format, ...) { (void)format; }
static uint64_t sys_read(const char *name) { (void)name; return 0; }
static void sys_write(const char *name, uint64_t value) {
    if (!strcmp(name, "ICC_IGRPEN1_EL1")) group1 = value;
}
#define __builtin_arm_rsr64(name) sys_read(name)
#define __builtin_arm_wsr64(name, value) sys_write(name, value)
#define __builtin_arm_isb(value) ((void)(value))
#define __builtin_arm_dsb(value) ((void)(value))
''' + helper + setup + r'''
int main(void) {
    const uint32_t states[] = {0, 0x10, 0x12};
    for (unsigned i = 0; i < 3; i++) {
        gicd_base = gicr_base = gicr_size = 0;
        ctl = states[i]; enabled = ignored = group1 = 0;
        pe_init_fiq();
        assert(gicd_base == 0xf200000 && gicr_base == 0xf300000 && gicr_size == 0x100000);
        assert(ignored == 0 && enabled == ((1U << 19) | (1U << 1)));
        assert((ctl & 0x12) == 0x12 && group1 == 1 && sweet_vtimer_intid == 19);
    }
    gicd_base = 0; ctl = 0; stuck = expect_panic = 1;
    if (!setjmp(panic_target)) { pe_init_fiq(); abort(); }
}
'''
with tempfile.TemporaryDirectory() as directory:
    path = Path(directory)
    (path / 'gic.c').write_text(source)
    subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                    '-I' + str(args.xnu / 'pexpert'), str(path / 'gic.c'),
                    '-o', str(path / 'gic')], check=True)
    subprocess.run([str(path / 'gic')], check=True, timeout=10)
print('Actual XNU pe_init_fiq: ARE-off/on, group enable and RWP timeout PASS')
