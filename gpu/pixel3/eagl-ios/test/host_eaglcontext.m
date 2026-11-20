/*
 * host_eaglcontext.m - Mac host test only (build.sh HOST=1): an EAGLContext class shaped like
 * OpenGLES 16.7.16's, for eagl-test to run blueeagl-gl.dylib against without an iPhone.
 *
 * What it imitates is what the shim depends on, read off the 20H392 disassembly
 * (ca-research/OpenGLES, see stage6f-research.md and eagl.c struct eagl_private):
 *   - one ivar, _private, right after isa;
 *   - -initWithAPI: is initWithAPI:properties: with nil; the public texImageIOSurface:...plane:
 *     is the ...plane:invert: one with NO;
 *   - +setCurrentContext: stores _private in thread-specific slot 30 (here a __thread variable,
 *     so as not to touch the Mac's own reserved key), retaining the new context and releasing the
 *     old unless bit 0 of [P+0x18] is set; +currentContext returns [P]; -API reads [P+0x10];
 *   - an exported gl* function calls [P + 0x20 + OFF] with [P + 0x20] first: host_current_table().
 * Darwin's own initialisers fail here (no GL engine), as they would on the phone without the shim.
 *
 * Copyright (c) 2026 pixel3-ios. MIT licence.
 */
#import <Foundation/Foundation.h>
#include <IOSurface/IOSurfaceRef.h>
#include <objc/message.h>
#include <objc/runtime.h>

#include "host_eaglcontext.h"

static __thread void *tls30;

static void *
private_of(id self)
{
	Ivar ivar = class_getInstanceVariable(object_getClass(self), "_private");

	return *(void **)((char *)(__bridge void *)self + ivar_getOffset(ivar));
}

static id
apple_initWithAPI(id self, SEL _cmd, unsigned long api)
{
	(void)_cmd;
	return ((id (*)(id, SEL, unsigned long, id))objc_msgSend)(self, sel_registerName("initWithAPI:properties:"), api, nil);
}

static id
apple_initWithAPI_properties(id self, SEL _cmd, unsigned long api, id properties)
{
	(void)_cmd, (void)api, (void)properties;
	fprintf(stderr, "host EAGLContext: Darwin's own init reached: no GL engine on this Mac -> nil\n");
	((void (*)(id, SEL))objc_msgSend)(self, sel_registerName("release"));
	return nil;
}

static unsigned long
apple_API(id self, SEL _cmd)
{
	uint8_t *p = private_of(self);

	(void)_cmd;
	return p != NULL ? *(uint64_t *)(p + 0x10) : 0;
}

static id
apple_sharegroup(id self, SEL _cmd)
{
	uint8_t *p = private_of(self);

	(void)_cmd;
	return p != NULL ? *(id *)(p + 8) : nil;
}

static BOOL
apple_setParameter(id self, SEL _cmd, unsigned parameter, const int32_t *values)
{
	(void)self, (void)_cmd, (void)parameter, (void)values;
	return NO;
}

static void *
apple_getMacroContextPrivate(id self, SEL _cmd)
{
	(void)self, (void)_cmd;
	return NULL;
}

static BOOL
apple_texImageIOSurface_invert(id self, SEL _cmd, IOSurfaceRef surface, NSUInteger target, NSUInteger internal,
    uint32_t width, uint32_t height, NSUInteger format, NSUInteger type, uint32_t plane, BOOL invert)
{
	(void)self, (void)_cmd, (void)surface, (void)target, (void)internal, (void)width, (void)height, (void)format;
	(void)type, (void)plane, (void)invert;
	return NO;
}

static BOOL
apple_texImageIOSurface(id self, SEL _cmd, IOSurfaceRef surface, NSUInteger target, NSUInteger internal,
    uint32_t width, uint32_t height, NSUInteger format, NSUInteger type, uint32_t plane)
{
	(void)_cmd;
	return ((BOOL (*)(id, SEL, IOSurfaceRef, NSUInteger, NSUInteger, uint32_t, uint32_t, NSUInteger, NSUInteger, uint32_t,
	    BOOL))objc_msgSend)(self, sel_registerName("texImageIOSurface:target:internalFormat:width:height:format:type:plane:invert:"),
	    surface, target, internal, width, height, format, type, plane, NO);
}

static BOOL
apple_attachImage(id self, SEL _cmd, NSUInteger target, IOSurfaceRef surface, BOOL inverted)
{
	(void)self, (void)_cmd, (void)target, (void)surface, (void)inverted;
	return NO;
}

static void
apple_dealloc(id self, SEL _cmd)
{
	struct objc_super super = { self, class_getSuperclass(object_getClass(self)) };

	((void (*)(struct objc_super *, SEL))objc_msgSendSuper)(&super, _cmd);
}

static BOOL
apple_setCurrentContext(id class, SEL _cmd, id context)
{
	uint8_t *old = tls30, *now = context != nil ? private_of(context) : NULL;

	(void)class, (void)_cmd;
	if (now == old) {
		return YES;
	}
	tls30 = now;
	if (now != NULL && !(now[0x18] & 1)) {
		((id (*)(id, SEL))objc_msgSend)(context, sel_registerName("retain"));
	}
	if (old != NULL && *(id *)old != nil && !(old[0x18] & 1)) {
		((void (*)(id, SEL))objc_msgSend)(*(id *)old, sel_registerName("release"));
	}
	return YES;
}

static id
apple_currentContext(id class, SEL _cmd)
{
	(void)class, (void)_cmd;
	return tls30 != NULL ? *(id *)tls30 : nil;
}

void **
host_current_table(void)
{
	return tls30 != NULL ? (void **)((char *)tls30 + 0x20) : NULL;
}

__attribute__((constructor)) static void
host_eaglcontext_register(void)
{
	Class class = objc_allocateClassPair(objc_getClass("NSObject"), "EAGLContext", 0);
	Class meta;

	if (class == Nil) {
		return;
	}
	class_addIvar(class, "_private", sizeof(void *), 3, "^v");
	class_addMethod(class, sel_registerName("initWithAPI:"), (IMP)apple_initWithAPI, "@24@0:8Q16");
	class_addMethod(class, sel_registerName("initWithAPI:properties:"), (IMP)apple_initWithAPI_properties, "@32@0:8Q16@24");
	class_addMethod(class, sel_registerName("commonInitWithAPI:properties:"), (IMP)apple_initWithAPI_properties,
	    "@32@0:8Q16@24");
	class_addMethod(class, sel_registerName("API"), (IMP)apple_API, "Q16@0:8");
	class_addMethod(class, sel_registerName("sharegroup"), (IMP)apple_sharegroup, "@16@0:8");
	class_addMethod(class, sel_registerName("setParameter:to:"), (IMP)apple_setParameter, "B28@0:8I16r^i20");
	class_addMethod(class, sel_registerName("getMacroContextPrivate"), (IMP)apple_getMacroContextPrivate, "^v16@0:8");
	class_addMethod(class, sel_registerName("texImageIOSurface:target:internalFormat:width:height:format:type:plane:invert:"),
	    (IMP)apple_texImageIOSurface_invert, "B76@0:8^{__IOSurface=}16Q24Q32I40I44Q48Q56I64B68");
	class_addMethod(class, sel_registerName("texImageIOSurface:target:internalFormat:width:height:format:type:plane:"),
	    (IMP)apple_texImageIOSurface, "B68@0:8^{__IOSurface=}16Q24Q32I40I44Q48Q56I64");
	class_addMethod(class, sel_registerName("attachImage:toCoreSurface:invertedRender:"), (IMP)apple_attachImage,
	    "B36@0:8Q16^{__IOSurface=}24B32");
	class_addMethod(class, sel_registerName("dealloc"), (IMP)apple_dealloc, "v16@0:8");
	objc_registerClassPair(class);
	meta = object_getClass((id)class);
	class_addMethod(meta, sel_registerName("setCurrentContext:"), (IMP)apple_setCurrentContext, "B24@0:8@16");
	class_addMethod(meta, sel_registerName("currentContext"), (IMP)apple_currentContext, "@16@0:8");
}
