"""Exercise actual SM6115 power sequence, status gates and MMIO write scope."""
import argparse
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--xnu', type=Path, required=True)
tree = parser.parse_args().xnu
source = (tree/'bsd/dev/lemon_gpu_power.c').read_text()
assert '#include <kern/clock.h>' in source
assert 'bsd/dev/lemon_gpu_power.c' in (tree/'bsd/conf/files').read_text()
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
source = re.sub(r'^#include <[^>]+>\n','',source,flags=re.M)
mock = re.sub(r'static void\nlp_write\(.*?\n}\n','static void lp_write(vm_offset_t,unsigned,uint32_t);\n',source,flags=re.S)
assert mock != source
mock = re.sub(r'^\s*__asm__ volatile\([^\n]+\);','',mock,flags=re.M)
test = r'''
static uint32_t gcc[0x80000/4],cc[0x9000/4];
static unsigned failure,writes,pll_writes,reset_writes,waits;
void delay(int us) {assert(us==1 || us==5 || us==10);waits++;}
vm_offset_t ml_io_map(vm_offset_t pa,vm_size_t size) {
    if(pa==0x01400000) {assert(size==sizeof(gcc));return (uintptr_t)gcc;}
    assert(pa==0x05990000 && size==sizeof(cc));return failure==6?0:(uintptr_t)cc;
}
static void lp_write(vm_offset_t base,unsigned o,uint32_t value) {
    assert(!(o&3));writes++;
    if(base==(uintptr_t)gcc) {
        uint32_t mask=o==0x79004?1u<<15:1;
        assert(o==0x79004 || o==0x71154 || o==0x3600c || o==0x36018);
        assert(((gcc[o/4]^value)&~mask)==0);
        gcc[o/4]=value;
        if(o!=0x79004) gcc[o/4]&=~(1u<<31);
        return;
    }
    assert(base==(uintptr_t)cc);
    uint32_t mask=1;
    switch(o) {
    case 0x104:case 0x108:case 0x118: mask=0xffffffff;pll_writes++;break;
    case 0x10c:mask=0xff;pll_writes++;break;
    case 0x110:mask=0x01338003;pll_writes++;break;
    case 0x100:mask=7;pll_writes++;break;
    case 0x101c:case 0x1120:mask=3;break;
    case 0x1020:case 0x1124:mask=0x10371f;break;
    case 0x106c:case 0x100c:case 0x1008:case 0x1508:
    case 0x1078:case 0x109c:case 0x1060:
    case 0x1098:case 0x1054:break;
    default:assert(!"unapproved GPUCC write");
    }
    assert(((cc[o/4]^value)&~mask)==0);
    if(failure==11 && o==0x104) return;
    if(failure==12 && o==0x1008) return;
    if(failure==13 && o==0x1508) return;
    cc[o/4]=value;
    if(o==0x106c && !(value&1) && failure!=1) cc[0x1540/4]|=1u<<31;
    if(o==0x1008) {assert(cc[0x1540/4]>>31);reset_writes++;}
    if(o==0x100c && !(value&1)) {
        assert(cc[0x1540/4]>>31);assert(reset_writes==2 && !(cc[0x1508/4]&1));
        if(failure!=2) cc[o/4]|=1u<<31;
    }
    if(o>=0x100 && o<=0x118) {
        assert(cc[0x100c/4]>>31);
        if(o==0x100 && (value&6)==6 && failure!=3) cc[o/4]|=1u<<31;
    }
    if(o==0x101c || o==0x1120) {
        assert(cc[0x100/4]>>31);
        if(failure!=4) cc[o/4]&=~(0x80000001u);
    }
    if(o==0x1078 || o==0x109c || o==0x1060 || o==0x108c || o==0x1098 || o==0x10a4 || o==0x1054) {
        assert(cc[0x1540/4]>>31);
        if(o==0x1060 || o==0x10a4 || o==0x1054) assert(cc[0x100c/4]>>31);
        if(o==0x1098) assert((cc[0x1124/4]&0x10371f)==0x505);
        if(o==0x1054 || o==0x10a4) assert((cc[0x1020/4]&0x10371f)==0x303);
        if(!(failure==5 && o==0x109c) && !(failure==14 && o==0x1098)) cc[o/4]&=~(1u<<31);
    }
}
static void setup(unsigned mode) {
    failure=mode;writes=pll_writes=reset_writes=waits=0;
    memset(cc,0,sizeof(cc));memset(gcc,0,sizeof(gcc));
    gcc[0x7900c/4]=0x4bf0;gcc[0x36004/4]=9;gcc[0x36040/4]=8;
    gcc[0]=0x80000007;gcc[1]=31;gcc[3]=0x40;gcc[6]=1u<<24;
    gcc[0x79004/4]=0x3456;
    gcc[0x71154/4]=gcc[0x3600c/4]=gcc[0x36018/4]=0x80000000;
    cc[0x106c/4]=cc[0x100c/4]=0x222001;cc[0x1508/4]=1;
    cc[0x1054/4]=cc[0x10a4/4]=cc[0x1098/4]=0x80004220;
    cc[0x1078/4]=cc[0x109c/4]=cc[0x1060/4]=cc[0x108c/4]=0x80000000;
    cc[0x108c/4]=0; /* Actual v29 readback: optional branch is not requested. */
    cc[0x101c/4]=cc[0x1120/4]=0x80000000;
    if(mode==7) gcc[0x7900c/4]&=~16u;
    if(mode==8) gcc[1]=40;
    if(mode==9) cc[0x100c/4]|=1u<<31;
    if(mode==10) cc[0x100/4]=0x80000007;
}
int main(void) {
    setup(0);lemon_gpu_power_probe();
    assert((cc[0x1054/4]&0x80000001u)==1 && (cc[0x1098/4]&0x80000001u)==1);
    assert(!(cc[0x101c/4]&2) && !(cc[0x1120/4]&2));
    assert(gcc[0x79004/4]==(0x3456|0x8000) && reset_writes==2);
    assert(cc[0x108c/4]==0 && cc[0x10a4/4]==0x80004220);
    setup(0);cc[0x100/4]=0x80000007;cc[0x104/4]=0x21;
    cc[0x108/4]=0x55555555;cc[0x10c/4]=0x55;cc[0x110/4]=0x01200003;
    lemon_gpu_power_probe();assert(!pll_writes && (cc[0x1054/4]&0x80000001u)==1);
    for(unsigned mode=1;mode<=14;mode++) {
        setup(mode);lemon_gpu_power_probe();assert(!(cc[0x1054/4]&1));
        if(mode==1) assert(!reset_writes && !pll_writes);
        if(mode==2 || mode==5) assert(!pll_writes);
        if(mode==6 || mode==7 || mode==8 || mode==9) assert(!writes);
        if(mode==10) assert(!pll_writes); /* do not retune running unknown PLL */
        if(mode==11) assert(!(cc[0x100/4]&7)); /* failed rate write stops enable */
        if(mode==12 || mode==13) assert(!pll_writes && !(cc[0x100c/4]>>31));
    }
    puts("PASS: actual CX-before-GX sequence, dedicated PLL640 and roots, clock status/readback, timeouts, unknown handoff guards, MMIO write masks, no shared PLL writes or core/SMMU access");
}
'''
with tempfile.TemporaryDirectory() as directory:
    folder = Path(directory)
    (folder/'full.c').write_text(header+source)
    (folder/'test.c').write_text(header+mock+test)
    flags = ['-std=c11','-Wall','-Wextra','-Werror']
    subprocess.run(['cc',*flags,'-fsanitize=address,undefined',str(folder/'test.c'),'-o',str(folder/'test')],check=True)
    subprocess.run([str(folder/'test')],check=True)
    cross = shutil.which('aarch64-linux-gnu-gcc')
    if cross:
        subprocess.run([cross,*flags,'-mcpu=cortex-a53','-march=armv8-a+crypto','-mno-outline-atomics','-c',str(folder/'full.c'),'-o',str(folder/'arm64.o')],check=True)
        print('PASS: actual GPU power module ARMv8.0 cross-compile')
