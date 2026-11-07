#define _GNU_SOURCE
#include <sched.h>
#include <stdint.h>
#include <stdio.h>

int main(void)
{
	/* Linux may emulate MRS with system-wide sanitized feature registers. */
	puts("Linux EL0 MRS view; hidden fields cannot establish hardware granule support.");
	for (int cpu = 0; cpu < CPU_SETSIZE; cpu++) {
		cpu_set_t set;
		CPU_ZERO(&set);
		CPU_SET(cpu, &set);
		if (sched_setaffinity(0, sizeof(set), &set))
			continue;
		uint64_t midr, mmfr0;
		__asm__ volatile("mrs %0, midr_el1" : "=r"(midr));
		__asm__ volatile("mrs %0, id_aa64mmfr0_el1" : "=r"(mmfr0));
		printf("cpu=%d midr=0x%016llx mmfr0=0x%016llx TGran16=%llu\n",
		       cpu, (unsigned long long)midr, (unsigned long long)mmfr0,
		       (unsigned long long)((mmfr0 >> 20) & 15));
	}
	return 0;
}
