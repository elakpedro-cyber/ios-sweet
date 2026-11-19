#include "console.h"

#ifdef LEMON_GIC_QEMU
#define GICD 0x08000000UL
#define GICR 0x080a0000UL
#define VTIMER 27
#else
#define GICD 0x0f200000UL
#define GICR 0x0f300000UL
#define VTIMER 19
#endif
#define SGI 1
#define rsr(r) ({ uint64_t v; __asm__ volatile("mrs %0, " r : "=r"(v)); v; })
#define wsr(r, v) __asm__ volatile("msr " r ", %0" : : "r"((uint64_t)(v)))

volatile uint64_t lemon_gic_result[8];
static uintptr_t redistributor;
static const char *stage;

static uint32_t rd32(uintptr_t address) { return *(volatile uint32_t *)address; }
static uint64_t rd64(uintptr_t address) { return *(volatile uint64_t *)address; }
static void wr32(uintptr_t address, uint32_t value) { *(volatile uint32_t *)address = value; }
static void halt(void) { for (;;) __asm__ volatile("wfe"); }

static uint64_t now(void)
{
	__asm__ volatile("isb" ::: "memory");
	return rsr("cntpct_el0");
}

static int wait_clear(uintptr_t address, uint32_t mask)
{
	uint64_t deadline = now() + rsr("cntfrq_el0") / 10;
	while (rd32(address) & mask) {
		if (now() >= deadline) return 0;
	}
	return 1;
}

void exc_handler(uint64_t slot, uint64_t *regs)
{
	(void)regs;
	if (slot == 5) {
		uint64_t iar = rsr("icc_iar1_el1");
		unsigned id = iar & 0xffffff;
		if (id >= 1020 && id <= 1023) return;
		lemon_gic_result[5] = id;
		if (id == SGI) lemon_gic_result[3]++;
		else if (id == VTIMER) {
			lemon_gic_result[2]++;
			wsr("cntv_tval_el0", rsr("cntfrq_el0") / 100);
		} else {
			lemon_gic_result[4]++;
			/* Quiesce an inherited unrelated source rather than spin in its IRQ. */
			if (id < 32) wr32(redistributor + 0x10180, 1U << id);
			else if (id < 1020) wr32(GICD + 0x180 + (id / 32) * 4, 1U << (id % 32));
		}
		wsr("icc_eoir1_el1", iar);
		__asm__ volatile("dsb sy; isb" ::: "memory");
		return;
	}
	con_str("FAULT", stage ? stage : "entry");
	con_hex("SLOT", slot);
	con_hex("ESR", rsr("esr_el1"));
	con_hex("ELR", rsr("elr_el1"));
	con_hex("FAR", rsr("far_el1"));
	halt();
}

void secondary_main(uint64_t cpu) { (void)cpu; halt(); }

void shim_main(uint64_t dtb)
{
	(void)dtb;
	stage = "read GIC";
	con_clear(BLUE);
	con_str("LEMON", "GIC SGI1 + timer probe");
	con_hex("EL", rsr("CurrentEL") >> 2);
	con_hex("MPIDR", rsr("mpidr_el1"));
	con_hex("CNTFRQ", rsr("cntfrq_el0"));
	if ((rsr("CurrentEL") >> 2) != 1 || !rsr("cntfrq_el0")) halt();
	con_hex("D CTLR", rd32(GICD));
	con_hex("D TYPER", rd32(GICD + 4));
	uint32_t affinity = rsr("mpidr_el1") & 0xffff;
	for (unsigned offset = 0; offset < 0x100000; offset += 0x20000) {
		uint64_t typer = rd64(GICR + offset + 8);
		if (((typer >> 32) & 0xffff) == affinity) { redistributor = GICR + offset; break; }
		if (typer & 0x10) break;
	}
	if (!redistributor) { con_str("STOP", "no CPU redistributor"); halt(); }
	con_hex("R BASE", redistributor);
	con_hex("R WAKER", rd32(redistributor + 0x14));
	con_hex("PRE EN", rd32(redistributor + 0x10100));
	con_hex("PRE PEND", rd32(redistributor + 0x10200));
	con_hex("PRE ACT", rd32(redistributor + 0x10300));
	stage = "GIC setup";
	wr32(redistributor + 0x14, rd32(redistributor + 0x14) & ~2U);
	if (!wait_clear(redistributor + 0x14, 4)) { con_str("STOP", "GICR wake timeout"); halt(); }
	/* Same Group 1 NS setup as the Sweet XNU platform path. */
	wr32(redistributor + 0x10080, 0xffffffff);
	for (unsigned i = 0; i < 32; i += 4) wr32(redistributor + 0x10400 + i, 0xa0a0a0a0);
	wr32(redistributor + 0x10100, (1U << SGI) | (1U << VTIMER));
	wsr("icc_sre_el1", rsr("icc_sre_el1") | 1);
	__asm__ volatile("isb" ::: "memory");
	wsr("icc_bpr1_el1", 0);
	wsr("icc_pmr_el1", 255);
	wsr("icc_ctlr_el1", rsr("icc_ctlr_el1") & ~2UL);
	wr32(GICD, rd32(GICD) | 0x13);
	if (!wait_clear(GICD, 0x80000000)) { con_str("STOP", "GICD RWP timeout"); halt(); }
	wsr("icc_igrpen1_el1", 1);
	__asm__ volatile("dsb sy; isb" ::: "memory");
	con_hex("R GROUP", rd32(redistributor + 0x10080));
	con_hex("R EN", rd32(redistributor + 0x10100));
	con_hex("ICC CTLR", rsr("icc_ctlr_el1"));
	con_hex("ICC PMR", rsr("icc_pmr_el1"));
	con_hex("ICC GRP1", rsr("icc_igrpen1_el1"));
	stage = "SGI + timer wait";
	uint64_t mpidr = rsr("mpidr_el1");
	if ((mpidr & 255) >= 16) { con_str("STOP", "unsupported SGI target"); halt(); }
	uint64_t sgi = (((mpidr >> 32) & 255) << 48) | (((mpidr >> 16) & 255) << 32) |
	    (((mpidr >> 8) & 255) << 16) | ((uint64_t)SGI << 24) | (1UL << (mpidr & 255));
	wsr("icc_sgi1r_el1", sgi);
	wsr("cntv_tval_el0", rsr("cntfrq_el0") / 100);
	wsr("cntv_ctl_el0", 1);
	__asm__ volatile("dsb sy; isb; msr daifclr, #2" ::: "memory");
	uint64_t begin = now(), deadline = begin + rsr("cntfrq_el0") / 5;
	while (now() < deadline) __asm__ volatile("yield");
	__asm__ volatile("msr daifset, #2" ::: "memory");
	lemon_gic_result[6] = rsr("cntv_ctl_el0");
	wsr("cntv_ctl_el0", 0);
	lemon_gic_result[1] = mpidr;
	lemon_gic_result[7] = now() - begin;
	lemon_gic_result[0] = 0x4c454d4f4e474943UL;
	con_hex("SGI CNT", lemon_gic_result[3]);
	con_hex("TMR CNT", lemon_gic_result[2]);
	con_hex("OTHER", lemon_gic_result[4]);
	con_hex("LAST IRQ", lemon_gic_result[5]);
	con_hex("R PEND", rd32(redistributor + 0x10200));
	con_hex("R ACTIVE", rd32(redistributor + 0x10300));
	con_hex("TMR CTL", lemon_gic_result[6]);
	con_hex("TICKS", lemon_gic_result[7]);
	con_str("RESULT", lemon_gic_result[2] && lemon_gic_result[3] ? "both IRQs delivered" : "IRQ delivery missing");
	con_str("END", "halt; no storage access");
	__asm__ volatile("dsb sy" ::: "memory");
	halt();
}
