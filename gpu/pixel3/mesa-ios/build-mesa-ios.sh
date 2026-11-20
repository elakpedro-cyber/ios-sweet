#!/bin/bash
# build-mesa-ios.sh - Mesa 26.3.1 freedreno (Adreno 630, GLES 2/3) for iOS 16 arm64, as one
# dylib (bluegl.dylib) + the gles-triangle test, against the BlueGPU libdrm stand-in.
# See README.md. Userland only: nothing here talks to the phone.
#
#   ./build-mesa-ios.sh            build (incremental: re-run after editing frontend/ test/ bluedrm/)
#   CLEAN=1 ./build-mesa-ios.sh    re-extract + re-patch Mesa and reconfigure from scratch
#   PAD=67108864 ./build-mesa-ios.sh  also write out/bluegl-padded.dylib zero-padded to that size
#                                  (fixed-size file for the in-place push flow, plan 2.0)
#   HOST=1 ./build-mesa-ios.sh     also build a macOS arm64 copy linked with fake/fake_bluegpu.c
#                                  (an in-process BlueGPU model) into out/host/ and run
#                                  gles-triangle there: exercises bluedrm, the uapi and Mesa's
#                                  compiler + command-stream building on the Mac
#
# Outputs in mesa-ios/out/: bluegl.dylib (stripped, ad-hoc signed, install name
# /usr/lib/bluegl.dylib), bluegl-unstripped.dylib, gles-triangle, exports.txt, sizes.txt.
#
# Needs: Xcode 15.4 (DEVELOPER_DIR), python3 >= 3.10 with venv (Homebrew's), bison, flex,
# curl. meson 1.6.1, ninja, mako, pyyaml, packaging are installed into ./venv.
set -euo pipefail

H=$(cd "$(dirname "$0")" && pwd)
VERSION=26.3.1
SHA256=4e4e438eac7b840a9383988cbb7c08dad8041da544b9319fc26d319fa7348961
export DEVELOPER_DIR=${DEVELOPER_DIR:-/Applications/Xcode-15.4.0.app/Contents/Developer}
PY=${PYTHON:-/opt/homebrew/bin/python3}
MIN=16.0

DL=$H/dl
B=$H/build
M=$B/mesa-$VERSION              # patched source (never ref/mesa)
O=$H/out
mkdir -p "$DL" "$B" "$O"

log() { echo "build-mesa-ios: $*"; }

# ---- tools ---------------------------------------------------------------------------------
if [ ! -x "$H/venv/bin/meson" ]; then
	log "creating venv (meson 1.6.1, ninja, mako, pyyaml, packaging)"
	"$PY" -m venv "$H/venv"
	"$H/venv/bin/pip" -q install 'meson==1.6.1' ninja mako pyyaml packaging
fi
# Mesa's generators run as "#!/usr/bin/env python3" scripts: the venv must come first on PATH
export PATH=$H/venv/bin:$PATH
for t in bison flex; do command -v $t >/dev/null || { echo "need $t"; exit 1; }; done
TC=$DEVELOPER_DIR/Toolchains/XcodeDefault.xctoolchain/usr/bin

# ---- source: pinned tarball + our patches --------------------------------------------------
[ -f "$DL/mesa-$VERSION.tar.xz" ] || curl -sL --fail -o "$DL/mesa-$VERSION.tar.xz" \
	"https://archive.mesa3d.org/mesa-$VERSION.tar.xz"
echo "$SHA256  $DL/mesa-$VERSION.tar.xz" | shasum -a 256 -c --quiet
PATCHES=$(cat "$H"/patches/*.patch | shasum -a 256 | cut -d' ' -f1)
if [ "${CLEAN:-0}" = 1 ] || [ ! -d "$M" ] || [ "$(cat "$M/.blue-patches" 2>/dev/null)" != "$PATCHES" ]; then
	log "extracting Mesa $VERSION and applying patches/"
	rm -rf "$M" "$B"/out-*
	tar xJf "$DL/mesa-$VERSION.tar.xz" -C "$B"
	for p in "$H"/patches/*.patch; do
		patch -s --no-backup-if-mismatch -d "$M" -p1 < "$p"
	done
	echo "$PATCHES" > "$M/.blue-patches"
fi
# the libdrm stand-in + the uapi header always come fresh from mesa-ios/
mkdir -p "$M/src/bluedrm"
for f in "$H"/bluedrm/* "$H/blue_gpu_uapi.h"; do
	cmp -s "$f" "$M/src/bluedrm/$(basename "$f")" || cp "$f" "$M/src/bluedrm/"
done

# ---- meson + link, per target (ios = the deliverable, macos = host ABI test) --------------
LIBS=(
	src/mesa/libmesa.a src/gallium/auxiliary/libgallium.a
	src/gallium/drivers/freedreno/libfreedreno.a src/gallium/winsys/freedreno/drm/libfreedrenowinsys.a
	src/freedreno/drm/libfreedreno_drm.a src/freedreno/ir3/libfreedreno_ir3.a
	src/freedreno/ir2/libfreedreno_ir2.a src/freedreno/fdl/libfreedreno_layout.a
	src/freedreno/common/libfreedreno_common.a src/freedreno/isa/libir3encode.a
	src/freedreno/isa/libir3decode.a src/compiler/isaspec/libisaspec.a
	src/freedreno/perfcntrs/libfreedreno_perfcntrs.a
	src/compiler/glsl/libglsl.a src/compiler/glsl/glcpp/libglcpp.a src/compiler/nir/libnir.a
	src/compiler/spirv/libvtn.a src/compiler/libcompiler.a
	src/mesa/glapi/glapi/libglapi_bridge.a src/mesa/glapi/shared-glapi/libglapi.a
	src/util/libxmlconfig.a src/util/libmesa_util.a src/util/libmesa_util_simd.a
	src/util/blake3/libblake3.a src/c11/impl/libmesa_util_c11.a
)

build_for() {
	local T=$1 SDKNAME MINFLAG SUBSYS OD BO INSTALL SDK
	local EXTRA_O=()
	case $T in
	ios)   SDKNAME=iphoneos; MINFLAG=-miphoneos-version-min=$MIN; SUBSYS=ios; OD=$O
	       INSTALL=/usr/lib/bluegl.dylib ;;
	macos) SDKNAME=macosx; MINFLAG=-mmacosx-version-min=13.0; SUBSYS=macos; OD=$O/host
	       INSTALL=@rpath/bluegl.dylib ;;
	esac
	BO=$B/out-$T
	mkdir -p "$OD"
	SDK=$(xcrun -sdk $SDKNAME --show-sdk-path)
	{
		echo "[binaries]"
		echo "c = ['$TC/clang', '-arch', 'arm64', '-mcpu=cortex-a53', '-march=armv8-a+crypto', '-mno-outline-atomics', '-isysroot', '$SDK', '$MINFLAG']"
		echo "cpp = ['$TC/clang++', '-arch', 'arm64', '-mcpu=cortex-a53', '-march=armv8-a+crypto', '-mno-outline-atomics', '-isysroot', '$SDK', '$MINFLAG']"
		echo "objc = ['$TC/clang', '-arch', 'arm64', '-mcpu=cortex-a53', '-march=armv8-a+crypto', '-mno-outline-atomics', '-isysroot', '$SDK', '$MINFLAG']"
		echo "ar = '$TC/ar'"
		echo "strip = '$TC/strip'"
		echo "pkg-config = 'false'"
		echo
		echo "[host_machine]"
		echo "system = 'darwin'"
		echo "subsystem = '$SUBSYS'"
		echo "cpu_family = 'aarch64'"
		echo "cpu = 'arm64'"
		echo "endian = 'little'"
		echo
		echo "[properties]"
		echo "needs_exe_wrapper = true"
	} > "$B/cross-$T.ini.new"
	cmp -s "$B/cross-$T.ini.new" "$B/cross-$T.ini" || { mv "$B/cross-$T.ini.new" "$B/cross-$T.ini"; rm -rf "$BO"; }
	rm -f "$B/cross-$T.ini.new"
	# -Dshader-cache=enabled (with zlib, which it needs): compiled shaders are kept on disk
	# (MESA_SHADER_CACHE_DIR, set by blueeagl), so a shader is compiled once per phone, not
	# once per boot. Changed options reconfigure in place.
	local OPTS=(--buildtype=release -Db_ndebug=true -Ddefault_library=static
		-Dplatforms= -Degl=disabled -Dglx=disabled -Dgbm=disabled
		-Dgallium-drivers=freedreno -Dvulkan-drivers= -Dfreedreno-kmds=msm
		-Dllvm=disabled -Dgles1=disabled -Dgles2=enabled -Dopengl=true
		-Dzstd=disabled -Dzlib=enabled -Dexpat=disabled -Dxmlconfig=disabled
		-Dvalgrind=disabled -Dlibunwind=disabled -Dlmsensors=disabled
		-Dbuild-tests=false -Dshader-cache=enabled -Dperfetto=false
		-Dgallium-va=disabled -Dgallium-rusticl=false -Dtools=
		-Dhtml-docs=disabled -Ddisplay-info=disabled -Dteflon=false)
	if [ ! -f "$BO/build.ninja" ]; then
		log "[$T] meson setup"
		meson setup "$BO" "$M" --cross-file "$B/cross-$T.ini" --wrap-mode=nofallback \
			"${OPTS[@]}" > "$B/meson-setup-$T.log"
		echo "${OPTS[*]}" > "$BO/.bluegl-opts"
	elif [ "$(cat "$BO/.bluegl-opts" 2>/dev/null)" != "${OPTS[*]}" ]; then
		log "[$T] meson reconfigure (options changed)"
		meson setup --reconfigure "$BO" "$M" --cross-file "$B/cross-$T.ini" --wrap-mode=nofallback \
			"${OPTS[@]}" > "$B/meson-setup-$T.log"
		echo "${OPTS[*]}" > "$BO/.bluegl-opts"
	fi
	log "[$T] ninja (${#LIBS[@]} static libraries)"
	ninja -C "$BO" "${LIBS[@]}" > "$B/ninja-$T.log" || { tail -40 "$B/ninja-$T.log"; exit 1; }

	local CC=(xcrun -sdk $SDKNAME clang -arch arm64 $MINFLAG)
	local CXX=(xcrun -sdk $SDKNAME clang++ -arch arm64 $MINFLAG)
	# Mesa's own -D/-I set for the state tracker, so bluegl.c sees the same config as libmesa
	python3 -I "$H/tools/mesa-cflags.py" "$BO" state_tracker/st_manager.c > "$OD/mesa-flags.rsp"
	"${CC[@]}" -O2 -Wall -fvisibility=hidden @"$OD/mesa-flags.rsp" \
		-I"$M/src/gallium/drivers" -I"$M/src/gallium/winsys" -I"$M/src/bluedrm" -I"$M/src/mesa/glapi" \
		-I"$H/frontend" -c "$H/frontend/bluegl.c" -o "$OD/bluegl.o"
	if [ $T = macos ]; then
		"${CC[@]}" -O2 -Wall -I"$H" -c "$H/fake/fake_bluegpu.c" -o "$OD/fake_bluegpu.o"
		EXTRA_O=("$OD/fake_bluegpu.o")
	fi
	# exports: the public gl* entry points of Mesa's glapi bridge + bluegl_*
	xcrun nm -gU "$BO/src/mesa/glapi/glapi/libglapi_bridge.a" 2>/dev/null |
		awk '$2 == "T" && $3 ~ /^_gl[A-Z]/ { print $3 }' | sort -u > "$OD/exports.txt"
	echo '_bluegl_*' >> "$OD/exports.txt"
	log "[$T] linking bluegl.dylib"
	"${CXX[@]}" -dynamiclib -dead_strip -Wl,-no_warn_inits \
		-install_name $INSTALL -current_version 26.3.1 -compatibility_version 1 \
		-exported_symbols_list "$OD/exports.txt" -o "$OD/bluegl-unstripped.dylib" "$OD/bluegl.o" \
		${EXTRA_O[@]+"${EXTRA_O[@]}"} "${LIBS[@]/#/$BO/}" -framework IOKit -lz
	xcrun strip -x -o "$OD/bluegl.dylib" "$OD/bluegl-unstripped.dylib"
	codesign -f -s - "$OD/bluegl.dylib" 2>/dev/null
	"${CC[@]}" -O2 -Wall -I"$M/include" -I"$H/frontend" "$H/test/gles-triangle.c" \
		-o "$OD/gles-triangle" "$OD/bluegl.dylib" -Wl,-rpath,@executable_path
	codesign -f -s - "$OD/gles-triangle" 2>/dev/null
}

build_for ios

# ---- checks + report (iOS) -----------------------------------------------------------------
# Every import must be a plain libSystem/libc++/IOKit/libz symbol that iOS 16.0 has. Weak
# imports other than C++ operator new/delete and pthread_mutexattr_* (Mesa's #pragma weak) are
# suspect (flame's strchrnul lesson: a weak import iOS lacks binds to NULL and crashes later).
WEAK=$(xcrun nm -m -u "$O/bluegl.dylib" | grep 'weak external' |
	grep -v -E '__Z(n|d)|__ZTISt|_pthread_mutexattr_' || true)
[ -z "$WEAK" ] || { echo "unexpected weak imports:"; echo "$WEAK"; exit 1; }
xcrun vtool -show-build "$O/bluegl.dylib" | grep -q "minos $MIN" || { echo "minos is not $MIN"; exit 1; }
if [ -n "${PAD:-}" ]; then
	[ "$(stat -f %z "$O/bluegl.dylib")" -le "$PAD" ] || { echo "bluegl.dylib larger than PAD"; exit 1; }
	cp "$O/bluegl.dylib" "$O/bluegl-padded.dylib"
	truncate -s "$PAD" "$O/bluegl-padded.dylib"
fi
{
	echo "Mesa $VERSION freedreno for iOS arm64 (minos $MIN), $(date '+%Y-%m-%d %H:%M')"
	for f in bluegl.dylib bluegl-unstripped.dylib gles-triangle; do
		printf '%-26s %10d bytes\n' "$f" "$(stat -f %z "$O/$f")"
	done
	printf '%-26s %10d\n' "exported gl* functions" "$(xcrun nm -gU "$O/bluegl.dylib" | grep -c ' _gl[A-Z]')"
	printf '%-26s %10d\n' "imported symbols" "$(xcrun nm -u "$O/bluegl.dylib" | wc -l)"
	xcrun size -m "$O/bluegl.dylib" | awk '/^Segment __(TEXT|DATA|DATA_CONST|LINKEDIT)/'
} | tee "$O/sizes.txt"

if [ "${HOST:-0}" = 1 ]; then
	build_for macos
	log "[macos] running gles-triangle over the fake BlueGPU"
	GLES_TRIANGLE_NO_PIXELS=1 "$O/host/gles-triangle" 2>&1 | tee "$O/host/gles-triangle.log"
	grep -q 'errors 0$' "$O/host/gles-triangle.log" || { echo "fake BlueGPU saw ABI errors"; exit 1; }
fi
log "done: $O/bluegl.dylib, $O/gles-triangle"
