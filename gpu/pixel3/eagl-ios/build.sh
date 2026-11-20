#!/bin/bash
# build.sh - the EAGL shim for stage 6f (CoreAnimation's GLES renderer on Mesa freedreno), iOS 16 arm64.
#
#   ./build.sh            iOS: out/blueeagl.dylib, out/blueeagl-gl.dylib, out/eagl-test (+ checks)
#   HOST=1 ./build.sh     also macOS copies in out/host/ against mesa-ios's fake BlueGPU, and run
#                         eagl-test there (pixels are not checked: the fake executes nothing)
#
# Needs mesa-ios built first (../mesa-ios/build-mesa-ios.sh, and HOST=1 for the host test): this
# links its out/bluegl.dylib (install name /usr/lib/bluegl.dylib) and reads Mesa's gl.xml and the
# exported gl* list to generate the function table (tools/mkeagl.py, HackiOS).
#
# Outputs (all arm64, minos 16.0, ad-hoc signed; push to the paths in brackets):
#   blueeagl.dylib     [/usr/lib/blueeagl.dylib]     inserted into backboardd: gates, kill switch, CA hooks
#   blueeagl-gl.dylib  [/usr/lib/blueeagl-gl.dylib]  eagl.c + gl_blue.c, links /usr/lib/bluegl.dylib
#   eagl-test          [/usr/local/bin/eagl-test]    the offline test (dlopens /usr/lib/blueeagl.dylib)
set -euo pipefail

H=$(cd "$(dirname "$0")" && pwd)
MESA=${MESA:-$(cd "$H/../mesa-ios" && pwd)}
export DEVELOPER_DIR=${DEVELOPER_DIR:-/Applications/Xcode-15.4.0.app/Contents/Developer}
MIN=16.0
GLXML=$MESA/build/mesa-26.3.1/src/mesa/glapi/glapi/registry/gl.xml
O=$H/out
B=$H/build
mkdir -p "$O" "$B"
log() { echo "build: $*"; }

[ -f "$MESA/out/bluegl.dylib" ] || { echo "no $MESA/out/bluegl.dylib: run mesa-ios/build-mesa-ios.sh first"; exit 1; }
[ -f "$GLXML" ] || { echo "no $GLXML (mesa-ios build tree)"; exit 1; }

# ---- the function table (HackiOS mkeagl.py): every OpenGLES 16.7.16 entry -> Mesa or by hand ------
sed -n 's/^_\(gl[A-Z].*\)/\1/p' "$MESA/out/exports.txt" > "$B/exported-gl.txt"
python3 -I "$H/tools/mkeagl.py" "$H/src/eagl_slots.txt" "$GLXML" "$B/exported-gl.txt" "$H/src/eagl.c" \
	> "$B/eagl_gen.h.new" 2> "$B/mkeagl.log"
cmp -s "$B/eagl_gen.h.new" "$B/eagl_gen.h" || mv "$B/eagl_gen.h.new" "$B/eagl_gen.h"
rm -f "$B/eagl_gen.h.new"
cat "$B/mkeagl.log"
printf '_hakios_gl_function_values\n_hakios_gl_function_refused\n' > "$B/gl-exports.txt"
: > "$B/no-exports.txt"

WARN=(-Wall -Wextra -Wno-unused-parameter -Wno-sign-compare -Wno-frame-address -Wno-missing-field-initializers)

build_for() {
	local T=$1 SDKNAME MINFLAG OD BLUEGL INST_E INST_G
	local DEFS=() RPATH=()
	case $T in
	ios)   SDKNAME=iphoneos; MINFLAG=-miphoneos-version-min=$MIN; OD=$O; BLUEGL=$MESA/out/bluegl.dylib
	       INST_E=/usr/lib/blueeagl.dylib; INST_G=/usr/lib/blueeagl-gl.dylib ;;
	macos) SDKNAME=macosx; MINFLAG=-mmacosx-version-min=13.0; OD=$O/host; BLUEGL=$MESA/out/host/bluegl.dylib
	       INST_E=@rpath/blueeagl.dylib; INST_G=@rpath/blueeagl-gl.dylib
	       DEFS=(-DBLUE_HOST); RPATH=(-Wl,-rpath,"$MESA/out/host")
	       [ -f "$BLUEGL" ] || { echo "no $BLUEGL: run HOST=1 mesa-ios/build-mesa-ios.sh first"; exit 1; } ;;
	esac
	mkdir -p "$OD"
	local CC=(xcrun -sdk $SDKNAME clang -arch arm64 -mcpu=cortex-a53 -march=armv8-a+crypto -mno-outline-atomics $MINFLAG -O2 -g "${WARN[@]}" ${DEFS[@]+"${DEFS[@]}"})

	log "[$T] blueeagl.dylib"
	"${CC[@]}" -fvisibility=hidden -dynamiclib -install_name $INST_E -current_version 1 -compatibility_version 1 \
		-Wl,-exported_symbols_list,"$B/no-exports.txt" -I"$H/src" -o "$OD/blueeagl.dylib" "$H/src/blueeagl.c" \
		-framework CoreFoundation -framework IOKit -Wl,-no_warn_inits
	log "[$T] blueeagl-gl.dylib"
	# (default visibility: the exported_symbols_list alone decides; eagl.c's two tables stay plain globals)
	"${CC[@]}" -dynamiclib -install_name $INST_G -current_version 1 -compatibility_version 1 \
		-Wl,-exported_symbols_list,"$B/gl-exports.txt" -I"$B" -I"$H/src" -I"$MESA/frontend" \
		-o "$OD/blueeagl-gl.dylib" "$H/src/eagl.c" "$H/src/gl_blue.c" "$BLUEGL" ${RPATH[@]+"${RPATH[@]}"} \
		-framework CoreFoundation -framework IOKit -framework IOSurface -lobjc -Wl,-no_warn_inits
	log "[$T] eagl-test"
	if [ $T = ios ]; then
		"${CC[@]}" -fno-objc-arc -Wno-deprecated-declarations -o "$OD/eagl-test" "$H/test/eagl-test.m" \
			-framework Foundation -framework OpenGLES -framework IOSurface -framework CoreFoundation
	else
		"${CC[@]}" -fno-objc-arc -I"$H/test" -o "$OD/eagl-test" "$H/test/eagl-test.m" "$H/test/host_eaglcontext.m" \
			-framework Foundation -framework IOSurface -framework CoreFoundation
	fi
	for f in blueeagl.dylib blueeagl-gl.dylib eagl-test; do
		codesign -f -s - "$OD/$f" 2>/dev/null
	done
}

# ---- checks on the iOS build: what dyld on the phone will see -----------------------------------
checks() {
	local bad=0 f
	for f in blueeagl.dylib blueeagl-gl.dylib eagl-test; do
		[ "$(xcrun lipo -archs "$O/$f")" = arm64 ] || { echo "CHECK $f: not plain arm64"; bad=1; }
		xcrun vtool -show-build "$O/$f" | grep -q "minos $MIN" || { echo "CHECK $f: minos is not $MIN"; bad=1; }
		xcrun vtool -show-build "$O/$f" | grep -q 'platform IOS' || { echo "CHECK $f: not built for iOS"; bad=1; }
		codesign -v "$O/$f" 2>/dev/null || { echo "CHECK $f: signature"; bad=1; }
		# weak imports bind to NULL when iOS 16.0 lacks the symbol (flame's strchrnul lesson)
		if xcrun nm -m -u "$O/$f" | grep -q 'weak external'; then
			echo "CHECK $f: weak imports:"; xcrun nm -m -u "$O/$f" | grep 'weak external'; bad=1
		fi
	done
	# the injector links no GL at all (so the kill switch keeps Mesa out of backboardd)
	if xcrun otool -L "$O/blueeagl.dylib" | grep -E -q 'bluegl|OpenGLES'; then
		echo "CHECK blueeagl.dylib links GL"; bad=1
	fi
	# every gl* the shim calls must come from bluegl (two-level namespace), none from OpenGLES:
	# a gl* bound to OpenGLES's trampolines would call straight back into our own table
	if xcrun otool -L "$O/blueeagl-gl.dylib" | grep -q OpenGLES; then echo "CHECK blueeagl-gl.dylib links OpenGLES"; bad=1; fi
	if xcrun nm -m -u "$O/blueeagl-gl.dylib" | grep ' _gl[A-Z]' | grep -v '(from bluegl)' | grep -q .; then
		echo "CHECK blueeagl-gl.dylib: gl* not from bluegl:"
		xcrun nm -m -u "$O/blueeagl-gl.dylib" | grep ' _gl[A-Z]' | grep -v '(from bluegl)'; bad=1
	fi
	# eagl-test's gl* must come from OpenGLES (the public door), never from bluegl
	if xcrun nm -m -u "$O/eagl-test" | grep ' _gl[A-Z]' | grep -v '(from OpenGLES)' | grep -q .; then
		echo "CHECK eagl-test: gl* not from OpenGLES"; bad=1
	fi
	[ "$(xcrun nm -gU "$O/blueeagl.dylib" | wc -l | tr -d ' ')" = 0 ] || { echo "CHECK blueeagl.dylib exports symbols"; bad=1; }
	[ "$(xcrun nm -gU "$O/blueeagl-gl.dylib" | wc -l | tr -d ' ')" = 2 ] || { echo "CHECK blueeagl-gl.dylib exports"; bad=1; }
	{
		echo "eagl-ios build $(date '+%Y-%m-%d %H:%M'), iOS arm64 minos $MIN"
		for f in blueeagl.dylib blueeagl-gl.dylib eagl-test; do
			printf '%-20s %8d bytes; links:' "$f" "$(stat -f %z "$O/$f")"
			xcrun otool -L "$O/$f" | tail -n +2 | awk '{printf " %s", $1}'; echo
		done
		printf 'blueeagl-gl.dylib imports %d gl* from bluegl, %d symbols in all\n' \
			"$(xcrun nm -m -u "$O/blueeagl-gl.dylib" | grep -c '(from bluegl)')" "$(xcrun nm -u "$O/blueeagl-gl.dylib" | wc -l)"
		printf 'eagl-test imports %d gl* from OpenGLES\n' "$(xcrun nm -m -u "$O/eagl-test" | grep -c '(from OpenGLES)')"
	} | tee "$O/report.txt"
	[ $bad = 0 ] || { echo "CHECKS FAILED"; exit 1; }
	log "checks passed"
}

build_for ios
checks

if [ "${HOST:-0}" = 1 ]; then
	build_for macos
	log "[macos] running eagl-test over mesa-ios's fake BlueGPU"
	(cd "$O/host" && BLUEEAGL_FORCE=1 BLUEEAGL_LOG=stderr BLUEEAGL_LOGRATE=0 EAGL_TEST_NO_PIXELS=1 \
		EAGL_TEST_LIB="$O/host/blueeagl.dylib" ./eagl-test both) 2>&1 | tee "$O/host/eagl-test.log"
	grep -q '^EAGL-TEST: PASS' "$O/host/eagl-test.log" || { echo "host eagl-test failed"; exit 1; }
	grep -q 'errors 0$' "$O/host/eagl-test.log" || { echo "the fake BlueGPU saw ABI errors"; exit 1; }
fi
log "done: $O/blueeagl.dylib $O/blueeagl-gl.dylib $O/eagl-test"
