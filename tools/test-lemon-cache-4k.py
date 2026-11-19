"""Check cache re-signing, byte preservation and rejection of corrupt inputs."""
import hashlib
import importlib.util
from pathlib import Path
import struct
import tempfile

spec = importlib.util.spec_from_file_location('cache4k', Path(__file__).with_name('lemon-cache-4k.py'))
cache4k = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cache4k)


def fixture():
    limit = 0x14000
    data = bytearray((i * 17 + 3) & 255 for i in range(limit))
    data[:16] = b'dyld_v1   arm64\0'
    struct.pack_into('<QQ', data, 0x28, limit, 0x4000)
    ident = b'org.lemon.cache-test\0'
    requirements = struct.pack('>III', 0xfade0c01, 12, 0)
    hash_offset = 88 + len(ident) + 64
    cd = bytearray(hash_offset)
    struct.pack_into('>9I4B', cd, 0, 0xfade0c02, hash_offset + 5 * 32,
                     0x20400, 2, hash_offset, 88, 2, 5, limit, 32, 2, 0, 14)
    cd[88:88 + len(ident)] = ident
    cd[hash_offset - 64:hash_offset - 32] = hashlib.sha256(requirements).digest()
    cd += b''.join(hashlib.sha256(data[i:i + 0x4000]).digest() for i in range(0, limit, 0x4000))
    signature = cache4k.superblob([(0, cd), (2, requirements),
                                  (0x10000, struct.pack('>II', 0xfade0b01, 8))])
    return bytes(data) + signature + bytes(0x4000 - len(signature))


def verify(path, original):
    data = path.read_bytes()
    offset, size = struct.unpack_from('<QQ', data, 0x28)
    assert data[:0x30] == original[:0x30]
    assert data[0x38:offset] == original[0x38:offset]
    assert len(data) == offset + size
    cd = cache4k.signature_parts(data[offset:])[0][1]
    assert cd[39] == 12
    hash_offset, = struct.unpack_from('>I', cd, 16)
    for index, start in enumerate(range(0, offset, 4096)):
        assert hashlib.sha256(data[start:start + 4096]).digest() == cd[hash_offset + 32 * index:hash_offset + 32 * (index + 1)]


with tempfile.TemporaryDirectory() as folder:
    root = Path(folder)
    source, target = root / 'source', root / 'target'
    original = fixture()
    source.write_bytes(original)
    record = cache4k.convert(source, target)
    assert record['source_sha256'] == hashlib.sha256(original).hexdigest()
    assert record['sha256'] == hashlib.sha256(target.read_bytes()).hexdigest()
    assert source.read_bytes() == original
    verify(target, original)
    # Already-4K input produces identical bytes and valid hashes.
    cache4k.convert(target, root / 'again')
    assert (root / 'again').read_bytes() == target.read_bytes()
    try:
        cache4k.convert(source, target)
        raise AssertionError('existing output overwritten')
    except FileExistsError:
        assert hashlib.sha256(target.read_bytes()).hexdigest() == record['sha256']
    bad = bytearray(original)
    bad[0x4001] ^= 1
    source.write_bytes(bad)
    try:
        cache4k.convert(source, root / 'bad')
        raise AssertionError('corrupt signed payload accepted')
    except ValueError as error:
        assert 'original page hash mismatch' in str(error)
        assert not (root / 'bad').exists()
    bad = bytearray(original)
    # A nonempty CMS blob must be rejected, never replaced by an ad-hoc one.
    offset, = struct.unpack_from('<Q', bad, 0x28)
    cms_offset, = struct.unpack_from('>I', bad, offset + 32)
    blob_length, = struct.unpack_from('>I', bad, offset + 4)
    struct.pack_into('>I', bad, offset + 4, blob_length + 1)
    struct.pack_into('>I', bad, offset + cms_offset + 4, 9)
    source.write_bytes(bad)
    try:
        cache4k.convert(source, root / 'cms')
        raise AssertionError('CMS signed cache accepted')
    except ValueError as error:
        assert 'refusing to replace a CMS signature' in str(error)
        assert not (root / 'cms').exists()
print('PASS: original hashes checked; 4K hashes/header valid; payload preserved; '
      'idempotent; corrupt/CMS inputs and output overwrite rejected')
