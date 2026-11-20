/*
 * bluegl.c - minimal Mesa (26.3) GL frontend for Darwin/iOS: freedreno screen over bluedrm, GLES
 * contexts made current surfaceless. Mesa 25.1 removed OSMesa, which HakiOS (Mesa 25.0.7) used;
 * this is the small part of it we need, written against st_api_* directly.
 *
 * The IOSurface-as-EGLImage hook follows HakiOS tools/mesa/freedreno-darwin.patch
 * (osmesa_st_get_egl_image / osmesa_surface_resource), Copyright (c) 2025-2026 the HakiOS
 * authors, MIT License (../LICENSES/HakiOS-MIT.txt).
 *
 * Copyright (c) 2026 pixel3-ios. MIT licence.
 */
#include <errno.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "pipe/p_context.h"
#include "pipe/p_screen.h"
#include "pipe/p_state.h"
#include "frontend/api.h"
#include "frontend/winsys_handle.h"
#include "state_tracker/st_context.h"
#include "glapi/glapi.h"
#include "util/u_debug.h"
#include "util/u_memory.h"
#include "util/xmlconfig.h"
#include "util/driconf.h"
#include "freedreno/drm/freedreno_drm_public.h"

#include <xf86drm.h>
#include "blue_gpu_uapi.h"
#include "bluegl.h"

#define EXPORT __attribute__((visibility("default")))

struct bluegl_context {
	struct st_context *st;
};

static pthread_once_t init_once = PTHREAD_ONCE_INIT;
static int init_result = -ENODEV;
static int gpu_fd = -1;
static struct pipe_frontend_screen *fscreen;

static const driOptionDescription bluegl_driconf[] = {
#include "pipe-loader/driinfo_gallium.h"
#include "freedreno/driinfo_freedreno.h"
};

/* glEGLImageTarget*OES((GLeglImageOES)(uintptr_t)IOSurfaceID): the surface's pages as a texture */
static struct pipe_resource *
iosurface_resource(struct pipe_screen *screen, uint32_t surface)
{
	struct blue_gpu_iosurface s = { .surface = surface };
	struct pipe_resource templ = {
		.target = PIPE_TEXTURE_2D,
		.format = PIPE_FORMAT_B8G8R8A8_UNORM,
		.depth0 = 1,
		.array_size = 1,
		.bind = PIPE_BIND_SAMPLER_VIEW | PIPE_BIND_RENDER_TARGET,
	};
	struct winsys_handle handle = { .type = WINSYS_HANDLE_TYPE_FD };

	if (gpu_fd < 0 || bluedrm_iosurface_describe(gpu_fd, &s) != 0)
		return NULL;
	if (s.pixel_format != 0x42475241 /* 'BGRA' */ || s.planes != 0 || (s.row_bytes & 3) != 0)
		return NULL;    /* (the EAGL shim copies through a staging texture instead) */
	templ.width0 = s.width;
	templ.height0 = s.height;
	handle.handle = surface;        /* drmPrimeFDToHandle() imports by IOSurface ID */
	handle.stride = s.row_bytes;
	handle.offset = s.offset;
	handle.size = (s.size + 0xfffull) & ~0xfffull;     /* (whole 4 KiB pages: bluedrm_import_size) */
	handle.modifier = 0;            /* DRM_FORMAT_MOD_LINEAR */
	return screen->resource_from_handle(screen, &templ, &handle, 0);
}

static bool
get_egl_image(struct pipe_frontend_screen *fs, void *image, struct st_egl_image *out)
{
	memset(out, 0, sizeof(*out));
	out->texture = iosurface_resource(fs->screen, (uint32_t)(uintptr_t)image);
	if (!out->texture)
		return false;
	out->format = out->texture->format;
	return true;
}

static bool
validate_egl_image(struct pipe_frontend_screen *fs, void *image)
{
	(void)fs;
	return (uintptr_t)image != 0;
}

static void
do_init(void)
{
	static driOptionCache info, cache;
	static struct pipe_screen_config config;
	struct pipe_screen *screen;

	gpu_fd = drmOpenWithType("msm", NULL, DRM_NODE_RENDER);
	if (gpu_fd < 0) {
		init_result = -ENODEV;
		return;
	}
	driParseOptionInfo(&info, bluegl_driconf, ARRAY_SIZE(bluegl_driconf));
	driParseConfigFiles(&cache, &info, &(driConfigFileParseParams){ .driverName = "msm" });

	config.options = &cache;
	config.options_info = &info;
	screen = fd_drm_screen_create_renderonly(gpu_fd, NULL, &config);
	if (screen == NULL) {
		init_result = -ENODEV;
		return;
	}
	fscreen = CALLOC_STRUCT(pipe_frontend_screen);
	fscreen->screen = screen;
	fscreen->get_egl_image = get_egl_image;
	fscreen->validate_egl_image = validate_egl_image;
	init_result = 0;
}

EXPORT int
bluegl_init(void)
{
	pthread_once(&init_once, do_init);
	return init_result;
}

EXPORT bluegl_context *
bluegl_create_context(int major, int minor, bluegl_context *share)
{
	struct st_context_attribs attribs;
	enum st_context_error error = ST_CONTEXT_SUCCESS;
	bluegl_context *ctx;

	if (bluegl_init() != 0)
		return NULL;
	ctx = calloc(1, sizeof(*ctx));
	if (ctx == NULL)
		return NULL;
	memset(&attribs, 0, sizeof(attribs));
	attribs.profile = API_OPENGLES2;        /* (ES 2.0 .. 3.2 by version) */
	attribs.major = major;
	attribs.minor = minor;
	attribs.visual.color_format = PIPE_FORMAT_NONE; /* surfaceless: no window-system buffers */
	attribs.visual.depth_stencil_format = PIPE_FORMAT_NONE;
	attribs.visual.accum_format = PIPE_FORMAT_NONE;
	ctx->st = st_api_create_context(fscreen, &attribs, &error, share ? share->st : NULL);
	if (ctx->st == NULL) {
		fprintf(stderr, "bluegl: st_api_create_context(ES %d.%d): error %d\n", major, minor, error);
		free(ctx);
		return NULL;
	}
	return ctx;
}

EXPORT bool
bluegl_make_current(bluegl_context *ctx)
{
	return st_api_make_current(ctx ? ctx->st : NULL, NULL, NULL);
}

EXPORT void
bluegl_destroy_context(bluegl_context *ctx)
{
	if (ctx == NULL)
		return;
	if (st_api_get_current() == ctx->st)
		st_api_make_current(NULL, NULL, NULL);
	st_destroy_context(ctx->st);
	free(ctx);
}

EXPORT void (*bluegl_get_proc_address(const char *name))(void)
{
	return (void (*)(void))_mesa_glapi_get_proc_address(name);
}

EXPORT bool
bluegl_iosurface_importable(uint32_t iosurface_id)
{
	struct blue_gpu_iosurface s = { .surface = iosurface_id };

	return bluegl_init() == 0 && bluedrm_iosurface_describe(gpu_fd, &s) == 0 &&
	       s.pixel_format == 0x42475241 && s.planes == 0 && (s.row_bytes & 3) == 0;   /* (any pitch: patch 0005) */
}
