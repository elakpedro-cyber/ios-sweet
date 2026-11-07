#!/usr/bin/env python3
"""Extract distinct compiler errors from a large Actions text log."""
import re
import sys

errors = {}
patches = []
with open(sys.argv[1], errors='replace') as log:
    for line in log:
        line = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', line)
        line = re.sub(r'^\S+Z\s+', '', line.rstrip())
        if 'Applying patch:' in line or 'Skipping patch ' in line:
            patches.append(line)
        if re.search(r'\berror:|fatal error:|undefined symbols|Undefined symbols|No rule to make', line):
            key = re.sub(r'^.*?(/[^ :]+:\d+:\d+:)', r'\1', line)
            errors[key] = errors.get(key, 0) + 1
print('PATCHES')
for line in patches:
    print(line[:900])
print('\nDISTINCT ERRORS:', len(errors))
for line, count in list(errors.items())[:100]:
    print(f'[{count}x] {line[:900]}')
