#!/usr/bin/env python3
"""Run XNU's actual FIFO trylock helpers on a QEMU Cortex-A53."""
import argparse
from pathlib import Path
import subprocess
import tempfile

ap = argparse.ArgumentParser()
ap.add_argument('--xnu', type=Path, required=True)
args = ap.parse_args()
source = (args.xnu / 'osfmk/arm/commpage/commpage_asm.s').read_text()
source = source[source.index('_pfz_trylock_and_enqueue:'):
                source.index('/* Preemptible functions */')]
for macro, replacement in [('ARM64_STACK_PROLOG', ''), ('PUSH_FRAME', ''),
                           ('POP_FRAME', ''), ('ARM64_STACK_EPILOG', 'ret')]:
    source = source.replace(macro, replacement)
source = '.text\n.globl _pfz_trylock_and_enqueue\n' + source

with tempfile.TemporaryDirectory() as directory:
    out = Path(directory)
    (out / 'helpers.S').write_text(source)
    (out / 'start.S').write_text('''
.text
.global _start
_start:
    ldr x0, =stack_end
    mov sp, x0
    bl test
    ldr x1, =exit_block
    str x0, [x1, #8]
    mov x0, #0x20
    hlt #0xf000
    b .
.data
.balign 8
exit_block: .quad 0x20026, 1
.bss
.balign 16
    .space 65536
stack_end:
''')
    (out / 'test.c').write_text('''
typedef unsigned long size_t;
struct node { struct node *next; };
struct queue { struct node *head, *tail; unsigned lock; };
extern int _pfz_trylock_and_enqueue(struct queue *, struct node *, size_t, unsigned *);
extern struct node *_pfz_trylock_and_dequeue(struct queue *, size_t, unsigned *);
#define CHECK(cond) do { if (!(cond)) return __LINE__; } while (0)
int test(void) {
    struct queue q = {0};
    struct node a = {0}, b = {0};
    CHECK(_pfz_trylock_and_dequeue(&q, 0, &q.lock) == 0);
    CHECK(q.lock == 0);
    q.lock = 1;
    CHECK(_pfz_trylock_and_enqueue(&q, &a, 0, &q.lock) == -1);
    CHECK(_pfz_trylock_and_dequeue(&q, 0, &q.lock) == (void *)-1L);
    CHECK(q.head == 0 && q.tail == 0 && q.lock == 1);
    q.lock = 0;
    CHECK(_pfz_trylock_and_enqueue(&q, &a, 0, &q.lock) == 0);
    CHECK(q.head == &a && q.tail == &a && q.lock == 0);
    CHECK(_pfz_trylock_and_enqueue(&q, &b, 0, &q.lock) == 0);
    CHECK(q.head == &a && q.tail == &b && a.next == &b && q.lock == 0);
    CHECK(_pfz_trylock_and_dequeue(&q, 0, &q.lock) == &a);
    CHECK(q.head == &b && q.tail == &b && a.next == 0 && q.lock == 0);
    CHECK(_pfz_trylock_and_dequeue(&q, 0, &q.lock) == &b);
    CHECK(q.head == 0 && q.tail == 0 && b.next == 0 && q.lock == 0);
    return 0;
}
''')
    subprocess.run(['aarch64-linux-gnu-gcc', '-DLEMON_4K', '-mcpu=cortex-a53',
                    '-mgeneral-regs-only', '-ffreestanding', '-fno-stack-protector',
                    '-nostdlib', '-static', '-no-pie', '-O2', '-Wl,-Ttext=0x40200000',
                    '-Wl,-e,_start', str(out / 'start.S'), str(out / 'helpers.S'),
                    str(out / 'test.c'), '-o', str(out / 'test.elf')], check=True)
    subprocess.run(['qemu-system-aarch64', '-M', 'virt', '-cpu', 'cortex-a53',
                    '-m', '128', '-nic', 'none', '-display', 'none', '-serial', 'none',
                    '-monitor', 'none', '-semihosting-config', 'enable=on,target=native',
                    '-device', f'loader,file={out / "test.elf"},cpu-num=0'],
                   check=True, timeout=10)
print('A53 PFZ: empty/populated FIFO, enqueue/dequeue, held lock and unlock PASS')
