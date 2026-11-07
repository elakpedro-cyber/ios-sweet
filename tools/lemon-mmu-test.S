#include <arm64/lemon_fb_map.h>

.section .text.head, "ax"
.global _head
_head:
    b entry
    .word 0
    .quad 0
    .quad _end
    .quad 0xa
    .quad 0, 0, 0
    .ascii "ARM\x64"
    .word 0

.macro framebuffer va
    ldr x6, =\va
    ldr x7, =LEMON_FB_BASE
    ldr x8, =(\va + LEMON_FB_MAP_BYTES)
.endm

entry:
    msr daifset, #15
    adr x25, tables
    adr x2, ram_l2
    adr x17, tables_end
    orr x0, x2, #3
    str x0, [x25, #8]
    ldr x0, =0x40200701
    str x0, [x2, #8]
    /* Final KVA code alias shares the existing executable RAM table. */
    orr x0, x2, #3
    str x0, [x25, #(385 * 8)]

    /* An L1 block must be rejected instead of destroying another mapping. */
    ldr x0, =0x40000701
    str x0, [x25, #(384 * 8)]
    framebuffer 0xffffffe000200000
    lemon_map_fb x25, x2, x17, conflict_rejected
    b failed
conflict_rejected:
    str xzr, [x25, #(384 * 8)]
    /* No room for another whole table: reject before publishing the entry. */
    add x17, x2, #4096
    framebuffer 0xffffffe000200000
    lemon_map_fb x25, x2, x17, capacity_rejected
    b failed
capacity_rejected:
    ldr x0, [x25, #(384 * 8)]
    cbnz x0, failed
    adr x17, tables_end

    framebuffer LEMON_FB_BASE
    lemon_map_fb x25, x2, x17, failed
    mov x18, x2
    framebuffer LEMON_FB_BASE
    lemon_map_fb x25, x2, x17, failed
    cmp x18, x2
    b.ne failed
    framebuffer 0xffffffe000200000
    lemon_map_fb x25, x2, x17, failed
    adr x0, result
    str x2, [x0, #32]

    ldr x0, =0x44ff
    msr mair_el1, x0
    msr ttbr0_el1, x25
    msr ttbr1_el1, x25
    /* 39-bit VA, 4K for TTBR0 and TTBR1; Normal WB table walks. */
    ldr x0, =0x2b5193519
    msr tcr_el1, x0
    dsb sy
    isb
    tlbi vmalle1
    dsb sy
    isb
    mrs x0, sctlr_el1
    orr x0, x0, #1
    msr sctlr_el1, x0
    isb

    /* Run from the high kernel alias before invalidating all TTBR0 walks. */
    adr x0, high_entry
    ldr x1, =0xffffffe000000000
    add x0, x0, x1
    br x0
high_entry:
    mrs x0, tcr_el1
    orr x0, x0, #0x80
    msr tcr_el1, x0
    isb
    tlbi vmalle1
    dsb sy
    isb
    ldr x1, =(0xffffffe000200000 + LEMON_FB_BYTES - 4)
    at s1e1r, x1
    isb
    mrs x2, par_el1
    tbnz x2, #0, failed
    adr x3, result
    str x2, [x3, #16]
    ldr x0, =LEMON_FB_BASE
    at s1e1r, x0
    isb
    mrs x2, par_el1
    str x2, [x3, #24]
    tbz x2, #0, failed
    ldr x0, =0xffffffe000200000
    ldr w2, =0x11223344
    str w2, [x0]
    ldr w2, =0xaabbccdd
    str w2, [x1]
    dsb sy
    mrs x0, id_aa64mmfr0_el1
    str x0, [x3, #8]
    ldr x0, =0x4c454d4f4e4d4d55
    str x0, [x3]
    dsb sy
halt:
    wfe
    b halt
failed:
    adr x0, result
    mov x1, #-1
    str x1, [x0]
    b halt
.ltorg

.bss
.balign 4096
.global tables
tables:
    .space 4096
ram_l2:
    .space (4096 * (LEMON_BOOTSTRAP_PAGES - 1))
tables_end:
.global result
result:
    .space 64
.global _end
_end:
