"""Exercise actual UFS wait guards and opt-in touch diagnostic accounting."""
import argparse
from pathlib import Path
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--xnu', type=Path, required=True)
tree = parser.parse_args().xnu
touch = (tree / 'bsd/dev/lemon_touch.c').read_text()
start = touch.index('static struct {', touch.index('/* Diagnostics only:'))
end = touch.index('/* A corrupt sample', start)
helper = touch[start:end]
ufs = (tree / 'bsd/dev/sweet_ufs.c').read_text()
start = ufs.index('\tbool sleepable = su.wait')
end = ufs.index('\n\t__builtin_arm_dsb', start)
wait = ufs[start:end]
aks = (tree / 'iokit/Kernel/arm/SweetKeyStore.cpp').read_text()
assert 'static int sweet_aks_log = 1;' in aks
assert 'PE_parse_boot_argn("sweetaks_log"' in aks
assert 'if (sweet_aks_log) {\n\t\tchar name[32];' in aks

program = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <stdarg.h>
typedef void *event_t;
#define THREAD_UNINT 0
#define TIMEOUT_URGENCY_SYS_CRITICAL 0
#define THREAD_WAITING 1
#define THREAD_CONTINUE_NULL 0
#define CMD_SPIN_NS 50000
#define CMD_SLEEP_NS 200000
#define REG_UTRLDBR 1
#define REG_UTRLCLR 2
#define MIN(a,b) ((a)<(b)?(a):(b))
static uint64_t clock_ns, complete_at, wake_at;
static unsigned sleeps, writes;
static bool interrupts=true, interrupt_context;
static int preemption;
static struct {bool wait,ready;} su;
static uint64_t mach_absolute_time(void) {return clock_ns;}
static void nanoseconds_to_absolutetime(uint64_t n,uint64_t *p) {*p=n;}
static void absolutetime_to_nanoseconds(uint64_t n,uint64_t *p) {*p=n;}
static bool ml_get_interrupts_enabled(void) {return interrupts;}
static bool ml_at_interrupt_context(void) {return interrupt_context;}
static int get_preemption_level(void) {return preemption;}
static unsigned ufs_rd(unsigned r) {assert(r==REG_UTRLDBR); return clock_ns<complete_at;}
static void ufs_wr(unsigned r,unsigned v) {assert(r==REG_UTRLCLR && v==~1u);writes++;}
static void delay(unsigned n) {clock_ns+=n*1000;}
static int assert_wait_deadline_with_leeway(event_t e,int i,int urgency,uint64_t w,unsigned leeway) {
    assert(e==&su.wait && !i && !urgency && !leeway);
    assert(w>=clock_ns);wake_at=w;return THREAD_WAITING;
}
static void thread_block(void *p) {assert(!p);sleeps++;clock_ns=wake_at>clock_ns?wake_at:clock_ns+1;}
static int run_wait(uint64_t deadline) {
    uint8_t cdb[]={0x28};
/* WAIT */
    return 0;
}
/* TOUCH */
int main(void) {
    for(unsigned mode=0;mode<6;mode++) {
        clock_ns=1;complete_at=1000001;sleeps=writes=0;
        su.wait=mode!=1;su.ready=mode!=2;
        interrupts=mode!=3;interrupt_context=mode==4;preemption=mode==5;
        assert(!run_wait(5000001));
        assert((sleeps>0)==(mode==0) && !writes);
    }
    su.wait=su.ready=interrupts=true;interrupt_context=false;preemption=0;
    clock_ns=1;complete_at=10001;sleeps=0;
    assert(!run_wait(5000001) && !sleeps); /* fast command never sleeps */
    clock_ns=1;complete_at=10000001;sleeps=writes=0;
    assert(run_wait(500001)==ETIMEDOUT && writes==1);
    assert(clock_ns<=501001); /* sleeping stays bounded by original timeout */

    uint8_t report[66]={0};
    lt_perf_record(report,0,0,1,1001);
    assert(!lt_perf.polls && !lt_perf.start); /* default off */
    lt_perf.enabled=1;
    report[1]=1;report[65]=255;
    lt_perf_record(report,0,1,1,1001);
    assert(lt_perf.valid==1 && lt_perf.contacts==1 && !lt_perf.up);
    memset(report,0,sizeof(report));
    lt_perf_record(report,0,0,20000001,20001001);
    assert(lt_perf.up==1 && lt_perf.zero==1);
    report[65]=1;
    lt_perf_record(report,EINVAL,0,40000001,40002001);
    assert(lt_perf.checksum==1 && lt_perf.zero==1);
    report[1]=255;
    lt_perf_record(report,EINVAL,0,60000001,60001001);
    assert(lt_perf.invalid==1 && lt_perf.checksum==1);
    lt_perf_record(report,EAGAIN,0,80000001,80001001);
    assert(lt_perf.recovery==1);
    assert(lt_perf.gap==20000000 && lt_perf.read==2000);
    lt_perf_record(report,ERANGE,0,5100000001ULL,5100100001ULL);
    assert(!lt_perf.polls && !lt_perf.gap && !lt_perf.read);
    assert(lt_perf.start==5100100001ULL && lt_perf.enabled==1);
    puts("PASS: UFS yields only in sleepable runtime context, bounded timeout, unchanged fast/default path; opt-in touch counters");
}
'''.replace('/* WAIT */', wait).replace('/* TOUCH */', helper)
with tempfile.TemporaryDirectory() as directory:
    path = Path(directory)
    (path / 'test.c').write_text(program)
    subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=address,undefined', str(path / 'test.c'), '-o', str(path / 'test')], check=True)
    subprocess.run([str(path / 'test')], check=True)
