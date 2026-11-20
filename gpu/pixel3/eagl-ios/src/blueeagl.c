/*
 * blueeagl.c - /usr/lib/blueeagl.dylib: what the kernel inserts into backboardd
 * (sweetenv=backboardd:DYLD_INSERT_LIBRARIES=/usr/lib/blueeagl.dylib) to put CoreAnimation's
 * OpenGL ES renderer on the Adreno 630.
 *
 * It is small on purpose and links nothing of Mesa. Its constructor decides, and only when every
 * gate passes does it dlopen blueeagl-gl.dylib (eagl.c + gl_blue.c, which links bluegl.dylib):
 *
 *   1. the program: backboardd, or eagl-test (the offline test), or anything with
 *      BLUEEAGL_FORCE=1 in its environment; otherwise it returns at once, silently;
 *   2. the kill switches, any one of which leaves CoreAnimation on its software renderer:
 *        environment BLUEEAGL_OFF=1           (bluerun_env=BLUEEAGL_OFF=1 for eagl-test)
 *        boot-arg   blueeagl=0
 *        file       /var/mobile/blueeagl.off  (push an empty file: tools/phonetest.sh --push
 *                                              EMPTY:/private/var/mobile/blueeagl.off; --rm it again)
 *        crash loop: backboardd started more than blueeagl_tries=N times (default 3) in this
 *                    boot (/var/mobile/blueeagl.starts holds the boot session UUID and the count)
 *   3. the kernel's GPU: an IOService named BlueGPU (stage 6d) must exist (BLUEEAGL_FORCE=1 skips
 *      this, for the Mac host test where the fake BlueGPU lives inside bluegl.dylib);
 *   4. dlopen of blueeagl-gl.dylib from the directory this library was loaded from (or
 *      $BLUEEAGL_GL), whose constructor replaces EAGLContext's methods (eagl.c install()).
 * Then, in backboardd only, the inject.c subset (HackiOS) against QuartzCore 16.7.16 (20H392):
 *   - EAGLServer::renderer() tried once (otherwise a failed GL context is retried every frame),
 *     and logged: "the server has an accelerated renderer" is the line that says CA took GL;
 *   - EAGLServer::render_update() logged for its first calls;
 *   - GLESContext::function_supported/function_uniform/compile_shader watched (what CA's GL
 *     renderer cannot draw; the numbers for eagl.c's own programs; that shaders compile);
 *   - the fatal signals logged with unslid addresses (ipsw dyld a2s names them).
 * Every virtual-table entry is checked against the expected original before it is written, so
 * a different QuartzCore build is logged and left alone rather than crashed.
 *
 * Boot-arg caenv=NAME=VALUE (repeatable, no spaces; a decimal point is written p: 0p25) puts
 * that into backboardd's environment before QuartzCore reads it (CA_DISABLED_EXTENSIONS,
 * CA_PRINT_SHADERS=1 ...): launchd passes no DYLD_ variables and sweetenv takes one.
 *
 * Origin: HackiOS userland/src/inject.c (backboardd part), commit
 * 63fc2b4633bac3af8e57dadab9f5a8d4cb940438; addresses re-derived for 20H392 in
 * stage6f-research.md section 2.4. The gates, kill switches and loader are new.
 *
 * Copyright (c) 2025-2026 the HakiOS authors. Changes Copyright (c) 2026 pixel3-ios.
 *
 * MIT License
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all
 * copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 */
#include <CoreFoundation/CoreFoundation.h>
#include <IOKit/IOKitLib.h>
#include <dlfcn.h>
#include <CoreFoundation/CoreFoundation.h>
#include <errno.h>
#include <fcntl.h>
#include <mach/mach.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/sysctl.h>
#include <sys/ucontext.h>
#include <unistd.h>

#include "blueeagl_log.h"
#include "hakios.gl.h"

#define say blog

extern const void *_dyld_get_shared_cache_range(size_t *length);

#include "../../mesa-ios/blue_gpu_uapi.h"
#define BLUEGPU_SERVICE         BLUE_GPU_SERVICE                       /* mesa-ios blue_gpu_uapi.h BLUE_GPU_SERVICE */
#define GL_LIBRARY              "blueeagl-gl.dylib"
#define KILL_FILE               "/var/mobile/blueeagl.off"
#define STARTS_FILE             "/var/mobile/blueeagl.starts"

/* ---- QuartzCore 16.7.16 (20H392, iPhone X), unslid; stage6f-research.md 2.4 ------------------- */
#define CACHE_BASE              0x180000000UL
#define VT_EAGL_SERVER          0x1d5b39ed0UL   /* vtable for CA::WindowServer::EAGLServer */
#define EXPECT_RENDERER         0x1882eaf3cUL   /* ... +0x1a0 renderer() */
#define EXPECT_RENDER_UPDATE    0x1883601dcUL   /* ... +0x178 render_update() */
#define VT_GLES_CONTEXT         0x1d5b2f6e8UL   /* vtable for CA::OGL::GLESContext */
#define EXPECT_FUNCTION_SUPP    0x1884b2164UL   /* ... +0x378 GLContext::function_supported() */
#define EXPECT_FUNCTION_UNIF    0x1884b21acUL   /* ... +0x388 GLContext::function_uniform() */
#define EXPECT_COMPILE_SHADER   0x1884053fcUL   /* ... +0x060 Context::compile_shader() */
#define VSLOT(vtable, offset)   ((vtable) + 0x10 + (offset))

static uintptr_t slide;

/* Replace one entry of a virtual table (unslid address `slot`) that must now hold `expected`. */
static void *
replace_virtual(const char *what, uintptr_t slot, uintptr_t expected, void *replacement)
{
	uintptr_t *entry = (uintptr_t *)(slot + slide);
	vm_address_t page = (vm_address_t)entry & ~(vm_address_t)(vm_page_size - 1);
	kern_return_t kr;
	void *original;

	if (*entry != expected + slide) {
		say("hakios: %s: found %#lx, expected %#lx; left alone\n", what, *entry - slide, expected);
		return NULL;
	}
	/* the tables are in read-only memory shared by every process: get a private writable copy of the page */
	kr = vm_protect(mach_task_self(), page, vm_page_size, FALSE, VM_PROT_READ | VM_PROT_WRITE | VM_PROT_COPY);
	if (kr != KERN_SUCCESS) {
		say("hakios: %s: cannot make the table writable (%d)\n", what, kr);
		return NULL;
	}
	original = (void *)*entry;
	*entry = (uintptr_t)replacement;
	vm_protect(mach_task_self(), page, vm_page_size, FALSE, VM_PROT_READ);
	say("hakios: replaced %s (%#lx ok)\n", what, expected);
	return original;
}

/* ---- CA::WindowServer::EAGLServer ------------------------------------------------------------- */

static void *(*orig_renderer)(void *server);
static uintptr_t (*orig_render_update)(void *server, void *update, unsigned *flags);
static unsigned calls_render;

/*
 * Every frame the server asks for its renderer, and while there is none it tries again to make a
 * Metal and then an OpenGL ES context, which costs a lot and cannot succeed here. One try is enough:
 * without a renderer the server draws with CA::WindowServer::Server::sw_renderer().
 */
static void *
my_renderer(void *server)
{
	static int failed, said;
	void *renderer;

	if (failed) {
		return NULL;
	}
	renderer = orig_renderer(server);
	if (renderer == NULL) {
		failed = 1;
		say("hakios: no accelerated renderer; the software one will draw\n");
	} else if (!said) {
		said = 1;
		say("hakios: the server has an accelerated renderer (%p)\n", renderer);
	}
	return renderer;
}

static uintptr_t
my_render_update(void *server, void *update, unsigned *flags)
{
	uintptr_t r = orig_render_update(server, update, flags);

	if (calls_render++ < 6) {
		say("hakios: render_update -> %#lx (flags %#x)\n", r, flags ? *flags : 0);
	}
	return r;
}

/* ---- CA::OGL::GLESContext ---------------------------------------------------------------------- */

static void (*gl_function_refused)(unsigned function);  /* eagl.c's census */
static void (*gl_function_values)(void *context, unsigned function, unsigned index, size_t components, size_t count,
    const float *values);
static int (*orig_function_supported)(void *context);
static void (*orig_function_uniform)(void *context, unsigned index, size_t components, size_t count, const float *values);
static uintptr_t (*orig_compile_shader)(void *context, const char *source);
static int compile_shaders_said;                /* boot-arg glcompile=1: write down every shader source */

/* (the function being drawn: [[context + 0x10] + 0x10], as GLContext::function_supported() reads it in 20H392) */
static uint8_t
function_of(void *context)
{
	return *(*(uint8_t **)((char *)context + 0x10) + 0x10);
}

static int
my_function_supported(void *context)
{
	static const char names[] = HAKIOS_CA_FUNCTIONS;
	static uint8_t said[256];
	int supported = orig_function_supported(context);
	uint8_t function = function_of(context);

	if (!supported && gl_function_refused != NULL) {
		gl_function_refused(function);
	}
	if (!supported && !said[function]) {
		said[function] = 1;
		say("hakios: CoreAnimation's OpenGL ES renderer has no function %u (\"%.3s\"): what needs it is not drawn\n",
		    function, function < 90 ? names + 4 * function : "?");
	}
	return supported;
}

static void
my_function_uniform(void *context, unsigned index, size_t components, size_t count, const float *values)
{
	if (gl_function_values != NULL) {
		gl_function_values(context, function_of(context), index, components, count, values);
	}
	orig_function_uniform(context, index, components, count, values);
}

static uintptr_t
my_compile_shader(void *context, const char *source)
{
	static unsigned told, seen;

	if (seen++ == 0) {
		say("hakios: CoreAnimation compiles its shaders through the table (the first of them, %zu characters)\n",
		    source != NULL ? strlen(source) : 0);
	}
	if (compile_shaders_said && told < 24) {
		told++;
		say("hakios: CoreAnimation compiles a shader, %zu characters:\n", source != NULL ? strlen(source) : 0);
		for (size_t at = 0, length = source != NULL ? strlen(source) : 0; at < length; at += 700) {
			say("hakios:  %.700s\n", source + at);
		}
	}
	return orig_compile_shader(context, source);
}

/* ---- where the window server died ------------------------------------------------------------- */

static int
where_is(uintptr_t a, char *out, size_t room)
{
	Dl_info d;
	if (a == 0 || !dladdr((const void *)a, &d) || d.dli_fbase == NULL) {
		return snprintf(out, room, " %#lx(?)", a);
	}
	const char *img = d.dli_fname ? strrchr(d.dli_fname, '/') : NULL;
	img = img ? img + 1 : (d.dli_fname ? d.dli_fname : "?");
	if (d.dli_sname != NULL && d.dli_saddr != NULL) {
		return snprintf(out, room, " %s+%#lx(%s+%#lx)", img, a - (uintptr_t)d.dli_fbase, d.dli_sname,
		    a - (uintptr_t)d.dli_saddr);
	}
	return snprintf(out, room, " %s+%#lx", img, a - (uintptr_t)d.dli_fbase);
}

static void
say_the_fault(int signal_number, siginfo_t *info, void *context_in)
{
	ucontext_t *context = context_in;
	uintptr_t pc = 0, lr = 0, fp = 0;
	char line[1800];
	int n = 0;

	if (context != NULL && context->uc_mcontext != NULL) {
		pc = (uintptr_t)context->uc_mcontext->__ss.__pc;
		lr = (uintptr_t)context->uc_mcontext->__ss.__lr;
		fp = (uintptr_t)context->uc_mcontext->__ss.__fp;
	}
	n += snprintf(line + n, sizeof(line) - n, BLUEEAGL_PREFIX "signal %d at %p, pc", signal_number,
	    info != NULL ? info->si_addr : NULL);
	n += where_is(pc, line + n, sizeof(line) - n);
	n += snprintf(line + n, sizeof(line) - n, ", lr");
	n += where_is(lr, line + n, sizeof(line) - n);
	n += snprintf(line + n, sizeof(line) - n, ", called from");
	/* the callers, by the frame pointers: [fp] the previous frame, [fp + 8] its return address */
	for (unsigned i = 0; i < 12 && fp != 0 && (fp & 7) == 0 && n < (int)sizeof(line) - 120; i++) {
		uintptr_t next = ((uintptr_t *)fp)[0], ret = ((uintptr_t *)fp)[1];
		if (ret == 0) {
			break;
		}
		n += where_is(ret, line + n, sizeof(line) - n);
		fp = next > fp ? next : 0;
	}
	if (n > (int)sizeof(line) - 2) {
		n = (int)sizeof(line) - 2;
	}
	line[n++] = '\n';
	(void)write(blog_fd >= 0 ? blog_fd : 2, line, (size_t)n);
	(void)slide;
	signal(signal_number, SIG_DFL);
	raise(signal_number);
}

static void
watch_for_faults(void)
{
	struct sigaction action;

	memset(&action, 0, sizeof(action));
	action.sa_sigaction = say_the_fault;
	action.sa_flags = SA_SIGINFO | SA_RESETHAND;
	sigaction(SIGSEGV, &action, NULL);
	sigaction(SIGBUS, &action, NULL);
	sigaction(SIGABRT, &action, NULL);
	sigaction(SIGILL, &action, NULL);
	sigaction(SIGTRAP, &action, NULL);
}

static void
window_server_hooks(void)
{
	orig_renderer = replace_virtual("renderer", VSLOT(VT_EAGL_SERVER, 0x1a0), EXPECT_RENDERER, my_renderer);
	orig_render_update = replace_virtual("render_update", VSLOT(VT_EAGL_SERVER, 0x178), EXPECT_RENDER_UPDATE,
	    my_render_update);
	orig_function_supported = replace_virtual("function_supported", VSLOT(VT_GLES_CONTEXT, 0x378),
	    EXPECT_FUNCTION_SUPP, my_function_supported);
	if (gl_function_values != NULL) {
		orig_function_uniform = replace_virtual("function_uniform", VSLOT(VT_GLES_CONTEXT, 0x388),
		    EXPECT_FUNCTION_UNIF, my_function_uniform);
	}
	orig_compile_shader = (uintptr_t (*)(void *, const char *))replace_virtual("compile_shader",
	    VSLOT(VT_GLES_CONTEXT, 0x060), EXPECT_COMPILE_SHADER, my_compile_shader);
	say("hakios: window server hooks %s\n", orig_renderer && orig_render_update && orig_function_supported &&
	    orig_compile_shader ? "installed" : "INCOMPLETE (see above; GL still loaded)");
}

/* ---- gates ------------------------------------------------------------------------------------- */

static int
env_on(const char *name)
{
	const char *value = getenv(name);

	return value != NULL && *value != 0 && strcmp(value, "0") != 0;
}

/*
 * backboardd started more than `tries` times in this boot: a crash loop (it is KeepAlive), and
 * the shim is the first suspect. The count is per boot session, so the next boot tries again.
 */
static int
crash_looping(void)
{
	char session[64] = "", line[128], previous[64] = "";
	size_t size = sizeof(session) - 1;
	const char *argument = blog_bootarg("blueeagl_tries");
	unsigned tries = argument != NULL ? (unsigned)strtoul(argument, NULL, 10) : 3, count = 0;
	int fd;
	ssize_t n;

	if (tries == 0) {
		return 0;                       /* blueeagl_tries=0: no limit */
	}
	if (sysctlbyname("kern.bootsessionuuid", session, &size, NULL, 0) != 0 || session[0] == 0) {
		struct timeval boot;

		size = sizeof(boot);
		if (sysctlbyname("kern.boottime", &boot, &size, NULL, 0) != 0) {
			return 0;
		}
		snprintf(session, sizeof(session), "boot-%ld", (long)boot.tv_sec);
	}
	if ((fd = open(STARTS_FILE, O_RDWR | O_CREAT | O_CLOEXEC, 0644)) < 0) {
		say("can't open %s (errno %d): no crash counter\n", STARTS_FILE, errno);
		return 0;
	}
	if ((n = read(fd, line, sizeof(line) - 1)) > 0) {
		line[n] = 0;
		if (sscanf(line, "%63s %u", previous, &count) != 2 || strcmp(previous, session) != 0) {
			count = 0;
		}
	}
	count++;
	n = snprintf(line, sizeof(line), "%s %u\n", session, count);
	if (pwrite(fd, line, (size_t)n, 0) != n || ftruncate(fd, n) != 0) {
		say("can't write %s (errno %d)\n", STARTS_FILE, errno);
	}
	close(fd);
	if (count > tries) {
		say("OFF: backboardd start %u in this boot, more than blueeagl_tries=%u (crash loop?); "
		    "rm %s or reboot to try again\n", count, tries, STARTS_FILE);
		return 1;
	}
	say("backboardd start %u of at most %u in this boot\n", count, tries);
	return 0;
}

static int
gpu_present(void)
{
	io_service_t gpu = IOServiceGetMatchingService(kIOMainPortDefault, IOServiceMatching(BLUEGPU_SERVICE));
	io_connect_t connection = 0;
	if (!gpu) return 0;
	kern_return_t result = IOServiceOpen(gpu, mach_task_self(), BLUE_GPU_UC_TYPE, &connection);
	IOObjectRelease(gpu);
	if (result != KERN_SUCCESS) return 0;
	const uint32_t params[] = {BLUE_GPU_PARAM_GPU_ID, BLUE_GPU_PARAM_CHIP_ID, BLUE_GPU_PARAM_GMEM_SIZE};
	const uint64_t expected[] = {LEMON_GPU_ID, LEMON_GPU_CHIP_ID, LEMON_GPU_GMEM_SIZE};
	int ready = 1;
	for (unsigned i = 0; i < 3; i++) {
		struct blue_gpu_param param = {.pipe = BLUE_GPU_PIPE_3D0, .param = params[i]};
		size_t size = sizeof(param);
		result = IOConnectCallStructMethod(connection, BLUE_GPU_SEL_GET_PARAM,
		    &param, sizeof(param), &param, &size);
		if (result != KERN_SUCCESS || size != sizeof(param) || param.value != expected[i]) {
			ready = 0;
			break;
		}
	}
	IOServiceClose(connection);
	return ready;
}

/* boot-arg caenv=NAME=VALUE (repeatable): into this process's environment */
static void
ca_environment(void)
{
	const char *arguments = blog_bootargs();

	for (const char *argument = arguments; (argument = strstr(argument, "caenv=")) != NULL; argument += 6) {
		char setting[128];
		size_t length = strcspn(argument + 6, " ");
		char *equals;

		if ((argument != arguments && argument[-1] != ' ') || length == 0 || length >= sizeof(setting)) {
			continue;
		}
		memcpy(setting, argument + 6, length);
		setting[length] = 0;
		if ((equals = strchr(setting, '=')) != NULL) {
			*equals = 0;
			/* a fraction is written 0p25: the boot-args lose what follows a "." of a number */
			for (char *point = equals + 1; *point != 0; point++) {
				if (*point == 'p' && point > equals + 1 && point[-1] >= '0' && point[-1] <= '9' &&
				    point[1] >= '0' && point[1] <= '9') {
					*point = '.';
					break;
				}
			}
			setenv(setting, equals + 1, 1);
			say("caenv: %s=%s\n", setting, equals + 1);
		}
	}
}

/* The GL library: beside this one (dladdr), or $BLUEEAGL_GL */
static void *
load_gl(void)
{
	char path[1024];
	const char *forced = getenv("BLUEEAGL_GL");
	Dl_info self;
	void *library;

	if (forced != NULL && *forced != 0) {
		snprintf(path, sizeof(path), "%s", forced);
	} else if (dladdr((const void *)load_gl, &self) != 0 && self.dli_fname != NULL && strrchr(self.dli_fname, '/') != NULL) {
		snprintf(path, sizeof(path), "%.*s/%s", (int)(strrchr(self.dli_fname, '/') - self.dli_fname), self.dli_fname,
		    GL_LIBRARY);
	} else {
		snprintf(path, sizeof(path), "/usr/lib/%s", GL_LIBRARY);
	}
	say("loading %s\n", path);
	if ((library = dlopen(path, RTLD_NOW | RTLD_LOCAL)) == NULL) {
		say("OFF: %s\n", dlerror());
	}
	return library;
}

__attribute__((constructor)) static void
blueeagl_init(void)
{
	const char *name = getprogname(), *off = NULL;
	int window_server = name != NULL && strcmp(name, "backboardd") == 0;
	int forced = env_on("BLUEEAGL_FORCE");
	size_t length = 0;
	const void *cache = _dyld_get_shared_cache_range(&length);
	const char *argument;
	void *library;

	if (!window_server && !forced && (name == NULL || strcmp(name, "eagl-test") != 0)) {
		return;                         /* not ours to touch */
	}
	say("blueeagl in %s pid %d (%s)\n", name, getpid(), forced ? "BLUEEAGL_FORCE" : "by name");
	/* the kill switches, before anything else is done */
	if (env_on("BLUEEAGL_OFF")) {
		off = "environment BLUEEAGL_OFF";
	} else if ((argument = blog_bootarg("blueeagl")) != NULL && argument[0] == '0') {
		off = "boot-arg blueeagl=0";
	} else if (access(KILL_FILE, F_OK) == 0) {
		off = "file " KILL_FILE;
	} else if (window_server && crash_looping()) {
		off = "crash counter";
	} else if (!forced && !gpu_present()) {
		off = "missing or incompatible " BLUEGPU_SERVICE " service";
	}
	if (off != NULL) {
		say("OFF (%s): CoreAnimation keeps its software renderer\n", off);
		return;
	}
	if (cache != NULL) {
		slide = (uintptr_t)cache - CACHE_BASE;
	}
	if (window_server) {
		/* As flame: without this the window server's framebuffer is 'b3a8' (BGRA10_XR, 2 planes), which
		 * attachImage can't render into; CA reads the key when it makes its display, after this. */
		CFPreferencesSetAppValue(CFSTR("CAEnableDeepFramebuffer"), kCFBooleanFalse, kCFPreferencesCurrentApplication);
		/* Mesa's needs on this kernel (no UBWC, sysmem rendering) unless glenv= says otherwise:
		 * saves 34 bytes of the 607-byte boot command line. */
		setenv("FD_MESA_DEBUG", "noubwc,sysmem", 0);
		/* Mesa's disk shader cache (built with -Dshader-cache=enabled): a shader is compiled
		 * once per phone instead of at its first use in every boot, which is what made the
		 * 100-150 ms frames when an app or effect appeared for the first time. */
		setenv("MESA_SHADER_CACHE_DIR", "/private/var/mobile/Library/Caches/bluegl", 0);
		say("CAEnableDeepFramebuffer = NO for %s\n", name);
		ca_environment();
		compile_shaders_said = strstr(blog_bootargs(), "glcompile=1") != NULL;
		watch_for_faults();
	}
	if ((library = load_gl()) == NULL) {
		return;
	}
	gl_function_values = (void (*)(void *, unsigned, unsigned, size_t, size_t, const float *))dlsym(library,
	    "hakios_gl_function_values");
	gl_function_refused = (void (*)(unsigned))dlsym(library, "hakios_gl_function_refused");
	if (window_server) {
		if (cache == NULL) {
			say("no shared cache range: window server hooks left out\n");
		} else {
			window_server_hooks();
		}
	}
	say("ON in %s: EAGLContext is ours (cache slide %#lx)\n", name, slide);
}
