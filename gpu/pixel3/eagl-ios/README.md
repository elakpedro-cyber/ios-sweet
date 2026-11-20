# eagl-ios: CoreAnimation's GL renderer on Mesa freedreno (stage 6f userland)

backboardd's `CA::WindowServer::EAGLServer::renderer()` tries Metal first, and that fails because
IOAcceleratorES has no MetalPluginName. It then calls `[[EAGLContext alloc] initWithAPI:3 properties:]`
and renders through the function table from `-getMacroContextPrivate`. This shim replaces
EAGLContext's methods so that the context and the table are Mesa's (`/usr/lib/bluegl.dylib`, from
`../mesa-ios`). The port is HackiOS's MIT `eagl.c` and the minimal subset of `inject.c` (commit
63fc2b46; see `LICENSES/HakiOS-MIT.txt`).

## Files

| file | what |
|---|---|
| `src/blueeagl.c` | **`/usr/lib/blueeagl.dylib`**: the inserted library. It applies the gates and kill switches, the crash counter and the BlueGPU check, then sets up `caenv=`. It installs the 20H392 vtable hooks (renderer, render_update, function_supported, function_uniform, compile_shader), the fault logger, and the dlopen of the GL half. It links no GL. |
| `src/eagl.c` | HackiOS eagl.c, ported. It replaces the EAGLContext methods and does the CA-dialect to GLSL ES 3.00 rewrite, IOSurface textures/targets and frame-end copy-out. It also fills `_private` with Apple's layout so `+setCurrentContext:`, `+currentContext` and OpenGLES's exported gl* trampolines reach our table. |
| `src/gl_blue.c` | The `hakios.gl.h` back end: bluegl create/make_current/destroy, plus IOSurface-as-EGLImage via `glEGLImageTargetTexture2DOES`, gated by `bluegl_iosurface_importable`. |
| `src/blueeagl_log.h` | `BLUEEAGL: ` lines on `/dev/console`, rate limited. |
| `src/eagl_slots.txt`, `tools/mkeagl.py`, `src/hakios.gl.h` | HackiOS's generator and the slot list. The slot list is identical to OpenGLES 16.7.16's 409 offsets. |
| `test/eagl-test.m` | The offline test: public API phase and CA-path phase, with an IOSurface target and a CPU check plus a glReadPixels check. Prints PASS/FAIL. |
| `test/host_eaglcontext.[mh]` | Mac only: a stand-in EAGLContext class with Apple's `_private`/TLS behaviour. |
| `build.sh` | Builds and runs the checks. `HOST=1` also builds for macOS and runs the test against the fake BlueGPU. |

Why two dylibs of ours rather than one combined with bluegl:
- With the kill switch on, nothing of Mesa (18 MB) is even mapped into backboardd.
- The inserted library stays small, and a shim fix is a 0.7 MB push, not 18 MB.
- `bluegl.dylib` stays exactly mesa-ios's build.

## Build

    cd eagl-ios && ./build.sh          # iOS: out/blueeagl.dylib, out/blueeagl-gl.dylib, out/eagl-test
    HOST=1 ./build.sh                  # + out/host/*, and runs eagl-test on the Mac

mesa-ios must be built first, plus `HOST=1` for the Mac half. The build uses Xcode 15.4 and the
iPhoneOS 17.5 SDK, `-miphoneos-version-min=16.0`, arm64 (not arm64e), ad-hoc signed.

`build.sh` checks:
- plain arm64, minos 16.0, platform iOS, valid signature, no weak imports;
- blueeagl.dylib links no GL and exports nothing;
- blueeagl-gl.dylib exports exactly two symbols;
- every gl* import of blueeagl-gl is two-level bound to bluegl, none to OpenGLES (a gl* bound to OpenGLES would call back into our own table);
- eagl-test's 35 gl* come from OpenGLES.

See `out/report.txt`.

## Phone, step 1: eagl-test (no backboardd change)

This needs a kernel with 6d (BlueGPU user client, 0153) and 0152 (bluepush). It is run from `pixel3-ios-dev`:

    E=../pixel3-ios-gpu
    tools/phonetest.sh --name eagl1 --grep 'BLUERUN|BLUEEAGL|BLUELINE (GPU|REBOOT)' \
      --push $E/mesa-ios/out/bluegl.dylib:/usr/lib/bluegl.dylib:0755 \
      --push $E/eagl-ios/out/blueeagl.dylib:/usr/lib/blueeagl.dylib:0755 \
      --push $E/eagl-ios/out/blueeagl-gl.dylib:/usr/lib/blueeagl-gl.dylib:0755 \
      --push $E/eagl-ios/out/eagl-test:/usr/local/bin/eagl-test:0755 \
      --run /usr/local/bin/eagl-test,both --run-timeout 60 \
      'bluerun_env=FD_MESA_DEBUG=noubwc,sysmem;BLUEEAGL_LOGRATE=0'

Variants:
- `--run /usr/local/bin/eagl-test,ca` runs only the CA path.
- `;BLUEEAGL_COPY=1` in `bluerun_env` forces the copy path (no IOSurface import). It tells a coherence problem from a draw problem.

Expected output on success:

    BLUEEAGL: blueeagl in eagl-test pid N (by name)
    BLUEEAGL: loading /usr/lib/blueeagl-gl.dylib
    BLUEEAGL: 9 of 9 methods of EAGLContext are ours; OpenGL ES by Mesa freedreno over BlueGPU (bluegl.dylib)
    BLUEEAGL: ON in eagl-test: EAGLContext is ours (cache slide 0x...)
    BLUEEAGL: an OpenGL ES 3 context for CoreAnimation, by Mesa freedreno over BlueGPU (bluegl.dylib): OpenGL ES 3.2 Mesa 26.3.1; FD630; ...
    BLUERUN: EAGL-TEST: public initWithAPI PASS: API 3
    BLUERUN: EAGL-TEST: public: GL_VENDOR freedreno / GL_RENDERER FD630 / GL_VERSION OpenGL ES 3.2 Mesa 26.3.1
    BLUERUN: EAGL-TEST: public attachImage PASS ...
    (no "copied, not shared" line when the kernel imports the IOSurface through 0x7e)
    BLUERUN: EAGL-TEST: public iosurface PASS: 0 of 65536 pixels wrong ...
    BLUERUN: EAGL-TEST: public readpixels PASS ...
    BLUERUN: EAGL-TEST: ca ... PASS (same again)
    BLUERUN: EAGL-TEST: PASS

How to read a failure:
- `iosurface FAIL ... STALE`: the CPU sees 0x55, so it is kernel coherence (see below). If `readpixels` passes at the same time, the GPU drew correctly but the CPU view is stale.
- `ZERO`: nothing was written.
- `program FAIL`: the shader rewrite. The BLUEEAGL lines carry Mesa's info log.
- `OFF (no BlueGPU service ...)`: the kernel lacks 6d.

## Phone, step 2: backboardd

The kernel needs 0203/0205 (sweetenv, AMFI dyld policy) and 0206-0208, as listed in stage6f-research.md.
The four files above must already be pushed; pushes persist on userdata.

    tools/phonetest.sh --name eagl-bb1 --grep 'BLUEEAGL|BLUELINE (SNAP|SCRIPT|REBOOT|GPU)' \
      sweetenv=backboardd:DYLD_INSERT_LIBRARIES=/usr/lib/blueeagl.dylib cs_enforcement_disable=1 \
      glenv=FD_MESA_DEBUG=noubwc,sysmem \
      bluesnap=sb+20,sb+40 bluesnap_on_reboot=1 \
      'bluetouchscript=sb+25:swipe,540,2150,540,900,300' \
      bluereboot=recovery bluereboot_after=springboard bluereboot_delay=50

Screenshots arrive as `work/test/eagl-bb1-snapN.png`. Compare them with the same command without
`sweetenv=` (the software renderer). Expected log:

    BLUEEAGL: blueeagl in backboardd pid N (by name)
    BLUEEAGL: backboardd start 1 of at most 3 in this boot
    BLUEEAGL: replaced renderer (0x1882eaf3c ok)
    BLUEEAGL: replaced render_update (0x1883601dc ok)
    BLUEEAGL: replaced function_supported (0x1884b2164 ok)   (+ function_uniform 0x1884b21ac, compile_shader 0x1884053fc)
    BLUEEAGL: window server hooks installed
    BLUEEAGL: 9 of 9 methods of EAGLContext are ours; ...
    BLUEEAGL: ON in backboardd: EAGLContext is ours (cache slide 0x...)
    BLUEEAGL: an OpenGL ES 3 context for CoreAnimation, by Mesa freedreno over BlueGPU (bluegl.dylib): OpenGL ES 3.2 Mesa 26.3.1; FD630; ...
    BLUEEAGL: the server has an accelerated renderer (0x...)
    BLUEEAGL: CoreAnimation compiles its shaders through the table ...
    BLUEEAGL: render_update -> 0x... (flags 0x...)            (first 6 frames)
    BLUEEAGL: frame N: ... GL calls, ... draws ...

### Kill switches

These are checked in order. Each one logs `OFF (reason): CoreAnimation keeps its software renderer`
and leaves backboardd untouched.
1. Drop `sweetenv=`, or add the boot-arg `blueeagl=0`.
2. Push an empty file: `touch off; tools/phonetest.sh --push off:/private/var/mobile/blueeagl.off ...` (remove it with `--rm /private/var/mobile/blueeagl.off`).
3. Crash counter: `/var/mobile/blueeagl.starts` counts backboardd starts per boot session. After `blueeagl_tries` starts (default 3; 0 means no limit), the shim stays off for the rest of that boot. A crash loop therefore ends in SpringBoard on the software renderer without a reflash. A "window server hooks" line that says `found 0x..., expected 0x...; left alone` means the 20H392 addresses do not match this build.
4. No BlueGPU service.
5. For eagl-test, the environment variable `BLUEEAGL_OFF=1`.

Other knobs:
- `blueeagl_lograte=N` sets the log rate (default 60 lines/s; 0 means unlimited).
- `caenv=NAME=VALUE` sets CA environment variables (`p` stands for `.`).
- `glenv=`, `gltrace=` and `glcopy=1` are as in eagl.c.

## What the kernel's 6d user client (0153) must give

- **0x7e IOSurface import, writable.** CA renders into the display's IOSurfaces, and the GPU must write into the surface's own pages (non-contiguous, so a GPU VA mapping of the page list). If the import is refused, the shim falls back to a copy, which costs about 1 ms per frame.
- **Coherence.**
  - Clean and invalidate the surface's pages at import.
  - CPU reads after GPU writes must see the GPU's data: invalidate at CPU_PREP or fence retire, or map the surface non-cacheable.
  - The eagl-test `STALE` verdict catches this case.
- **Repeated imports.** Importing the same surface again returns the same handle, or is at least cheap. CA re-imports every frame.
- **Pitch.** It must be a multiple of 64 bytes (A6xx). `bluegl_iosurface_importable` refuses anything else.
- **Unmapping.** Unmap only after the last fence that used the surface.
- **Boot-args.** The full kernel needs 0203/0205/0206-0208 and `cs_enforcement_disable=1`. The vtable hooks write into the shared cache with `VM_PROT_COPY`.
- **IOAcceleratorES.** Keep it empty, with no MetalPluginName, so Metal still fails first.

## Mac test (HOST=1)

eagl-test runs both phases against mesa-ios's fake BlueGPU. The fake executes nothing, so pixels
are reported as SKIP. All other checks pass, ending with `EAGL-TEST: PASS (pixels not checked)` and
`bluegpu-fake: ... errors 0`. The log is in `out/host/eagl-test.log`.
