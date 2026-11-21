"""Test SMMU ATS and disabled-context fallback with a page-walking MMIO model."""
import argparse
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--xnu', type=Path, required=True)
tree = parser.parse_args().xnu
source = (tree/'bsd/dev/lemon_gpu_memory.c').read_text()
for include in ('kern/clock.h','vm/vm_kern.h','vm/pmap.h','arm/caches_internal.h'):
    assert '#include <'+include+'>' in source
assert 'bsd/dev/lemon_gpu_memory.c' in (tree/'bsd/conf/files').read_text()
source = re.sub(r'^#include <[^>]+>\n','',source,flags=re.M)
header = '''
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#define ARM64_BOARD_CONFIG_SWEET 1
#define LEMON_4K 1
#define PAGE_SIZE 4096u
#define PAGE_MASK 4095u
#define KMA_DATA 1
#define KMA_ZERO 2
#define VM_KERN_MEMORY_IOKIT 1
#define KERN_SUCCESS 0
#define TRUE 1
#define ptoa_64(p) ((uint64_t)(p)<<12)
typedef uintptr_t vm_offset_t,vm_size_t;
typedef uint64_t addr64_t;
typedef uint32_t ppnum_t;
typedef void *pmap_t,*vm_map_t;
extern pmap_t kernel_pmap;
extern vm_map_t kernel_map;
extern void delay(int);
extern int kmem_alloc_contig(vm_map_t,vm_offset_t*,vm_size_t,vm_offset_t,ppnum_t,ppnum_t,unsigned,unsigned);
extern void kmem_free(vm_map_t,vm_offset_t,vm_size_t);
extern void clean_dcache64(addr64_t,unsigned,bool);
'''
mock = source
for name,result,args in [('lm_read','uint32_t','vm_offset_t,unsigned'),('lm_read64','uint64_t','vm_offset_t,unsigned'),
                         ('lm_write','void','vm_offset_t,unsigned,uint32_t'),('lm_write64','void','vm_offset_t,unsigned,uint64_t')]:
    mock,count = re.subn(r'static '+result+r'\n'+name+r'\(.*?\n}\n',
                         'static '+result+' '+name+'('+args+');\n',mock,flags=re.S)
    assert count==1,name
mock = re.sub(r'^\s*__asm__ volatile\([^\n]+\);','',mock,flags=re.M)
test = r'''
static uint32_t gcc[0x80000/4],cc[0x9000/4],regs[LM_MAP_SIZE/4];
static unsigned mode,allocations,frees,context_writes,bank_reads,ats_calls,cleaned,enabled;
static unsigned ttbr_reads;
static uint32_t original_sctlr;
static uint64_t original_ttbr[2];
static void *allocation;
static const uint64_t physical=0x100100000ull;
pmap_t kernel_pmap=(void*)1;
vm_map_t kernel_map=(void*)2;
void delay(int us) {assert(us==1);}
vm_offset_t ml_io_map(vm_offset_t pa,vm_size_t size) {
    if(pa==0x01400000) {assert(size==sizeof(gcc));return (uintptr_t)gcc;}
    if(pa==0x05990000) {assert(size==sizeof(cc));return (uintptr_t)cc;}
    assert(pa==0x059a0000 && size==sizeof(regs));
    assert((cc[0x5000/4]&0x80000001u)==1);
    return mode==2?0:(uintptr_t)regs;
}
int kmem_alloc_contig(vm_map_t map,vm_offset_t *out,vm_size_t size,vm_offset_t mask,
    ppnum_t max,ppnum_t pnum_mask,unsigned flags,unsigned tag) {
    assert(map==kernel_map && size==LM_BYTES && mask==4095 && !max && !pnum_mask);
    assert(flags==(KMA_DATA|KMA_ZERO) && tag==VM_KERN_MEMORY_IOKIT);allocations++;
    if(mode==6) return -1;
    allocation=aligned_alloc(4096,size);assert(allocation);memset(allocation,0,size);
    *out=(uintptr_t)allocation;return 0;
}
ppnum_t pmap_find_phys(pmap_t map,addr64_t va) {
    assert(map==kernel_pmap && allocation && va>=(uintptr_t)allocation && va<(uintptr_t)allocation+LM_BYTES);
    unsigned offset=va-(uintptr_t)allocation;
    if(mode==7 && offset==8192) offset+=4096;
    return (physical+offset)>>12;
}
void clean_dcache64(addr64_t pa,unsigned length,bool physical_flag) {
    assert(pa==physical && length==LM_BYTES && physical_flag);cleaned++;
    assert(*(uint32_t*)((uintptr_t)allocation+12288)==0x4c454d4f);
}
void kmem_free(vm_map_t map,vm_offset_t va,vm_size_t size) {
    assert(map==kernel_map && va==(uintptr_t)allocation && size==LM_BYTES);
    assert(regs[LM_CB/4]==original_sctlr && !(original_sctlr&1));
    assert(!(regs[(LM_CB+0x8f0)/4]&1) && !(regs[(LM_CB+0x7f4)/4]&1));
    assert(lm_read64((uintptr_t)regs,LM_CB+0x20)==original_ttbr[0]);
    assert(lm_read64((uintptr_t)regs,LM_CB+0x28)==original_ttbr[1]);
    frees++;free(allocation);allocation=0;
}
static bool cb_register(unsigned o) {
    return o==LM_CB || o==LM_CB+0x10 || (o>=LM_CB+0x20 && o<=LM_CB+0x3c) ||
           o==LM_CB+0x50 || o==LM_CB+0x54 || o==LM_CB+0x58 ||
           o==LM_CB+0x610 || o==LM_CB+0x7f0 || o==LM_CB+0x7f4 ||
           o==LM_CB+0x800 || o==LM_CB+0x804 || o==LM_CB+0x8f0;
}
static uint32_t lm_read(vm_offset_t base,unsigned o) {
    assert(!(o&3));
    if(base==(uintptr_t)gcc) {
        assert(o==0x36004 || o==0x7900c || o==0x36040 || o==0x3600c || o==0x36018);
        return gcc[o/4];
    }
    if(base==(uintptr_t)cc) {
        assert(o==0x1540 || o==0x1078 || o==0x5000);return cc[o/4];
    }
    assert(base==(uintptr_t)regs && o<LM_MAP_SIZE);
    if(regs[0x20/4]&(1u<<26)) assert(o!=LM_CB+0x8f0 && o!=LM_CB+0x50 && o!=LM_CB+0x54);
    assert(o==0 || o==0x20 || o==0x24 || o==0x28 || o==0x3c || o==0x48 ||
           o==0x1000 || o==0x1800 || (o>=0x800 && o<0x820) ||
           (o>=0xc00 && o<0xc20) || cb_register(o));
    if(o>=LM_CB) bank_reads++;
    if(mode==34 && o==LM_CB+0x20 && ++ttbr_reads==2) return regs[o/4]^0x1000;
    return regs[o/4];
}
static uint64_t lm_read64(vm_offset_t base,unsigned o) {
    assert(base==(uintptr_t)regs && (o==LM_CB+0x20 || o==LM_CB+0x28 || o==LM_CB+0x50));
    return lm_read(base,o)|((uint64_t)lm_read(base,o+4)<<32);
}
static void lm_write(vm_offset_t base,unsigned o,uint32_t value) {
    if(base==(uintptr_t)cc) {
        assert(o==0x5000 && ((value^cc[o/4])&~1u)==0);
        if(mode!=1) cc[o/4]=value&~(1u<<31);
        return;
    }
    assert(base==(uintptr_t)regs && allocation);
    if(regs[0x20/4]&(1u<<26)) {
        assert(o!=LM_CB+0x610 && o!=LM_CB+0x7f0);
        assert(o!=LM_CB); /* No SCTLR writes at all on the no-ATS path. */
    }
    /* No global CR0, SMR/S2CR, other banks, reset, stream or GPU writes. */
    assert(o==0x1000 || o==0x1800 || o==LM_CB || o==LM_CB+0x10 || o==LM_CB+0x30 ||
           o==LM_CB+0x34 || o==LM_CB+0x38 || o==LM_CB+0x3c || o==LM_CB+0x58 ||
           o==LM_CB+0x610 || o==LM_CB+0x7f0);
    context_writes++;
    if(mode==9 && o==LM_CB+0x34) return;
    if(mode==15 && o==0x1800 && value==1) return;
    if(mode==30 && o==LM_CB+0x30 && value) return;
    if(mode==31 && o==LM_CB+0x30 && !value) return;
    if(mode==13 && enabled && o==LM_CB && value==0) return;
    if(mode==14 && enabled && o==LM_CB+0x30 && value==0) return;
    if(o==LM_CB+0x58) {regs[o/4]&=~value;return;}
    regs[o/4]=value;
    if(o==LM_CB && (value&1)) {
        assert(cleaned && regs[0x1800/4]==1 && (regs[0x1000/4]&0x30000)==0x10000);
        assert(lm_read64(base,LM_CB+0x20)==physical);
        assert((regs[(LM_CB+0x30)/4]&63)==32 && (regs[(LM_CB+0x30)/4]&(1u<<23)));
        assert(!(value&(1u<<6)));enabled++;
    }
    if(o==LM_CB+0x7f0) regs[(LM_CB+0x7f4)/4]=mode==12?1:0;
}
static uint64_t table_word(uint64_t pa) {
    assert(allocation && pa>=physical && pa+8<=physical+12288 && !(pa&7));
    return *(uint64_t*)((uintptr_t)allocation+pa-physical);
}
static uint64_t walk(uint32_t va) {
    uint64_t table=lm_read64((uintptr_t)regs,LM_CB+0x20)&0x0000fffffffff000ull;
    const unsigned shifts[3]={30,21,12};
    for(unsigned level=0;level<3;level++) {
        uint64_t pte=table_word(table+((va>>shifts[level])&511)*8);
        if((pte&3)!=3) return 1;
        table=pte&0x0000fffffffff000ull;
        if(level==2) {
            assert((pte&(1u<<10)) && (pte&(1u<<5)));
            assert(table>=physical+12288 && table<physical+LM_BYTES);
        }
    }
    return table;
}
static void lm_write64(vm_offset_t base,unsigned o,uint64_t value) {
    assert(base==(uintptr_t)regs && allocation);
    assert(o==LM_CB+0x20 || o==LM_CB+0x28 || o==LM_CB+0x800);context_writes++;
    if(regs[0x20/4]&(1u<<26)) assert(o!=LM_CB+0x800);
    if(mode==36 && o==LM_CB+0x20 && value==original_ttbr[0]) return;
    regs[o/4]=value;regs[o/4+1]=value>>32;
    if(o==LM_CB+0x800) {
        assert(enabled && (regs[LM_CB/4]&1));ats_calls++;
        if(mode==11) {regs[(LM_CB+0x8f0)/4]=1;return;}
        uint64_t par=walk(value);
        if(mode==10) par=value; /* Detect bypass/wrong translation. */
        regs[(LM_CB+0x50)/4]=par;regs[(LM_CB+0x54)/4]=par>>32;
        if(par&1) regs[(LM_CB+0x58)/4]|=2;
    }
}
static void setup(unsigned m) {
    if(allocation) {free(allocation);allocation=0;} /* model-only retained-memory release */
    mode=m;allocations=frees=context_writes=bank_reads=ats_calls=cleaned=enabled=ttbr_reads=0;
    memset(gcc,0,sizeof(gcc));memset(cc,0,sizeof(cc));memset(regs,0,sizeof(regs));
    gcc[0x36004/4]=9;gcc[0x7900c/4]=0x4bf0;gcc[0x36040/4]=8;
    gcc[0x3600c/4]=gcc[0x36018/4]=1;cc[0x1540/4]=1u<<31;cc[0x1078/4]=1;
    cc[0x5000/4]=0x80000000;
    regs[0x20/4]=(1u<<30)|(1u<<27)|8;regs[0x24/4]=0x20000008;
    regs[0x28/4]=(1u<<12)|0x11;regs[0x3c/4]=0x20;
    if(m==3) regs[0x20/4]=0;
    if(m==4) regs[0x800/4]=1u<<31;
    if(m==5) regs[LM_CB/4]=1;
    if(m==8) regs[0x28/4]=(1u<<12);
    if(m==16) regs[0x24/4]|=1u<<31;
    if(m==17) regs[(LM_CB+0x20)/4]=0x12345000;
    if(m==18) regs[0x20/4]=(1u<<30)|(1u<<27)|129;
    if(m==19) regs[0]=1;
    if(m==20) regs[0x20/4]|=1u<<26;
    if(m==21) regs[0x28/4]|=0xf0;
    if(m==22) gcc[0x36018/4]=0x80000000;
    if(m==23) regs[0x48/4]=1;
    if(m==24) regs[0x24/4]|=1u<<16;
    if(m==25) regs[0x1000/4]=7;
    if(m==26) regs[0x1800/4]=1u<<16;
    if(m==27) regs[(LM_CB+0x58)/4]=2;
    if(m==28) {regs[0x800/4]=1u<<31;regs[0xc00/4]=0x30000;}
    if(m>=29) {
        regs[0]=0x220406;regs[0x20/4]=0x4c017e04;regs[0x24/4]=0x20000005;
        regs[0x28/4]=0x5511;regs[0x3c/4]=0x24;
    }
    if(m>=32) {
        regs[LM_CB/4]=0x14136108;
        regs[(LM_CB+0x20)/4]=0x1242b820;regs[(LM_CB+0x24)/4]=0x2c087de5;
        regs[(LM_CB+0x28)/4]=0x08433320;regs[(LM_CB+0x2c)/4]=0x110910d9;
        regs[(LM_CB+0x10)/4]=0x123;regs[(LM_CB+0x30)/4]=0x123456;
        regs[(LM_CB+0x34)/4]=0x33;regs[(LM_CB+0x38)/4]=0xabc;
    }
    if(m==33) regs[LM_CB/4]|=1;
    if(m==35) {regs[0x800/4]=1u<<31;regs[0xc00/4]=0;}
    original_sctlr=regs[LM_CB/4];
    original_ttbr[0]=lm_read64((uintptr_t)regs,LM_CB+0x20);
    original_ttbr[1]=lm_read64((uintptr_t)regs,LM_CB+0x28);ttbr_reads=0;
}
int main(void) {
    uint64_t *tables=aligned_alloc(4096,LM_BYTES);assert(tables);
    memset(tables,0,LM_BYTES);assert(lm_tables((uintptr_t)tables,physical,36));
    assert(lm_walk((uintptr_t)tables,physical,LM_VA)==physical+12288);
    assert(lm_walk((uintptr_t)tables,physical,LM_VA+4096)==physical+16384);
    assert(lm_walk((uintptr_t)tables,physical,LM_VA+8192)==1);
    tables[LM_VA>>30]=(physical+LM_BYTES)|3; /* Out-of-allocation table pointer. */
    assert(lm_walk((uintptr_t)tables,physical,LM_VA)==1);
    tables[LM_VA>>30]=physical|1; /* Block descriptor is not a table. */
    assert(lm_walk((uintptr_t)tables,physical,LM_VA)==1);free(tables);
    setup(0);lemon_gpu_memory_probe();
    assert(allocations==1 && frees==1 && ats_calls==3 && enabled==1 && !allocation);
    assert(!regs[0x1000/4] && !regs[0x1800/4] && !regs[LM_CB/4]);
    for(unsigned m=1;m<=36;m++) {
        setup(m);lemon_gpu_memory_probe();
        if(m==11 || m==12 || m==13 || m==14 || m==31 || m==36) assert(allocation && !frees);
        else assert(!allocation);
        if(m<=5 || (m>=16 && m<=28 && m!=20)) assert(!allocations && !context_writes);
        if(m==6) assert(allocations==1 && !context_writes && !frees);
        if(m==7 || m==8) assert(allocations==1 && frees==1 && !context_writes);
        if(m==9 || m==15) assert(!ats_calls && frees==1);
        if(m==10) assert(ats_calls==1 && frees==1);
        if(m==20 || (m>=29 && m<=32) || m==36) {
            assert(allocations==1 && context_writes && !enabled && !ats_calls);
            if(m!=31 && m!=36) assert(frees==1 && !regs[0x1000/4] && !regs[0x1800/4]);
        }
        if(m==32) assert(regs[(LM_CB+0x10)/4]==0x123 && regs[(LM_CB+0x30)/4]==0x123456 &&
                         regs[(LM_CB+0x34)/4]==0x33 && regs[(LM_CB+0x38)/4]==0xabc);
        if(m>=33 && m<=35) assert(!allocations && !context_writes);
    }
    setup(0);
    puts("PASS: ATS/no-ATS and exact v32 disabled nonzero registers, stable snapshot gate, original TTBR/SCTLR restore, active/routed/unstable refusal, restore failure retention, bounded tables; no no-ATS SCTLR/ATS/TLB or global/stream/secure writes");
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
        print('PASS: full GPU memory module including explicit-GPR MMIO stores ARMv8.0 compile')
