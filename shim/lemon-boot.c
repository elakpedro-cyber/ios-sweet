#include "console.h"
#include "loader.h"

#define rsr(r) ({ uint64_t v; __asm__ volatile("mrs %0, " r : "=r"(v)); v; })

static void halt(void)
{
	for (;;)
		__asm__ volatile("wfe");
}

void exc_handler(uint64_t slot, uint64_t *regs)
{
	(void)regs;
	con_str("FAULT", "lemon loader stopped");
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
	con_clear(BLUE);
	con_str("LEMON", "XNU RAM-only boot v1");
	con_hex("DTB", dtb);
	con_hex("EL", rsr("CurrentEL") >> 2);
	con_hex("SCTLR", rsr("sctlr_el1"));
	if ((rsr("CurrentEL") >> 2) != 1 || (rsr("sctlr_el1") & 5)) {
		con_str("STOP", "EL1 with MMU/cache off required");
		halt();
	}
	con_str("STOP", loader_boot(dtb));
	halt();
}
