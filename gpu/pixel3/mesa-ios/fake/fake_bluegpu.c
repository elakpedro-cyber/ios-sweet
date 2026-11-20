/*
 * fake_bluegpu.c - an in-process stand-in for the BlueGPU kernel user client, for the macOS
 * host build only (build-mesa-ios.sh HOST=1). It defines the IOKit calls bluedrm.c makes, so
 * the same bluedrm.c + Mesa run on the Mac without a kernel or GPU.
 *
 * Two jobs:
 *   1. ABI test: every selector is checked against blue_gpu_uapi.h (struct sizes, handles,
 *      flags, IB ranges inside their BO, PM4 header parity, IB / draw-state addresses that
 *      resolve to a BO), so a Mesa/bluedrm/uapi mismatch shows up on the Mac.
 *   2. Reference model for kernel stage 6d: the semantics here are what BlueGPU must do,
 *      minus the hardware (no command is executed: every fence retires at once, pixels stay 0).
 *
 * BLUEGPU_FAKE_VERBOSE=1 prints each call. A summary line is printed at exit:
 *   "bluegpu-fake: ... errors 0"
 *
 * Copyright (c) 2026 pixel3-ios. MIT licence.
 */
#include <errno.h>
#include <pthread.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <IOKit/IOKitLib.h>
#include <mach/mach_time.h>

#include "blue_gpu_uapi.h"

#define MAX_BOS         8192
#define GRANULE         (64 * 1024)

struct bo {
	bool used;
	void *mem;
	uint64_t size, iova;
	uint32_t flags;
	uint32_t last_fence;
	char name[33];
};

static struct bo bos[MAX_BOS];
static pthread_mutex_t lock = PTHREAD_MUTEX_INITIALIZER;
static uint64_t next_iova = BLUE_GPU_VA_START_DEFAULT;
static uint32_t fence_seq, queue_seq;
static unsigned long n_calls, n_errors, n_submits, n_ibs, n_pkts, n_bo_new, n_maps, n_drawstate;
static uint64_t bytes_alloc, bytes_peak;
static int verbose = -1;
static bool opened;

#define V(...) do { if (verbose > 0) fprintf(stderr, "bluegpu-fake: " __VA_ARGS__); } while (0)
#define BAD(...) do { n_errors++; fprintf(stderr, "bluegpu-fake: ERROR " __VA_ARGS__); } while (0)

static void
summary(void)
{
	fprintf(stderr, "bluegpu-fake: calls %lu, BOs %lu (peak %llu KiB), maps %lu, submits %lu, IBs %lu, "
	        "packets %lu, draw-state groups %lu, errors %lu\n", n_calls, n_bo_new,
	        (unsigned long long)(bytes_peak >> 10), n_maps, n_submits, n_ibs, n_pkts, n_drawstate, n_errors);
}

/* ---- IOKit surface bluedrm.c uses -------------------------------------------------------- */
CFMutableDictionaryRef
IOServiceMatching(const char *name)
{
	return (CFMutableDictionaryRef)strdup(name);
}

io_service_t
IOServiceGetMatchingService(mach_port_t port, CFDictionaryRef matching)
{
	bool ok = strcmp((const char *)matching, BLUE_GPU_SERVICE) == 0;

	(void)port;
	free((void *)matching);
	return ok ? 0x4242 : 0;
}

kern_return_t
IOObjectRelease(io_object_t o)
{
	(void)o;
	return KERN_SUCCESS;
}

kern_return_t
IOServiceOpen(io_service_t s, task_port_t task, uint32_t type, io_connect_t *conn)
{
	(void)task;
	if (s != 0x4242 || type != BLUE_GPU_UC_TYPE)
		return kIOReturnBadArgument;
	if (verbose < 0)
		verbose = getenv("BLUEGPU_FAKE_VERBOSE") != NULL;
	if (!opened)
		atexit(summary);
	opened = true;
	*conn = 0x4343;
	return KERN_SUCCESS;
}

static struct bo *
bo_of(uint32_t h)
{
	return h != 0 && h < MAX_BOS && bos[h].used ? &bos[h] : NULL;
}

static struct bo *
bo_at(uint64_t iova, uint64_t len)
{
	for (uint32_t h = 1; h < MAX_BOS; h++)
		if (bos[h].used && iova >= bos[h].iova && iova + len <= bos[h].iova + bos[h].size)
			return &bos[h];
	return NULL;
}

static int walk_ib(uint64_t iova, uint32_t dwords, int depth);

/* PM4 type4/type7 headers: odd parity per Mesa's pm4_odd_parity_bit() */
static unsigned
odd_parity(unsigned v)
{
	v ^= v >> 16; v ^= v >> 8; v ^= v >> 4; v &= 0xf;
	return (~0x6996 >> v) & 1;
}

static int
walk_ib(uint64_t iova, uint32_t dwords, int depth)
{
	struct bo *bo = bo_at(iova, (uint64_t)dwords * 4);
	const uint32_t *p;
	uint32_t i = 0;

	if (bo == NULL) {
		BAD("IB 0x%llx (%u dwords) not inside any BO\n", (unsigned long long)iova, dwords);
		return -1;
	}
	if (depth > 3) {
		BAD("IB nesting deeper than 3 at 0x%llx\n", (unsigned long long)iova);
		return -1;
	}
	n_ibs++;
	p = (const uint32_t *)((const char *)bo->mem + (iova - bo->iova));
	while (i < dwords) {
		uint32_t h = p[i], cnt;
		if ((h & 0xf0000000) == 0x40000000) {           /* type 4: register write */
			cnt = h & 0x7f;
			if (((h >> 7) & 1) != odd_parity(cnt) || ((h >> 27) & 1) != odd_parity((h >> 8) & 0x3ffff)) {
				BAD("bad type4 parity 0x%08x at IB 0x%llx +%u\n", h, (unsigned long long)iova, i);
				return -1;
			}
		} else if ((h & 0xf0000000) == 0x70000000) {    /* type 7: CP packet */
			uint32_t op = (h >> 16) & 0x7f;
			cnt = h & 0x3fff;
			if (((h >> 15) & 1) != odd_parity(cnt) || ((h >> 23) & 1) != odd_parity(op)) {
				BAD("bad type7 parity 0x%08x at IB 0x%llx +%u\n", h, (unsigned long long)iova, i);
				return -1;
			}
			if (i + 1 + cnt > dwords) {
				BAD("packet runs past the IB end at +%u\n", i);
				return -1;
			}
			if ((op == 0x3f || op == 0x37 || op == 0x57) && cnt >= 3) {  /* CP_INDIRECT_BUFFER(_PFD/_CHAIN) */
				uint64_t a = p[i + 1] | (uint64_t)p[i + 2] << 32;
				if (walk_ib(a, p[i + 3] & 0xfffff, depth + 1))
					return -1;
			} else if (op == 0x43) {                         /* CP_SET_DRAW_STATE groups */
				for (uint32_t g = 0; g + 3 <= cnt; g += 3) {
					uint32_t d0 = p[i + 1 + g];
					uint64_t a = p[i + 2 + g] | (uint64_t)p[i + 3 + g] << 32;
					n_drawstate++;
					if ((d0 & 0xffff) && !(d0 & (3u << 17)) && walk_ib(a, d0 & 0xffff, depth + 1))
						return -1;
				}
			}
		} else if (h == 0) {
			cnt = 0;        /* (padding; the CP treats it as a type-0 nop) */
		} else {
			BAD("unknown PM4 header 0x%08x at IB 0x%llx +%u\n", h, (unsigned long long)iova, i);
			return -1;
		}
		n_pkts++;
		i += 1 + cnt;
	}
	return 0;
}

static IOReturn
do_param(struct blue_gpu_param *p)
{
	if (p->pipe != BLUE_GPU_PIPE_3D0)
		return kIOReturnBadArgument;
	switch (p->param) {
	case BLUE_GPU_PARAM_GPU_ID:           p->value = LEMON_GPU_ID; break;
	case BLUE_GPU_PARAM_GMEM_SIZE:        p->value = LEMON_GPU_GMEM_SIZE; break;
	case BLUE_GPU_PARAM_CHIP_ID:          p->value = LEMON_GPU_CHIP_ID; break;
	case BLUE_GPU_PARAM_MAX_FREQ:         p->value = 500000000; /* synthetic host-test clock, not a hardware setting */ break;
	case BLUE_GPU_PARAM_TIMESTAMP:        p->value = mach_absolute_time(); break;
	case BLUE_GPU_PARAM_GMEM_BASE:        p->value = BLUE_GPU_A630_GMEM_BASE; break;
	case BLUE_GPU_PARAM_PRIORITIES:       p->value = 1; break;
	case BLUE_GPU_PARAM_PP_PGTABLE:       p->value = 0; break;
	case BLUE_GPU_PARAM_FAULTS:           p->value = 0; break;
	case BLUE_GPU_PARAM_SUSPENDS:         p->value = 0; break;
	case BLUE_GPU_PARAM_VA_START:         p->value = BLUE_GPU_VA_START_DEFAULT; break;
	case BLUE_GPU_PARAM_VA_SIZE:          p->value = BLUE_GPU_VA_SIZE_BACKBOARDD; break;
	case BLUE_GPU_PARAM_HIGHEST_BANK_BIT: p->value = LEMON_GPU_HIGHEST_BANK_BIT; break;
	case BLUE_GPU_PARAM_RAYTRACING:       p->value = 0; break;
	case BLUE_GPU_PARAM_MACROTILE_MODE:   p->value = 0; break;
	case BLUE_GPU_PARAM_HAS_PRR:          p->value = 0; break;
	default:                              return kIOReturnBadArgument;
	}
	return kIOReturnSuccess;
}

static IOReturn
do_submit(struct blue_gpu_submit *s)
{
	const struct blue_gpu_submit_bo *sb = (const void *)(uintptr_t)s->bos;
	const struct blue_gpu_submit_cmd *sc = (const void *)(uintptr_t)s->cmds;
	const uint32_t bad_flags = BLUE_GPU_SUBMIT_FENCE_FD_IN | BLUE_GPU_SUBMIT_FENCE_FD_OUT | BLUE_GPU_SUBMIT_SUDO |
	                           BLUE_GPU_SUBMIT_SYNCOBJ_IN | BLUE_GPU_SUBMIT_SYNCOBJ_OUT | BLUE_GPU_SUBMIT_FENCE_SN_IN;

	if ((s->flags & 0xffff) != BLUE_GPU_PIPE_3D0 || (s->flags & bad_flags)) {
		BAD("submit flags 0x%x\n", s->flags);
		return kIOReturnBadArgument;
	}
	for (uint32_t i = 0; i < s->nr_bos; i++) {
		if (bo_of(sb[i].handle) == NULL || (sb[i].flags & ~0xfu)) {
			BAD("submit bo[%u] handle %u flags 0x%x\n", i, sb[i].handle, sb[i].flags);
			return kIOReturnBadArgument;
		}
	}
	for (uint32_t i = 0; i < s->nr_cmds; i++) {
		struct bo *bo;
		if (sc[i].submit_idx >= s->nr_bos || sc[i].nr_relocs != 0 || sc[i].type < 1 || sc[i].type > 3 ||
		    (sc[i].size & 3) || (sc[i].submit_offset & 3)) {
			BAD("submit cmd[%u]: type %u idx %u off %u size %u relocs %u\n", i, sc[i].type, sc[i].submit_idx,
			    sc[i].submit_offset, sc[i].size, sc[i].nr_relocs);
			return kIOReturnBadArgument;
		}
		bo = bo_of(sb[sc[i].submit_idx].handle);
		if ((uint64_t)sc[i].submit_offset + sc[i].size > bo->size) {
			BAD("submit cmd[%u] past its BO\n", i);
			return kIOReturnBadArgument;
		}
		if (sc[i].type != BLUE_GPU_SUBMIT_CMD_IB_TARGET_BUF &&
		    walk_ib(bo->iova + sc[i].submit_offset, sc[i].size / 4, 0))
			return kIOReturnBadArgument;
	}
	s->fence = ++fence_seq;
	for (uint32_t i = 0; i < s->nr_bos; i++)
		bo_of(sb[i].handle)->last_fence = s->fence;
	n_submits++;
	V("submit %u: %u bos, %u cmds\n", s->fence, s->nr_bos, s->nr_cmds);
	return kIOReturnSuccess;
}

static IOReturn
dispatch(uint32_t sel, void *in, size_t insz)
{
#define NEED(T) do { if (insz != sizeof(T)) { BAD("sel 0x%x size %zu != %zu\n", sel, insz, sizeof(T)); \
                                               return kIOReturnBadArgument; } } while (0)
	switch (sel) {
	case BLUE_GPU_SEL_GET_PARAM:
		NEED(struct blue_gpu_param);
		return do_param(in);
	case BLUE_GPU_SEL_SET_PARAM:
		NEED(struct blue_gpu_param);
		return kIOReturnSuccess;
	case BLUE_GPU_SEL_GEM_NEW: {
		struct blue_gpu_gem_new *r = in;
		uint64_t size = (r->size + GRANULE - 1) & ~(uint64_t)(GRANULE - 1);
		NEED(*r);
		if (r->size == 0 || (r->flags & BLUE_GPU_BO_CACHE_MASK) == BLUE_GPU_BO_CACHED ||
		    (r->flags & BLUE_GPU_BO_CACHED_COHERENT))
			return kIOReturnBadArgument;
		for (uint32_t h = 1; h < MAX_BOS; h++) {
			if (!bos[h].used) {
				if (posix_memalign(&bos[h].mem, GRANULE, size))
					return kIOReturnNoMemory;
				memset(bos[h].mem, 0, size);
				bos[h].used = true;
				bos[h].size = size;
				bos[h].flags = r->flags;
				bos[h].iova = next_iova;
				bos[h].last_fence = 0;
				bos[h].name[0] = 0;
				next_iova += size;
				r->handle = h;
				n_bo_new++;
				bytes_alloc += size;
				if (bytes_alloc > bytes_peak)
					bytes_peak = bytes_alloc;
				V("gem_new %u: 0x%llx bytes flags 0x%x iova 0x%llx\n", h, (unsigned long long)size, r->flags,
				  (unsigned long long)bos[h].iova);
				return kIOReturnSuccess;
			}
		}
		return kIOReturnNoMemory;
	}
	case BLUE_GPU_SEL_GEM_CLOSE: {
		struct blue_gpu_gem_close *r = in;
		struct bo *bo;
		NEED(*r);
		if ((bo = bo_of(r->handle)) == NULL)
			return kIOReturnNotFound;
		/* (the kernel defers this until bo->last_fence retires and no task maps it) */
		bytes_alloc -= bo->size;
		free(bo->mem);
		bo->used = false;
		return kIOReturnSuccess;
	}
	case BLUE_GPU_SEL_GEM_INFO: {
		struct blue_gpu_gem_info *r = in;
		struct bo *bo;
		NEED(*r);
		if ((bo = bo_of(r->handle)) == NULL)
			return kIOReturnNotFound;
		switch (r->info) {
		case BLUE_GPU_INFO_GET_OFFSET: r->value = r->handle; return kIOReturnSuccess;
		case BLUE_GPU_INFO_GET_IOVA:   r->value = bo->iova; return kIOReturnSuccess;
		case BLUE_GPU_INFO_GET_FLAGS:  r->value = bo->flags; return kIOReturnSuccess;
		case BLUE_GPU_INFO_SET_NAME: {
			size_t n = r->len < 32 ? r->len : 32;
			memcpy(bo->name, (const void *)(uintptr_t)r->value, n);   /* (copyin in the kernel) */
			bo->name[n] = 0;
			return kIOReturnSuccess;
		}
		default:
			return kIOReturnBadArgument;
		}
	}
	case BLUE_GPU_SEL_GEM_CPU_PREP: {
		struct blue_gpu_gem_cpu_prep *r = in;
		NEED(*r);
		return bo_of(r->handle) ? kIOReturnSuccess : kIOReturnNotFound;   /* everything retired */
	}
	case BLUE_GPU_SEL_GEM_CPU_FINI:
		NEED(struct blue_gpu_gem_cpu_fini);
		return kIOReturnSuccess;
	case BLUE_GPU_SEL_GEM_SUBMIT:
		NEED(struct blue_gpu_submit);
		return do_submit(in);
	case BLUE_GPU_SEL_WAIT_FENCE: {
		struct blue_gpu_wait_fence *r = in;
		NEED(*r);
		return (int32_t)(r->fence - fence_seq) <= 0 ? kIOReturnSuccess : kIOReturnBadArgument;
	}
	case BLUE_GPU_SEL_GEM_MADVISE: {
		struct blue_gpu_gem_madvise *r = in;
		NEED(*r);
		r->retained = 1;
		return bo_of(r->handle) ? kIOReturnSuccess : kIOReturnNotFound;
	}
	case BLUE_GPU_SEL_SUBMITQUEUE_NEW: {
		struct blue_gpu_submitqueue *r = in;
		NEED(*r);
		if (r->flags & ~1u)
			return kIOReturnBadArgument;
		r->id = ++queue_seq;
		return kIOReturnSuccess;
	}
	case BLUE_GPU_SEL_SUBMITQUEUE_CLOSE:
		NEED(uint32_t);
		return kIOReturnSuccess;
	case BLUE_GPU_SEL_SUBMITQUEUE_QUERY: {
		struct blue_gpu_submitqueue_query *r = in;
		NEED(*r);
		if (r->param != 0)
			return kIOReturnBadArgument;
		if (r->len >= 4 && r->data)
			*(uint32_t *)(uintptr_t)r->data = 0;                     /* (copyout) */
		r->len = 4;
		return kIOReturnSuccess;
	}
	case BLUE_GPU_SEL_IOSURFACE:
		NEED(struct blue_gpu_iosurface);
		return kIOReturnUnsupported;
	case BLUE_GPU_SEL_USERPTR:
		NEED(struct blue_gpu_userptr);
		return kIOReturnUnsupported;
	default:
		BAD("unknown selector 0x%x\n", sel);
		return kIOReturnUnsupported;
	}
#undef NEED
}

kern_return_t
IOConnectCallStructMethod(mach_port_t conn, uint32_t sel, const void *in, size_t insz, void *out, size_t *outsz)
{
	IOReturn r;

	if (conn != 0x4343)
		return kIOReturnBadArgument;
	if (out != in || outsz == NULL || *outsz != insz) {
		BAD("sel 0x%x: struct must go in and come back (in %p/%zu out %p/%zu)\n", sel, in, insz, out,
		    outsz ? *outsz : 0);
		return kIOReturnBadArgument;
	}
	pthread_mutex_lock(&lock);
	n_calls++;
	r = dispatch(sel, out, insz);
	pthread_mutex_unlock(&lock);
	V("sel 0x%02x -> 0x%x\n", sel, r);
	return r;
}

kern_return_t
IOConnectMapMemory64(io_connect_t conn, uint32_t type, task_port_t task, mach_vm_address_t *addr,
                     mach_vm_size_t *size, IOOptionBits options)
{
	struct bo *bo;

	(void)task;
	if (conn != 0x4343 || !(options & kIOMapAnywhere))
		return kIOReturnBadArgument;
	pthread_mutex_lock(&lock);
	bo = bo_of(type);                       /* the token is the handle (GET_OFFSET) */
	if (bo != NULL) {
		*addr = (mach_vm_address_t)(uintptr_t)bo->mem;
		*size = bo->size;
		n_maps++;
	}
	pthread_mutex_unlock(&lock);
	return bo ? kIOReturnSuccess : kIOReturnBadArgument;
}

kern_return_t
IOConnectUnmapMemory64(io_connect_t conn, uint32_t type, task_port_t task, mach_vm_address_t addr)
{
	(void)conn; (void)type; (void)task; (void)addr;
	return kIOReturnSuccess;
}
