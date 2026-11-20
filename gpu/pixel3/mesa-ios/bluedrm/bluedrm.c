/*
 * bluedrm.c - libdrm stand-in for Mesa freedreno on Darwin (pixel3-ios, Adreno 630).
 *
 * Linux drm/msm requests become calls of the BlueGPU IOKit user client: the selector is the
 * low byte of the ioctl number (DRM_COMMAND_BASE + DRM_MSM_*), the struct goes in and comes back
 * unchanged in size. A BO's memory is the client memory of type GEM_INFO(GET_OFFSET).value.
 * The full contract is ../blue_gpu_uapi.h (kernel stage 6d implements it).
 *
 * freedreno knows its device by a file descriptor; it gets a dup of /dev/null. There is one GPU
 * and one connection per process.
 *
 * Derived from HakiOS tools/mesa/hakios-drm/hakios.drm.c (commit 63fc2b46)
 *   Copyright (c) 2025-2026 the HakiOS authors, MIT License (see ../LICENSES/HakiOS-MIT.txt)
 * pixel3-ios changes (MIT): BlueGPU service + blue_gpu_uapi.h, layout static asserts against
 * Mesa's msm_drm.h, mmap by offset token, version 1.9, BLUEDRM_DEBUG trace, dropped the
 * host-surface registry (Turnip/Metal only).
 */
#include <assert.h>
#include <errno.h>
#include <pthread.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/time.h>
#include <time.h>
#include <unistd.h>

#include <IOKit/IOKitLib.h>

#include "xf86drm.h"
#include "drm-uapi/msm_drm.h"
#include "blue_gpu_uapi.h"

/* ---- the ABI is msm_drm.h: prove it at compile time ---- */
#define SAME(a, b) _Static_assert(sizeof(struct a) == sizeof(struct b), #a " size")
#define OFF(a, fa, b, fb) _Static_assert(offsetof(struct a, fa) == offsetof(struct b, fb), #a "." #fa)
SAME(blue_gpu_param, drm_msm_param);
OFF(blue_gpu_param, value, drm_msm_param, value);
OFF(blue_gpu_param, len, drm_msm_param, len);
SAME(blue_gpu_gem_new, drm_msm_gem_new);
OFF(blue_gpu_gem_new, handle, drm_msm_gem_new, handle);
SAME(blue_gpu_gem_close, drm_gem_close);
SAME(blue_gpu_gem_info, drm_msm_gem_info);
OFF(blue_gpu_gem_info, value, drm_msm_gem_info, value);
OFF(blue_gpu_gem_info, len, drm_msm_gem_info, len);
SAME(blue_gpu_timespec, drm_msm_timespec);
SAME(blue_gpu_gem_cpu_prep, drm_msm_gem_cpu_prep);
OFF(blue_gpu_gem_cpu_prep, timeout, drm_msm_gem_cpu_prep, timeout);
SAME(blue_gpu_gem_cpu_fini, drm_msm_gem_cpu_fini);
SAME(blue_gpu_submit_bo, drm_msm_gem_submit_bo);
OFF(blue_gpu_submit_bo, presumed, drm_msm_gem_submit_bo, presumed);
SAME(blue_gpu_submit_cmd, drm_msm_gem_submit_cmd);
OFF(blue_gpu_submit_cmd, size, drm_msm_gem_submit_cmd, size);
OFF(blue_gpu_submit_cmd, nr_relocs, drm_msm_gem_submit_cmd, nr_relocs);
OFF(blue_gpu_submit_cmd, relocs_or_iova, drm_msm_gem_submit_cmd, relocs);
SAME(blue_gpu_submit_syncobj, drm_msm_syncobj);
SAME(blue_gpu_submit, drm_msm_gem_submit);
OFF(blue_gpu_submit, bos, drm_msm_gem_submit, bos);
OFF(blue_gpu_submit, cmds, drm_msm_gem_submit, cmds);
OFF(blue_gpu_submit, fence_fd, drm_msm_gem_submit, fence_fd);
OFF(blue_gpu_submit, queueid, drm_msm_gem_submit, queueid);
OFF(blue_gpu_submit, in_syncobjs, drm_msm_gem_submit, in_syncobjs);
OFF(blue_gpu_submit, syncobj_stride, drm_msm_gem_submit, syncobj_stride);
SAME(blue_gpu_wait_fence, drm_msm_wait_fence);
OFF(blue_gpu_wait_fence, timeout, drm_msm_wait_fence, timeout);
OFF(blue_gpu_wait_fence, queueid, drm_msm_wait_fence, queueid);
SAME(blue_gpu_gem_madvise, drm_msm_gem_madvise);
SAME(blue_gpu_submitqueue, drm_msm_submitqueue);
SAME(blue_gpu_submitqueue_query, drm_msm_submitqueue_query);
_Static_assert(sizeof(struct blue_gpu_userptr) == 24, "userptr");
_Static_assert(sizeof(struct blue_gpu_iosurface) == 40, "iosurface");
_Static_assert((DRM_IOCTL_GEM_CLOSE & 0xff) == BLUE_GPU_SEL_GEM_CLOSE, "GEM_CLOSE nr");
_Static_assert(DRM_COMMAND_BASE + DRM_MSM_GET_PARAM == BLUE_GPU_SEL_GET_PARAM, "GET_PARAM");
_Static_assert(DRM_COMMAND_BASE + DRM_MSM_GEM_NEW == BLUE_GPU_SEL_GEM_NEW, "GEM_NEW");
_Static_assert(DRM_COMMAND_BASE + DRM_MSM_GEM_INFO == BLUE_GPU_SEL_GEM_INFO, "GEM_INFO");
_Static_assert(DRM_COMMAND_BASE + DRM_MSM_GEM_CPU_PREP == BLUE_GPU_SEL_GEM_CPU_PREP, "CPU_PREP");
_Static_assert(DRM_COMMAND_BASE + DRM_MSM_GEM_SUBMIT == BLUE_GPU_SEL_GEM_SUBMIT, "SUBMIT");
_Static_assert(DRM_COMMAND_BASE + DRM_MSM_WAIT_FENCE == BLUE_GPU_SEL_WAIT_FENCE, "WAIT_FENCE");
_Static_assert(DRM_COMMAND_BASE + DRM_MSM_GEM_MADVISE == BLUE_GPU_SEL_GEM_MADVISE, "MADVISE");
_Static_assert(DRM_COMMAND_BASE + DRM_MSM_SUBMITQUEUE_NEW == BLUE_GPU_SEL_SUBMITQUEUE_NEW, "SQ_NEW");
_Static_assert(DRM_COMMAND_BASE + DRM_MSM_SUBMITQUEUE_CLOSE == BLUE_GPU_SEL_SUBMITQUEUE_CLOSE, "SQ_CLOSE");
_Static_assert(DRM_COMMAND_BASE + DRM_MSM_SUBMITQUEUE_QUERY == BLUE_GPU_SEL_SUBMITQUEUE_QUERY, "SQ_QUERY");
_Static_assert(MSM_PARAM_CHIP_ID == BLUE_GPU_PARAM_CHIP_ID && MSM_PARAM_VA_SIZE == BLUE_GPU_PARAM_VA_SIZE &&
               MSM_PARAM_UCHE_TRAP_BASE == BLUE_GPU_PARAM_UCHE_TRAP_BASE, "params");
_Static_assert(MSM_BO_WC == BLUE_GPU_BO_WC && MSM_BO_CACHED_COHERENT == BLUE_GPU_BO_CACHED_COHERENT, "bo flags");
_Static_assert(MSM_SUBMIT_SYNCOBJ_IN == BLUE_GPU_SUBMIT_SYNCOBJ_IN && MSM_SUBMIT_NO_IMPLICIT == BLUE_GPU_SUBMIT_NO_IMPLICIT,
               "submit flags");

#define EXPORT __attribute__((visibility("default")))

static io_connect_t connection;
static int connection_fd = -1;
static int debug = -1;

#define TRACE(...) do { if (debug > 0) fprintf(stderr, "bluedrm: " __VA_ARGS__); } while (0)

/* ---- BOs in our own memory when the kernel's pool is full ----
 * The pool is at most 32 MiB (its kernel view comes from ml_io_map); CoreAnimation in backboardd
 * wants more (screen-sized intermediates are 11 MiB each). When GEM_NEW says ENOMEM, the BO is
 * made from anonymous memory of ours and handed over by USERPTR (the kernel cleans + invalidates
 * it at every submit that uses it). freedreno sees an ordinary handle; it maps it here, not by
 * the kernel (clientMemoryForType has no userptr). Closed ones are kept for reuse by size, not
 * unmapped: the kernel keeps the pages wired until the GPU is done with them. */
#define OWN_MAX 2048
static struct own { uint32_t handle; uint64_t size; void *address; int mapped; } own[OWN_MAX];
static struct own spare[OWN_MAX];
static unsigned owns, spares, own_made, own_reused;
static pthread_mutex_t own_lock = PTHREAD_MUTEX_INITIALIZER;
static int call(unsigned selector, void *data, size_t size);

/* Own BOs freedreno never maps are GPU-only: their submits carry BLUE_GPU_SUBMIT_BO_NOSYNC, and the
 * kernel cleans them once (the first submit) instead of at every submit (48 MiB a frame before). */
static int
own_unmapped(uint32_t handle)
{
	int r = 0;
	pthread_mutex_lock(&own_lock);
	for (unsigned i = 0; i < owns; i++) {
		if (own[i].handle == handle) {
			r = !own[i].mapped;
			break;
		}
	}
	pthread_mutex_unlock(&own_lock);
	return r;
}

static void *
own_find_map(uint32_t handle, int map)
{
	void *address = NULL;
	pthread_mutex_lock(&own_lock);
	for (unsigned i = 0; i < owns; i++) {
		if (own[i].handle == handle) {
			address = own[i].address;
			own[i].mapped |= map;
			break;
		}
	}
	pthread_mutex_unlock(&own_lock);
	return address;
}

static void *
own_find(uint32_t handle)
{
	return own_find_map(handle, 0);
}

static int
own_new(struct drm_msm_gem_new *r)
{
	long page = sysconf(_SC_PAGESIZE);
	if (page <= 0 || (page & (page - 1)) != 0) return EINVAL;
	uint64_t mask = (uint64_t)page - 1;
	if (!r->size || r->size > SIZE_MAX - mask) return EINVAL;
	uint64_t size = (r->size + mask) & ~mask;
	void *address = NULL;
	int error;

	pthread_mutex_lock(&own_lock);
	for (unsigned i = 0; i < spares; i++) {
		if (spare[i].size == size) {
			address = spare[i].address;
			spare[i] = spare[--spares];
			own_reused++;
			break;
		}
	}
	pthread_mutex_unlock(&own_lock);
	if (address != NULL) {
		memset(address, 0, size);
	} else {
		address = mmap(NULL, size, PROT_READ | PROT_WRITE, MAP_ANON | MAP_PRIVATE, -1, 0);
		if (address == MAP_FAILED)
			return ENOMEM;
		own_made++;
	}
	struct blue_gpu_userptr u = { .address = (uintptr_t)address, .size = size };
	if ((error = call(BLUE_GPU_SEL_USERPTR, &u, sizeof(u))) != 0) {
		munmap(address, size);
		return error;
	}
	pthread_mutex_lock(&own_lock);
	if (owns < OWN_MAX)
		own[owns++] = (struct own){ u.handle, size, address, 0 };
	pthread_mutex_unlock(&own_lock);
	r->handle = u.handle;
	if (own_made + own_reused <= 8 || ((own_made + own_reused) & 63) == 0)
		fprintf(stderr, "bluedrm: pool full: BO of %llu KiB in our own memory (handle %u; %u made, %u reused, %u live)\n",
		        (unsigned long long)(size >> 10), u.handle, own_made, own_reused, owns);
	return 0;
}

static void
own_closed(uint32_t handle)
{
	pthread_mutex_lock(&own_lock);
	for (unsigned i = 0; i < owns; i++) {
		if (own[i].handle == handle) {
			if (spares < OWN_MAX)
				spare[spares++] = own[i];
			own[i] = own[--owns];
			break;
		}
	}
	pthread_mutex_unlock(&own_lock);
}

int
drmOpenWithType(const char *name, const char *busid, int type)
{
	io_service_t service;
	kern_return_t kr;

	(void)busid;
	(void)type;
	if (debug < 0)
		debug = getenv("BLUEDRM_DEBUG") != NULL;
	if (strcmp(name, "msm") != 0)
		return -1;
	if (connection_fd >= 0)
		return dup(connection_fd);
	service = IOServiceGetMatchingService(kIOMainPortDefault, IOServiceMatching(BLUE_GPU_SERVICE));
	if (service == 0) {
		TRACE("no %s service\n", BLUE_GPU_SERVICE);
		return -1;
	}
	kr = IOServiceOpen(service, mach_task_self(), BLUE_GPU_UC_TYPE, &connection);
	IOObjectRelease(service);
	if (kr != KERN_SUCCESS) {
		TRACE("IOServiceOpen: 0x%x\n", kr);
		return -1;
	}
	connection_fd = open("/dev/null", O_RDWR | O_CLOEXEC);
	TRACE("connected to %s\n", BLUE_GPU_SERVICE);
	return dup(connection_fd);
}

static int
call(unsigned selector, void *data, size_t size)
{
	size_t returned = size;
	kern_return_t result = IOConnectCallStructMethod(connection, selector, data, size, data, &returned);

	TRACE("sel 0x%02x size %zu -> 0x%x\n", selector, size, result);
	switch (result) {
	case kIOReturnSuccess:          return 0;
	case kIOReturnNoMemory:         return ENOMEM;
	case kIOReturnBadArgument:      return EINVAL;
	case kIOReturnTimeout:          return ETIMEDOUT;
	case kIOReturnBusy:             return EBUSY;
	case kIOReturnNotFound:         return ENOENT;
	case kIOReturnUnsupported:      return ENOSYS;
	case kIOReturnNotPrivileged:    return EPERM;
	default:                        return EIO;
	}
}

int
drmIoctl(int fd, unsigned long request, void *arg)
{
	int error = call((unsigned)(request & 0xff), arg, IOCPARM_LEN(request));

	(void)fd;
	if (error != 0) {
		errno = error;
		return -1;
	}
	if ((request & 0xff) == BLUE_GPU_SEL_GEM_CLOSE)
		own_closed(((struct drm_gem_close *)arg)->handle);
	return 0;
}

int
drmCommandWrite(int fd, unsigned long index, void *data, unsigned long size)
{
	(void)fd;
	return -call((unsigned)(DRM_COMMAND_BASE + index), data, size);
}

static int submit_with_syncobjs(struct drm_msm_gem_submit *submit, unsigned long size);

int
drmCommandWriteRead(int fd, unsigned long index, void *data, unsigned long size)
{
	(void)fd;
	if (index == DRM_MSM_GEM_SUBMIT && size >= sizeof(struct drm_msm_gem_submit))
		return submit_with_syncobjs(data, size);
	if (index == DRM_MSM_GEM_INFO && size >= sizeof(struct drm_msm_gem_info) &&
	    ((struct drm_msm_gem_info *)data)->info == MSM_INFO_GET_OFFSET &&
	    own_find(((struct drm_msm_gem_info *)data)->handle) != NULL) {
		((struct drm_msm_gem_info *)data)->value = ((struct drm_msm_gem_info *)data)->handle;
		return 0;       /* ours: bluedrm_map knows it by handle */
	}
	if (index == DRM_MSM_GEM_NEW && size >= sizeof(struct drm_msm_gem_new)) {
		int error = call((unsigned)(DRM_COMMAND_BASE + index), data, size);
		if (error == ENOMEM && getenv("BLUEDRM_NO_OWN") == NULL)
			error = own_new(data);
		return -error;
	}
	return -call((unsigned)(DRM_COMMAND_BASE + index), data, size);
}

drmVersionPtr
drmGetVersion(int fd)
{
	drmVersionPtr version = calloc(1, sizeof(*version));

	(void)fd;
	if (version != NULL) {
		version->version_major = BLUE_GPU_DRM_MAJOR;
		version->version_minor = BLUE_GPU_DRM_MINOR;
		version->name = strdup(BLUE_GPU_DRM_NAME);
		version->name_len = (int)strlen(version->name);
		version->date = strdup("");
		version->desc = strdup("Adreno on Darwin (LemonGPU)");
		version->desc_len = (int)strlen(version->desc);
	}
	return version;
}

void
drmFreeVersion(drmVersionPtr version)
{
	if (version != NULL) {
		free(version->name);
		free(version->date);
		free(version->desc);
		free(version);
	}
}

int
drmGetCap(int fd, uint64_t capability, uint64_t *value)
{
	(void)fd;
	(void)capability;
	*value = 0;     /* no DRM_CAP_SYNCOBJ: gallium freedreno then never uses fence fds */
	return 0;
}

void *
bluedrm_map(int fd, uint32_t handle, uint64_t offset, uint64_t size)
{
	mach_vm_address_t address = 0;
	mach_vm_size_t mapped = 0;
	kern_return_t kr;

	(void)fd;
	void *mine = own_find_map(handle, 1);
	if (mine != NULL)
		return (char *)mine;
	/* The kernel's pool is write-combined with no physmap alias, so the mapping is WC like
	 * Linux's msm BOs (the kernel picks the cache mode in clientMemoryForType). */
	kr = IOConnectMapMemory64(connection, (uint32_t)offset, mach_task_self(), &address, &mapped, kIOMapAnywhere);
	TRACE("map handle %u token 0x%llx size 0x%llx -> 0x%llx (0x%x)\n", handle, (unsigned long long)offset,
	      (unsigned long long)size, (unsigned long long)address, kr);
	if (kr != KERN_SUCCESS || mapped < size)
		return MAP_FAILED;
	return (void *)(uintptr_t)address;
}

void
bluedrm_unmap(int fd, uint32_t handle, void *address, uint64_t size)
{
	struct drm_msm_gem_info info = { .handle = handle, .info = MSM_INFO_GET_OFFSET };

	(void)fd;
	(void)size;
	if (own_find(handle) == address)
		return;
	/* (the token is asked again: freedreno does not keep it next to bo->map) */
	if (call(DRM_COMMAND_BASE + DRM_MSM_GEM_INFO, &info, sizeof(info)) == 0)
		IOConnectUnmapMemory64(connection, (uint32_t)info.value, mach_task_self(),
		                       (mach_vm_address_t)(uintptr_t)address);
}

EXPORT int
bluedrm_iosurface_describe(int fd, struct blue_gpu_iosurface *s)
{
	int error;

	(void)fd;
	s->handle = BLUE_GPU_IOSURFACE_DESCRIBE;
	error = call(BLUE_GPU_SEL_IOSURFACE, s, sizeof(*s));
	if (error != 0) {
		errno = error;
		return -1;
	}
	return 0;
}

uint64_t
bluedrm_import_size(int fd, int surface_id)
{
	struct blue_gpu_iosurface s = { .surface = (uint32_t)surface_id };

	/*
	 * The kernel maps a surface for the GPU in whole 4 KiB pages (bg_import_map), so all of the
	 * last page can be read. A wrapped picture's memory ends at its last pixel, short of a whole
	 * last row, and Mesa wants pitch x height: without this such pictures were copied instead.
	 */
	return bluedrm_iosurface_describe(fd, &s) == 0 ? (s.size + 0xfffull) & ~0xfffull : 0;
}

int
drmPrimeFDToHandle(int fd, int prime_fd, uint32_t *handle)
{
	struct blue_gpu_iosurface s = { .surface = (uint32_t)prime_fd, .handle = 0 };
	int error = call(BLUE_GPU_SEL_IOSURFACE, &s, sizeof(s));

	(void)fd;
	if (error != 0) {
		errno = error;
		return -1;
	}
	*handle = s.handle;
	return 0;
}

EXPORT int
bluedrm_user_memory(int fd, const void *address, uint64_t size, uint32_t *handle)
{
	struct blue_gpu_userptr r = { .address = (uintptr_t)address, .size = size };
	int error = call(BLUE_GPU_SEL_USERPTR, &r, sizeof(r));

	(void)fd;
	if (error != 0) {
		errno = error;
		return -1;
	}
	*handle = r.handle;
	return 0;
}

static int
none(void)
{
	errno = ENOSYS;
	return -1;
}

int drmPrimeHandleToFD(int fd, uint32_t h, uint32_t f, int *p) { (void)fd; (void)h; (void)f; (void)p; return none(); }
int drmSyncobjFDToHandle(int fd, int o, uint32_t *h) { (void)fd; (void)o; (void)h; return none(); }
int drmSyncobjHandleToFD(int fd, uint32_t h, int *o) { (void)fd; (void)h; (void)o; return none(); }
int drmSyncobjImportSyncFile(int fd, uint32_t h, int s) { (void)fd; (void)h; (void)s; return none(); }
int drmSyncobjExportSyncFile(int fd, uint32_t h, int *s) { (void)fd; (void)h; (void)s; return none(); }

/*
 * DRM syncobjs kept in this process (HakiOS design): one GPU, one connection, so a syncobj waits
 * for one of this process's submissions, a kernel fence (WAIT_FENCE tells when it retired). A
 * syncobj is a timeline: the last point known reached plus the points still on their way, each
 * with the submission's fence. A binary one is the timeline of point 1.
 */
#define SYNCOBJS        4096
#define PENDING         16

struct syncobj {
	bool used;
	uint64_t reached;
	unsigned pending;
	struct { uint64_t point; uint32_t fence; } on_the_way[PENDING];
};
static struct syncobj syncobjs[SYNCOBJS];
static pthread_mutex_t syncobj_lock = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t syncobj_submitted = PTHREAD_COND_INITIALIZER;

static struct syncobj *
syncobj_of(uint32_t handle)
{
	return handle != 0 && handle < SYNCOBJS && syncobjs[handle].used ? &syncobjs[handle] : NULL;
}

static int64_t
now_ns(void)
{
	struct timespec t;

	clock_gettime(CLOCK_MONOTONIC_RAW, &t);         /* the kernel's clock: blue_gpu_uapi.h */
	return (int64_t)t.tv_sec * 1000000000 + t.tv_nsec;
}

/* whether the kernel retired FENCE, waiting until DEADLINE (absolute ns; 0 = poll) */
static bool
fence_done(uint32_t fence, int64_t deadline)
{
	struct drm_msm_wait_fence wait = { .fence = fence, .queueid = 0 };

	wait.timeout.tv_sec = deadline / 1000000000;
	wait.timeout.tv_nsec = deadline % 1000000000;
	return call(DRM_COMMAND_BASE + DRM_MSM_WAIT_FENCE, &wait, sizeof(wait)) == 0;
}

static void
syncobj_poll(struct syncobj *s)
{
	unsigned kept = 0;

	for (unsigned i = 0; i < s->pending; i++) {
		if (fence_done(s->on_the_way[i].fence, 0)) {
			if (s->on_the_way[i].point > s->reached)
				s->reached = s->on_the_way[i].point;
		} else {
			s->on_the_way[kept++] = s->on_the_way[i];
		}
	}
	s->pending = kept;
}

static void
syncobj_add(struct syncobj *s, uint64_t point, uint32_t fence)
{
	if (s->pending == PENDING)
		syncobj_poll(s);
	if (s->pending == PENDING) {
		fence_done(s->on_the_way[0].fence, now_ns() + 10000000000LL);
		if (s->on_the_way[0].point > s->reached)
			s->reached = s->on_the_way[0].point;
		memmove(&s->on_the_way[0], &s->on_the_way[1], (PENDING - 1) * sizeof(s->on_the_way[0]));
		s->pending--;
	}
	s->on_the_way[s->pending].point = point;
	s->on_the_way[s->pending].fence = fence;
	s->pending++;
}

int
drmSyncobjCreate(int fd, uint32_t flags, uint32_t *handle)
{
	(void)fd;
	pthread_mutex_lock(&syncobj_lock);
	for (uint32_t h = 1; h < SYNCOBJS; h++) {
		if (!syncobjs[h].used) {
			memset(&syncobjs[h], 0, sizeof(syncobjs[h]));
			syncobjs[h].used = true;
			syncobjs[h].reached = (flags & DRM_SYNCOBJ_CREATE_SIGNALED) ? 1 : 0;
			*handle = h;
			pthread_mutex_unlock(&syncobj_lock);
			return 0;
		}
	}
	pthread_mutex_unlock(&syncobj_lock);
	errno = ENOMEM;
	return -ENOMEM;
}

int
drmSyncobjDestroy(int fd, uint32_t handle)
{
	struct syncobj *s;

	(void)fd;
	pthread_mutex_lock(&syncobj_lock);
	s = syncobj_of(handle);
	if (s != NULL)
		s->used = false;
	pthread_mutex_unlock(&syncobj_lock);
	return s != NULL ? 0 : -EINVAL;
}

int
drmSyncobjReset(int fd, const uint32_t *handles, uint32_t count)
{
	(void)fd;
	pthread_mutex_lock(&syncobj_lock);
	for (uint32_t i = 0; i < count; i++) {
		struct syncobj *s = syncobj_of(handles[i]);
		if (s != NULL)
			s->reached = 0, s->pending = 0;
	}
	pthread_mutex_unlock(&syncobj_lock);
	return 0;
}

int
drmSyncobjTimelineSignal(int fd, const uint32_t *handles, uint64_t *points, uint32_t count)
{
	(void)fd;
	pthread_mutex_lock(&syncobj_lock);
	for (uint32_t i = 0; i < count; i++) {
		struct syncobj *s = syncobj_of(handles[i]);
		uint64_t point = points != NULL && points[i] != 0 ? points[i] : 1;
		if (s != NULL && point > s->reached)
			s->reached = point;
	}
	pthread_cond_broadcast(&syncobj_submitted);
	pthread_mutex_unlock(&syncobj_lock);
	return 0;
}

int
drmSyncobjSignal(int fd, const uint32_t *handles, uint32_t count)
{
	return drmSyncobjTimelineSignal(fd, handles, NULL, count);
}

int
drmSyncobjQuery2(int fd, uint32_t *handles, uint64_t *points, uint32_t count, uint32_t flags)
{
	(void)fd;
	(void)flags;
	pthread_mutex_lock(&syncobj_lock);
	for (uint32_t i = 0; i < count; i++) {
		struct syncobj *s = syncobj_of(handles[i]);
		if (s != NULL)
			syncobj_poll(s);
		points[i] = s != NULL ? s->reached : 0;
	}
	pthread_mutex_unlock(&syncobj_lock);
	return 0;
}

int
drmSyncobjQuery(int fd, uint32_t *handles, uint64_t *points, uint32_t count)
{
	return drmSyncobjQuery2(fd, handles, points, count, 0);
}

int
drmSyncobjTimelineWait(int fd, uint32_t *handles, uint64_t *points, unsigned count, int64_t deadline,
                       unsigned flags, uint32_t *first)
{
	const bool all = (flags & DRM_SYNCOBJ_WAIT_FLAGS_WAIT_ALL) != 0;

	(void)fd;
	pthread_mutex_lock(&syncobj_lock);
	for (;;) {
		unsigned reached = 0, unknown = 0;
		uint32_t wait_fence = 0;
		bool have_fence = false;

		for (unsigned i = 0; i < count; i++) {
			struct syncobj *s = syncobj_of(handles[i]);
			uint64_t point = points != NULL && points[i] != 0 ? points[i] : 1;
			bool on_the_way = false;

			if (s == NULL) {
				pthread_mutex_unlock(&syncobj_lock);
				return -EINVAL;
			}
			syncobj_poll(s);
			for (unsigned k = 0; k < s->pending; k++) {
				if (s->on_the_way[k].point >= point) {
					on_the_way = true;
					if (!have_fence || (int32_t)(s->on_the_way[k].fence - wait_fence) < 0)
						wait_fence = s->on_the_way[k].fence;
					have_fence = true;
					break;
				}
			}
			if (s->reached >= point || (on_the_way && (flags & DRM_SYNCOBJ_WAIT_FLAGS_WAIT_AVAILABLE))) {
				reached++;
				if (!all) {
					if (first != NULL)
						*first = i;
					pthread_mutex_unlock(&syncobj_lock);
					return 0;
				}
			} else if (!on_the_way) {
				unknown++;
			}
		}
		if (reached == count) {
			if (first != NULL)
				*first = 0;
			pthread_mutex_unlock(&syncobj_lock);
			return 0;
		}
		if (unknown != 0 && !(flags & DRM_SYNCOBJ_WAIT_FLAGS_WAIT_FOR_SUBMIT)) {
			pthread_mutex_unlock(&syncobj_lock);
			return -EINVAL;
		}
		if (now_ns() >= deadline)
			break;
		if (have_fence && unknown == 0) {
			pthread_mutex_unlock(&syncobj_lock);
			fence_done(wait_fence, deadline);
			pthread_mutex_lock(&syncobj_lock);
		} else {
			/* a point not submitted yet: wait for a submit/signal, 1 ms steps (realtime cond clock) */
			struct timeval tv;
			struct timespec until;
			int64_t left = deadline - now_ns();
			int64_t real;

			gettimeofday(&tv, NULL);
			real = (int64_t)tv.tv_sec * 1000000000 + (int64_t)tv.tv_usec * 1000 + (left < 1000000 ? left : 1000000);
			until.tv_sec = real / 1000000000;
			until.tv_nsec = real % 1000000000;
			pthread_cond_timedwait(&syncobj_submitted, &syncobj_lock, &until);
		}
	}
	pthread_mutex_unlock(&syncobj_lock);
	return -ETIME;
}

int
drmSyncobjWait(int fd, uint32_t *handles, unsigned count, int64_t deadline, unsigned flags, uint32_t *first)
{
	return drmSyncobjTimelineWait(fd, handles, NULL, count, deadline, flags, first);
}

int
drmSyncobjTransfer(int fd, uint32_t dst, uint64_t dst_point, uint32_t src, uint64_t src_point, uint32_t flags)
{
	struct syncobj *d, *s;
	uint64_t want = src_point != 0 ? src_point : 1, to = dst_point != 0 ? dst_point : 1;

	(void)fd;
	(void)flags;
	pthread_mutex_lock(&syncobj_lock);
	d = syncobj_of(dst);
	s = syncobj_of(src);
	if (d == NULL || s == NULL) {
		pthread_mutex_unlock(&syncobj_lock);
		return -EINVAL;
	}
	syncobj_poll(s);
	if (dst_point == 0)
		d->reached = 0, d->pending = 0;
	if (s->reached >= want) {
		if (to > d->reached)
			d->reached = to;
	} else {
		for (unsigned k = 0; k < s->pending; k++) {
			if (s->on_the_way[k].point >= want) {
				syncobj_add(d, to, s->on_the_way[k].fence);
				break;
			}
		}
	}
	pthread_cond_broadcast(&syncobj_submitted);
	pthread_mutex_unlock(&syncobj_lock);
	return 0;
}

static uint32_t last_fence;

static int
submit_with_syncobjs(struct drm_msm_gem_submit *submit, unsigned long size)
{
	const struct drm_msm_syncobj *in = (const void *)(uintptr_t)submit->in_syncobjs;
	const struct drm_msm_syncobj *out = (const void *)(uintptr_t)submit->out_syncobjs;
	const uint32_t stride = submit->syncobj_stride ? submit->syncobj_stride : sizeof(*in);
	const uint32_t nin = (submit->flags & MSM_SUBMIT_SYNCOBJ_IN) ? submit->nr_in_syncobjs : 0;
	const uint32_t nout = (submit->flags & MSM_SUBMIT_SYNCOBJ_OUT) ? submit->nr_out_syncobjs : 0;
	int error;

	for (uint32_t i = 0; i < nin; i++) {
		const struct drm_msm_syncobj *x = (const void *)((const uint8_t *)in + i * stride);
		uint32_t h = x->handle;
		uint64_t p = x->point;
		int r = drmSyncobjTimelineWait(0, &h, &p, 1, now_ns() + 10000000000LL,
		                               DRM_SYNCOBJ_WAIT_FLAGS_WAIT_ALL | DRM_SYNCOBJ_WAIT_FLAGS_WAIT_FOR_SUBMIT, NULL);
		if (r != 0)
			return r;
		if (x->flags & MSM_SYNCOBJ_RESET)
			drmSyncobjReset(0, &h, 1);
	}
	submit->flags &= ~(uint32_t)(MSM_SUBMIT_SYNCOBJ_IN | MSM_SUBMIT_SYNCOBJ_OUT);
	submit->in_syncobjs = submit->out_syncobjs = 0;
	submit->nr_in_syncobjs = submit->nr_out_syncobjs = 0;
	if (submit->nr_cmds == 0) {
		/* nothing for the GPU: done when everything before it is (one ring) */
		submit->fence = __atomic_load_n(&last_fence, __ATOMIC_ACQUIRE);
	} else {
		struct drm_msm_gem_submit_bo *bos = (void *)(uintptr_t)submit->bos;
		if (owns != 0 && getenv("BLUEDRM_SYNC_ALL") == NULL)
			for (uint32_t i = 0; i < submit->nr_bos; i++)
				if (own_unmapped(bos[i].handle))
					bos[i].flags |= BLUE_GPU_SUBMIT_BO_NOSYNC;
		error = call((unsigned)(DRM_COMMAND_BASE + DRM_MSM_GEM_SUBMIT), submit, size);
		if (error != 0) {
			errno = error;
			return -error;
		}
		__atomic_store_n(&last_fence, submit->fence, __ATOMIC_RELEASE);
	}
	pthread_mutex_lock(&syncobj_lock);
	for (uint32_t i = 0; i < nout; i++) {
		const struct drm_msm_syncobj *x = (const void *)((const uint8_t *)out + i * stride);
		struct syncobj *s = syncobj_of(x->handle);
		if (s == NULL)
			continue;
		if (x->point == 0)
			s->reached = 0, s->pending = 0;
		syncobj_add(s, x->point != 0 ? x->point : 1, submit->fence);
	}
	pthread_cond_broadcast(&syncobj_submitted);
	pthread_mutex_unlock(&syncobj_lock);
	return 0;
}

int drmGetNodeTypeFromFd(int fd) { (void)fd; return DRM_NODE_RENDER; }
int drmGetDevices2(uint32_t flags, drmDevicePtr devices[], int max) { (void)flags; (void)devices; (void)max; return 0; }
void drmFreeDevices(drmDevicePtr devices[], int count) { (void)devices; (void)count; }
int drmGetDevice2(int fd, uint32_t flags, drmDevicePtr *device) { (void)fd; (void)flags; *device = NULL; return -ENODEV; }
void drmFreeDevice(drmDevicePtr *device) { (void)device; }
