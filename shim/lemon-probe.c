#include "console.h"

#define rsr(r) ({ uint64_t v; __asm__ volatile("mrs %0, " r : "=r"(v)); v; })

volatile uint64_t lemon_mmfr0;

static void halt(void)
{
	for (;;)
		__asm__ volatile("wfe");
}

void exc_handler(uint64_t slot, uint64_t *regs)
{
	(void)regs;
	con_str("FAULT", "lemon probe stopped");
	con_hex("SLOT", slot);
	con_hex("ESR", rsr("esr_el1"));
	con_hex("ELR", rsr("elr_el1"));
	con_hex("FAR", rsr("far_el1"));
	halt();
}

void secondary_main(uint64_t cpu)
{
	(void)cpu;
	halt();
}

void shim_main(uint64_t dtb)
{
	lemon_mmfr0 = rsr("id_aa64mmfr0_el1");
	con_clear(BLUE);
	con_str("LEMON", "iOS port: CPU probe v1");
	con_hex("DTB", dtb);
	con_hex("EL", rsr("CurrentEL") >> 2);
	con_hex("SCTLR", rsr("sctlr_el1"));
	con_hex("MIDR", rsr("midr_el1"));
	con_hex("MPIDR", rsr("mpidr_el1"));
	uint64_t mmfr0 = lemon_mmfr0;
	con_hex("MMFR0", mmfr0);
	con_hex("TGran16", (mmfr0 >> 20) & 15);
	con_hex("CNTFRQ", rsr("cntfrq_el0"));
	unsigned gran16 = (mmfr0 >> 20) & 15;
	con_str("16K", gran16 == 1 || gran16 == 2 ? "supported" :
		gran16 == 0 ? "unsupported" : "unknown encoding");
	con_str("END", "halt; no storage access");
	__asm__ volatile("dsb sy" ::: "memory");
	halt();
}
