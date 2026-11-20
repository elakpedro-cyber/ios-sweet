# GPU userland (stage 6f)

What makes CoreAnimation draw on the Adreno 630 instead of the CPU. It works
together with the kernel's BlueGPU user client (`xnu/patches/0153`, `0157`–`0160`).

| folder | builds | goes to |
|---|---|---|
| `mesa-ios/` | Mesa 26.3.1 freedreno (fetched by the script, plus `patches/`), over `bluedrm` (a libdrm stand-in that talks to the BlueGPU user client) | `/usr/lib/bluegl.dylib` |
| `eagl-ios/` | the EAGLContext shim that backboardd's GL renderer uses (a port of HakiOS's MIT `eagl.c`) | `/usr/lib/blueeagl.dylib`, `/usr/lib/blueeagl-gl.dylib` |

Build `mesa-ios` first (`./build-mesa-ios.sh`), then `eagl-ios` (`./build.sh`).
Each folder's README has the details. Then boot with `blueui=1` and push the three
dylibs, for example:

    tools/phonetest.sh --push gpu/mesa-ios/out/bluegl.dylib:/usr/lib/bluegl.dylib \
      --push gpu/eagl-ios/out/blueeagl.dylib:/usr/lib/blueeagl.dylib \
      --push gpu/eagl-ios/out/blueeagl-gl.dylib:/usr/lib/blueeagl-gl.dylib blueui=1 ...
