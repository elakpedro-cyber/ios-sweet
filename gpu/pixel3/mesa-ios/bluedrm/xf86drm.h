/*
 * xf86drm.h for Darwin (pixel3-ios): what Mesa's freedreno takes from libdrm, implemented by
 * bluedrm.c over the BlueGPU IOKit user client (blue_gpu_uapi.h).
 *
 * Derived from HakiOS tools/mesa/hakios-drm/xf86drm.h
 *   Copyright (c) 2025-2026 the HakiOS authors, MIT License (see ../LICENSES/HakiOS-MIT.txt)
 * Changes for pixel3-ios: service name, mmap by GEM_INFO offset token, bluedrm_* names.
 */
#ifndef BLUEDRM_XF86DRM_H
#define BLUEDRM_XF86DRM_H

#include <fcntl.h>
#include <stddef.h>
#include <stdint.h>
#include <sys/types.h>

#include "drm-uapi/drm.h"

#ifdef __cplusplus
extern "C" {
#endif

#define DRM_NODE_PRIMARY        0
#define DRM_NODE_CONTROL        1
#define DRM_NODE_RENDER         2
#define DRM_NODE_MAX            3
#define DRM_CLOEXEC             O_CLOEXEC
#define DRM_RDWR                O_RDWR

typedef struct _drmVersion {
	int version_major, version_minor, version_patchlevel;
	int name_len;
	char *name;
	int date_len;
	char *date;
	int desc_len;
	char *desc;
} drmVersion, *drmVersionPtr;

int drmOpenWithType(const char *name, const char *busid, int type);
int drmIoctl(int fd, unsigned long request, void *arg);
int drmCommandWrite(int fd, unsigned long index, void *data, unsigned long size);
int drmCommandWriteRead(int fd, unsigned long index, void *data, unsigned long size);
drmVersionPtr drmGetVersion(int fd);
void drmFreeVersion(drmVersionPtr version);
int drmGetCap(int fd, uint64_t capability, uint64_t *value);

/* "dma-buf fds" are IOSurface IDs here (see bluedrm_import_size); no fds for BOs or fences out. */
int drmPrimeHandleToFD(int fd, uint32_t handle, uint32_t flags, int *prime_fd);
int drmPrimeFDToHandle(int fd, int prime_fd, uint32_t *handle);

/* syncobjs emulated in-process over kernel fences (Turnip needs them; gallium does not) */
int drmSyncobjCreate(int fd, uint32_t flags, uint32_t *handle);
int drmSyncobjDestroy(int fd, uint32_t handle);
int drmSyncobjReset(int fd, const uint32_t *handles, uint32_t count);
int drmSyncobjSignal(int fd, const uint32_t *handles, uint32_t count);
int drmSyncobjTimelineSignal(int fd, const uint32_t *handles, uint64_t *points, uint32_t count);
int drmSyncobjWait(int fd, uint32_t *handles, unsigned count, int64_t timeout_nsec, unsigned flags,
                   uint32_t *first_signaled);
int drmSyncobjTimelineWait(int fd, uint32_t *handles, uint64_t *points, unsigned count,
                           int64_t timeout_nsec, unsigned flags, uint32_t *first_signaled);
int drmSyncobjQuery(int fd, uint32_t *handles, uint64_t *points, uint32_t count);
int drmSyncobjQuery2(int fd, uint32_t *handles, uint64_t *points, uint32_t count, uint32_t flags);
int drmSyncobjTransfer(int fd, uint32_t dst_handle, uint64_t dst_point, uint32_t src_handle,
                       uint64_t src_point, uint32_t flags);
int drmSyncobjFDToHandle(int fd, int obj_fd, uint32_t *handle);
int drmSyncobjHandleToFD(int fd, uint32_t handle, int *obj_fd);
int drmSyncobjImportSyncFile(int fd, uint32_t handle, int sync_file_fd);
int drmSyncobjExportSyncFile(int fd, uint32_t handle, int *sync_file_fd);
int drmGetNodeTypeFromFd(int fd);

#define DRM_BUS_PCI             0
#define DRM_BUS_USB             1
#define DRM_BUS_PLATFORM        2
#define DRM_BUS_HOST1X          3
typedef struct _drmDevice {
	char **nodes;
	int available_nodes;
	int bustype;
	union { void *pci, *usb, *platform, *host1x; } businfo;
	union { void *pci, *usb, *platform, *host1x; } deviceinfo;
} drmDevice, *drmDevicePtr;
int drmGetDevices2(uint32_t flags, drmDevicePtr devices[], int max_devices);
void drmFreeDevices(drmDevicePtr devices[], int count);
int drmGetDevice2(int fd, uint32_t flags, drmDevicePtr *device);
void drmFreeDevice(drmDevicePtr *device);

/* ---- not libdrm: called from the patched freedreno_bo.c ---- */
/* mmap replacement: maps memory type (uint32_t)offset of the user client; MAP_FAILED on error */
void *bluedrm_map(int fd, uint32_t handle, uint64_t offset, uint64_t size);
void bluedrm_unmap(int fd, uint32_t handle, void *address, uint64_t size);
/* size of the BO an IOSurface ID would import as (0 on error) */
uint64_t bluedrm_import_size(int fd, int surface_id);

/* ---- not libdrm: for the frontend / EAGL shim ---- */
struct blue_gpu_iosurface;
int bluedrm_iosurface_describe(int fd, struct blue_gpu_iosurface *s);  /* 0 or -1 + errno */
int bluedrm_user_memory(int fd, const void *address, uint64_t size, uint32_t *handle);

#ifdef __cplusplus
}
#endif

#endif
