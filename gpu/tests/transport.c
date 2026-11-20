#include <assert.h>
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include "xf86drm.h"
#include "drm-uapi/msm_drm.h"
#include "blue_gpu_uapi.h"

int main(void) {
    int fd = drmOpenWithType("msm", NULL, DRM_NODE_RENDER);
    assert(fd >= 0);
    drmVersionPtr version = drmGetVersion(fd);
    assert(version && !strcmp(version->name, "msm") && version->version_minor == 9);
    drmFreeVersion(version);
    const unsigned ids[] = {MSM_PARAM_GPU_ID, MSM_PARAM_CHIP_ID, MSM_PARAM_GMEM_SIZE, MSM_PARAM_HIGHEST_BANK_BIT};
    const uint64_t values[] = {610, 0x06010000, 0x21000, 14};
    for (unsigned i = 0; i < 4; i++) {
        struct drm_msm_param param = {.pipe = MSM_PIPE_3D0, .param = ids[i]};
        assert(!drmCommandWriteRead(fd, DRM_MSM_GET_PARAM, &param, sizeof(param)));
        assert(param.value == values[i]);
    }
    struct drm_msm_gem_new bo = {.size = 4096, .flags = MSM_BO_WC};
    assert(!drmCommandWriteRead(fd, DRM_MSM_GEM_NEW, &bo, sizeof(bo)) && bo.handle);
    struct drm_msm_gem_info info = {.handle = bo.handle, .info = MSM_INFO_GET_OFFSET};
    assert(!drmCommandWriteRead(fd, DRM_MSM_GEM_INFO, &info, sizeof(info)));
    void *memory = bluedrm_map(fd, bo.handle, info.value, 4096);
    assert(memory && memory != (void *)-1);
    memset(memory, 0, 4096);
    struct drm_msm_gem_submit_bo submit_bo = {.flags = MSM_SUBMIT_BO_READ, .handle = bo.handle};
    struct drm_msm_gem_submit_cmd cmd = {.type = MSM_SUBMIT_CMD_BUF, .submit_idx = 0, .size = 4};
    struct drm_msm_gem_submit submit = {.flags = MSM_PIPE_3D0, .nr_bos = 1, .nr_cmds = 1,
        .bos = (uintptr_t)&submit_bo, .cmds = (uintptr_t)&cmd};
    assert(!drmCommandWriteRead(fd, DRM_MSM_GEM_SUBMIT, &submit, sizeof(submit)) && submit.fence);
    struct drm_msm_wait_fence fence = {.fence = submit.fence};
    assert(!drmCommandWrite(fd, DRM_MSM_WAIT_FENCE, &fence, sizeof(fence)));
    fence.fence++;
    assert(drmCommandWrite(fd, DRM_MSM_WAIT_FENCE, &fence, sizeof(fence)) == -EINVAL);
    struct drm_msm_gem_cpu_prep prep = {.handle = bo.handle, .op = MSM_PREP_READ};
    assert(!drmCommandWrite(fd, DRM_MSM_GEM_CPU_PREP, &prep, sizeof(prep)));
    bluedrm_unmap(fd, bo.handle, memory, 4096);
    struct drm_gem_close close_bo = {.handle = bo.handle};
    assert(!drmIoctl(fd, DRM_IOCTL_GEM_CLOSE, &close_bo));
    info.info = MSM_INFO_GET_IOVA;
    assert(drmCommandWriteRead(fd, DRM_MSM_GEM_INFO, &info, sizeof(info)) == -ENOENT);
    close(fd);
    puts("PASS: actual bluedrm -> fake IOKit ABI, A610 identity, BO map, submit/fences, prep/close and stale handle rejection");
    puts("No GPU execution or pixel rendering was tested");
}
