/*
 * host_eaglcontext.h - Mac host test only: a stand-in for OpenGLES.framework's EAGLContext
 * class (host_eaglcontext.m), registered before main so blueeagl-gl.dylib has a class to replace.
 *
 * Copyright (c) 2026 pixel3-ios. MIT licence.
 */
#ifndef HOST_EAGLCONTEXT_H
#define HOST_EAGLCONTEXT_H

/* What OpenGLES's exported gl* trampolines would use on this thread: tls[30] + 0x20 (NULL: none) */
void **host_current_table(void);

#endif
