#!/usr/bin/env python3
"""Check the actual framebuffer probe/render code with a guarded host buffer."""
import argparse
from pathlib import Path
import subprocess
import tempfile

ap = argparse.ArgumentParser()
ap.add_argument('--xnu', type=Path, required=True)
args = ap.parse_args()
serial = (args.xnu / 'pexpert/arm/pe_serial.c').read_text()
early = (args.xnu / 'osfmk/arm64/sweet_early.c').read_text()

def function(source, signature):
    begin = source.index(signature)
    return source[begin:source.index('\n}\n', begin) + 3]

render = serial[serial.index('#define FBCON_SCALE'):
                serial.index('static unsigned int\nfbcon_receive_ready')]
render = render.replace('__asm__ volatile("dsb sy" ::: "memory");', 'flushes++;')
probe = function(serial, 'static void\nfbcon_probe(void)')
getter = function(early, 'uintptr_t\nsweet_early_framebuffer(void)')
source = r'''#include <assert.h>
#include <stdint.h>
#include <string.h>
#define LEMON_4K 1
#include "lemon_fb_map.h"
#define kSuccess 0
typedef int DTEntry;
static uint32_t pixels[LEMON_FB_BYTES / 4 + 2];
static volatile uint32_t *early_fb = pixels + 1;
unsigned char iso_font[256 * 16];
static unsigned flushes, registrations, mappings;
static uint64_t reg_data[] = { LEMON_FB_BASE, 0xf00000 };
static uint32_t width = LEMON_FB_WIDTH, height = LEMON_FB_HEIGHT, stride = LEMON_FB_STRIDE;
static int sweet_fbcon_serial_functions;
static int SecureDTFindEntry(const char *key, const char *name, DTEntry *entry) {
    assert(!strcmp(key, "name") && !strcmp(name, "sweet-fbcon"));
    *entry = 1;
    return kSuccess;
}
static int SecureDTGetProperty(DTEntry entry, const char *key, const void **value, unsigned *size) {
    assert(entry == 1);
    *size = 4;
    if (!strcmp(key, "reg")) { *value = reg_data; *size = sizeof(reg_data); }
    else if (!strcmp(key, "width")) *value = &width;
    else if (!strcmp(key, "height")) *value = &height;
    else if (!strcmp(key, "stride")) *value = &stride;
    else return -1;
    return kSuccess;
}
static void sweet_early_mark(unsigned stage, const char *label) { (void)stage; (void)label; }
static void register_serial_functions(void *functions) {
    assert(functions == &sweet_fbcon_serial_functions);
    registrations++;
}
uintptr_t ml_io_map_wcomb(uint64_t base, uint64_t size) {
    (void)base; (void)size;
    mappings++;
    return (uintptr_t)early_fb;
}
''' + getter + render + probe + r'''
int main(void) {
    pixels[0] = pixels[LEMON_FB_BYTES / 4 + 1] = 0x12345678;
    fbcon_probe();
    assert(registrations == 1 && mappings == 0 && fbcon_base == early_fb);
    fbcon_init();
    assert(fbcon_transmit_ready());
    memset(iso_font + 'A' * 16, 255, 16);
    fbcon_transmit_data('A');
    assert(early_fb[0] == FBCON_FG && fbcon_col == 1);
    fbcon_transmit_data('\n');
    assert(flushes == 1 && fbcon_row == 1 && fbcon_col == 0);
    for (unsigned i = 0; i < 74; i++) fbcon_transmit_data('\n');
    assert(fbcon_row < fbcon_rows && flushes == 75);
    assert(pixels[0] == 0x12345678 && pixels[LEMON_FB_BYTES / 4 + 1] == 0x12345678);
    reg_data[0] = 0x9c000000;
    fbcon_probe();
    assert(registrations == 1 && mappings == 0);
    reg_data[0] = LEMON_FB_BASE;
    stride += 4;
    fbcon_probe();
    assert(registrations == 1 && mappings == 0);
}
'''
with tempfile.TemporaryDirectory() as directory:
    path = Path(directory)
    (path / 'console.c').write_text(source)
    subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                    '-I' + str(args.xnu / 'osfmk/arm64'), str(path / 'console.c'),
                    '-o', str(path / 'console')], check=True)
    subprocess.run([str(path / 'console')], check=True)
print('Console: actual permanent-alias probe, rendering, wrap, bounds and flush path PASS')
