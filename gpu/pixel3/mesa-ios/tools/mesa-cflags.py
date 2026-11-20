# Print the -D/-I/-std flags Mesa's build used for one source file, with -I made absolute.
# usage: python3 -I mesa-cflags.py BUILD_DIR SUFFIX   (e.g. state_tracker/st_manager.c)
import json, os, shlex, sys
build, suffix = sys.argv[1], sys.argv[2]
cc = json.load(open(os.path.join(build, 'compile_commands.json')))
e = next(x for x in cc if x['file'].endswith(suffix))
args = shlex.split(e['command'])
out, i = [], 0
while i < len(args):
    a = args[i]
    if a == '-I' or a == '-D':
        a += args[i + 1]; i += 1
    if a.startswith('-I'):
        p = a[2:]
        out.append('-I' + os.path.normpath(os.path.join(e['directory'], p)))
    elif a.startswith('-D') or a.startswith('-std='):
        out.append(a)
    i += 1
print('\n'.join(shlex.quote(a) for a in out))
