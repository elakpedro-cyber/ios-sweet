"""Exercise the actual optional PID1 failure hold and its process gate."""
import argparse
from pathlib import Path
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--xnu', type=Path, required=True)
args = parser.parse_args()
text = (args.xnu / 'bsd/kern/kern_exit.c').read_text()
start = text.index('static void\nlemon_hold_pid1_failure(')
helper = text[start:text.index('\n}\n', start)+3]
start = text.index('#if defined(LEMON_4K)', text.index('sync(p, (void *)NULL, (int *)NULL);'))
hook = text[start:text.index('#endif', start)] + '#endif\n'
assert text.index('sync(p, (void *)NULL, (int *)NULL);') < start < text.index('panic_with_options(', start)
source = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <setjmp.h>
#define LEMON_4K 1
typedef void *proc_t;
static proc_t initproc=(void *)1;
static uint32_t option;
static unsigned delays;
static jmp_buf stopped;
static void PE_parse_boot_argn(const char *name,uint32_t *value,unsigned size) {
    assert(!strcmp(name,"lemonpid1hold") && size==4); *value=option;
}
static void delay(int usec) { assert(usec==1000000); delays++; longjmp(stopped,1); }
/* HELPER */
static void critical_exit_gate(proc_t p) {
/* HOOK */
}
int main(void) {
    option=0; critical_exit_gate(initproc); assert(!delays);
    option=2; critical_exit_gate(initproc); assert(!delays);
    option=1; critical_exit_gate((void *)2); assert(!delays);
    if (!setjmp(stopped)) { critical_exit_gate(initproc); assert(0); }
    assert(delays==1);
    puts("PASS: default/off unchanged, PID1 only, exact1 opt-in, bounded delay iteration");
}
'''.replace('/* HELPER */',helper).replace('/* HOOK */',hook)
with tempfile.TemporaryDirectory() as folder:
    c, binary = Path(folder) / 'hold.c', Path(folder) / 'hold'
    c.write_text(source)
    subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',
                    str(c),'-o',str(binary)],check=True)
    subprocess.run([str(binary)],check=True)
