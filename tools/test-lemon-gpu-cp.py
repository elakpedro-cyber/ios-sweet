"""Run the actual opt-in A610 CP checkpoint against a bounded MMIO/PM4 model."""
import argparse
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--xnu', type=Path, required=True)
tree = parser.parse_args().xnu
source = (tree/'bsd/dev/lemon_gpu_cp.c').read_text()
assert 'bsd/dev/lemon_gpu_cp.c' in (tree/'bsd/conf/files').read_text()
for include in ('pexpert/device_tree.h','arm/caches_internal.h','kern/clock.h','vm/vm_kern.h'):
    assert '#include <'+include+'>' in source
source = re.sub(r'^#include <[^>]+>\n','',source,flags=re.M)
header = r'''
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#define ARM64_BOARD_CONFIG_SWEET 1
#define LEMON_4K 1
#define PAGE_MASK 4095u
#define KMA_DATA 1u
#define KMA_ZERO 2u
#define VM_KERN_MEMORY_IOKIT 1u
#define KERN_SUCCESS 0
#define kSuccess 0
#define TRUE 1
#define ptoa_64(p) ((uint64_t)(p)<<12)
typedef uintptr_t vm_offset_t,vm_size_t;
typedef uint64_t addr64_t;
typedef uint32_t ppnum_t;
typedef void *vm_map_t,*pmap_t,*DTEntry;
extern vm_map_t kernel_map;
extern pmap_t kernel_pmap;
extern int PE_parse_boot_argn(const char*,void*,unsigned);
extern int SecureDTLookupEntry(DTEntry,const char*,DTEntry*);
extern int SecureDTGetProperty(DTEntry,const char*,const void**,unsigned*);
extern void delay(int),clean_dcache64(addr64_t,unsigned,int),flush_dcache64(addr64_t,unsigned,int);
extern int kmem_alloc_contig(vm_map_t,vm_offset_t*,vm_size_t,vm_offset_t,ppnum_t,ppnum_t,unsigned,unsigned);
extern void kmem_free(vm_map_t,vm_offset_t,vm_size_t);
'''
mock=source
for name,result,args in [('lc_read','uint32_t','vm_offset_t,unsigned'),('lc_write','void','vm_offset_t,unsigned,uint32_t'),
                         ('lc_read64','uint64_t','vm_offset_t,unsigned'),('lc_write64','void','vm_offset_t,unsigned,uint64_t')]:
    mock,count=re.subn(r'static '+result+r'\n'+name+r'\(.*?\n}\n',
                       'static '+result+' '+name+'('+args+');\n',mock,flags=re.S)
    assert count==1,name
mock=re.sub(r'^\s*__asm__ volatile\([^\n]+\);','',mock,flags=re.M)
test=r'''
static uint32_t gpu[0x40000/4],smmu[0x10000/4],gcc[0x80000/4],cc[0x9000/4];
static uint32_t fw[8066],chip;
static unsigned scenario,option,maps,writes,gpu_writes,submits,allocations,frees,cleans,flushes,processed,clock_writes;
static unsigned poll_delays;
static uint32_t pending_roq;
static void *allocation;
static const uint64_t physical=0x103100000ull,prepared=0x102d94000ull;
vm_map_t kernel_map=(void*)1;
pmap_t kernel_pmap=(void*)2;
int PE_parse_boot_argn(const char *n,void *p,unsigned len) {
    assert(!strcmp(n,"lemongpu") && len==4);*(int*)p=option;return 1;
}
int SecureDTLookupEntry(DTEntry search,const char *name,DTEntry *out) {
    assert(!search && !strcmp(name,"/lemon-gpu"));*out=(void*)3;return scenario==2?-1:0;
}
int SecureDTGetProperty(DTEntry node,const char *name,const void **out,unsigned *size) {
    assert(node==(void*)3);
    if(!strcmp(name,"chip-id")) {*out=&chip;*size=4;return 0;}
    assert(!strcmp(name,"sqe-firmware"));*out=fw;*size=scenario==26?3:sizeof(fw);return 0;
}
bool lemon_gpu_memory_context(vm_offset_t *base,uint64_t *pa) {
    if(scenario==1) return false;
    *base=(uintptr_t)smmu;*pa=prepared;return true;
}
vm_offset_t ml_io_map(vm_offset_t pa,vm_size_t size) {
    maps++;
    if(pa==0x5990000) {assert(size==sizeof(cc));return (uintptr_t)cc;}
    if(pa==0x1400000) {assert(size==sizeof(gcc));return (uintptr_t)gcc;}
    assert(pa==0x5900000 && size==sizeof(gpu));return scenario==8?0:(uintptr_t)gpu;
}
void delay(int us) {assert(us==1 || us==10);poll_delays++;}
int kmem_alloc_contig(vm_map_t map,vm_offset_t *out,vm_size_t bytes,vm_offset_t mask,
    ppnum_t max,ppnum_t pmask,unsigned flags,unsigned tag) {
    assert(map==kernel_map && bytes==0x13000 && mask==4095 && !max && !pmask);
    assert(flags==(KMA_DATA|KMA_ZERO) && tag==VM_KERN_MEMORY_IOKIT);allocations++;
    if(scenario==10) return -1;
    allocation=aligned_alloc(4096,bytes);assert(allocation);memset(allocation,0,bytes);
    *out=(uintptr_t)allocation;return 0;
}
ppnum_t pmap_find_phys(pmap_t map,addr64_t va) {
    assert(map==kernel_pmap && allocation && va>=(uintptr_t)allocation && va<(uintptr_t)allocation+LC_SIZE);
    uint64_t off=va-(uintptr_t)allocation;
    if(scenario==11 && off==8192) off+=4096;
    return (physical+off)>>12;
}
void kmem_free(vm_map_t map,vm_offset_t va,vm_size_t bytes) {
    assert(map==kernel_map && va==(uintptr_t)allocation && bytes==LC_SIZE && !writes);
    frees++;free(allocation);allocation=0;
}
void clean_dcache64(addr64_t pa,unsigned bytes,int phys) {
    assert(phys && allocation);
    assert((pa==physical && bytes==LC_SIZE) || (pa==physical+LC_RING && bytes==4096));cleans++;
}
void flush_dcache64(addr64_t pa,unsigned bytes,int phys) {
    assert(phys && pa==physical+LC_TARGET && bytes==4096);flushes++;
}
static uint64_t raw64(unsigned off) {return smmu[off/4]|((uint64_t)smmu[off/4+1]<<32);}
static uint32_t lc_read(vm_offset_t base,unsigned off) {
    assert(!(off&3));
    if(base==(uintptr_t)cc) {
        assert(off==0x1540 || off==0x100c || off==0x1078 || off==0x1054 || off==0x1098 || off==0x5000);
        return cc[off/4];
    }
    if(base==(uintptr_t)gcc) {
        assert(off==0x3600c || off==0x36018 || off==0x36004 || off==0x7900c || off==0x36040);
        return gcc[off/4];
    }
    if(base==(uintptr_t)smmu) {
        assert(off==0x20 || off==0x48 || off==0x1000 || off==0x1800 ||
            (off>=0x800 && off<0x810) || (off>=0xc00 && off<0xc10) ||
            off==0x8000 || off==0x8010 || (off>=0x8020 && off<=0x803c) ||
            off==0x8058 || off==0x8060 || off==0x8064 || off==0x8068 || off==0x87f4);
        return off==0x8058?smmu[off/4]|0x400:smmu[off/4];
    }
    assert(base==(uintptr_t)gpu && off<sizeof(gpu));
    if(scenario==38 && off==LC_ROQ2*4 && poll_delays<5) return 0;
    if(scenario==42 && off==LC_ROQ2*4 && gpu[LC_POOL]==48) {smmu[0x8058/4]=2;return 0;}
    return gpu[off/4];
}
static uint64_t lc_read64(vm_offset_t base,unsigned off) {
    assert(base==(uintptr_t)smmu && (off==0x8020 || off==0x8028 || off==0x8060));
    return lc_read(base,off)|((uint64_t)lc_read(base,off+4)<<32);
}
static void lc_write64(vm_offset_t base,unsigned off,uint64_t value) {
    assert(base==(uintptr_t)smmu && off==0x8020 && allocation);writes++;
    assert(!(smmu[0x8000/4]&1) && !(smmu[0x800/4]&(1u<<31)));
    if(scenario==15) return;
    smmu[off/4]=value;smmu[off/4+1]=value>>32;
}
static uint64_t translate(uint32_t va,bool write,bool instruction) {
    uint64_t pa=raw64(0x8020);
    const unsigned shifts[]={30,21,12};
    for(unsigned level=0;level<3;level++) {
        assert(pa>=physical+0x10000 && pa<physical+0x13000 && !(pa&4095));
        uint64_t word=*(uint64_t*)((uintptr_t)allocation+pa-physical+((va>>shifts[level])&511)*8);
        if((word&3)!=3) return 0;
        pa=word&0x0000fffffffff000ull;
        if(level==2) {
            assert(word&(1u<<10));
            if(instruction && (word&(3ull<<53))) return 0;
            if(va<LC_VA+0x8000) assert(((word>>6)&3)==3); /* Firmware stays RO. */
            else assert((word&(3ull<<53))==(3ull<<53)); /* Ring/data never executable. */
            if(write) assert(((word>>6)&3)==1);
            assert(pa>=physical && pa<physical+0xc000);
        }
    }
    return pa+(va&4095);
}
static uint32_t *gpu_word(uint32_t va,bool write) {
    uint64_t pa=translate(va,write,false);assert(pa && allocation);
    return (uint32_t*)((uintptr_t)allocation+pa-physical);
}
static unsigned odd_parity(uint32_t value) {
    unsigned bits=0;for(unsigned i=0;i<32;i++) bits+=(value>>i)&1;return !(bits&1);
}
static void execute(unsigned end) {
    assert(allocation && cleans>=2 && (gpu[LC_SQE]&1) && (smmu[0x8000/4]&1));
    submits++;
    if(scenario==20) return;
    if(scenario==24 && submits==2) {smmu[0x8058/4]=2;return;}
    assert(smmu[0x800/4]==0x80010000 && !(smmu[0xc00/4]&0x30300ff));
    assert(gpu[LC_SQE_BASE]==LC_VA && gpu[LC_SQE_BASE+1]==0);
    assert(*gpu_word(LC_VA,false)==fw[1]);
    assert(!translate(LC_VA+0x8000,false,false) && !translate(LC_VA+0x10000,false,false));
    assert(gpu[LC_RB_CNTL]==0x08000209 && gpu[LC_RB_BASE]==LC_VA+LC_RING);
    assert(end==9 || end==18);
    while(processed<end) {
        uint32_t h=*gpu_word(gpu[LC_RB_BASE]+4*processed++,false);
        if((h>>28)==7) {
            unsigned count=h&0x3fff,op=(h>>16)&0x7f;
            assert(((h>>15)&1)==odd_parity(count) && ((h>>23)&1)==odd_parity(op));
            assert(processed+count<=end);
            uint32_t a[8]={0};assert(count<=8);
            for(unsigned i=0;i<count;i++) a[i]=*gpu_word(gpu[LC_RB_BASE]+4*processed++,false);
            if(op==0x48) {assert(count==8 && a[0]==0x2f && a[1]==3 && a[2]==0x20000000);}
            else if(op==0x10) assert(count==1);
            else if(op==0x26) assert(!count);
            else {
                assert(op==0x3d && count==3 && !a[1] && a[0]==LC_VA+LC_TARGET && a[2]==0x600df00d);
                if(scenario==22) {smmu[0x8058/4]=2;return;}
                if(scenario!=21) *gpu_word(a[0],true)=a[2];
            }
        } else {
            assert((h>>28)==4);unsigned reg=(h>>8)&0x3ffff,count=h&0x7f;
            assert(count==1 && reg==0x883 && ((h>>7)&1)==odd_parity(count) && ((h>>27)&1)==odd_parity(reg));
            uint32_t value=*gpu_word(gpu[LC_RB_BASE]+4*processed++,false);
            if(scenario!=33) gpu[reg]=value;
        }
    }
    gpu[LC_RPTR]=end;
    if(scenario==24 && submits==1) smmu[0x800/4]=0x80000004; /* Foreign route must not be overwritten. */
    if(scenario==31) smmu[0x48/4]=1;
    if(scenario==48 && submits==1) smmu[0x8000/4]&=~1u;
}
static bool clock_register(unsigned reg) {
    switch(reg) {
    case 0xb0: case 0xb4: case 0xb8: case 0xbc: case 0xc0: case 0xc4:
    case 0xc8: case 0xcc: case 0xd0: case 0xd4: case 0xd8: case 0xdc:
    case 0xe0: case 0xe4: case 0xe8: case 0xec: case 0xf0: case 0xf4: case 0xf8:
    case 0x100: case 0x104: case 0x105: case 0x106: case 0x107: case 0x108:
    case 0x111: case 0x114: case 0x117: case 0x11b: case 0x109: case 0x112:
    case 0x115: case 0x11c: case 0x10a: case 0x113: case 0x116: case 0x11d:
    case 0x10b: case 0x110: case 0x10f: case 0x533: case 0x44: case 0x42:
    case 0x118: case 0x119: case 0x11a: return true;
    default: return false;
    }
}
static void lc_write(vm_offset_t base,unsigned off,uint32_t value) {
    assert(allocation);writes++;
    if(base==(uintptr_t)smmu) {
        assert(off==0x8000 || off==0x8610 || off==0x87f0 || off==0x800 || off==0xc00);
        if(off==0x87f0) {smmu[0x87f4/4]=scenario==16?1:0;return;}
        if(scenario==17 && off==0x8000 && (value&1)) return;
        if(scenario==18 && off==0x800 && (value&(1u<<31))) return;
        if(scenario==49 && off==0xc00 && value) return; /* v40 old FAULT entry restore ignored. */
        if(off==0x8000 && (value&1)) {
            assert(value==0x127 && !(value&0x1000));
            if(scenario==43) value&=~0x1000u; /* Observed bit12 reads zero. */
            if(scenario==44) value|=0x1000;
            if(scenario==45) value&=~2u;
            if(scenario==46) value|=0x40;
        }
        smmu[off/4]=value;
        if(scenario==47 && off==0x800 && value==0x80010000) smmu[0x8000/4]&=~1u;
        return;
    }
    assert(base==(uintptr_t)gpu && !(off&3));gpu_writes++;
    unsigned reg=off/4;
    bool allowed=reg==0x11 || reg==0x16 || reg==0x38 || (reg>=0x3c03 && reg<=0x3c06) ||
        reg==0x3c45 || reg==0x842 || reg==0x8c1 || reg==0x8c2 || reg==0x8c3 || reg==0x90e || reg==0x98d ||
        reg==0x800 || reg==0x801 || reg==0x802 || reg==0x804 || reg==0x805 || reg==0x808 ||
        reg==0x830 || reg==0x831 || reg==0x807 || reg==0xae || clock_register(reg);
    assert(allowed); /* No SECVID/TRUST, GMU AO, reset or framebuffer access. */
    if(clock_register(reg)) {assert(!gpu[0xae] && !submits);clock_writes++;}
    if(reg==0xae) {
        assert(clock_writes==46 && value==0xaaa8aa82 && !submits);
        if(scenario==34) return;
        if(scenario==35) smmu[0x8058/4]=2;
    }
    if(reg==0x8c2 || reg==0x8c1 || reg==0x8c3) {
        assert(gpu[0xae]==0xaaa8aa82 && gpu[0x118]==0x222 && clock_writes==46);
    }
    if(scenario==14 && reg==0x8c2) return;
    if(scenario==39 && reg==0x8c2) {pending_roq=value;return;}
    if(scenario==39 && reg==0x8c3) {
        assert(gpu[0x8c1]==0x40201b16 && value==48);
        gpu[0x8c2]=pending_roq;
    }
    if(scenario==40 && reg==0x8c1) return;
    if(scenario==41 && reg==0x8c3) return;
    if(scenario==19 && reg==0x808 && value==1) return;
    if(scenario==23 && reg==0x808 && value==3) return;
    if(scenario==36 && reg==0x808 && value==3) gpu[LC_STATUS]=4;
    if(scenario==32 && reg==0x800) return;
    gpu[reg]=value;
    if(reg==LC_SQE && value==1) {
        if(scenario==50) *(uint64_t*)((uintptr_t)allocation+0x12000)|=3ull<<53;
        if(!translate(LC_VA,false,true) || scenario==49) {
            smmu[0x8058/4]=8;smmu[0x8060/4]=LC_VA;smmu[0x8068/4]=0x50043;gpu[LC_CP_INT]=0x80;
        } else {
            assert(*gpu_word(LC_VA,false)==fw[1]);
            assert(!translate(LC_VA+LC_RING,false,true) && !translate(LC_VA+LC_TARGET,false,true));
        }
    }
    if(reg==0x807) execute(value);
}
static void setup(unsigned mode) {
    if(allocation) {free(allocation);allocation=0;} /* Simulated reboot of retained memory. */
    memset(&lc,0,sizeof(lc));memset(gpu,0,sizeof(gpu));memset(smmu,0,sizeof(smmu));
    memset(cc,0,sizeof(cc));memset(gcc,0,sizeof(gcc));memset(fw,0,sizeof(fw));
    scenario=mode;option=7;chip=0x06010000;
    maps=writes=gpu_writes=submits=allocations=frees=cleans=flushes=processed=clock_writes=0;
    poll_delays=pending_roq=0;
    fw[1]=0x197;
    cc[0x1540/4]=cc[0x100c/4]=1u<<31;
    cc[0x1078/4]=cc[0x1054/4]=cc[0x1098/4]=cc[0x5000/4]=1;
    gcc[0x3600c/4]=gcc[0x36018/4]=gcc[0x36004/4]=1;gcc[0x7900c/4]=16;
    smmu[0x20/4]=0x4c017e04;smmu[0x1800/4]=1;smmu[0x1000/4]=0x1f300;
    smmu[0x8010/4]=0x38071;smmu[0x8030/4]=0xa0a02020;smmu[0x8038/4]=0x44;
    smmu[0x8020/4]=(uint32_t)prepared;smmu[0x8024/4]=(uint32_t)(prepared>>32);
    smmu[0x808/4]=0x80000002;smmu[0xc08/4]=0x10000; /* Secure SID2 entry, unchanged. */
    if(mode==3) chip=0x06030001;
    if(mode==4) cc[0x1054/4]=0x80000000;
    if(mode==5) smmu[0x8020/4]^=4096;
    if(mode==6) smmu[0x800/4]=0x80000000;
    if(mode==7) smmu[0x808/4]=0x80030002;
    if(mode==9) gpu[LC_STATUS]=4;
    if(mode==12) smmu[0x8030/4]^=1;
    if(mode==13) for(unsigned i=0;i<4;i++) {smmu[(0x800+i*4)/4]=0x80000004+i;smmu[(0xc00+i*4)/4]=0x10000;}
    if(mode==25) fw[1]=0x100;
    if(mode==28) smmu[0x48/4]=1;
    if(mode==29) gpu[LC_HW_FAULT]=1;
    if(mode==30) gpu[LC_RPTR]=1;
    if(mode==37) gpu[LC_SQE]=3;
    if(mode==49) smmu[0xc00/4]=0x4a20ff;
}
int main(void) {
    assert(lc_pkt7(0x48,8)==0x70c80008 && lc_pkt7(0x3d,3)==0x703d8003 && lc_pkt7(0x26,0)==0x70268000);
    setup(0);option=6;lemon_gpu_cp_probe();assert(!maps && !writes && !allocations);
    setup(0);lemon_gpu_cp_probe();
    assert(lc.executed && lc.checkpoints==0x1f && submits==2 && flushes==1 && allocation && !frees);
    assert(!(smmu[0x8000/4]&1) && smmu[0x800/4]==0 && gpu[LC_SQE]==3);
    unsigned previous=writes;lemon_gpu_cp_probe();assert(writes==previous);
    for(unsigned i=1;i<=50;i++) {
        if(i==27) continue;
        setup(i);lemon_gpu_cp_probe();
        if(i==23 || i==36 || i==38 || i==39 || i==43) assert(lc.executed); /* Execution and teardown are separate outcomes. */
        else assert(!lc.executed);
        assert(smmu[0x808/4]==(i==7?0x80030002:i==13?0x80000006:0x80000002));
        if(i<=13 || i==25 || i==26 || i==28 || i==29 || i==30 || i==37) assert(!writes);
        if(i==11) assert(frees==1 && !allocation);
        if(i>=14 && i<=24) assert(allocation && !frees);
        if(i==23) assert(gpu[LC_SQE]==1 && (smmu[0x8000/4]&1));
        if(i==24) assert(smmu[0x800/4]==0x80000004 && (smmu[0x8000/4]&1));
        if(i==33) assert(*(uint32_t*)((uintptr_t)allocation+LC_TARGET)==LC_MARKER && !lc.executed);
        if(i==14 || i==34 || i==35) assert(!submits && !lc.pointer && !lc.route && allocation && !frees && !gpu[LC_SQE]);
        if(i==36) assert(gpu[LC_SQE]==3 && (smmu[0x8000/4]&1));
        if(i==38) assert(poll_delays==5 && submits==2);
        if(i==39) assert(pending_roq==0x00800060 && submits==2);
        if(i==14 || i==40 || i==41 || i==42) {
            assert(!submits && !lc.pointer && !lc.route && !gpu[LC_SQE] && !gpu[LC_AHB]);
            assert(allocation && !frees && gpu[0x8c3]==(i==41?0:48));
            assert(poll_delays==(i==42?0:1000));
        }
        if(i==43) assert(lc.checkpoints==0x1f && submits==2);
        if(i==44 || i==45 || i==46) assert(!submits && !lc.route && !lc.checkpoints && !gpu[LC_SQE]);
        if(i==47) assert(!submits && !lc.started && lc.checkpoints==1);
        if(i==48) assert(submits==1 && lc.checkpoints==7 && *(uint32_t*)((uintptr_t)allocation+LC_TARGET)==0x11111111);
        if(i==49 || i==50) assert(!submits && !lc.executed && lc.checkpoints==7 && smmu[0x8058/4]==8 && !smmu[0x800/4] && !(smmu[0x8000/4]&1) && allocation && !frees);
    }
    setup(0);
    puts("PASS: actual combined A610 CP code; 49 scenarios, SMMU instruction fetch permission model, RO executable firmware/NX ring+data, PF fault stops before WPTR, ignored inactive S2CR restore separate from detach, live context/marker/full proof and retention guards; MODEL ONLY");
}
'''
with tempfile.TemporaryDirectory() as directory:
    root=Path(directory)
    (root/'full.c').write_text(header+source)
    (root/'test.c').write_text(header+mock+test)
    flags=['-std=c11','-Wall','-Wextra','-Werror']
    subprocess.run(['cc',*flags,'-fsanitize=address,undefined',str(root/'test.c'),'-o',str(root/'test')],check=True)
    subprocess.run([str(root/'test')],check=True)
    cross=shutil.which('aarch64-linux-gnu-gcc')
    if cross:
        subprocess.run([cross,*flags,'-mcpu=cortex-a53','-march=armv8-a+crypto','-mno-outline-atomics','-c',str(root/'full.c'),'-o',str(root/'cp.o')],check=True)
        print('PASS: actual CP module ARMv8.0 compile including explicit-GPR MMIO/barriers')
