/*
 * eagl-test - the EAGL shim (blueeagl.dylib + blueeagl-gl.dylib over bluegl.dylib) driven the
 * way CoreAnimation drives it, before backboardd is touched (stage 6f, step 4).
 *
 * It loads /usr/lib/blueeagl.dylib with dlopen (as DYLD_INSERT_LIBRARIES would; the library lets
 * a program named eagl-test through its gates) and then runs one scene twice:
 *
 *   public   the public API: -[EAGLContext initWithAPI:kEAGLRenderingAPIOpenGLES3],
 *            +setCurrentContext:, +currentContext, -API, OpenGLES's exported gl* functions and
 *            -texImageIOSurface:...plane: (OpenGLES/EAGLIOSurface.h). The render target is
 *            the one private call CA's make_buffer_current() uses, attachImage:toCoreSurface:
 *            invertedRender: (renderbufferStorage:fromDrawable: needs a CAEAGLLayer, which CA's
 *            window server never uses).
 *   ca       exactly CoreAnimation's window-server path: initWithAPI:3 properties:, setParameter
 *            0x260, the function table from -getMacroContextPrivate called as entry(table[0],
 *            ...) at OpenGLES 16.7.16's offsets, texImageIOSurface:...invert:, no
 *            setCurrentContext at all.
 *
 * The scene: a 256x256 BGRA IOSurface (bytesPerRow 1024) pre-filled by the CPU with 0x55, attached
 * as the colour target of an FBO; cleared to magenta; a 64x64 BGRA IOSurface with four coloured
 * quadrants drawn over the middle 128x128 as a textured quad, by a shader in CoreAnimation's
 * dialect (no #version, attribute/varying, sampler2DRect + texture2DRect in pixels, gl_FragColor),
 * which the shim rewrites to GLSL ES 3.00. Then glFlush (CA's frame end: the shim copies or blits
 * into the surface and waits), and two checks:
 *   iosurface  the target IOSurface's memory, read by the CPU under IOSurfaceLock: what the
 *              display would scan out. 0x55 left there means the CPU sees stale cache lines or
 *              the GPU never wrote (coherence, kernel 6d); zeros mean nothing was written.
 *   readpixels glReadPixels of the FBO.
 * plus glGetError() == 0 and, for public, [EAGLContext currentContext] == the context.
 *
 * Output: "EAGL-TEST: ..." lines on stdout (bluerun turns them into BLUERUN: lines), the shim's
 * own on /dev/console as BLUEEAGL: lines; the last line "EAGL-TEST: PASS" (exit 0) or
 * "EAGL-TEST: FAIL (N)" (exit 1).
 *
 *   eagl-test [public|ca|both]          default both
 *   EAGL_TEST_LIB=PATH                  the library to dlopen (default /usr/lib/blueeagl.dylib)
 *   EAGL_TEST_NO_PIXELS=1               pixel checks are reported but do not fail (Mac fake GPU)
 *
 * Built twice by build.sh: for iOS (OpenGLES.framework; the real thing) and with BLUE_HOST for
 * the Mac, where test/host_eaglcontext.m stands in for OpenGLES's EAGLContext class and its gl*
 * trampolines, and bluegl.dylib carries the fake BlueGPU (nothing executes: pixels stay 0).
 *
 * Copyright (c) 2026 pixel3-ios. MIT licence.
 */
#import <Foundation/Foundation.h>
#include <IOSurface/IOSurfaceRef.h>
#include <dlfcn.h>
#include <objc/message.h>
#include <objc/runtime.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifdef BLUE_HOST
typedef uint32_t GLbitfield, GLenum, GLuint;
typedef uint8_t GLboolean, GLubyte;
typedef float GLfloat;
typedef int32_t GLint, GLsizei;
typedef char GLchar;
#include "host_eaglcontext.h"
#else
#import <OpenGLES/EAGL.h>
#import <OpenGLES/EAGLIOSurface.h>
#include <OpenGLES/ES3/gl.h>
/* the one private method CA uses for its render targets (QuartzCore GLESContext::make_buffer_current) */
@interface EAGLContext (BlueTest)
- (BOOL)attachImage:(NSUInteger)target toCoreSurface:(IOSurfaceRef)surface invertedRender:(BOOL)inverted;
@end
#endif

#ifdef BLUE_HOST                /* (on iOS these come from OpenGLES/ES3/gl.h) */
#define GL_TRIANGLE_STRIP       0x0005
#define GL_TEXTURE_2D           0x0de1
#define GL_UNSIGNED_BYTE        0x1401
#define GL_FLOAT                0x1406
#define GL_RGBA                 0x1908
#define GL_VENDOR               0x1f00
#define GL_RENDERER             0x1f01
#define GL_VERSION              0x1f02
#define GL_BLEND                0x0be2
#define GL_SCISSOR_TEST         0x0c11
#define GL_NEAREST              0x2600
#define GL_TEXTURE_MAG_FILTER   0x2800
#define GL_TEXTURE_MIN_FILTER   0x2801
#define GL_TEXTURE_WRAP_S       0x2802
#define GL_TEXTURE_WRAP_T       0x2803
#define GL_CLAMP_TO_EDGE        0x812f
#define GL_TEXTURE0             0x84c0
#define GL_FRAGMENT_SHADER      0x8b30
#define GL_VERTEX_SHADER        0x8b31
#define GL_LINK_STATUS          0x8b82
#define GL_COLOR_BUFFER_BIT     0x4000
#define GL_FRAMEBUFFER          0x8d40
#define GL_COLOR_ATTACHMENT0    0x8ce0
#define GL_FRAMEBUFFER_COMPLETE 0x8cd5
#define GL_PACK_ALIGNMENT       0x0d05
#endif
#ifndef GL_BGRA_EXT
#define GL_BGRA_EXT             0x80e1
#endif

#define DST     256             /* the target: DST x DST, rows of DST * 4 bytes (a multiple of 64) */
#define SRC     64              /* the picture: SRC x SRC */
#define STALE   0x55            /* what the CPU put into the target before the GPU drew */

static int failures, no_pixels;

#define say(...) do { printf("EAGL-TEST: " __VA_ARGS__); fflush(stdout); } while (0)

static void
check(const char *phase, const char *what, int ok, const char *detail)
{
	if (!ok && no_pixels && (strcmp(what, "iosurface") == 0 || strcmp(what, "readpixels") == 0)) {
		say("%s %s SKIP (no GPU behind it: %s)\n", phase, what, detail);
		return;
	}
	say("%s %s %s%s%s\n", phase, what, ok ? "PASS" : "FAIL", detail[0] ? ": " : "", detail);
	failures += !ok;
}

/* ---- the GL calls the scene makes, through whichever door the phase uses ------------------------ */

struct gl {
	void (*GenTextures)(GLsizei, GLuint *);
	void (*BindTexture)(GLenum, GLuint);
	void (*TexParameteri)(GLenum, GLenum, GLint);
	void (*GenFramebuffers)(GLsizei, GLuint *);
	void (*BindFramebuffer)(GLenum, GLuint);
	void (*FramebufferTexture2D)(GLenum, GLenum, GLenum, GLuint, GLint);
	GLenum (*CheckFramebufferStatus)(GLenum);
	void (*Viewport)(GLint, GLint, GLsizei, GLsizei);
	void (*ClearColor)(GLfloat, GLfloat, GLfloat, GLfloat);
	void (*Clear)(GLbitfield);
	GLuint (*CreateShader)(GLenum);
	void (*ShaderSource)(GLuint, GLsizei, const GLchar *const *, const GLint *);
	void (*CompileShader)(GLuint);
	GLuint (*CreateProgram)(void);
	void (*AttachShader)(GLuint, GLuint);
	void (*BindAttribLocation)(GLuint, GLuint, const GLchar *);
	void (*LinkProgram)(GLuint);
	void (*GetProgramiv)(GLuint, GLenum, GLint *);
	void (*UseProgram)(GLuint);
	GLint (*GetUniformLocation)(GLuint, const GLchar *);
	void (*Uniform1i)(GLint, GLint);
	void (*VertexAttribPointer)(GLuint, GLint, GLenum, GLboolean, GLsizei, const void *);
	void (*EnableVertexAttribArray)(GLuint);
	void (*DrawArrays)(GLenum, GLint, GLsizei);
	void (*ReadPixels)(GLint, GLint, GLsizei, GLsizei, GLenum, GLenum, void *);
	void (*PixelStorei)(GLenum, GLint);
	void (*Flush)(void);
	GLenum (*GetError)(void);
	const GLubyte *(*GetString)(GLenum);
	void (*ActiveTexture)(GLenum);
	void (*Disable)(GLenum);
	void (*DeleteTextures)(GLsizei, const GLuint *);
	void (*DeleteFramebuffers)(GLsizei, const GLuint *);
	void (*DeleteProgram)(GLuint);
};

/*
 * The function table as CoreAnimation calls it: entry at byte offset OFF, first argument table[0]
 * (OpenGLES 16.7.16 = HackiOS eagl_slots.txt, verified in stage6f-research.md 2.2). The table is
 * the one -getMacroContextPrivate gave (ca), or on the Mac the one the emulated trampolines find
 * through the _private block (host_eaglcontext.m), the way OpenGLES's exported gl* do on iOS.
 */
static void **table;
#define E(off, type)    ((type)table[(off) / 8])
#define C               (table[0])

static void t_GenTextures(GLsizei n, GLuint *t) { E(0x318, void (*)(void *, GLsizei, GLuint *))(C, n, t); }
static void t_BindTexture(GLenum a, GLuint t) { E(0x030, void (*)(void *, GLenum, GLuint))(C, a, t); }
static void t_TexParameteri(GLenum a, GLenum b, GLint c) { E(0x988, void (*)(void *, GLenum, GLenum, GLint))(C, a, b, c); }
static void t_GenFramebuffers(GLsizei n, GLuint *f) { E(0x1518, void (*)(void *, GLsizei, GLuint *))(C, n, f); }
static void t_BindFramebuffer(GLenum a, GLuint f) { E(0x1508, void (*)(void *, GLenum, GLuint))(C, a, f); }
static void t_FramebufferTexture2D(GLenum a, GLenum b, GLenum c, GLuint t, GLint l)
{ E(0x1530, void (*)(void *, GLenum, GLenum, GLenum, GLuint, GLint))(C, a, b, c, t, l); }
static GLenum t_CheckFramebufferStatus(GLenum a) { return E(0x1520, GLenum (*)(void *, GLenum))(C, a); }
static void t_Viewport(GLint x, GLint y, GLsizei w, GLsizei h) { E(0xa80, void (*)(void *, GLint, GLint, GLsizei, GLsizei))(C, x, y, w, h); }
static void t_ClearColor(GLfloat r, GLfloat g, GLfloat b, GLfloat a)
{ E(0x068, void (*)(void *, GLfloat, GLfloat, GLfloat, GLfloat))(C, r, g, b, a); }
static void t_Clear(GLbitfield m) { E(0x058, void (*)(void *, GLbitfield))(C, m); }
static GLuint t_CreateShader(GLenum t) { return E(0x1298, GLuint (*)(void *, GLenum))(C, t); }
static void t_ShaderSource(GLuint s, GLsizei n, const GLchar *const *t, const GLint *l)
{ E(0x12a0, void (*)(void *, GLuint, GLsizei, const GLchar *const *, const GLint *))(C, s, n, t, l); }
static void t_CompileShader(GLuint s) { E(0x12a8, void (*)(void *, GLuint))(C, s); }
static GLuint t_CreateProgram(void) { return E(0x12b0, GLuint (*)(void *))(C); }
static void t_AttachShader(GLuint p, GLuint s) { E(0x12b8, void (*)(void *, GLuint, GLuint))(C, p, s); }
static void t_BindAttribLocation(GLuint p, GLuint i, const GLchar *n) { E(0x13b8, void (*)(void *, GLuint, GLuint, const GLchar *))(C, p, i, n); }
static void t_LinkProgram(GLuint p) { E(0x12c0, void (*)(void *, GLuint))(C, p); }
static void t_GetProgramiv(GLuint p, GLenum n, GLint *v) { E(0x1498, void (*)(void *, GLuint, GLenum, GLint *))(C, p, n, v); }
static void t_UseProgram(GLuint p) { E(0x12c8, void (*)(void *, GLuint))(C, p); }
static GLint t_GetUniformLocation(GLuint p, const GLchar *n) { return E(0x1390, GLint (*)(void *, GLuint, const GLchar *))(C, p, n); }
static void t_Uniform1i(GLint l, GLint v) { E(0x12f8, void (*)(void *, GLint, GLint))(C, l, v); }
static void t_VertexAttribPointer(GLuint i, GLint s, GLenum t, GLboolean n, GLsizei st, const void *p)
{ E(0x1000, void (*)(void *, GLuint, GLint, GLenum, GLboolean, GLsizei, const void *))(C, i, s, t, n, st, p); }
static void t_EnableVertexAttribArray(GLuint i) { E(0x1008, void (*)(void *, GLuint))(C, i); }
static void t_DrawArrays(GLenum m, GLint f, GLsizei c) { E(0x210, void (*)(void *, GLenum, GLint, GLsizei))(C, m, f, c); }
static void t_ReadPixels(GLint x, GLint y, GLsizei w, GLsizei h, GLenum f, GLenum t, void *p)
{ E(0x770, void (*)(void *, GLint, GLint, GLsizei, GLsizei, GLenum, GLenum, void *))(C, x, y, w, h, f, t, p); }
static void t_PixelStorei(GLenum n, GLint v) { E(0x620, void (*)(void *, GLenum, GLint))(C, n, v); }
static void t_Flush(void) { E(0x2d8, void (*)(void *))(C); }
static GLenum t_GetError(void) { return E(0x338, GLenum (*)(void *))(C); }
static const GLubyte *t_GetString(GLenum n) { return E(0x3b0, const GLubyte *(*)(void *, GLenum))(C, n); }
static void t_ActiveTexture(GLenum u) { E(0xab8, void (*)(void *, GLenum))(C, u); }
static void t_Disable(GLenum c) { E(0x200, void (*)(void *, GLenum))(C, c); }
static void t_DeleteTextures(GLsizei n, const GLuint *t) { E(0x1e0, void (*)(void *, GLsizei, const GLuint *))(C, n, t); }
static void t_DeleteFramebuffers(GLsizei n, const GLuint *f) { E(0x1510, void (*)(void *, GLsizei, const GLuint *))(C, n, f); }
static void t_DeleteProgram(GLuint p) { E(0x1280, void (*)(void *, GLuint))(C, p); }

static const struct gl via_table = {
	t_GenTextures, t_BindTexture, t_TexParameteri, t_GenFramebuffers, t_BindFramebuffer, t_FramebufferTexture2D,
	t_CheckFramebufferStatus, t_Viewport, t_ClearColor, t_Clear, t_CreateShader, t_ShaderSource, t_CompileShader,
	t_CreateProgram, t_AttachShader, t_BindAttribLocation, t_LinkProgram, t_GetProgramiv, t_UseProgram,
	t_GetUniformLocation, t_Uniform1i, t_VertexAttribPointer, t_EnableVertexAttribArray, t_DrawArrays, t_ReadPixels,
	t_PixelStorei, t_Flush, t_GetError, t_GetString, t_ActiveTexture, t_Disable, t_DeleteTextures, t_DeleteFramebuffers,
	t_DeleteProgram,
};

#ifndef BLUE_HOST
/* OpenGLES.framework's exported functions: trampolines through tpidrro_el0[30], i.e. the shim's table */
static const struct gl via_exports = {
	glGenTextures, glBindTexture, glTexParameteri, glGenFramebuffers, glBindFramebuffer, glFramebufferTexture2D,
	glCheckFramebufferStatus, glViewport, glClearColor, glClear, glCreateShader, glShaderSource, glCompileShader,
	glCreateProgram, glAttachShader, glBindAttribLocation, glLinkProgram, glGetProgramiv, glUseProgram,
	glGetUniformLocation, glUniform1i, glVertexAttribPointer, glEnableVertexAttribArray, glDrawArrays, glReadPixels,
	glPixelStorei, glFlush, glGetError, glGetString, glActiveTexture, glDisable, glDeleteTextures, glDeleteFramebuffers,
	glDeleteProgram,
};
#endif

/* ---- EAGLContext: public calls, and CA's private ones -------------------------------------------- */

static id
context_public(void)
{
#ifdef BLUE_HOST
	id c = ((id (*)(id, SEL))objc_msgSend)(objc_getClass("EAGLContext"), sel_registerName("alloc"));
	return ((id (*)(id, SEL, unsigned long))objc_msgSend)(c, sel_registerName("initWithAPI:"), 3);
#else
	return [[EAGLContext alloc] initWithAPI:kEAGLRenderingAPIOpenGLES3];
#endif
}

static BOOL
set_current(id context)
{
#ifdef BLUE_HOST
	return ((BOOL (*)(id, SEL, id))objc_msgSend)(objc_getClass("EAGLContext"), sel_registerName("setCurrentContext:"), context);
#else
	return [EAGLContext setCurrentContext:context];
#endif
}

static id
current_context(void)
{
#ifdef BLUE_HOST
	return ((id (*)(id, SEL))objc_msgSend)(objc_getClass("EAGLContext"), sel_registerName("currentContext"));
#else
	return [EAGLContext currentContext];
#endif
}

static unsigned long
api_of(id context)
{
	return ((unsigned long (*)(id, SEL))objc_msgSend)(context, sel_registerName("API"));
}

/* the public texImageIOSurface (no invert:), which OpenGLES forwards to the invert: one with NO */
static BOOL
tex_image_public(id context, IOSurfaceRef surface)
{
	return ((BOOL (*)(id, SEL, IOSurfaceRef, NSUInteger, NSUInteger, uint32_t, uint32_t, NSUInteger, NSUInteger, uint32_t))
	    objc_msgSend)(context, sel_registerName("texImageIOSurface:target:internalFormat:width:height:format:type:plane:"),
	    surface, GL_TEXTURE_2D, GL_RGBA, SRC, SRC, GL_BGRA_EXT, GL_UNSIGNED_BYTE, 0);
}

/* CA's: GLESContext::create_surface_from_iosurface -> ...plane:invert: (GL_RGBA, GL_BGRA_EXT, UNSIGNED_BYTE, 0, NO) */
static BOOL
tex_image_ca(id context, IOSurfaceRef surface)
{
	return ((BOOL (*)(id, SEL, IOSurfaceRef, NSUInteger, NSUInteger, uint32_t, uint32_t, NSUInteger, NSUInteger, uint32_t, BOOL))
	    objc_msgSend)(context,
	    sel_registerName("texImageIOSurface:target:internalFormat:width:height:format:type:plane:invert:"),
	    surface, GL_TEXTURE_2D, GL_RGBA, SRC, SRC, GL_BGRA_EXT, GL_UNSIGNED_BYTE, 0, NO);
}

static BOOL
attach(id context, IOSurfaceRef surface)
{
	return ((BOOL (*)(id, SEL, NSUInteger, IOSurfaceRef, BOOL))objc_msgSend)(context,
	    sel_registerName("attachImage:toCoreSurface:invertedRender:"), GL_TEXTURE_2D, surface, NO);
}

/* ---- the surfaces ------------------------------------------------------------------------------- */

static IOSurfaceRef
surface_new(int size, uint8_t fill)
{
	int row = size * 4;
	NSDictionary *properties = @{
		(id)kIOSurfaceWidth: @(size), (id)kIOSurfaceHeight: @(size), (id)kIOSurfaceBytesPerElement: @4,
		(id)kIOSurfaceBytesPerRow: @(row), (id)kIOSurfaceAllocSize: @(row * size),
		(id)kIOSurfacePixelFormat: @((uint32_t)'BGRA'),
	};
	IOSurfaceRef surface = IOSurfaceCreate((__bridge CFDictionaryRef)properties);

	if (surface != NULL && IOSurfaceLock(surface, 0, NULL) == 0) {
		memset(IOSurfaceGetBaseAddress(surface), fill, IOSurfaceGetBytesPerRow(surface) * (size_t)size);
		IOSurfaceUnlock(surface, 0, NULL);
	}
	return surface;
}

/* The picture's quadrant colours, RGBA, by (u >= SRC/2) + 2 * (v >= SRC/2), v = memory row */
static const uint8_t quadrant[4][4] = {
	{ 255, 0, 0, 255 }, { 0, 255, 0, 255 }, { 0, 0, 255, 255 }, { 255, 255, 255, 255 },
};
static const uint8_t magenta[4] = { 255, 0, 255, 255 };

static void
picture_fill(IOSurfaceRef surface)
{
	uint8_t *base;
	size_t row = IOSurfaceGetBytesPerRow(surface);

	IOSurfaceLock(surface, 0, NULL);
	base = IOSurfaceGetBaseAddress(surface);
	for (int v = 0; v < SRC; v++) {
		for (int u = 0; u < SRC; u++) {
			const uint8_t *c = quadrant[(u >= SRC / 2) + 2 * (v >= SRC / 2)];
			uint8_t *p = base + row * (size_t)v + 4 * (size_t)u;

			p[0] = c[2], p[1] = c[1], p[2] = c[0], p[3] = c[3];     /* BGRA in memory */
		}
	}
	IOSurfaceUnlock(surface, 0, NULL);
}

/* What (x, y) of the target must be, RGBA; y is GL's row = the texture's row = the surface's memory row */
static const uint8_t *
expected(int x, int y)
{
	int lo = (DST - 2 * SRC) / 2, hi = lo + 2 * SRC;

	if (x < lo || x >= hi || y < lo || y >= hi) {
		return magenta;
	}
	return quadrant[((x - lo) / 2 >= SRC / 2) + 2 * ((y - lo) / 2 >= SRC / 2)];
}

/* Compare DST x DST pixels; `bgra`: memory order of the surface, else glReadPixels' RGBA */
static void
compare(const char *phase, const char *what, const uint8_t *pixels, size_t row, int bgra)
{
	unsigned wrong = 0, stale = 0, zero = 0, shown = 0;
	uint32_t hash = 2166136261u;
	char detail[300] = "";

	for (int y = 0; y < DST; y++) {
		for (int x = 0; x < DST; x++) {
			const uint8_t *p = pixels + row * (size_t)y + 4 * (size_t)x, *want = expected(x, y);
			uint8_t got[4] = { p[bgra ? 2 : 0], p[1], p[bgra ? 0 : 2], p[3] };
			int bad = 0;

			for (int i = 0; i < 4; i++) {
				bad |= got[i] > want[i] + 2 || got[i] + 2 < want[i];
				hash = (hash ^ got[i]) * 16777619u;
			}
			stale += p[0] == STALE && p[1] == STALE && p[2] == STALE && p[3] == STALE;
			zero += (p[0] | p[1] | p[2] | p[3]) == 0;
			if (bad && shown++ < 4) {
				say("%s %s: (%d,%d) is %u,%u,%u,%u, not %u,%u,%u,%u (RGBA)\n", phase, what, x, y, got[0], got[1],
				    got[2], got[3], want[0], want[1], want[2], want[3]);
			}
			wrong += bad;
		}
	}
	snprintf(detail, sizeof(detail), "%u of %u pixels wrong (%u still the CPU's 0x%02x, %u zero), fnv %08x%s", wrong,
	    DST * DST, stale, STALE, zero, hash,
	    stale > (unsigned)(DST * DST / 2) ? " -- STALE: the CPU sees its own old data (6d coherence: clean+invalidate "
	    "at import, invalidate at CPU_PREP/IOSurface lock) or the GPU never wrote" :
	    zero > (unsigned)(DST * DST / 2) ? " -- ZERO: nothing reached the surface" : "");
	check(phase, what, wrong == 0, detail);
}

/* ---- the scene ---------------------------------------------------------------------------------- */

/* in CoreAnimation's dialect; blueeagl-gl rewrites both to GLSL ES 3.00 (eagl.c my_glShaderSource) */
static const char vertex_text[] =
    "attribute highp vec4 position;\n"
    "attribute highp vec2 texcoord;\n"
    "varying highp vec2 texcoord0;\n"
    "void main() {\n"
    "  gl_Position = position;\n"
    "  texcoord0 = texcoord;\n"
    "}\n";
static const char fragment_text[] =
    "precision mediump float;\n"
    "uniform lowp sampler2DRect texture0;\n"
    "varying highp vec2 texcoord0;\n"
    "void main() {\n"
    "  gl_FragColor = texture2DRect(texture0, texcoord0);\n"
    "}\n";

static void
scene(const char *phase, id context, const struct gl *gl, BOOL (*tex_image)(id, IOSurfaceRef))
{
	static const GLfloat corners[] = { -0.5f, -0.5f, 0.5f, -0.5f, -0.5f, 0.5f, 0.5f, 0.5f };
	static const GLfloat places[] = { 0, 0, SRC, 0, 0, SRC, SRC, SRC };   /* in the picture's pixels (texture2DRect) */
	IOSurfaceRef target = surface_new(DST, STALE), picture = surface_new(SRC, 0);
	GLuint colour = 0, framebuffer = 0, texture = 0, vs, fs, program;
	const GLchar *text;
	GLint linked = 0, where;
	GLenum status, error;
	uint8_t *read;
	char detail[200];

	if (target == NULL || picture == NULL) {
		check(phase, "iosurfaces", 0, "IOSurfaceCreate failed");
		return;
	}
	picture_fill(picture);
	say("%s: GL_VENDOR %s / GL_RENDERER %s / GL_VERSION %s\n", phase, (const char *)gl->GetString(GL_VENDOR),
	    (const char *)gl->GetString(GL_RENDERER), (const char *)gl->GetString(GL_VERSION));
	say("%s: target IOSurface %u (%dx%d, %zu bytes a row), picture IOSurface %u\n", phase, IOSurfaceGetID(target), DST,
	    DST, IOSurfaceGetBytesPerRow(target), IOSurfaceGetID(picture));

	/* the render target, as CA::OGL::GLESContext::make_buffer_current() makes it */
	gl->GenTextures(1, &colour);
	gl->BindTexture(GL_TEXTURE_2D, colour);
	gl->TexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
	gl->TexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
	gl->TexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
	gl->TexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
	check(phase, "attachImage", attach(context, target), "attachImage:toCoreSurface:invertedRender:");
	gl->GenFramebuffers(1, &framebuffer);
	gl->BindFramebuffer(GL_FRAMEBUFFER, framebuffer);
	gl->FramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, colour, 0);
	status = gl->CheckFramebufferStatus(GL_FRAMEBUFFER);
	snprintf(detail, sizeof(detail), "status %#x", status);
	check(phase, "framebuffer", status == GL_FRAMEBUFFER_COMPLETE, detail);

	/* the picture, as CA::OGL::GLESContext::create_surface_from_iosurface() makes it */
	gl->ActiveTexture(GL_TEXTURE0);
	gl->GenTextures(1, &texture);
	gl->BindTexture(GL_TEXTURE_2D, texture);
	check(phase, "texImageIOSurface", tex_image(context, picture), "");
	gl->TexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
	gl->TexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
	gl->TexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
	gl->TexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);

	/* the program (CA never asks whether it compiled; we do, once, through GetProgramiv) */
	vs = gl->CreateShader(GL_VERTEX_SHADER);
	text = vertex_text;
	gl->ShaderSource(vs, 1, &text, NULL);
	gl->CompileShader(vs);
	fs = gl->CreateShader(GL_FRAGMENT_SHADER);
	text = fragment_text;
	gl->ShaderSource(fs, 1, &text, NULL);
	gl->CompileShader(fs);
	program = gl->CreateProgram();
	gl->AttachShader(program, vs);
	gl->AttachShader(program, fs);
	gl->BindAttribLocation(program, 0, "position");
	gl->BindAttribLocation(program, 1, "texcoord");
	gl->LinkProgram(program);
	gl->GetProgramiv(program, GL_LINK_STATUS, &linked);
	check(phase, "program", linked != 0, "CA-dialect shaders rewritten to GLSL ES 3.00 (BLUEEAGL lines say why if not)");

	/* the frame: clear, one textured quad, glFlush (CA's frame end) */
	gl->Viewport(0, 0, DST, DST);
	gl->Disable(GL_BLEND);
	gl->Disable(GL_SCISSOR_TEST);
	gl->ClearColor(1, 0, 1, 1);
	gl->Clear(GL_COLOR_BUFFER_BIT);
	gl->UseProgram(program);
	where = gl->GetUniformLocation(program, "texture0");
	gl->Uniform1i(where, 0);
	gl->VertexAttribPointer(0, 2, GL_FLOAT, 0, 0, corners);
	gl->VertexAttribPointer(1, 2, GL_FLOAT, 0, 0, places);
	gl->EnableVertexAttribArray(0);
	gl->EnableVertexAttribArray(1);
	gl->DrawArrays(GL_TRIANGLE_STRIP, 0, 4);
	gl->Flush();

	/* what the display would scan out */
	if (IOSurfaceLock(target, kIOSurfaceLockReadOnly, NULL) == 0) {
		compare(phase, "iosurface", IOSurfaceGetBaseAddress(target), IOSurfaceGetBytesPerRow(target), 1);
		IOSurfaceUnlock(target, kIOSurfaceLockReadOnly, NULL);
	} else {
		check(phase, "iosurface", 0, "IOSurfaceLock failed");
	}
	/* what GL says it drew */
	read = calloc(DST * DST, 4);
	gl->BindFramebuffer(GL_FRAMEBUFFER, framebuffer);
	gl->PixelStorei(GL_PACK_ALIGNMENT, 4);
	gl->ReadPixels(0, 0, DST, DST, GL_RGBA, GL_UNSIGNED_BYTE, read);
	compare(phase, "readpixels", read, DST * 4, 0);
	free(read);
	error = gl->GetError();
	snprintf(detail, sizeof(detail), "glGetError %#x", error);
	check(phase, "glerror", error == 0, detail);

	gl->DeleteProgram(program);
	gl->DeleteProgram(vs);          /* (Darwin's table has one entry for programs and shaders) */
	gl->DeleteProgram(fs);
	gl->DeleteFramebuffers(1, &framebuffer);
	gl->DeleteTextures(1, &texture);
	gl->DeleteTextures(1, &colour);
	CFRelease(target);
	CFRelease(picture);
}

static void
phase_public(void)
{
	id context = context_public();
	char detail[100];

	if (context == nil) {
		check("public", "initWithAPI", 0, "[[EAGLContext alloc] initWithAPI:3] is nil");
		return;
	}
	snprintf(detail, sizeof(detail), "API %lu", api_of(context));
	check("public", "initWithAPI", api_of(context) == 3, detail);
	check("public", "setCurrentContext", set_current(context), "");
	check("public", "currentContext", current_context() == context,
	    "[EAGLContext currentContext] reads the _private block (+0); the gl* trampolines read +0x20");
#ifdef BLUE_HOST
	table = host_current_table();   /* what OpenGLES's trampolines would load: tls[30] + 0x20 */
	scene("public", context, &via_table, tex_image_public);
#else
	scene("public", context, &via_exports, tex_image_public);
#endif
	set_current(nil);
	check("public", "currentContext nil", current_context() == nil, "");
	((void (*)(id, SEL))objc_msgSend)(context, sel_registerName("release"));
}

static void
phase_ca(void)
{
	id context = ((id (*)(id, SEL))objc_msgSend)(objc_getClass("EAGLContext"), sel_registerName("alloc"));
	int32_t zero = 0;

	/* CA::WindowServer::EAGLServer::renderer(): API 3 with properties, parameter 0x260 := 0, -API == 3 */
	context = ((id (*)(id, SEL, unsigned long, id))objc_msgSend)(context, sel_registerName("initWithAPI:properties:"), 3, nil);
	if (context == nil) {
		check("ca", "initWithAPI:properties:", 0, "nil");
		return;
	}
	((BOOL (*)(id, SEL, unsigned, const int32_t *))objc_msgSend)(context, sel_registerName("setParameter:to:"), 0x260, &zero);
	check("ca", "API", api_of(context) == 3, "");
	table = ((void **(*)(id, SEL))objc_msgSend)(context, sel_registerName("getMacroContextPrivate"));
	check("ca", "getMacroContextPrivate", table != NULL && table[0] != NULL, "");
	if (table == NULL) {
		return;
	}
	scene("ca", context, &via_table, tex_image_ca);
	((void (*)(id, SEL))objc_msgSend)(context, sel_registerName("release"));
}

int
main(int argc, char **argv)
{
	const char *which = argc > 1 ? argv[1] : "both";
	const char *library = getenv("EAGL_TEST_LIB") ? getenv("EAGL_TEST_LIB") : "/usr/lib/blueeagl.dylib";

	setvbuf(stdout, NULL, _IOLBF, 0);
	no_pixels = getenv("EAGL_TEST_NO_PIXELS") != NULL && strcmp(getenv("EAGL_TEST_NO_PIXELS"), "0") != 0;
	@autoreleasepool {
		Class class = objc_getClass("EAGLContext");
		IMP before = class ? method_getImplementation(class_getInstanceMethod(class,
		    sel_registerName("initWithAPI:properties:"))) : NULL;

		say("loading %s\n", library);
		if (dlopen(library, RTLD_NOW) == NULL) {
			say("%s\n", dlerror());
			say("FAIL (dlopen)\n");
			return 1;
		}
		class = objc_getClass("EAGLContext");
		if (class == Nil || method_getImplementation(class_getInstanceMethod(class,
		    sel_registerName("initWithAPI:properties:"))) == before) {
			say("EAGLContext was not replaced: the shim is off (see the BLUEEAGL: lines for why)\n");
			say("FAIL (shim off)\n");
			return 1;
		}
		if (strcmp(which, "ca") != 0) {
			phase_public();
		}
		if (strcmp(which, "public") != 0) {
			phase_ca();
		}
	}
	if (failures == 0) {
		say("PASS%s\n", no_pixels ? " (pixels not checked)" : "");
	} else {
		say("FAIL (%d)\n", failures);
	}
	return failures != 0;
}
