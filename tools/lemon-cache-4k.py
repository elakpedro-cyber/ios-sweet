#!/usr/bin/env python3
"""Copy ad-hoc SHA256 arm64 dyld caches with verified 4K signing pages.

Usage: lemon-cache-4k.py SOURCE_CACHE_DIRECTORY OUTPUT_DIRECTORY
Source files are read-only. Only codeSignatureSize and the signature tail change;
cache UUIDs, mappings and library contents stay unchanged. Rejects CMS signatures,
scatter directories and unsupported formats rather than stripping protections.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct


def signature_parts(signature):
    magic, length, count = struct.unpack_from('>III', signature)
    if magic != 0xfade0cc0 or not 12 + 8 * count <= length <= len(signature):
        raise ValueError('invalid signature superblob')
    parts = []
    end = 12 + 8 * count
    for index in range(count):
        kind, offset = struct.unpack_from('>II', signature, 12 + 8 * index)
        if offset < end or offset + 8 > length:
            raise ValueError('overlapping/out-of-bounds signature blob')
        _, size = struct.unpack_from('>II', signature, offset)
        if size < 8 or offset + size > length:
            raise ValueError('invalid signature blob size')
        parts.append((kind, signature[offset:offset + size]))
        end = offset + size
    if [kind for kind, _ in parts] != [0, 2, 0x10000]:
        raise ValueError('expected one CodeDirectory, requirements and empty CMS')
    if parts[2][1] != struct.pack('>II', 0xfade0b01, 8):
        raise ValueError('refusing to replace a CMS signature')
    return parts


def superblob(parts):
    offset = 12 + len(parts) * 8
    indices, blobs = [], []
    for kind, blob in parts:
        indices.append(struct.pack('>II', kind, offset))
        blobs.append(blob)
        offset += len(blob)
    return struct.pack('>III', 0xfade0cc0, offset, len(parts)) + b''.join(indices + blobs)


def convert(source, target):
    with source.open('rb') as stream:
        header = bytearray(stream.read(0x1000))
        if header[:16] != b'dyld_v1   arm64\0':
            raise ValueError('not a plain arm64 dyld cache')
        offset, size = struct.unpack_from('<QQ', header, 0x28)
        if offset < len(header) or offset + size != source.stat().st_size:
            raise ValueError('signature is not the complete file tail')
        stream.seek(offset)
        signature = stream.read(size)
        parts = signature_parts(signature)
        cd = parts[0][1]
        (magic, length, version, flags, hash_offset, ident, special,
         slots, limit, hash_size, hash_type, platform, shift) = struct.unpack_from('>9I4B', cd)
        if (magic != 0xfade0c02 or length != len(cd) or version != 0x20400
                or flags != 2 or hash_size != 32 or hash_type != 2
                or shift not in (12, 14) or limit != offset or limit % 0x4000
                or slots != limit >> shift or hash_offset + slots * 32 != len(cd)
                or not 88 <= ident < hash_offset - special * 32
                or struct.unpack_from('>I', cd, 44)[0] != 0
                or struct.unpack_from('>Q', cd, 56)[0] != 0):
            raise ValueError('unsupported ad-hoc CodeDirectory layout')
        if special != 2 or cd[hash_offset - 64:hash_offset - 32] != hashlib.sha256(parts[1][1]).digest():
            raise ValueError('requirements special-slot hash mismatch')
        if cd[hash_offset - 32:hash_offset] != bytes(32):
            raise ValueError('unexpected Info.plist special-slot hash')

        new_slots = limit >> 12
        new_length = hash_offset + new_slots * 32
        new_size = (12 + 8 * len(parts) + new_length + sum(len(b) for _, b in parts[1:]) + 0x3fff) & ~0x3fff
        struct.pack_into('<Q', header, 0x30, new_size)
        hashes = bytearray()
        source_hash = hashlib.sha256()
        body_hash = hashlib.sha256()
        stream.seek(0)
        try:
            with target.open('xb') as output:
                for position in range(0, limit, 1 << shift):
                    data = stream.read(1 << shift)
                    if hashlib.sha256(data).digest() != cd[hash_offset + (position >> shift) * 32:hash_offset + ((position >> shift) + 1) * 32]:
                        raise ValueError(f'original page hash mismatch at {position:#x}')
                    source_hash.update(data)
                    # The only permitted payload difference is this 8-byte header field.
                    if position == 0:
                        body_hash.update(data[:0x30] + data[0x38:])
                        data = bytes(header) + data[len(header):]
                    else:
                        body_hash.update(data)
                    for start in range(0, len(data), 4096):
                        hashes += hashlib.sha256(data[start:start + 4096]).digest()
                    output.write(data)
                source_hash.update(signature)
                new_cd = bytearray(cd[:hash_offset]) + hashes
                struct.pack_into('>I', new_cd, 4, new_length)
                struct.pack_into('>I', new_cd, 28, new_slots)
                new_cd[39] = 12
                new_signature = superblob([(0, new_cd), *parts[1:]])
                output.write(new_signature)
                output.write(bytes(new_size - len(new_signature)))
        except Exception:
            # Never remove an existing output that caused open('xb') to fail.
            if 'output' in locals():
                target.unlink()
            raise
    with target.open('rb') as output:
        target_hash = hashlib.file_digest(output, 'sha256').hexdigest()
    return dict(name=source.name, source_sha256=source_hash.hexdigest(),
                sha256=target_hash, original_size=offset + size, size=offset + new_size,
                signature_offset=offset, original_signature_size=size,
                signature_size=new_size, original_page_shift=shift, page_shift=12,
                payload_excluding_signature_size_sha256=body_hash.hexdigest())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.source.resolve() == args.output.resolve():
        parser.error('output must differ from source')
    args.output.mkdir(parents=True, exist_ok=True)
    caches = sorted(p for p in args.source.glob('dyld_shared_cache_arm64*')
                    if not p.name.endswith('.symbols'))
    if not caches:
        parser.error('no arm64 caches found')
    records = []
    for source in caches:
        record = convert(source, args.output / source.name)
        records.append(record)
        print(f'{source.name}: verified {record["original_page_shift"]} -> 12, '
              f'{record["signature_size"]} signature bytes', flush=True)
    with (args.output / 'manifest.json').open('x') as output:
        json.dump(records, output, indent=2)
        output.write('\n')


if __name__ == '__main__':
    main()
