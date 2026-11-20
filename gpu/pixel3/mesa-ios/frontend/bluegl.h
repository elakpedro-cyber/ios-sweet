/*
 * bluegl.h - the minimal GL frontend of bluegl.dylib (pixel3-ios): Mesa freedreno GLES contexts
 * with no window system. Everything renders into FBOs (that is all EAGL / CoreAnimation needs:
 * the EAGL shim, stage 6f, binds IOSurface-backed renderbuffers/textures as FBO attachments).
 *
 * The gl* entry points are exported by the same dylib (Mesa's glapi bridge) and dispatch to the
 * context made current on the calling thread.
 *
 * Copyright (c) 2026 pixel3-ios. MIT licence.
 */
#ifndef BLUEGL_H
#define BLUEGL_H

#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct bluegl_context bluegl_context;

/* Opens the BlueGPU user client and creates the freedreno screen. 0, or -errno
 * (-ENODEV: no BlueGPU service / not msm-compatible). Idempotent, thread-safe. */
int bluegl_init(void);

/* A GLES context of at least MAJOR.MINOR (2.0 .. 3.2); SHARE may be NULL. NULL on failure. */
bluegl_context *bluegl_create_context(int major, int minor, bluegl_context *share);

/* Binds CTX surfaceless to the calling thread (NULL: release). Draw/read framebuffer 0 is
 * incomplete; render into an FBO. */
bool bluegl_make_current(bluegl_context *ctx);

void bluegl_destroy_context(bluegl_context *ctx);

/* GL / GLES entry point by name (also OES/EXT ones not exported by name). */
void (*bluegl_get_proc_address(const char *name))(void);

/* For the EAGL shim (6f): glEGLImageTargetTexture2DOES / glEGLImageTargetRenderbufferStorageOES
 * accept (GLeglImageOES)(uintptr_t)IOSurfaceID; this reports whether the kernel can import it. */
bool bluegl_iosurface_importable(uint32_t iosurface_id);

#ifdef __cplusplus
}
#endif

#endif
