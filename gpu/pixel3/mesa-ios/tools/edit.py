# usage: python3 edit.py FILE  (reads pairs OLD\n===\nNEW from stdin separated by '\n%%%\n')
import sys
path = sys.argv[1]
s = open(path).read()
data = sys.stdin.read()
if data.endswith('\n'): data = data[:-1]   # (heredoc's final newline)
for block in data.split('\n%%%\n'):
    if not block.strip(): continue
    old, new = block.split('\n===\n')
    if s.count(old) != 1:
        sys.exit(f'{path}: expected one match for:\n{old}\n(found {s.count(old)})')
    s = s.replace(old, new)
open(path, 'w').write(s)
