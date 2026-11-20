#include <assert.h>
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <IOKit/IOKitLib.h>
#include "blue_gpu_uapi.h"
#define BLUEGPU_SERVICE BLUE_GPU_SERVICE
static unsigned mode, closed, released;
CFMutableDictionaryRef IOServiceMatching(const char *name) {return (void *)name;}
io_service_t IOServiceGetMatchingService(mach_port_t port, CFDictionaryRef name) {
    (void)port;
    assert(!strcmp(name, "LemonGPU"));
    return mode == 0 ? 0 : 1;
}
kern_return_t IOServiceOpen(io_service_t service, task_port_t task, uint32_t type, io_connect_t *connection) {
    assert(service && task && type == 0);
    *connection = 2;
    return mode == 1 ? kIOReturnUnsupported : KERN_SUCCESS;
}
kern_return_t IOObjectRelease(io_object_t object) {assert(object == 1);released++;return 0;}
kern_return_t IOServiceClose(io_connect_t connection) {assert(connection == 2);closed++;return 0;}
IOReturn IOConnectCallStructMethod(mach_port_t connection, uint32_t selector,
    const void *in, size_t in_size, void *out, size_t *out_size) {
    assert(connection == 2 && selector == BLUE_GPU_SEL_GET_PARAM && in == out);
    assert(in_size == sizeof(struct blue_gpu_param) && *out_size == in_size);
    struct blue_gpu_param *p = out;
    if (p->param == BLUE_GPU_PARAM_GPU_ID) p->value = mode == 2 ? 630 : LEMON_GPU_ID;
    else if (p->param == BLUE_GPU_PARAM_CHIP_ID) p->value = mode == 3 ? 0x06030001 : LEMON_GPU_CHIP_ID;
    else {assert(p->param == BLUE_GPU_PARAM_GMEM_SIZE);p->value = mode == 4 ? 0x100000 : LEMON_GPU_GMEM_SIZE;}
    if (mode == 5) *out_size = 0;
    return mode == 6 ? kIOReturnUnsupported : KERN_SUCCESS;
}
/* GPU_GATE */

static long page_size;
static long fake_sysconf(int name) {assert(name == _SC_PAGESIZE);return page_size;}
#define sysconf fake_sysconf
static uint64_t allocation_size(uint64_t requested) {
    struct {uint64_t size;} value = {requested}, *r = &value;
/* ALLOCATION */
    return size;
}
int main(void) {
    for (mode = 0; mode < 8; mode++) {
        closed = released = 0;
        assert(gpu_present() == (mode == 7));
        assert(released == (mode != 0));
        assert(closed == (mode > 1));
    }
    page_size = 4096;
    assert(allocation_size(1) == 4096 && allocation_size(4096) == 4096 && allocation_size(4097) == 8192);
    assert(allocation_size(0) == EINVAL && allocation_size(UINT64_MAX) == EINVAL);
    page_size = 16384;
    assert(allocation_size(4097) == 16384 && allocation_size(16385) == 32768);
    page_size = 0;assert(allocation_size(1) == EINVAL);
    page_size = 3000;assert(allocation_size(1) == EINVAL);
    puts("PASS: real EAGL gate rejects wrong GPU/chip/GMEM, bad sizes and missing service; real BO rounding handles 4K/16K and overflow");
}
