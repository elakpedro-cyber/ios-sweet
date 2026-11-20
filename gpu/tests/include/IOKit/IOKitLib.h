#ifndef LEMON_TEST_IOKIT_H
#define LEMON_TEST_IOKIT_H
#include <stddef.h>
#include <stdint.h>
/* Host-only ABI stand-ins. These values are not Darwin error numbers. */
typedef uint32_t mach_port_t, task_port_t, io_object_t, io_service_t, io_connect_t, IOOptionBits;
typedef uint64_t mach_vm_address_t, mach_vm_size_t;
typedef int kern_return_t;
typedef int IOReturn;
typedef const void *CFDictionaryRef;
typedef void *CFMutableDictionaryRef;
enum { KERN_SUCCESS, kIOReturnBadArgument, kIOReturnNoMemory, kIOReturnNotFound,
       kIOReturnUnsupported, kIOReturnNotPrivileged, kIOReturnBusy, kIOReturnTimeout };
#define kIOReturnSuccess KERN_SUCCESS
#define kIOMainPortDefault 0
#define kIOMapAnywhere 1
static inline mach_port_t mach_task_self(void) { return 1; }
CFMutableDictionaryRef IOServiceMatching(const char *);
io_service_t IOServiceGetMatchingService(mach_port_t, CFDictionaryRef);
kern_return_t IOObjectRelease(io_object_t);
kern_return_t IOServiceOpen(io_service_t, task_port_t, uint32_t, io_connect_t *);
kern_return_t IOServiceClose(io_connect_t);
IOReturn IOConnectCallStructMethod(mach_port_t, uint32_t, const void *, size_t, void *, size_t *);
kern_return_t IOConnectMapMemory64(io_connect_t, uint32_t, task_port_t, mach_vm_address_t *, mach_vm_size_t *, IOOptionBits);
kern_return_t IOConnectUnmapMemory64(io_connect_t, uint32_t, task_port_t, mach_vm_address_t);
#endif
