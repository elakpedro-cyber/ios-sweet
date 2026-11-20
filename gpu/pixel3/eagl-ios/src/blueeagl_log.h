/*
 * blueeagl_log.h - the log of blueeagl.dylib and blueeagl-gl.dylib: lines "BLUEEAGL: ..." on
 * /dev/console (devfs makes it 0622, so backboardd, which runs as mobile, can write it; the kernel
 * puts what is written there into the persistent log ring that tools/phone.sh log pulls).
 *
 * Rate limited, because a window server that logs every frame slows itself down and floods the
 * ring: at most RATE lines a second (default 60), the rest counted and reported as one line when
 * the next second begins. Boot-arg blueeagl_lograte=N sets N (0: no limit, for gltrace= runs).
 * Environment BLUEEAGL_LOG=stderr writes to fd 2 instead (the Mac host test; eagl-test under
 * bluerun gets its own lines on stdout and the shim's on the console either way).
 *
 * A line that starts with HackiOS's "hakios-gl: " or "hakios: " loses that prefix (eagl.c and
 * inject.c keep their strings as upstream has them, to keep the port diffable).
 *
 * Header-only, everything static: each dylib has its own copy and exports nothing.
 *
 * Copyright (c) 2026 pixel3-ios. MIT licence.
 */
#ifndef BLUEEAGL_LOG_H
#define BLUEEAGL_LOG_H

#include <fcntl.h>
#include <pthread.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/sysctl.h>
#include <time.h>
#include <unistd.h>

#define BLUEEAGL_PREFIX "BLUEEAGL: "

static pthread_mutex_t blog_lock = PTHREAD_MUTEX_INITIALIZER;
static int blog_fd = -1;
static int blog_ready;
static unsigned blog_rate = 60;                 /* lines a second; 0: unlimited */
static time_t blog_second;
static unsigned blog_lines, blog_dropped;

/* The kernel's boot-args (sysctl kern.bootargs), or "" */
static const char *
blog_bootargs(void)
{
	static char arguments[1024];
	static int read_them;

	if (!read_them) {
		size_t size = sizeof(arguments) - 1;

		read_them = 1;
		if (sysctlbyname("kern.bootargs", arguments, &size, NULL, 0) != 0) {
			arguments[0] = 0;
		}
	}
	return arguments;
}

/* Value of boot-arg NAME (a whole word: "blueeagl" does not match "xblueeagl"), or NULL */
static const char *
blog_bootarg(const char *name)
{
	const char *arguments = blog_bootargs(), *at = arguments;
	size_t length = strlen(name);

	while ((at = strstr(at, name)) != NULL) {
		if ((at == arguments || at[-1] == ' ') && at[length] == '=') {
			return at + length + 1;
		}
		at += length;
	}
	return NULL;
}

static void
blog_open(void)
{
	const char *where = getenv("BLUEEAGL_LOG"), *rate;

	blog_ready = 1;
	if (where != NULL && strcmp(where, "stderr") == 0) {
		blog_fd = 2;
	} else if ((blog_fd = open("/dev/console", O_WRONLY | O_NOCTTY | O_CLOEXEC)) < 0) {
		blog_fd = 2;
	}
	if ((rate = getenv("BLUEEAGL_LOGRATE")) != NULL || (rate = blog_bootarg("blueeagl_lograte")) != NULL) {
		blog_rate = (unsigned)strtoul(rate, NULL, 10);
	}
}

/* One line (no newline in it), prefixed; called with the lock held. */
static void
blog_line(const char *text, size_t length)
{
	char line[1100];
	size_t n = sizeof(BLUEEAGL_PREFIX) - 1;
	time_t now;

	if (length >= 11 && memcmp(text, "hakios-gl: ", 11) == 0) {
		text += 11, length -= 11;
	} else if (length >= 8 && memcmp(text, "hakios: ", 8) == 0) {
		text += 8, length -= 8;
	}
	if (blog_rate != 0) {
		now = time(NULL);
		if (now != blog_second) {
			if (blog_dropped != 0) {
				int m = snprintf(line, sizeof(line), BLUEEAGL_PREFIX "(%u lines dropped by the rate limit, "
				    "blueeagl_lograte=%u)\n", blog_dropped, blog_rate);
				(void)write(blog_fd, line, (size_t)m);
			}
			blog_second = now;
			blog_lines = blog_dropped = 0;
		}
		if (blog_lines >= blog_rate) {
			blog_dropped++;
			return;
		}
		blog_lines++;
	}
	memcpy(line, BLUEEAGL_PREFIX, n);
	if (length > sizeof(line) - n - 1) {
		length = sizeof(line) - n - 1;
	}
	memcpy(line + n, text, length);
	n += length;
	line[n++] = '\n';
	(void)write(blog_fd, line, n);
}

/* Text of any length, any number of lines: each becomes a log line of its own. */
static void
blog_write(const char *text, size_t length)
{
	pthread_mutex_lock(&blog_lock);
	if (!blog_ready) {
		blog_open();
	}
	while (length > 0) {
		const char *end = memchr(text, '\n', length);
		size_t part = end != NULL ? (size_t)(end - text) : length;

		if (part > 0) {
			blog_line(text, part);
		}
		part += end != NULL;
		text += part;
		length -= part;
	}
	pthread_mutex_unlock(&blog_lock);
}

static void blog(const char *format, ...) __attribute__((format(printf, 1, 2), unused));
static void
blog(const char *format, ...)
{
	char line[1024];
	va_list ap;
	int n;

	va_start(ap, format);
	n = vsnprintf(line, sizeof(line), format, ap);
	va_end(ap);
	if (n < 0) {
		return;
	}
	blog_write(line, (size_t)n < sizeof(line) ? (size_t)n : sizeof(line) - 1);
}

#endif
