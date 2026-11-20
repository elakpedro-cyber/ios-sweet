/*
 * gles-triangle - offscreen GLES 3.0 smoke test for bluegl.dylib (pixel3-ios, stage 6e).
 *
 * Clears a 256x256 RGBA8 FBO to blue, draws one red triangle over its lower-left half, reads the
 * pixels back and checks them against the expected picture (exact except a 1-px band along the
 * diagonal). Prints GL strings, compile/draw times, an FNV-1a checksum of the pixels and
 * "GLES-TRIANGLE: PASS" / "FAIL" for the log grep. Exit status 0 on PASS.
 *
 *   BLUEDRM_DEBUG=1   trace every user-client call (bluedrm)
 *   FD_MESA_DEBUG=... freedreno debug flags (e.g. noubwc,sysmem,msgs)
 *   GLES_TRIANGLE_NO_PIXELS=1  skip the pixel verdict (macOS host build over the fake GPU)
 *
 * Copyright (c) 2026 pixel3-ios. MIT licence.
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#define GL_GLES_PROTOTYPES 1
#include <GLES3/gl3.h>          /* Khronos headers from Mesa's include/ */

#include "bluegl.h"

#define W 256
#define H 256

static double
ms_now(void)
{
	struct timespec t;
	clock_gettime(CLOCK_MONOTONIC_RAW, &t);
	return t.tv_sec * 1e3 + t.tv_nsec / 1e6;
}

static GLuint
shader(GLenum type, const char *src)
{
	GLuint s = glCreateShader(type);
	GLint ok = 0;

	glShaderSource(s, 1, &src, NULL);
	glCompileShader(s);
	glGetShaderiv(s, GL_COMPILE_STATUS, &ok);
	if (!ok) {
		char log[1024] = "";
		glGetShaderInfoLog(s, sizeof(log), NULL, log);
		fprintf(stderr, "shader compile failed: %s\n", log);
		exit(2);
	}
	return s;
}

int
main(void)
{
	static const char *vs =
		"#version 300 es\n"
		"layout(location = 0) in vec2 pos;\n"
		"void main() { gl_Position = vec4(pos, 0.0, 1.0); }\n";
	static const char *fs =
		"#version 300 es\n"
		"precision mediump float;\n"
		"out vec4 color;\n"
		"void main() { color = vec4(1.0, 0.0, 0.0, 1.0); }\n";
	static const GLfloat tri[] = { -1, -1, 1, -1, -1, 1 };
	static uint8_t px[W * H * 4];
	bluegl_context *ctx;
	GLuint fbo, rb, prog, vbo, vao;
	double t0, t_compile, t_draw;
	uint32_t fnv = 2166136261u;
	unsigned wrong = 0, red = 0;
	int r;

	if ((r = bluegl_init()) != 0) {
		printf("GLES-TRIANGLE: FAIL (bluegl_init %d: no BlueGPU user client?)\n", r);
		return 1;
	}
	ctx = bluegl_create_context(3, 0, NULL);
	if (ctx == NULL || !bluegl_make_current(ctx)) {
		printf("GLES-TRIANGLE: FAIL (context)\n");
		return 1;
	}
	printf("GL_VENDOR   %s\nGL_RENDERER %s\nGL_VERSION  %s\nGLSL        %s\n",
	       glGetString(GL_VENDOR), glGetString(GL_RENDERER), glGetString(GL_VERSION),
	       glGetString(GL_SHADING_LANGUAGE_VERSION));

	glGenFramebuffers(1, &fbo);
	glGenRenderbuffers(1, &rb);
	glBindRenderbuffer(GL_RENDERBUFFER, rb);
	glRenderbufferStorage(GL_RENDERBUFFER, GL_RGBA8, W, H);
	glBindFramebuffer(GL_FRAMEBUFFER, fbo);
	glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_RENDERBUFFER, rb);
	if (glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE) {
		printf("GLES-TRIANGLE: FAIL (fbo incomplete)\n");
		return 1;
	}

	t0 = ms_now();
	prog = glCreateProgram();
	glAttachShader(prog, shader(GL_VERTEX_SHADER, vs));
	glAttachShader(prog, shader(GL_FRAGMENT_SHADER, fs));
	glLinkProgram(prog);
	glUseProgram(prog);
	t_compile = ms_now() - t0;

	glGenVertexArrays(1, &vao);
	glBindVertexArray(vao);
	glGenBuffers(1, &vbo);
	glBindBuffer(GL_ARRAY_BUFFER, vbo);
	glBufferData(GL_ARRAY_BUFFER, sizeof(tri), tri, GL_STATIC_DRAW);
	glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 0, 0);
	glEnableVertexAttribArray(0);

	t0 = ms_now();
	glViewport(0, 0, W, H);
	glClearColor(0, 0, 1, 1);
	glClear(GL_COLOR_BUFFER_BIT);
	glDrawArrays(GL_TRIANGLES, 0, 3);
	glReadPixels(0, 0, W, H, GL_RGBA, GL_UNSIGNED_BYTE, px);    /* (implies a finish) */
	t_draw = ms_now() - t0;

	for (int y = 0; y < H; y++) {
		for (int x = 0; x < W; x++) {
			const uint8_t *p = &px[(y * W + x) * 4];
			int d = x + y - (W - 1);        /* < 0: inside the triangle (pixel centres) */
			int is_red = p[0] == 255 && p[1] == 0 && p[2] == 0 && p[3] == 255;
			int is_blue = p[0] == 0 && p[1] == 0 && p[2] == 255 && p[3] == 255;
			red += is_red;
			if ((d < -1 && !is_red) || (d > 1 && !is_blue) || (!is_red && !is_blue))
				wrong++;
		}
	}
	for (unsigned i = 0; i < sizeof(px); i++)
		fnv = (fnv ^ px[i]) * 16777619u;

	printf("compile+link %.2f ms, clear+draw+readback %.2f ms\n", t_compile, t_draw);
	printf("pixels: %u red of %u, %u wrong, fnv1a 0x%08x, glGetError 0x%x\n", red, W * H, wrong, fnv,
	       glGetError());
	if (getenv("GLES_TRIANGLE_NO_PIXELS")) {
		/* (macOS host run against fake/fake_bluegpu.c: nothing executes, pixels stay 0) */
		printf("GLES-TRIANGLE: PASS (pixels not checked: fake GPU)\n");
		wrong = 0;
	} else {
		printf("GLES-TRIANGLE: %s\n", wrong == 0 && red > W * H / 2 - W && red < W * H / 2 + W ? "PASS" : "FAIL");
	}

	bluegl_make_current(NULL);
	bluegl_destroy_context(ctx);
	return wrong == 0 ? 0 : 1;
}
