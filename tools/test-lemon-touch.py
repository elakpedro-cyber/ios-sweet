"""Exercise the port's actual packet decoder, SPI FIFO loop and opt-in gates."""
import argparse
from pathlib import Path
import re
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--xnu', type=Path, required=True)
args = parser.parse_args()
source = (args.xnu / 'bsd/dev/lemon_touch.c').read_text()
assert 'clock_interval_to_deadline(100, NSEC_PER_MSEC, &lt.release_deadline);' in source
report_loop=source[source.index('err = lt_decode(report, &mask, x, y);'):]
bad_branch=report_loop[:report_loop.index('\n\t\t} else {')]
assert 'lt_expire_contacts();' in bad_branch and 'lt_report(0' not in bad_branch

# Check the whole worker too: the executable MMIO mocks below test selected functions.
syntax_header = r'''
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#define ARM64_BOARD_CONFIG_SWEET 1
#define LEMON_4K 1
#define KERN_SUCCESS 0
#define NSEC_PER_MSEC 1000000
#define THREAD_UNINT 0
#define THREAD_CONTINUE_NULL 0
typedef uintptr_t vm_offset_t, vm_size_t;
typedef void *thread_t;
typedef int kern_return_t, wait_result_t;
extern void delay(unsigned), clock_interval_to_deadline(unsigned,unsigned,uint64_t *);
extern void clock_get_uptime(uint64_t *);
extern void absolutetime_to_nanoseconds(uint64_t,uint64_t *);
extern int assert_wait_deadline(void *,int,uint64_t);
extern void thread_block(void *), thread_deallocate(thread_t);
extern thread_t current_thread(void);
extern kern_return_t kernel_thread_start(void (*)(void *,wait_result_t),void *,thread_t *);
extern int PE_parse_boot_argn(const char *,void *,unsigned);
'''
with tempfile.TemporaryDirectory() as folder:
    c = Path(folder) / 'syntax.c'
    c.write_text(syntax_header + re.sub(r'^#include <[^>]+>\n', '', source, flags=re.M))
    subprocess.run(['cc','-std=c11','-fsyntax-only','-Wall','-Wextra','-Werror',str(c)],check=True)

def function(name):
    match = re.search(r'(?:static )?(?:int|bool|void)\n' + name + r'\(', source)
    assert match, name
    end = source.index('\n}\n', match.start()) + 3
    return source[match.start():end]

assert '#if defined(ARM64_BOARD_CONFIG_SWEET) && defined(LEMON_4K)' in source
assert 'sweet_rpmh' not in source and 'sweet_spmi' not in source
hook = (args.xnu / 'bsd/dev/sweet_touch.c').read_text()
assert '#if defined(LEMON_4K)\n\textern void lemon_touch_init(void);\n\tlemon_touch_init();\n\treturn;' in hook
hid = (args.xnu / 'iokit/Kernel/arm/hid/SweetHID.cpp').read_text()
assert '#if defined(LEMON_4K)\n#define SWEET_PANEL_HEIGHT 2340\n#else\n#define SWEET_PANEL_HEIGHT 2400' in hid
assert '(fLogicalH - SWEET_PANEL_HEIGHT) / 2' in hid
assert 'y >= SWEET_PANEL_HEIGHT ? SWEET_PANEL_HEIGHT - 1 : y' in hid

program = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
typedef uintptr_t vm_offset_t;
typedef void *thread_t;
typedef int kern_return_t;
#define KERN_SUCCESS 0
/* DEFINITIONS */
static unsigned writes, ticks, option, threads, se_reads, gmode;
static unsigned wanted, sent, got, pending, fault;
static uint8_t wire[68], captured[68];
static unsigned regs[0x1000];
static unsigned hid_calls, hid_down, hid_up;
static uint64_t mock_now;
static void clock_get_uptime(uint64_t *now) {*now=mock_now;}
static void sweet_hid_touch(int i, int down, int x, int y) {
    assert(i>=0 && i<10 && x>=0 && x<1080 && y>=0 && y<2340);
    hid_calls++; if (down) hid_down++; else hid_up++;
}
static uint32_t lt_rd(vm_offset_t base, unsigned off) {
    if (base == 1) { /* GCC */
        if (off==LT_RCG || off==LT_RCG+4 || off==LT_RCG+0x14 || off==LT_VOTE) return 0;
        return gmode ? 1u<<31 : 0;
    }
    if (base == 2) return 0; /* WEST GPIO */
    assert(base == 3); se_reads++;
    if (off==0x68) return 1u<<8;
    if (off==0xe24 || off==0xe28) return (32u<<24)|(16u<<16);
    if (off==0x40) return fault==1 ? 1 : (wanted && !(sent==wanted && !pending));
    if (off==0x610) {
        if (fault==3 && ticks>2) return 8;
        if (fault==4 && sent==wanted && got==wanted) return 9; /* late error */
        return wanted && sent==wanted && (pending==0 || fault==5) ? 1 : 0;
    }
    if (off==0x800) return 0;
    if (off==0x804) {
        if (!wanted) return 0;
        if (fault==6) return 100;
        if (fault==2) return 0;
        return (pending+3)/4;
    }
    if (off==0x780) {
        uint32_t word=0;
        for (unsigned j=0; j<4 && pending; j++) {word|=(uint32_t)wire[got++]<<(8*j);pending--;}
        return word;
    }
    return regs[off/4];
}
static void lt_wr(vm_offset_t base, unsigned off, uint32_t value) {
    writes++;
    if (base != 3) return;
    if (off==0x600) {wanted=regs[0x26c/4];assert(value==(3u<<27) || value==(1u<<27));}
    if (off==0x700) {
        for(unsigned j=0;j<4 && sent<wanted;j++) captured[sent++]=(uint8_t)(value>>(8*j));
        if(regs[0x270/4] && fault!=2) pending=sent-got;
    }
    regs[off/4]=value;
}
static void delay(unsigned usec) {assert(usec==1);ticks++;}
/* FUNCTIONS */
static void lt_thread(void *arg, int result) {(void)arg;(void)result;}
static void PE_parse_boot_argn(const char *name, int *value, unsigned size) {
    assert(!strcmp(name,"lemontouch") && size==4); *value=(int)option;
}
static kern_return_t kernel_thread_start(void (*fn)(void *,int),void *arg,thread_t *thread) {
    assert(fn==lt_thread && (uintptr_t)arg==option);threads++;*thread=(void *)1;return 0;
}
static void thread_deallocate(thread_t thread) {assert(thread==(void *)1);}
/* INIT */
static void reset(void) {
    memset(&lt,0,sizeof(lt));lt.gcc=1;lt.gpio=2;lt.se=3;lt.depth=16;
    memset(regs,0,sizeof(regs));writes=ticks=se_reads=wanted=sent=got=pending=fault=0;
    for(unsigned i=0;i<68;i++) wire[i]=(uint8_t)(i*7+3);
}
static void checksum(uint8_t *r) {
    unsigned sum=0;for(unsigned i=1;i<65;i++)sum+=r[i];r[65]=(uint8_t)-sum;
}
static void point(uint8_t *r,unsigned slot,unsigned id,unsigned status,unsigned x,unsigned y) {
    uint8_t *p=r+1+slot*6;p[0]=(id<<3)|status;p[1]=x>>4;p[2]=y>>4;p[3]=(x<<4)|(y&15);
}
int main(void) {
    uint8_t report[66]={0};int x[10]={0},y[10]={0};unsigned mask=123;
    assert(!lt_decode(report,&mask,x,y) && mask==0);
    point(report,0,10,1,1079,2339);checksum(report);
    assert(!lt_decode(report,&mask,x,y) && mask==512 && x[9]==1079 && y[9]==2339);
    point(report,1,10,2,1,1);checksum(report);mask=123;
    assert(lt_decode(report,&mask,x,y)==EINVAL && mask==123);
    memset(report,0,66);point(report,0,0,1,1,1);checksum(report);assert(lt_decode(report,&mask,x,y));
    point(report,0,11,1,1,1);checksum(report);assert(lt_decode(report,&mask,x,y));
    point(report,0,1,1,1080,1);checksum(report);assert(lt_decode(report,&mask,x,y)==ERANGE);
    point(report,0,1,1,1,2340);checksum(report);assert(lt_decode(report,&mask,x,y)==ERANGE);
    memset(report,0,66);point(report,0,1,1,1,1);checksum(report);report[65]++;
    assert(lt_decode(report,&mask,x,y)==EINVAL);
    memset(report+1,0xfd,6);assert(lt_decode(report,&mask,x,y)==EAGAIN);
    memset(report+1,0x77,6);assert(lt_decode(report,&mask,x,y)==EAGAIN);
    memset(report,0,66);point(report,0,30,1,1,1);checksum(report);assert(lt_decode(report,&mask,x,y));
    memset(report,0,66);for(unsigned i=0;i<10;i++)point(report,i,i+1,1,i,i);checksum(report);
    assert(!lt_decode(report,&mask,x,y) && mask==1023);
    reset();lt_report(mask,x,y);assert(hid_down==10);lt_report(0,x,y);assert(hid_up==10 && !lt.active);
    reset();hid_calls=hid_down=hid_up=0;
    lt.release_deadline=100;lt_report(1,x,y);assert(hid_down==1);
    mock_now=1;lt_expire_contacts();mock_now=99;lt_expire_contacts();
    assert(!hid_up && lt.active==1); /* short bad-read gaps preserve the swipe */
    lt.release_deadline=180;mock_now=100;lt_expire_contacts();
    mock_now=179;lt_expire_contacts();assert(!hid_up && lt.active==1);
    mock_now=180;lt_expire_contacts();assert(hid_up==1 && !lt.active);
    mock_now=200;lt_expire_contacts();assert(hid_up==1); /* exactly one timeout release */
    lt.release_deadline=500;lt_report(1,x,y);mock_now=201;lt_report(0,x,y);
    assert(hid_up==2 && !lt.active); /* a real valid finger-up is still immediate */
    for(unsigned n=1;n<=67;n++) {
        uint8_t tx[68],rx[69];for(unsigned i=0;i<68;i++)tx[i]=(uint8_t)(i*3);
        reset();memset(rx,0xcc,sizeof(rx));
        assert(!lt_transfer(tx,rx,n));assert(sent==n && got==n);
        assert(!memcmp(rx,wire,n) && rx[n]==0xcc && !memcmp(tx,captured,n));
        reset();assert(!lt_transfer(tx,NULL,n));assert(sent==n && got==0 && !memcmp(tx,captured,n));
    }
    uint8_t tx[67]={0},rx[67];
    reset();fault=1;assert(lt_transfer(tx,rx,67)==EBUSY && writes==0);
    reset();fault=2;assert(lt_transfer(tx,rx,67)==ETIMEDOUT && ticks<=25000);
    reset();fault=3;assert(lt_transfer(tx,rx,67)==EIO);
    reset();fault=4;assert(lt_transfer(tx,rx,67)==EIO);
    reset();fault=5;assert(!lt_transfer(tx,rx,67)); /* DONE with RX data still queued */
    reset();fault=6;assert(lt_transfer(tx,rx,67)==EIO);
    reset();assert(lt_page(0x100)==EINVAL && writes==0);
    assert(lt_read(0,rx,66)==EINVAL && writes==0);
    reset();gmode=1;assert(!lt_snapshot() && !writes && !se_reads);
    reset();gmode=0;assert(lt_snapshot() && !writes && se_reads);
    reset();regs[0x254/4]=2;assert(lt_setup()); /* inherited 32-bit granularity must be cleared */
    assert(regs[0x254/4]==0);
    assert(regs[0x250/4]==0 && regs[0x268/4]==4 && regs[0x278/4]==200u<<10);
    assert(regs[0x260/4]==0x7f8fe && regs[0x264/4]==0xffefe && !regs[0xe1c/4]);
    for(option=0;option<=3;option++) {
        reset();unsigned before=threads;lemon_touch_init();lemon_touch_init();
        assert(threads-before==((option==1 || option==2)?1:0) && !writes && !se_reads);
    }
    puts("PASS: decoder/FIFO/errors, CS0 setup, read-only snapshot/default-off, invalid-frame grace, 100ms stale release, immediate real release");
}
'''
defines = source[source.index('#define LT_GCC'):source.index('static int lt_wait_chan;')]
functions = '\n'.join(function(name) for name in ('lt_clear', 'lt_snapshot', 'lt_setup', 'lt_transfer', 'lt_page', 'lt_read', 'lt_decode', 'lt_report', 'lt_expire_contacts'))
program = program.replace('/* DEFINITIONS */', defines).replace('/* FUNCTIONS */', functions)
program = program.replace('/* INIT */', function('lemon_touch_init'))
with tempfile.TemporaryDirectory() as folder:
    c, binary = Path(folder) / 'touch.c', Path(folder) / 'touch'
    c.write_text(program)
    subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', '-fsanitize=address,undefined',
                    str(c), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
