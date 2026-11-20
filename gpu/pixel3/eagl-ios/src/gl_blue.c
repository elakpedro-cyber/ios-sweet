/*
 * gl_blue.c - the OpenGL ES library behind eagl.c on the Pixel 3 iOS port: Mesa 26.3.1 freedreno
 * (Adreno 630) in /usr/lib/bluegl.dylib, reached through mesa-ios/frontend/bluegl.h.
 *
 * Takes the place of HackiOS's src/gl_osmesa.c (the "one implementation" of hakios.gl.h); same
 * five functions, same contract. The IOSurface-as-texture call keeps HackiOS's convention, which
 * bluegl.dylib also follows: the EGLImage handle is the IOSurfaceID, and the kernel's BlueGPU
 * user client (selector 0x7e) makes a GPU buffer of the surface's own pages.
 *
 * Port: Copyright (c) 2026 pixel3-ios. Derived from HackiOS userland/src/gl_osmesa.c,
 * Copyright (c) 2025-2026 the HakiOS authors (commit 63fc2b46). MIT licence: see
 * ../LICENSES/HakiOS-MIT.txt.
 */
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#include "bluegl.h"
#include "hakios.gl.h"

#define GL_TEXTURE_2D   0x0de1
#define GL_RENDERER     0x1f01

extern const unsigned char *glGetString(unsigned name);
extern unsigned glGetError(void);

struct hakios_gl {
	bluegl_context *context;
};

struct hakios_gl *
hakios_gl_create(int version)
{
	struct hakios_gl *gl;

	if (version < 2 || version > 3 || bluegl_init() != 0) {
		return NULL;
	}
	gl = calloc(1, sizeof(*gl));
	if (gl != NULL && (gl->context = bluegl_create_context(version, 0, NULL)) == NULL) {
		free(gl);
		gl = NULL;
	}
	return gl;
}

int
hakios_gl_make_current(struct hakios_gl *gl)
{
	return bluegl_make_current(gl != NULL ? gl->context : NULL);
}

void
hakios_gl_destroy(struct hakios_gl *gl)
{
	if (gl == NULL) {
		return;
	}
	bluegl_destroy_context(gl->context);
	free(gl);
}

const char *
hakios_gl_library(void)
{
	return "Mesa freedreno over BlueGPU (bluegl.dylib)";
}

/*
 * OES_EGL_image with the IOSurface's ID as the image (mesa-ios frontend/bluegl.c get_egl_image).
 * Only when the kernel says it can import the surface (BGRA, one plane, rows a multiple of 64
 * bytes): otherwise eagl.c copies through an ordinary texture. Environment BLUEEAGL_COPY=1 (or
 * eagl.c's glcopy=1 boot-arg) forces the copy path, to tell a coherence problem from a draw one.
 */
int
hakios_gl_surface_texture(struct hakios_gl *gl, uint32_t surface)
{
	static void (*image_target)(unsigned target, void *image);
	static int asked, never;

	(void)gl;
	if (!asked) {
		const char *copy = getenv("BLUEEAGL_COPY");

		asked = 1;
		image_target = (void (*)(unsigned, void *))bluegl_get_proc_address("glEGLImageTargetTexture2DOES");
		never = copy != NULL && *copy != 0 && *copy != '0';
	}
	if (image_target == NULL || never || !bluegl_iosurface_importable(surface)) {
		return 0;
	}
	while (glGetError() != 0) {
	}
	image_target(GL_TEXTURE_2D, (void *)(uintptr_t)surface);
	return glGetError() == 0;
}
