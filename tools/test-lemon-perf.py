"""Test optional display pacing, stats, and the two bounded lemon RAM profiles."""
import argparse
from pathlib import Path
import re
import subprocess
import tempfile
import struct
import adt
import mkadt

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--xnu',type=Path,required=True)
parser.add_argument('--iomem',type=Path)
args=parser.parse_args()
root=Path(__file__).resolve().parents[1]
seed=b'x'*64
normal=mkadt.build(seed=seed,lemon=True)
perf=mkadt.build(seed=seed,lemon=True,lemon_perf=True)
chosen=lambda tree:next(n for n in tree.children if n.name=='chosen')
pram=lambda tree:next(n for n in tree.children if n.name=='pram')
assert struct.unpack('<Q',chosen(perf).prop('dram-base'))==(0x100000000,)
assert struct.unpack('<Q',chosen(perf).prop('dram-size'))==(0x2fe00000,)
assert struct.unpack('<QQ',pram(perf).prop('reg'))==(0x12fe00000,0x200000)
for node,key,value in ((chosen(perf),'dram-size',chosen(normal).prop('dram-size')),
                       (pram(perf),'reg',pram(normal).prop('reg'))):
    node.props=[(k,f,value if k==key else v) for k,f,v in node.props]
assert adt.serialize(perf)==adt.serialize(normal), 'RAM profile must not change identity/display/touch'
for kwargs in ({'lemon_perf':True},{'lemon':True,'lemon_perf':True,'qemu':True}):
    try: mkadt.build(seed=seed,**kwargs)
    except ValueError: pass
    else: raise AssertionError('physical lemon only')
if args.iomem:
    ranges=[]
    for line in args.iomem.read_text().splitlines():
        m=re.match(r'\s*([0-9a-f]+)-([0-9a-f]+) : (.*)',line)
        if m:ranges.append((int(m[1],16),int(m[2],16)+1,m[3]))
    lo,hi=0x100000000,0x130000000 # includes the panic buffer
    assert any(a<=lo and hi<=b and n=='System RAM' for a,b,n in ranges)
    assert not [(a,b,n) for a,b,n in ranges if n!='System RAM' and a<hi and lo<b]

loader=(root/'shim/loader.c').read_text()
guard=re.search(r'if \(p->phys_base != 0x100000000UL.*?return "wrong lemon RAM profile";',loader,re.S)[0]
guard_test='''#include <assert.h>
#include <stdint.h>
#include <stddef.h>
static const char *check(uint64_t base,uint64_t size) {
    struct {uint64_t phys_base,mem_size;} value={base,size},*p=&value;
    /* GUARD */
    return NULL;
}
int main(void) {
    assert(!check(0x100000000ULL,0x1fe00000));
    assert(!check(0x100000000ULL,0x2fe00000));
    assert(check(0x100000000ULL,0x30000000));
    assert(check(0x100000000ULL,0x40000000));
    assert(check(0x80000000,0x2fe00000));
    assert(check(0x100000000ULL,0));
}
'''.replace('/* GUARD */',guard)

text=(args.xnu/'iokit/Kernel/arm/SweetFramebuffer.cpp').read_text()
start=text.index('\tuint32_t hz = 10, notifyHz = 60;')
block=text[start:text.index('\n\n\tsetProperty(kIOUserClientClassKey',start)]
start=text.index('void\nAppleCLCD::perfSample(')
sample=text[start:text.index('\n}\n',start)+3]
callback=text[text.index('void\nAppleCLCD::vsyncFired('):text.index('void\nAppleCLCD::perfSample(')]
assert callback.count('sender->setTimeoutUS(fb->fVsyncUS);')==2
assert 'fb->fPerfStart = now;' in callback
assert 'fb->perfSample(presentTicks, rec != NULL);' in callback
program=r'''
#include <cassert>
#include <cstdint>
#include <cstring>
#include <cstdarg>
static uint32_t cfgNotify=60,cfgCopy=10;
static int cfgStats;
static uint64_t now=1;
static unsigned logs;
static unsigned long long lastV,lastF,lastMS,lastPresent;
static uint64_t mach_absolute_time() {return now;}
static void absolutetime_to_nanoseconds(uint64_t value,uint64_t *out) {*out=value;}
static void PE_parse_boot_argn(const char *name,void *out,unsigned size) {
    assert(size==4);
    if(!std::strcmp(name,"sweetfb_hz")) *static_cast<uint32_t *>(out)=cfgCopy;
    else if(!std::strcmp(name,"sweetfb_vsync_hz")) *static_cast<uint32_t *>(out)=cfgNotify;
    else {assert(!std::strcmp(name,"sweetfb_stats"));*static_cast<int *>(out)=cfgStats;}
}
static void IOLog(const char *fmt,...) {
    if(!std::strstr(fmt,"LEMON PERF:")) return;
    va_list a;va_start(a,fmt);logs++;
    lastV=va_arg(a,unsigned long long);lastF=va_arg(a,unsigned long long);
    lastMS=va_arg(a,unsigned long long);lastPresent=va_arg(a,unsigned long long);va_end(a);
}
struct Timer {uint32_t delay=0;void setTimeoutUS(uint32_t value) {delay=value;}};
struct AppleCLCD {
    uint32_t fVsyncUS,fFlushTicks;
    bool fStats;
    uint64_t fPerfStart,fPerfVsyncs,fPerfFrames,fPerfPresent;
    Timer timer,*fVsync=&timer;
    void init() {
/* INIT */
    }
    void perfSample(uint64_t,bool);
};
/* SAMPLE */
int main() {
    AppleCLCD fb;
    fb.init();assert(fb.fVsyncUS==16667 && fb.fFlushTicks==6 && !fb.fStats);
    cfgCopy=15;fb.init();assert(fb.fVsyncUS==16667 && fb.fFlushTicks==4);
    cfgNotify=15;fb.init();assert(fb.fVsyncUS==66667 && fb.fFlushTicks==1);
    cfgNotify=30;fb.init();assert(fb.fVsyncUS==33334 && fb.fFlushTicks==2);
    cfgNotify=0;fb.init();assert(fb.fVsyncUS==16667);
    cfgNotify=61;fb.init();assert(fb.fVsyncUS==16667);
    cfgCopy=0;fb.init();assert(fb.fFlushTicks==1);
    now=5000000001ULL;fb.perfSample(1,true);assert(!logs);
    cfgNotify=15;cfgCopy=15;cfgStats=1;now=1;fb.init();
    now=4000000001ULL;fb.perfSample(1000000000ULL,true);assert(!logs);
    now=5000000001ULL;fb.perfSample(0,false);
    assert(logs==1 && lastV==2 && lastF==1 && lastMS==5000 && lastPresent==1000);
    assert(!fb.fPerfVsyncs && !fb.fPerfFrames && !fb.fPerfPresent);
    now=10000000001ULL;fb.perfSample(1000000,true);
    assert(logs==2 && lastF==1 && lastPresent==1);
}
'''.replace('/* INIT */',block).replace('/* SAMPLE */',sample)
with tempfile.TemporaryDirectory() as folder:
    p=Path(folder)
    (p/'guard.c').write_text(guard_test)
    (p/'timing.cpp').write_text(program)
    subprocess.run(['cc','-Wall','-Wextra','-Werror',str(p/'guard.c'),'-o',str(p/'guard')],check=True)
    subprocess.run([str(p/'guard')],check=True)
    subprocess.run(['c++','-std=c++11','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',str(p/'timing.cpp'),'-o',str(p/'timing')],check=True)
    subprocess.run([str(p/'timing')],check=True)
print('PASS: exact RAM profiles/loader bounds, ADT identity preserved, legacy and15Hz pacing, opt-in presentation timing')
