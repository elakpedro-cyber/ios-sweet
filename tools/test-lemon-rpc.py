#!/usr/bin/env python3
"""Exercise real RPC entry functions against the actual modern iig dispatcher.

IOKit objects, Mach parsing and TLS are mocked; this is not an iOS boot test.
"""
import argparse
from pathlib import Path
import subprocess
import tempfile

ap = argparse.ArgumentParser()
ap.add_argument('--xnu', type=Path, required=True)
ap.add_argument('--generated', type=Path, required=True, help='generated OSObject.iig.cpp')
args = ap.parse_args()
server = (args.xnu / 'iokit/Kernel/IOUserServer.cpp').read_text()
header = (args.xnu / 'iokit/IOKit/IORPC.h').read_text()
generated = args.generated.read_text()

def function(source, signature):
    start = source.index(signature)
    return source[start:source.index('\n}\n', start) + 3]

start = header.index('struct IORPC {')
rpc_struct = header[start:header.index('\n};', start) + 3]
incoming = next(line.strip() for line in server.splitlines() if 'IORPC rpc = { .message = msgin' in line)
start = server.index('\trpc.message   = mach;')
trap = server[start:server.index('\n\n', start)]
source = r'''
#include <cassert>
#include <cstddef>
#include <cstdint>
#include <cstring>
#define KERNEL 1
using kern_return_t = int;
using IOReturn = int;
constexpr int kIOReturnUnsupported=-1, kIOReturnIPCError=-2, kIOReturnSuccess=0;
constexpr uint64_t kIORPCMessageKernel=1, kIORPCMessageLocalHost=2, kIORPCMessageRemote=4;
constexpr uint64_t OSObject_Instantiate_ID=0x100;
constexpr int kIODKLogIPC=1, gIODKDebug=0;
#define DKLOG(...) ((void)0)
#define OSDynamicCast(type, object) dynamic_cast<type *>(object)
struct IORPCMessage { uint64_t msgid, flags; };
struct IORPCMessageMach { struct { uint32_t msgh_size; } msgh; IORPCMessage *payload; };
''' + rpc_struct + r'''
static_assert(offsetof(IORPC, kernelContent)==24 && sizeof(IORPC)==32);
static_assert(offsetof(IORPC, sendSize)==16 && offsetof(IORPC, replySize)==20);
static IORPCMessage *seen;
static IORPCMessage *IORPCMessageFromMach(IORPCMessageMach *msg, bool) {
    return msg ? msg->payload : nullptr;
}
static void *tls=reinterpret_cast<void *>(0x1234);
static void *thread_iokit_tls_get(int) { return tls; }
static void thread_iokit_tls_set(int, void *value) { tls=value; }
struct Meta { const char *getClassName() const { return "Test"; } };
class OSMetaClassBase {
public:
    virtual ~OSMetaClassBase()=default;
    virtual int Dispatch(IORPC) { return kIOReturnUnsupported; }
    int Invoke(IORPC);
    Meta *getMetaClass() { static Meta meta; return &meta; }
};
class OSObject : public OSMetaClassBase {
public:
    int Dispatch(const IORPC rpc) override;
    static int _Dispatch(OSObject *, const IORPC);
};
class IOUserServer;
struct Vars { IOUserServer *userServer=nullptr; };
class OSAction : public OSObject { public: Vars *ivars=nullptr; };
class IOEventLink : public OSObject { public: Vars *ivars=nullptr; };
class IOWorkGroup : public OSObject { public: Vars *ivars=nullptr; };
class IOService : public OSObject {
public:
    struct Reserved { Vars *uvars; } *reserved=nullptr;
};
class IOUserServer : public OSObject {
public:
    int kernelDispatch(OSObject *, IORPC);
    int rpc(IORPC rpc) { seen=rpc.kernelContent; return 7; }
    int objectInstantiate(OSObject *, IORPC rpc, IORPCMessage *) {
        seen=rpc.kernelContent; return 11;
    }
    static OSObject *target(OSAction *action, IORPCMessage *) { return action; }
};
'''
for signature in ['OSObject::Dispatch(const IORPC rpc)',
                  'OSObject::_Dispatch(OSObject * self, const IORPC rpc)']:
    source += '\nkern_return_t\n' + function(generated, signature)
for signature in ['OSMetaClassBase::Invoke(IORPC rpc)',
                  'IOUserServer::kernelDispatch(OSObject * obj, IORPC rpc)']:
    source += '\nkern_return_t\n' + function(server, signature)
source += r'''
int main() {
    IORPCMessage payload{0x777, kIORPCMessageLocalHost};
    IORPCMessageMach mach{{128}, &payload}, reply{{128}, nullptr};
    OSObject object;
    IOUserServer userServer;
    IORPC call{&mach, &reply, 128, 128, nullptr};
    assert(object.Invoke(call)==kIOReturnUnsupported);
    assert(tls==reinterpret_cast<void *>(0x1234));
    assert(payload.flags & kIORPCMessageKernel);
    call.kernelContent=reinterpret_cast<IORPCMessage *>(1);
    assert(object.Invoke(call)==kIOReturnUnsupported);
    assert(userServer.kernelDispatch(&object, call)==kIOReturnUnsupported);
    payload.msgid=OSObject_Instantiate_ID;
    assert(userServer.kernelDispatch(&object, call)==11 && seen==&payload);
    payload.msgid=0x777;
    payload.flags=0;
    assert(userServer.Invoke(call)==7 && seen==&payload);
    assert(payload.flags & kIORPCMessageRemote);
    mach.payload=nullptr;
    assert(object.Invoke(call)==kIOReturnIPCError);
    assert(userServer.kernelDispatch(&object, call)==kIOReturnIPCError);
    mach.payload=&payload;
    {
        auto *msgin=&mach;
        auto *msgout=&reply;
        auto *message=&payload;
        uint32_t replyAlloc=128;
''' + incoming + r'''
        assert(object.Dispatch(rpc)==kIOReturnUnsupported);
    }
    {
        IORPC rpc;
        std::memset(&rpc, 0xa5, sizeof(rpc));
        struct { char buffer[256]; } buffer{};
        uintptr_t p=reinterpret_cast<uintptr_t>(&buffer);
        uint32_t inSize=64;
        auto *message=&payload;
        auto *machPtr=&mach;
        // Keep names matching the actual trap's setup statements.
        auto *mach=machPtr;
''' + trap + r'''
        assert(object.Dispatch(rpc)==kIOReturnUnsupported);
        assert(rpc.kernelContent==message);
    }
}
'''
with tempfile.TemporaryDirectory() as directory:
    path = Path(directory)
    (path / 'rpc.cpp').write_text(source)
    subprocess.run(['c++', '-std=c++17', '-g', '-fsanitize=address,undefined',
                    '-fno-sanitize-recover=all', '-fno-omit-frame-pointer', str(path / 'rpc.cpp'),
                    '-o', str(path / 'rpc')], check=True)
    subprocess.run([str(path / 'rpc')], check=True)
print('RPC: Invoke, kernelDispatch, incoming IPC, trap, remote forwarding and invalid input PASS')
