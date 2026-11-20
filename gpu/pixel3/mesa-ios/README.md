# mesa-ios: Mesa freedreno GLES for the Pixel 3 iOS port (stage 6e)

Mesa 26.3.1's gallium freedreno driver (Adreno 630, a6xx), its compiler (ir3/NIR/GLSL) and the GL state
tracker, built for iOS 16 arm64 as **one dylib, `bluegl.dylib`**. A small libdrm stand-in (`bluedrm/`)
turns Mesa's msm ioctls into calls on the kernel's `BlueGPU` IOKit user client. Userland only: nothing
here talks to the phone, and `ref/mesa` is not touched (the build uses a pinned tarball).

```sh
./build-mesa-ios.sh                       # incremental (seconds after a frontend/bluedrm edit)
CLEAN=1 PAD=67108864 ./build-mesa-ios.sh  # from scratch: about 70 s on this Mac (M-series, 10 cores)
HOST=1 ./build-mesa-ios.sh                # also build for macOS over fake/ and run the test there
```

Needs Xcode 15.4 (`DEVELOPER_DIR`, defaults to `/Applications/Xcode-15.4.0.app`; iPhoneOS 17.5 SDK, minos
16.0), Homebrew `python3` (3.10 or newer), `bison`, `flex` and `curl`. The script creates `venv/`
(meson 1.6.1, ninja, mako, pyyaml, packaging) and downloads `dl/mesa-26.3.1.tar.xz` (sha256 pinned).

## Outputs (`out/`)

| File | Size | What |
|---|---|---|
| `bluegl.dylib` | 18,107,584 B | stripped, ad-hoc signed, install name `/usr/lib/bluegl.dylib`, minos 16.0. `__TEXT` 16.6 MB |
| `bluegl-unstripped.dylib` | 19,181,744 B | the same with local symbols (for crash logs) |
| `bluegl-padded.dylib` | 64 MiB | `PAD=`: zero-padded to a fixed size for in-place pushes (below) |
| `gles-triangle` | 70 KB | test binary, links `/usr/lib/bluegl.dylib` |
| `exports.txt`, `sizes.txt` | | 1310 exported `gl*` entry points + `bluegl_*`; size report |
| `host/` | | `HOST=1`: macOS build linked with the fake GPU, and `gles-triangle.log` |

The dylib imports 209 symbols, all from libSystem, libc++, IOKit and libz. The script fails if there is any
weak import other than C++ `operator new/delete` and `pthread_mutexattr_*` (Mesa's `#pragma weak`), or if
minos is not 16.0. This catches the problem flame hit with `strchrnul`: a weak import iOS 16 lacks binds to
NULL. `kIOMainPortDefault` needs iOS 15 or later, which is fine for 16.7.16.

## What is in it

```
dl/                     pinned tarball
src/mesa-26.3.1/        pristine extract, only for regenerating patches (deletable, 413 MB; re-extract with tar)
build/mesa-26.3.1/      patched tree (+ src/bluedrm copied in); build/out-ios, build/out-macos: meson dirs
patches/                0001-0004 below, applied with patch -p1 to a fresh extract
bluedrm/                libdrm stand-in: xf86drm.h + bluedrm.c (HakiOS port, MIT)
blue_gpu_uapi.h         the user-client ABI (shared with the kernel, 6d)
frontend/bluegl.[ch]    tiny surfaceless GL frontend (Mesa 25.1 removed OSMesa)
test/gles-triangle.c    offscreen GLES 3.0 triangle, readback, checksum
fake/fake_bluegpu.c     macOS-only in-process BlueGPU model: ABI test + reference for 6d
tools/                  edit.py (exact replacements), mesa-cflags.py (flags from compile_commands.json)
LICENSES/               HakiOS MIT licence
```

Mesa options: static libraries, `-Dgallium-drivers=freedreno -Dfreedreno-kmds=msm -Dvulkan-drivers=
-Dplatforms= -Degl/glx/gbm=disabled -Dllvm=disabled -Dgles1=disabled -Dgles2=enabled -Dopengl=true
-Dshader-cache=disabled -Dzstd/zlib/expat/xmlconfig=disabled`, release with NDEBUG. 25 static libraries
are linked with `-dead_strip` against an exports list. The list holds exactly the public `_gl[A-Z]*`
functions of `libglapi_bridge.a` plus `_bluegl_*`. A `_gl*` wildcard would also have caught hidden
`gl_`/`glsl_` internals.

### Patches

| Patch | Why |
|---|---|
| 0001 darwin-libdrm-standin-meson | On Darwin with freedreno, `dep_libdrm` becomes `src/bluedrm` + IOKit. Build `src/freedreno/drm` and compile `bluedrm.c` into it. Skip `u_sync_provider.c` (it needs real libdrm headers) |
| 0002 darwin-freedreno-bo-map-import-clock | `fd_bo` mmap/munmap go through `bluedrm_map`/`bluedrm_unmap` (IOConnectMapMemory64, with the token from `GEM_INFO(GET_OFFSET)`). IOSurface import size comes from the kernel (no `lseek` on a dma-buf fd). Absolute timeouts use `CLOCK_MONOTONIC_RAW` (= `mach_continuous_time`, the kernel's clock) |
| 0003 darwin-freedreno-dbg-tid | `DBG()` called `syscall(SYS_gettid)`. Darwin's 286 is a different call with out-pointers, so with `FD_MESA_DEBUG=msgs` it would write through garbage. Use the mach thread port instead |
| 0004 fd6-fbfetch-first-draw-barrier-hakios | HakiOS's fix ported to 26.3.1: before the first framebuffer-fetch draw after non-fetch draws, flush CCU colour and invalidate. CA's GL renderer needs it |

HakiOS's other Mesa changes are not needed on 26.3.1. Its Mach-O build-id for the disk cache is now
upstream (LC_UUID), freedreno no longer uses `sysinfo()`, and its OSMesa changes do not apply because
OSMesa is gone. Its IOSurface-as-EGLImage hook lives in `frontend/bluegl.c` instead.

### Frontend API (`frontend/bluegl.h`)

`bluegl_init()` opens BlueGPU and creates the screen: `fd_drm_screen_create_renderonly` with a driconf
cache built from `driinfo_gallium.h` + `driinfo_freedreno.h`. `bluegl_create_context(major, minor,
share)` creates a GLES context (2.0-3.2). `bluegl_make_current(ctx)` binds it surfaceless, so the default
framebuffer is incomplete and you render into FBOs. Also `bluegl_destroy_context`,
`bluegl_get_proc_address` and `bluegl_iosurface_importable(id)`. `glEGLImageTarget{Texture2D,
RenderbufferStorage}OES` accept `(GLeglImageOES)(uintptr_t)IOSurfaceID`. The frontend's `get_egl_image`
imports the surface by ID through `resource_from_handle` when the surface is BGRA, single-plane and has a
row pitch that is a multiple of 64. This is the hook the EAGL shim (6f) builds on.

## The user-client ABI (`blue_gpu_uapi.h`)

- **Service and versions:** service `BlueGPU`, user-client type 0. `drmGetVersion` reports msm 1.9 to Mesa (softpin).
- **Transport:** every call is `IOConnectCallStructMethod(selector, &s, sizeof s, &s, &size)`. The struct goes in and comes back.
- **Selectors:** the selector is the Linux ioctl's low byte (HackiOS numbering):

  | Selector | Call |
  |---|---|
  | 0x09 | GEM_CLOSE |
  | 0x40 | GET_PARAM |
  | 0x41 | SET_PARAM |
  | 0x42 | GEM_NEW |
  | 0x43 | GEM_INFO |
  | 0x44 | CPU_PREP |
  | 0x45 | CPU_FINI |
  | 0x46 | GEM_SUBMIT |
  | 0x47 | WAIT_FENCE |
  | 0x48 | MADVISE |
  | 0x4a / 0x4b / 0x4c | SUBMITQUEUE_NEW / CLOSE / QUERY |
  | 0x7d | USERPTR (non-Linux) |
  | 0x7e | IOSURFACE describe/import (non-Linux) |

- **Structs:** `blue_gpu_*` clones of `msm_drm.h`. `bluedrm.c` checks every size and offset against Mesa's copy with `_Static_assert`. Sizes:

  | Struct | Bytes |
  |---|---|
  | param | 24 |
  | gem_new | 16 |
  | gem_info | 24 |
  | cpu_prep | 24 |
  | submit_bo | 16 |
  | submit_cmd | 32 |
  | submit | 72 |
  | wait_fence | 32 |
  | madvise | 12 |
  | submitqueue | 12 |
  | iosurface | 40 |

- **Params** the kernel must answer:

  | Param | Value |
  |---|---|
  | GPU_ID | 630 |
  | CHIP_ID | 0x06030001 |
  | GMEM_SIZE | 1 MiB |
  | GMEM_BASE | 0x100000 |
  | MAX_FREQ | 710 MHz |
  | TIMESTAMP | CP always-on counter, 19.2 MHz |
  | PRIORITIES | 1 |
  | VA_START | 0x80000000 (kernel 0153, tested) |
  | VA_SIZE | 0x80000000 for every client (one shared VA space; pool at 0x80000000, imports at 0xc0000000) |
  | HIGHEST_BANK_BIT | 15 |

  FAULTS and SUSPENDS are counters. UBWC_SWIZZLE and UCHE_TRAP_BASE return EINVAL, which Mesa handles.
- **Mapping:** `mmap` becomes `IOConnectMapMemory64(memoryType = (uint32_t)GEM_INFO(GET_OFFSET))`.
- **Flags and errors:**
  - BO flags: WC only. CACHED and CACHED_COHERENT return EINVAL; Mesa probes CACHED_COHERENT and falls back.
  - Submit flags: fence-fd and SUDO flags return EINVAL. bluedrm emulates syncobjs in userland.
  - IOReturn codes map to errno. kIOReturnBusy means the ring is full and the call retries.
- **Kernel duties on submit:** invalidate CCU before, issue one CP_INDIRECT_BUFFER per cmd, end with a CACHE_FLUSH_TS fence.

## Test

On the phone: `gles-triangle` prints the GL strings, compile and draw times, the pixel count and an FNV-1a
checksum, then `GLES-TRIANGLE: PASS` (exit 0) or `FAIL`. Expected output: `GL_RENDERER FD630`, 32,640 red
pixels plus the diagonal band, and `glGetError 0x0`. These environment variables help:

- `BLUEDRM_DEBUG=1` traces every user-client call.
- `FD_MESA_DEBUG=noubwc` is needed until hw_init programs UBWC (a6xx turns UBWC on for RGBA8 renderbuffers by default).
- `FD_MESA_DEBUG=sysmem` skips GMEM binning, the simpler first path.
- `FD_MESA_DEBUG=msgs` gives verbose freedreno output.

On the Mac, `HOST=1` builds the same sources for macOS and links them with `fake/fake_bluegpu.c`, an
in-process model of the user client. Each call is checked against the uapi:

- struct sizes and in==out buffers
- known handles and flags
- cmds inside their BOs
- every PM4 type4/type7 header's parity
- nested IB / CP_SET_DRAW_STATE addresses resolving to a BO

Nothing executes, so the pixels stay 0. Result (2026-11-19):

```
bluegpu-fake: calls 113, BOs 22 (peak 13888 KiB), maps 21, submits 1, IBs 31, packets 202,
              draw-state groups 30, errors 0
GL_RENDERER FD630 / OpenGL ES 3.2 Mesa 26.3.1 / GLSL ES 3.20; compile+link 2.8 ms
```

So the screen is created, the ir3 compiler runs, and the command stream Mesa builds goes through bluedrm
with a well-formed ABI. The fake also shows what 6d has to implement (the WAIT_FENCE, CPU_PREP and
GEM_CLOSE semantics), minus the hardware.

## Problems hit and their fixes

| Problem | Fix |
|---|---|
| `ref/mesa` holds only 17 files of 26.3.1 | Use the full release tarball, sha-pinned; it matches ref's files |
| MacPorts meson 1.2.3; Mesa needs >= 1.5.0 | `venv/` with meson 1.6.1 |
| isaspec generators fail with "No module named mako" (their `env python3` found pyenv 3.8) | The venv goes first on `PATH` in the script |
| `u_sync_provider.c` redefinitions (dep_libdrm found, but no `HAVE_LIBDRM` headers) | Skip it on Darwin (0001); sync providers are not used |
| Link: undefined `gz*` from `freedreno_rd_output` | `-lz` (system libz on iOS) |
| `_gl*` export wildcard exported hidden `gl_`/`glsl_` internals (ld warnings) | Exact exports list from `libglapi_bridge.a` |
| `driParseConfigFiles` changed to 3 arguments in 26.x | `driConfigFileParseParams { .driverName = "msm" }` |
| OSMesa removed in Mesa 25.1 (HakiOS used it) | Own frontend over `st_api_create_context` / `st_api_make_current(NULL, NULL)` |
| `syscall(SYS_gettid)` in freedreno `DBG()` is a different syscall on Darwin | 0003 |
| Linux `mmap` on the DRM fd / `lseek` for dma-buf size | 0002 + `bluedrm_map`, `bluedrm_import_size` |
| `CLOCK_MONOTONIC` timeouts vs the kernel's continuous time | `CLOCK_MONOTONIC_RAW` (0002, and `now_ns` in bluedrm) |
| Our own edit helper left a blank line inside a multi-line macro ("expected 'while'" in a clean rebuild) | Fixed `tools/edit.py`; patches regenerated, clean rebuild passes |
| Unused `-framework CoreFoundation` warning | Dropped from the final link |

Not done: `-Dopengl=false` (GLES only) might cut `__TEXT` by about 1-2 MB. It is untested because CA does
not need desktop GL.

## Getting it onto the phone (described here, not done)

**Signing.** The kernel (ios-sweet 0015/0025/0035/0036 in `work/kbuild/dxb`) has no trust caches; they are
unavailable without Image4. Its built-in AMFI policy marks **every validly signed binary on the root
filesystem as a platform binary** and sets CS_SIGNED, so library validation between platform binaries
passes. Code-signature and page-hash checks stay in the kernel, so an **unsigned** dylib would be refused
or killed at page-in. **An ad-hoc signature (`codesign -s -`) is enough**, and the script applies it. No
trust-cache entry is needed, and nothing new is needed in the kernel. Sign **before** padding.
`bluegl-padded.dylib` carries zeros after `__LINKEDIT`. `codesign -v --strict` complains about the trailing
data, but dyld loads it: the padded macOS build loaded and ran `gles-triangle` on the Mac. The kernel only
hashes pages up to the code limit. Sailfish ships its pushes this way.

**Loading into a process.** `dxb` already has `sweetenv=NAME:VAR=VAL` (0203, from sailfish 0104), which adds
environment variables at exec for one executable. It also has the AMFI dyld policy (0205, from sailfish
0139), which answers dyld's `amfi_check_dyld_policy_self` with 0x7b, so `DYLD_INSERT_LIBRARIES` is
honoured, including in platform binaries. The stage-6 plan's `blueenv` is therefore already there under
the name `sweetenv`: `sweetenv=backboardd:DYLD_INSERT_LIBRARIES=/usr/lib/bluegl.dylib`. The Sandbox
stand-in (0050) allows all operations, so `IOServiceOpen("BlueGPU")` from backboardd is not blocked.
**Licence flag:** 0203 and 0205 come from sailfish, which has no licence. The rule here is "reference only,
don't copy code", so check whether these two need rewriting before anything is published. For the test
binary none of this is needed: `gles-triangle` links `/usr/lib/bluegl.dylib` directly.

**Putting the files on the root.** Today's flow, from LineageOS recovery with ADB, as in `docs/LOG.md` §Tools
and `tools/tweak-diff.sh`:

```sh
fastboot reboot recovery                          # Advanced -> Enable ADB
tools/phone.sh sync work/ios-root.img             # base == phone (iOS writes with rootrw=1)
cp -c work/ios-root.img work/ios-root-new.img
sudo tools/rootimg.sh mount work/ios-root-new.img
sudo install -m 755 -o root -g wheel mesa-ios/out/bluegl-padded.dylib work/root/usr/lib/bluegl.dylib
sudo install -d work/root/var/local/bin
sudo install -m 755 -o root -g wheel mesa-ios/out/gles-triangle work/root/var/local/bin/gputest
sudo tools/rootimg.sh umount
tools/simgdiff.py work/ios-root.img work/ios-root-new.img work/diff.simg   # about 64 + 0.1 MiB of blocks
adb reboot bootloader && fastboot flash userdata work/diff.simg
mv work/ios-root-new.img work/ios-root.img
```

Never touch `persist`, `modem` or EFS. Only `userdata` (the iOS root) is flashed. After this first flash,
the plan's 2.0 `phonetest.sh --push` can rewrite the 64 MiB file in place with `adb dd` into its existing
extents. The fixed size keeps the extents from moving. Iterations then cost a recovery boot and no
diff flash.

**Running it.** Use an autotest launchd job (plan 2.0) that runs `/var/local/bin/gputest` with stdout going to
`/dev/console`. Its output then lands in the log ring that `tools/phone.sh log` pulls. Look for
`GL_RENDERER FD630` and `GLES-TRIANGLE: PASS`, with no SMMU faults in the kernel log.

## Next steps

**6d, kernel `BlueGPU` user client (3-5 h on the plan; my estimate 4-6 h).** Implement exactly what
`blue_gpu_uapi.h` and `fake/fake_bluegpu.c` describe:

- **Memory and params:** GEM_NEW from the GPU pool into the SMMU (granule 64 KiB, the VA window from VA_START/SIZE), GET_OFFSET tokens with `clientMemoryForType`, IOVA, and GET_PARAM with the table above.
- **Submit:** prepend the CCU invalidate, issue one IB per cmd, and end with a CACHE_FLUSH_TS fence.
- **Waits:** WAIT_FENCE/CPU_PREP with absolute continuous-time deadlines.
- **Deferred frees:** GEM_CLOSE deferred until the last fence retires, and unmap-after-fence (flame 0113).
- **Hardware setup:** UBWC setup in hw_init, or ship with `noubwc` first.
- **Where the risk is:** the code is quick to write; the risk is GPU faults on the first real Mesa stream. That first bring-up is 1-2 h of the total.

**6e remainder (1-2 h).** The first on-phone run of `gles-triangle` (`FD_MESA_DEBUG=noubwc,sysmem`, then GMEM,
then UBWC), then fixes. The build itself is done.

**6f, EAGL shim + CA on GLES (plan 4-8 h; my estimate 6-10 h).** Write a separate `bluegl-eagl` layer in the
same dylib: `EAGLContext` (`initWithAPI:`, `setCurrentContext:`,
`renderbufferStorage:fromDrawable:`, `presentRenderbuffer:`) and `texImageIOSurface` /
`attachImage:toCoreSurface`. It goes on `bluegl_create_context` and the IOSurface EGLImage hook. Steps:

- Install it as `OpenGLES.framework` entry points (interpose with `DYLD_INSERT_LIBRARIES`).
- Find CA's `GLESContext` call sites in the 16.7.16 iPhone X cache with `ipsw dyld disass`.
- Make sure `MTLCreateSystemDefaultDevice` returns nil, so CA falls back to GLES.
- Emulate `GL_EXT_shader_framebuffer_fetch` (0004 is the fix on the barrier side).
- Fill missing texture functions, and fall back to copies for non-64-aligned IOSurfaces.

Most of the time goes into the unknowns in CA's private renderer. The plan's own calibration was about 29 h
for flame to reach the home screen from nothing in userland, which supports the upper end.

## Attribution

`bluedrm/` and the IOSurface hook in `frontend/bluegl.c` are ports of HakiOS
(`hakios-drm`, commit 63fc2b46; `tools/mesa/freedreno-darwin.patch`), MIT, Copyright (c) 2025-2026 the
HakiOS authors. See `LICENSES/HakiOS-MIT.txt`. Patch 0004 is HakiOS's fbfetch barrier. Mesa is MIT, and
the downloaded tarball keeps its own licence files. Nothing in this directory is copied from sailfish.


## Kernel side status (2026-11-19)

Kernel patch 0153 (BlueGPU user client) is committed and its in-kernel
self-test passes on the phone (32/32, FAULTS 0). Facts bluedrm must follow:
- GPU VA: GET_PARAM VA_START 0x80000000, VA_SIZE 0x80000000 (not the old
  0x10_0000_0000 plan). BO iova = 0x80000000 + pool offset; imports from 0xc0000000.
- Pool: 32 MiB by default (`bluegpu_pool_mb`, at most 32: the kernel view comes
  from the 64 MiB ml_io_map region). Big textures need care until the pool moves.
- Map with kIOMapAnywhere and default cache; the mmap token is the GEM handle.
- Deadlines on the mach_continuous_time() ns clock; retry SUBMIT on EBUSY; EIO
  means GPU access is off for the boot (a hang); never nr_cmds == 0; IBs only
  in GEM BOs; run with FD_MESA_DEBUG=noubwc.
- The kernel's copy (iokit/Kernel/arm/blue_gpu_uapi.h) predates this VA comment
  change; only the comment/default macros differ, no struct or selector change.
