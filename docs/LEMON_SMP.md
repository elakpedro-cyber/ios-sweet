# Opt-in SMP on lemon (SM6115)

v21 measurements showed the kernel framebuffer copy takes about 5 ms per frame,
while iOS presented at most about 3 frames/s during interaction. CoreAnimation
renders in software on one CPU, and that CPU is the boot Cortex-A53. More
cores, especially the Cortex-A73 cluster, are the main lever without a GPU.

SM6115 MPIDRs: Cortex-A53 `0x000-0x003` (Aff0 = core), Cortex-A73
`0x100-0x103` (Aff1 = cluster 1). Sweet's SMP code (patches 0065/0078) uses
Aff1 as the core number and rejected these values. Everything else already
matches the full Aff1:Aff0 value: GIC redistributor lookup (`GICR_TYPER`),
`ICC_SGI1R_EL1` routing, the reset-vector CPU-data search and
`ml_get_cpu_number()`. Port patch `0023-smp-topology.patch` only replaces the
lemon MPIDR validation and the CPU name. `cpus=1` remains the default.

`tools/lemon_smp_adt.py` expands the real single-CPU phone ADT to eight nodes:
boot A53, the four A73s, then the other three A53s. `cpus=5` selects the boot
core and the A73 cluster. One homogeneous SMP cluster; the scheduler does not
know the A73s are faster. Only `/cpus` changes; `tools/test-lemon-smp.py`
checks this and the kernel rules.

Packaging: `research/build_smp_boot.py [CPUS]` (ignored) reuses the v21 766 MiB
loader/ADT, enables `cpus=N`, 30 Hz notifications/copies and LEMON PERF stats.
If secondary startup fails the kernel panics with `SWEET CPU: cpu=N ...`; the
persistent log shows which core. Roll back by writing the v20 or v21 image.

Not covered: CPU frequency control, CPU idle/offline (quiesce/halt still panic,
as on sweet), AMP scheduling, and the GPU.
