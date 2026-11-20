/*
 * blue_gpu_uapi.h - the BlueGPU kernel user-client ABI (pixel3-ios, Adreno 630 / SDM845).
 *
 * This is the contract between:
 *   - kernel stage 6d: the IOService "BlueGPU" and its IOUserClient in our XNU tree, and
 *   - userland: mesa-ios/bluedrm (the libdrm stand-in that Mesa freedreno's drm/msm
 *     backend, and later Turnip's msm backend, are built against).
 *
 * Design (same as HakiOS, tools/mesa/hakios-drm, MIT): the ABI *is* Linux drm/msm.
 *   - selector  = low byte of the Linux ioctl number = DRM_COMMAND_BASE (0x40) + DRM_MSM_*,
 *                 plus the generic DRM GEM_CLOSE (0x09) and two non-Linux requests (0x7d, 0x7e).
 *   - transport = IOConnectCallStructMethod(conn, selector, &s, sizeof s, &s, &sizeof s):
 *                 the struct goes in and comes back (same size) for EVERY selector, including
 *                 the ones Linux declares write-only (CPU_PREP, WAIT_FENCE, SUBMITQUEUE_CLOSE).
 *   - structs   = byte-identical to include/drm-uapi/msm_drm.h (Mesa 26.3.1 copy).
 *                 bluedrm.c static-asserts every size/offset against Mesa's header.
 *   - errors    = IOReturn; bluedrm maps them to errno (table at the end).
 *   - pointers  = user VAs of the calling task (u64). The kernel copyin()s them
 *                 (submit bos/cmds arrays, SET_NAME strings, SUBMITQUEUE_QUERY data).
 *   - mmap      = IOConnectMapMemory64(conn, memoryType = (uint32_t)GEM_INFO(GET_OFFSET).value,
 *                 mach_task_self(), &addr, &size, kIOMapAnywhere) -> clientMemoryForType().
 *                 The kernel returns the *token* in GET_OFFSET (recommended: the GEM handle);
 *                 userland never interprets it. Unmap: IOConnectUnmapMemory64 with the same type.
 *   - timeouts  = absolute drm_msm_timespec on Darwin's CLOCK_MONOTONIC_RAW, i.e.
 *                 mach_continuous_time() converted to ns (mesa-ios patch 0002 changes Mesa's
 *                 get_abs_timeout() to that clock). {0,0} = "poll, don't wait".
 *
 * Kernel stage 6d implements exactly this header. Keep it free of Mesa/IOKit includes so the
 * kernel can include it as is (only <stdint.h>-style types).
 *
 * Copyright (c) 2026 pixel3-ios. MIT licence. Struct layouts are Linux's msm_drm.h (MIT).
 */
#ifndef BLUE_GPU_UAPI_H
#define BLUE_GPU_UAPI_H

#ifdef KERNEL
#include <stdint.h>
#else
#include <stdint.h>
#endif

#define BLUE_GPU_SERVICE        "LemonGPU"   /* IOServiceMatching() name of the GPU nub */
#define BLUE_GPU_UC_TYPE        0           /* IOServiceOpen() type */

/* What drmGetVersion() reports (bluedrm, not a selector). Mesa gates features on the minor:
 *   >=3 GMEM_BASE + submit queues + BO_IOVA, >=4 softpin (kernel-chosen IOVA, no relocs),
 *   >=5 robustness (FAULTS), >=7 SUSPENDS, >=8 probes MSM_BO_CACHED_COHERENT once (kernel
 *   answers EINVAL -> Mesa uses WC everywhere), >=9 asks VA_SIZE.  We report 1.9. */
#define BLUE_GPU_DRM_NAME       "msm"
#define BLUE_GPU_DRM_MAJOR      1
#define BLUE_GPU_DRM_MINOR      9

/* Lemon identity: validated against this phone's FDT and Linux a6xx_catalog.c.
 * These describe the target; they do not initialize or emulate the GPU. */
#define LEMON_GPU_ID             610u
#define LEMON_GPU_CHIP_ID        0x06010000ull
#define LEMON_GPU_GMEM_SIZE      0x21000ull
#define LEMON_GPU_HIGHEST_BANK_BIT 14u

/* ---- selectors -------------------------------------------------------------------------- */
#define BLUE_GPU_SEL_GEM_CLOSE          0x09    /* DRM_IOCTL_GEM_CLOSE (generic drm.h)      */
#define BLUE_GPU_SEL_GET_PARAM          0x40    /* DRM_MSM_GET_PARAM                        */
#define BLUE_GPU_SEL_SET_PARAM          0x41    /* DRM_MSM_SET_PARAM      (accept, ignore)  */
#define BLUE_GPU_SEL_GEM_NEW            0x42    /* DRM_MSM_GEM_NEW                          */
#define BLUE_GPU_SEL_GEM_INFO           0x43    /* DRM_MSM_GEM_INFO                         */
#define BLUE_GPU_SEL_GEM_CPU_PREP       0x44    /* DRM_MSM_GEM_CPU_PREP                     */
#define BLUE_GPU_SEL_GEM_CPU_FINI       0x45    /* DRM_MSM_GEM_CPU_FINI   (no-op)           */
#define BLUE_GPU_SEL_GEM_SUBMIT         0x46    /* DRM_MSM_GEM_SUBMIT                       */
#define BLUE_GPU_SEL_WAIT_FENCE         0x47    /* DRM_MSM_WAIT_FENCE                       */
#define BLUE_GPU_SEL_GEM_MADVISE        0x48    /* DRM_MSM_GEM_MADVISE    (retained = 1)    */
/*      0x49 DRM_MSM_GEM_SVM_NEW: never used by Mesa -> kIOReturnUnsupported                  */
#define BLUE_GPU_SEL_SUBMITQUEUE_NEW    0x4a    /* DRM_MSM_SUBMITQUEUE_NEW                  */
#define BLUE_GPU_SEL_SUBMITQUEUE_CLOSE  0x4b    /* DRM_MSM_SUBMITQUEUE_CLOSE (struct = u32) */
#define BLUE_GPU_SEL_SUBMITQUEUE_QUERY  0x4c    /* DRM_MSM_SUBMITQUEUE_QUERY                */
/*      0x4d VM_BIND, 0x4e PERFCNTR_CONFIG: not implemented -> kIOReturnUnsupported            */
#define BLUE_GPU_SEL_USERPTR            0x7d    /* HakiOS: whole pages of the caller as a BO */
#define BLUE_GPU_SEL_IOSURFACE          0x7e    /* HakiOS: BO over an IOSurface (by ID)      */
#define BLUE_GPU_SEL_MAX                0x7f    /* external-method table size                */

/* ---- 0x40 / 0x41 GET_PARAM / SET_PARAM --------------------------------------------------- */
struct blue_gpu_param {                 /* == struct drm_msm_param (24 bytes) */
	uint32_t pipe;                  /* in: BLUE_GPU_PIPE_3D0 (0x10); 2D0 (0x01) may fail   */
	uint32_t param;                 /* in: BLUE_GPU_PARAM_*                                */
	uint64_t value;                 /* out (get) / in (set)                                */
	uint32_t len;                   /* 0 for value params                                   */
	uint32_t pad;
};
#define BLUE_GPU_PIPE_2D0               0x01
#define BLUE_GPU_PIPE_3D0               0x10

/* param ids (MSM_PARAM_*) and the values the a630 kernel must return */
#define BLUE_GPU_PARAM_GPU_ID           0x01    /* 630                                          */
#define BLUE_GPU_PARAM_GMEM_SIZE        0x02    /* 0x100000 (1 MiB; a6xx_catalog.c a630)        */
#define BLUE_GPU_PARAM_CHIP_ID          0x03    /* 0x06030001 (Linux a6xx_catalog.c a630 ADRENO_CHIP_IDS) */
#define BLUE_GPU_PARAM_MAX_FREQ         0x04    /* Hz of the top OPP in use (710000000)         */
#define BLUE_GPU_PARAM_TIMESTAMP        0x05    /* CP_ALWAYS_ON_COUNTER, 19.2 MHz ticks          */
#define BLUE_GPU_PARAM_GMEM_BASE        0x06    /* 0x100000                                      */
#define BLUE_GPU_PARAM_PRIORITIES       0x07    /* 1 (one ring) - also MSM_PARAM_NR_RINGS        */
#define BLUE_GPU_PARAM_PP_PGTABLE       0x08    /* 0                                             */
#define BLUE_GPU_PARAM_FAULTS           0x09    /* global hang/fault count since boot            */
#define BLUE_GPU_PARAM_SUSPENDS         0x0a    /* GPU slumber/resume count (0 until 6c)         */
#define BLUE_GPU_PARAM_SYSPROF          0x0b    /* WO: accept, ignore                            */
#define BLUE_GPU_PARAM_COMM             0x0c    /* WO: (value = user ptr, len) accept, ignore    */
#define BLUE_GPU_PARAM_CMDLINE          0x0d    /* WO: accept, ignore                            */
#define BLUE_GPU_PARAM_VA_START         0x0e    /* start of this connection's GPU VA window      */
#define BLUE_GPU_PARAM_VA_SIZE          0x0f    /* size of it (kernel 0153: 0x80000000, all)     */
#define BLUE_GPU_PARAM_HIGHEST_BANK_BIT 0x10    /* 15 (sdm845, a6xx_set_ubwc_config)             */
#define BLUE_GPU_PARAM_RAYTRACING       0x11    /* 0                                             */
#define BLUE_GPU_PARAM_UBWC_SWIZZLE     0x12    /* EINVAL in v1 (only Turnip asks; default ~0)   */

#define BLUE_GPU_PARAM_MACROTILE_MODE   0x13    /* 0                                             */
#define BLUE_GPU_PARAM_UCHE_TRAP_BASE   0x14    /* EINVAL ok (Mesa then uses its default)        */
#define BLUE_GPU_PARAM_HAS_PRR          0x15    /* 0                                             */
/* unknown param -> kIOReturnBadArgument (EINVAL) */

#define BLUE_GPU_A630_GPU_ID            630
#define BLUE_GPU_A630_CHIP_ID           0x06030001ull
#define BLUE_GPU_A630_GMEM_SIZE         0x100000ull
#define BLUE_GPU_A630_GMEM_BASE         0x100000ull
#define BLUE_GPU_A630_HIGHEST_BANK_BIT  15
/*
 * What kernel 0153 returns (tested 2026-11-19): one GPU VA space shared by every
 * client (per-process tables are a later stage). 0x80000000.. is the pool, linear
 * (BO iova = 0x80000000 + its offset; 32 MiB by default), 0xc0000000..0xffffffff
 * holds imports (IOSurface, userptr). Always use the values GET_PARAM returns.
 */
#define BLUE_GPU_VA_START_DEFAULT       0x80000000ull   /* GET_PARAM VA_START */
#define BLUE_GPU_VA_SIZE_BACKBOARDD     0x80000000ull   /* GET_PARAM VA_SIZE (same for every client) */
#define BLUE_GPU_VA_SIZE_DEFAULT        0x80000000ull

/* ---- 0x42 GEM_NEW ----------------------------------------------------------------------- */
struct blue_gpu_gem_new {               /* == struct drm_msm_gem_new (16 bytes) */
	uint64_t size;                  /* in: bytes; kernel rounds up to its granule (64 KiB) */
	uint32_t flags;                 /* in: BLUE_GPU_BO_*                                    */
	uint32_t handle;                /* out: nonzero, per connection                          */
};
#define BLUE_GPU_BO_SCANOUT             0x00000001  /* contiguous, below 4 GiB (pool is anyway) */
#define BLUE_GPU_BO_GPU_READONLY        0x00000002
#define BLUE_GPU_BO_NO_SHARE            0x00000004
#define BLUE_GPU_BO_CACHE_MASK          0x000f0000
#define BLUE_GPU_BO_CACHED              0x00010000  /* -> EINVAL in v1 (pool is WC-only)         */
#define BLUE_GPU_BO_WC                  0x00020000  /* the only cache mode v1 accepts            */
#define BLUE_GPU_BO_UNCACHED            0x00040000  /* treat as WC                               */
#define BLUE_GPU_BO_CACHED_COHERENT     0x00080000  /* -> EINVAL (Mesa probes it once)           */
/* Memory: zero-filled, from the GPU carve-out (plan 6d), mapped at a kernel-chosen IOVA inside
 * the connection's VA window immediately (GET_IOVA must work right after GEM_NEW). */

/* ---- 0x09 GEM_CLOSE --------------------------------------------------------------------- */
struct blue_gpu_gem_close {             /* == struct drm_gem_close (8 bytes) */
	uint32_t handle;
	uint32_t pad;
};
/* Frees the handle. Pages and IOVA go to the zombie list until the last fence that used the BO
 * retires, and until no task still maps it (flame 0113). Never fails for a valid handle. */

/* ---- 0x43 GEM_INFO ---------------------------------------------------------------------- */
struct blue_gpu_gem_info {              /* == struct drm_msm_gem_info (24 bytes) */
	uint32_t handle;
	uint32_t info;                  /* BLUE_GPU_INFO_* */
	uint64_t value;                 /* in or out, or a user pointer (NAME, METADATA)       */
	uint32_t len;
	uint32_t pad;
};
#define BLUE_GPU_INFO_GET_OFFSET        0x00    /* out: mmap token = memoryType for IOConnectMapMemory64 */
#define BLUE_GPU_INFO_GET_IOVA          0x01    /* out: GPU VA                                    */
#define BLUE_GPU_INFO_SET_NAME          0x02    /* in: value = user ptr, len <= 32: keep for logs  */
#define BLUE_GPU_INFO_GET_NAME          0x03    /* optional                                        */
#define BLUE_GPU_INFO_SET_IOVA          0x04    /* in: client-chosen VA in the window (Turnip); EINVAL if busy/outside */
#define BLUE_GPU_INFO_GET_FLAGS         0x05    /* out: the GEM_NEW flags                          */
#define BLUE_GPU_INFO_SET_METADATA      0x06    /* EINVAL ok in v1 (Mesa logs once)               */
#define BLUE_GPU_INFO_GET_METADATA      0x07    /* EINVAL ok in v1                                 */

/* ---- 0x44 / 0x45 CPU_PREP / CPU_FINI ---------------------------------------------------- */
struct blue_gpu_timespec {              /* == struct drm_msm_timespec (16 bytes) */
	int64_t tv_sec;
	int64_t tv_nsec;
};
struct blue_gpu_gem_cpu_prep {          /* == struct drm_msm_gem_cpu_prep (24 bytes) */
	uint32_t handle;
	uint32_t op;                    /* BLUE_GPU_PREP_*                                     */
	struct blue_gpu_timespec timeout; /* absolute, CLOCK_MONOTONIC_RAW (see top)          */
};
#define BLUE_GPU_PREP_READ              0x01    /* wait for the GPU's last WRITE of the BO       */
#define BLUE_GPU_PREP_WRITE             0x02    /* wait for the GPU's last READ or WRITE          */
#define BLUE_GPU_PREP_NOSYNC            0x04    /* don't wait: kIOReturnBusy (EBUSY) if not idle   */
#define BLUE_GPU_PREP_BOOST             0x08    /* ignore                                          */
/* Result: 0 idle, kIOReturnBusy (EBUSY) with NOSYNC, kIOReturnTimeout (ETIMEDOUT) at the deadline.
 * For imported cacheable BOs (0x7d/0x7e): invalidate the CPU cache here if the GPU wrote it. */
struct blue_gpu_gem_cpu_fini {          /* == struct drm_msm_gem_cpu_fini (4 bytes) */
	uint32_t handle;
};

/* ---- 0x46 GEM_SUBMIT -------------------------------------------------------------------- */
struct blue_gpu_submit_bo {             /* == struct drm_msm_gem_submit_bo (16 bytes) */
	uint32_t flags;                 /* BLUE_GPU_SUBMIT_BO_*                                */
	uint32_t handle;
	uint64_t presumed;              /* Mesa sends 0; kernel ignores (softpin)              */
};
#define BLUE_GPU_SUBMIT_BO_READ         0x0001
#define BLUE_GPU_SUBMIT_BO_WRITE        0x0002
#define BLUE_GPU_SUBMIT_BO_DUMP         0x0004
#define BLUE_GPU_SUBMIT_BO_NO_IMPLICIT  0x0008
#define BLUE_GPU_SUBMIT_BO_NOSYNC       0x0100  /* blue: a USERPTR BO the CPU never touches; cleaned at its first submit only */

struct blue_gpu_submit_cmd {            /* == struct drm_msm_gem_submit_cmd (32 bytes) */
	uint32_t type;                  /* BLUE_GPU_SUBMIT_CMD_*                               */
	uint32_t submit_idx;            /* index into bos[] of the BO holding the IB           */
	uint32_t submit_offset;         /* byte offset of the IB in that BO                    */
	uint32_t size;                  /* IB size in BYTES (kernel emits size/4 dwords)       */
	uint32_t pad;
	uint32_t nr_relocs;             /* always 0 with softpin: reject nonzero (EINVAL)      */
	uint64_t relocs_or_iova;        /* relocs ptr (unused) / iova (VM_BIND only, unused)   */
};
#define BLUE_GPU_SUBMIT_CMD_BUF             0x0001  /* CP_INDIRECT_BUFFER                     */
#define BLUE_GPU_SUBMIT_CMD_IB_TARGET_BUF   0x0002  /* referenced from another IB: skip       */
#define BLUE_GPU_SUBMIT_CMD_CTX_RESTORE_BUF 0x0003  /* emit only if context switched (always: one ctx) */

struct blue_gpu_submit_syncobj {        /* == struct drm_msm_syncobj (16 bytes) */
	uint32_t handle;
	uint32_t flags;
	uint64_t point;
};

struct blue_gpu_submit {                /* == struct drm_msm_gem_submit (72 bytes) */
	uint32_t flags;                 /* BLUE_GPU_PIPE_3D0 | BLUE_GPU_SUBMIT_*              */
	uint32_t fence;                 /* out: seqno on this queue (monotonic, wraps at 2^32) */
	uint32_t nr_bos;
	uint32_t nr_cmds;
	uint64_t bos;                   /* user ptr: struct blue_gpu_submit_bo[nr_bos]         */
	uint64_t cmds;                  /* user ptr: struct blue_gpu_submit_cmd[nr_cmds]       */
	int32_t  fence_fd;              /* -1; FENCE_FD_IN/OUT -> EINVAL                       */
	uint32_t queueid;               /* from SUBMITQUEUE_NEW (0 = default queue)           */
	uint64_t in_syncobjs;           /* never reaches the kernel: bluedrm strips SYNCOBJ_* */
	uint64_t out_syncobjs;
	uint32_t nr_in_syncobjs;
	uint32_t nr_out_syncobjs;
	uint32_t syncobj_stride;
	uint32_t pad;
};
#define BLUE_GPU_SUBMIT_NO_IMPLICIT     0x80000000u /* gallium freedreno sets it; ignore       */
#define BLUE_GPU_SUBMIT_FENCE_FD_IN     0x40000000u /* EINVAL (no sync files on Darwin)        */
#define BLUE_GPU_SUBMIT_FENCE_FD_OUT    0x20000000u /* EINVAL (Mesa only asks when exporting)  */
#define BLUE_GPU_SUBMIT_SUDO            0x10000000u /* EINVAL                                  */
#define BLUE_GPU_SUBMIT_SYNCOBJ_IN      0x08000000u /* handled in bluedrm, stripped            */
#define BLUE_GPU_SUBMIT_SYNCOBJ_OUT     0x04000000u /* handled in bluedrm, stripped            */
#define BLUE_GPU_SUBMIT_FENCE_SN_IN     0x02000000u /* EINVAL                                  */
/* Kernel duty per submit (as Linux a6xx_submit): validate handles + IB ranges inside their BO,
 * CCU colour/depth invalidate + CACHE_INVALIDATE before, one CP_INDIRECT_BUFFER per CMD_BUF /
 * CTX_RESTORE_BUF, then CACHE_FLUSH_TS writing the fence seqno, then CP_ALWAYS_ON stamps for
 * stats. Clean cacheable imported BOs to PoC. Record the fence on every BO (for CPU_PREP and
 * deferred free). Ring full -> kIOReturnBusy (EBUSY; Mesa retries). nr_cmds == 0 never reaches
 * the kernel (bluedrm answers with the last fence). */

/* ---- 0x47 WAIT_FENCE -------------------------------------------------------------------- */
struct blue_gpu_wait_fence {            /* == struct drm_msm_wait_fence (32 bytes) */
	uint32_t fence;
	uint32_t flags;                 /* BOOST: ignore                                       */
	struct blue_gpu_timespec timeout; /* absolute CLOCK_MONOTONIC_RAW; {0,0} = poll        */
	uint32_t queueid;
	uint32_t pad_;                  /* (implicit tail padding of the Linux struct)         */
};
/* 0 = retired; kIOReturnTimeout (ETIMEDOUT) = not yet. A fence newer than the last submitted one
 * on that queue -> kIOReturnBadArgument (EINVAL), like Linux. After a GPU reset (6c) every
 * submitted fence counts as retired and FAULTS goes up. */

/* ---- 0x48 MADVISE ----------------------------------------------------------------------- */
struct blue_gpu_gem_madvise {           /* == struct drm_msm_gem_madvise (12 bytes) */
	uint32_t handle;
	uint32_t madv;                  /* 0 WILLNEED, 1 DONTNEED                               */
	uint32_t retained;              /* out: always 1 (we never purge)                       */
};

/* ---- 0x4a..0x4c SUBMITQUEUE ------------------------------------------------------------- */
struct blue_gpu_submitqueue {           /* == struct drm_msm_submitqueue (12 bytes) */
	uint32_t flags;                 /* ALLOW_PREEMPT ok; VM_BIND (0x2) -> EINVAL            */
	uint32_t prio;                  /* 0..PRIORITIES-1: ignored                             */
	uint32_t id;                    /* out: nonzero queue id (all share the one ring)       */
};
/* SUBMITQUEUE_CLOSE: the struct is a bare uint32_t id (4 bytes). */
struct blue_gpu_submitqueue_query {     /* == struct drm_msm_submitqueue_query (24 bytes) */
	uint64_t data;                  /* user ptr (len bytes) for the answer                  */
	uint32_t id;
	uint32_t param;                 /* 0 = FAULTS: u32 count of hangs caused by this queue  */
	uint32_t len;                   /* in/out: 0 in -> kernel writes needed size            */
	uint32_t pad;
};

/* ---- 0x7d USERPTR (HakiOS number; not used by gallium freedreno) ------------------------ */
struct blue_gpu_userptr {               /* 24 bytes (layout as hakios-drm) */
	uint64_t address;               /* page aligned, in the caller                          */
	uint64_t size;                  /* multiple of 16 KiB                                   */
	uint32_t handle;                /* out                                                  */
	uint32_t flags;                 /* 0                                                    */
};

/* ---- 0x7e IOSURFACE (HakiOS number) ----------------------------------------------------- */
struct blue_gpu_iosurface {             /* 40 bytes (layout as hakios-drm struct hakios_drm_surface) */
	uint32_t surface;               /* in: IOSurfaceID                                     */
	uint32_t handle;                /* in: BLUE_GPU_IOSURFACE_DESCRIBE = only describe;     */
	                                /* otherwise ignored on input; out: new/existing handle */
	uint64_t size;                  /* out: bytes of the BO                                */
	uint32_t offset;                /* out: first pixel's offset inside the BO              */
	uint32_t row_bytes;             /* out: bytesPerRow (must be %64 == 0 to render to it)  */
	uint32_t width, height;         /* out                                                  */
	uint32_t pixel_format;          /* out: e.g. 'BGRA' 0x42475241                           */
	uint32_t planes;                /* out: 0 for non-planar                                */
};
#define BLUE_GPU_IOSURFACE_DESCRIBE     0xffffffffu
/* Same surface imported twice in one connection returns the same handle (freedreno looks it up
 * under its table lock). Pages: SweetSurface's IOBufferMemoryDescriptor, 16 KiB, wired,
 * cacheable: kernel cleans to PoC at submit when the CPU wrote, invalidates at CPU_PREP. */

/* ---- IOReturn -> errno (bluedrm) -------------------------------------------------------- */
/*   kIOReturnSuccess 0 | kIOReturnNoMemory ENOMEM | kIOReturnBadArgument EINVAL |
 *   kIOReturnTimeout ETIMEDOUT | kIOReturnBusy EBUSY | kIOReturnNotFound ENOENT (bad handle) |
 *   kIOReturnUnsupported ENOSYS | kIOReturnNotPrivileged EPERM | anything else EIO           */

#endif /* BLUE_GPU_UAPI_H */
