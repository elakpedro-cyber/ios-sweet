"""Exercise the actual default-off GPU checkpoint with guarded MMIO mocks."""
import argparse
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--xnu', type=Path, required=True)
tree = parser.parse_args().xnu
source = (tree / 'bsd/dev/lemon_gpu.c').read_text()
assert '#if defined(ARM64_BOARD_CONFIG_SWEET) && defined(LEMON_4K)' in source
assert 'extern void lemon_gpu_init(void);' in (tree / 'bsd/dev/sweet_ufs.c').read_text()
assert 'bsd/dev/lemon_gpu.c' in (tree / 'bsd/conf/files').read_text()
hook = (tree / 'bsd/dev/sweet_ufs.c').read_text()
assert hook.index('\tlemon_gpu_init();') < hook.index('\tsweet_touch_init();')
header = r'''
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <assert.h>
#include <string.h>
#define ARM64_BOARD_CONFIG_SWEET 1
#define LEMON_4K 1
#define KERN_SUCCESS 0
#define THREAD_CONTINUE_NULL 0
typedef uintptr_t vm_offset_t, vm_size_t;
typedef void *thread_t;
typedef int kern_return_t, wait_result_t;
typedef void (*thread_continue_t)(void *, wait_result_t);
extern int PE_parse_boot_argn(const char *,void *,unsigned);
extern kern_return_t kernel_thread_start(thread_continue_t,void *,thread_t *);
extern void thread_deallocate(thread_t),thread_block(void *);
extern thread_t current_thread(void);
extern void delay(int);
'''
plain = re.sub(r'^#include <[^>]+>\n', '', source, flags=re.M)
mocked = re.sub(r'static uint32_t\nlg_read\(.*?\n}\n', 'static uint32_t lg_read(vm_offset_t, unsigned);\n', plain, flags=re.S)
assert mocked != plain
mocked = re.sub(r'static void\nlg_write\(.*?\n}\n', 'static void lg_write(vm_offset_t, unsigned, uint32_t);\n', mocked, flags=re.S)
test = r'''
static unsigned option, maps, reads, cc_reads, threads, terminated, map_failure;
static uint32_t cfg, qmip, vote;
static unsigned writes, delays, ignore_write, concurrent_vote;
void delay(int us) {
    assert(us==1);delays++;
    if(concurrent_vote) vote |= 0x1000;
}
static void lg_write(vm_offset_t base,unsigned offset,uint32_t value) {
    assert(option==2 && base==1 && offset==LG_VOTE);
    assert(((value^vote)&~16u)==0);writes++;
    if(!ignore_write) vote=value;
}
int PE_parse_boot_argn(const char *name,void *p,unsigned size) {
    assert(!strcmp(name,"lemongpu") && size==sizeof(int));*(int *)p=option;return 1;
}
vm_offset_t ml_io_map(vm_offset_t address,vm_size_t size) {
    maps++;
    if(address==LG_GCC_PA) {assert(size==LG_GCC_SIZE);return map_failure==1?0:1;}
    assert(address==LG_GPUCC_PA && size==LG_GPUCC_SIZE);
    assert((cfg&1) && !(cfg>>31) && (vote&16) && !(qmip>>31));
    return map_failure==2?0:2;
}
static uint32_t lg_read(vm_offset_t base,unsigned offset) {
    reads++;
    if(base==1) {
        switch(offset) {
        case LG_CFG_AHB:return cfg;
        case LG_QMIP_AHB:return qmip;
        case LG_VOTE:return vote;
        case LG_MEMNOC:case LG_SNOC:return 0;
        default:assert(!"unexpected GCC access");
        }
    }
    assert(base==2);cc_reads++;
    assert((cfg&1) && !(cfg>>31) && (vote&16) && !(qmip>>31));
    assert(offset==LG_CX_GDSC || offset==LG_GX_GDSC || offset==LG_AHB ||
           offset==LG_CX_GMU || offset==LG_CXO || offset==LG_GFX3D);
    return 0; /* even with CX/GX off, never read GPU/SMMU registers */
}
thread_t current_thread(void) {return (void *)3;}
kern_return_t thread_terminate(thread_t thread) {assert(thread==(void *)3);terminated++;return 0;}
void thread_block(void *p) {assert(!p);}
void thread_deallocate(thread_t thread) {assert(thread==(void *)3);}
kern_return_t kernel_thread_start(thread_continue_t f,void *arg,thread_t *out) {
    threads++;*out=(void *)3;f(arg,0);return 0;
}
static void run(unsigned mode,unsigned config,unsigned q,unsigned v,unsigned fail) {
    lg_started=false;maps=reads=cc_reads=threads=terminated=0;
    option=mode;cfg=config;qmip=q;vote=v;map_failure=fail;
    lemon_gpu_init();lemon_gpu_init();
    assert(threads==(mode==1) && terminated==threads);
}
int main(void) {
    run(0,1,0,16,0);assert(!maps && !reads);
    run(99,1,0,16,0);assert(!maps && !reads);
    run(1,0,0,16,0);assert(maps==1 && reads==5 && !cc_reads);
    run(1,0x80000001,0,16,0);assert(maps==1 && !cc_reads);
    run(1,1,0,0,0);assert(maps==1 && !cc_reads);
    run(1,1,0x80000000,16,0);assert(maps==1 && !cc_reads);
    run(1,1,0,16,1);assert(maps==1 && !reads);
    run(1,1,0,16,2);assert(maps==2 && reads==5 && !cc_reads);
    run(1,1,0,16,0);assert(maps==2 && reads==11 && cc_reads==6);
    run(2,1,8,0x4be0,0);assert(writes==1 && !delays && cc_reads==6 && vote==0x4bf0);
    writes=delays=0;
    run(2,1,8,0x4bf0,0);assert(!writes && !delays && cc_reads==6);
    run(2,0,8,0x4be0,0);assert(!writes && !cc_reads);
    run(2,0x80000001,8,0x4be0,0);assert(!writes && !cc_reads);
    run(2,1,8,0x4be0,1);assert(!writes && !cc_reads);
    concurrent_vote=1;
    run(2,1,0x80000008,0x4be0,0);
    assert(writes==2 && delays==200 && !cc_reads && vote==0x5be0);
    concurrent_vote=0;writes=delays=0;
    run(2,1,0x80000008,0x4bf0,0);
    assert(!writes && delays==200 && !cc_reads && vote==0x4bf0);
    ignore_write=1;writes=delays=0;
    run(2,1,8,0x4be0,0);assert(writes==2 && delays==200 && !cc_reads && vote==0x4be0);
    puts("PASS: opt-in config vote only, bounded timeout, rollback owned bit, preserve other voters, input initialization order");
    puts("PASS: actual GPU probe default off, single start, gated parent clocks, mapping failures; only whitelisted read accesses");
}
'''
with tempfile.TemporaryDirectory() as directory:
    folder = Path(directory)
    (folder / 'full.c').write_text(header + plain)
    (folder / 'test.c').write_text(header + mocked + test)
    flags = ['-std=c11', '-Wall', '-Wextra', '-Werror']
    subprocess.run(['cc', *flags, '-fsyntax-only', str(folder / 'full.c')], check=True)
    subprocess.run(['cc', *flags, '-fsanitize=address,undefined', str(folder / 'test.c'), '-o', str(folder / 'test')], check=True)
    subprocess.run([str(folder / 'test')], check=True)
    cross = shutil.which('aarch64-linux-gnu-gcc')
    if cross:
        subprocess.run([cross, *flags, '-mcpu=cortex-a53', '-march=armv8-a+crypto', '-mno-outline-atomics',
                        '-c', str(folder / 'full.c'), '-o', str(folder / 'arm64.o')], check=True)
        print('PASS: full probe including real read barrier compiled for Cortex-A53')
