"""Download the four iPhone X 20H392 components, with progress and resume."""
import argparse
import os
from pathlib import Path
import struct
import time
import zlib

import remotezip

URL = ('https://updates.cdn-apple.com/2025FallFCS/fullrestores/122-77006/'
       '1158E502-D76D-4226-AA06-ED5E30CD1111/'
       'iPhone10,3,iPhone10,6_16.7.16_20H392_Restore.ipsw')
FILES = ('087-86715-047.dmg', '087-86593-047.dmg',
         'Firmware/all_flash/DeviceTree.d22ap.im4p', '087-86698-044.dmg',
         'BuildManifest.plist')
CHUNK = 8 * 1024 * 1024


def checksum(path):
    crc = 0
    with path.open('rb') as stream:
        while data := stream.read(CHUNK):
            crc = zlib.crc32(data, crc)
    return crc


def download(entry, output):
    name, method, compressed, size, offset, crc = entry
    if method not in (0, 8):
        raise ValueError(f'Unsupported ZIP compression: {method}')
    target = output / name
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.stat().st_size == size and checksum(target) == crc:
        print(f'{name}: already downloaded, CRC OK', flush=True)
        return
    header = remotezip.get(URL, offset, offset + 29)
    name_size, extra_size = struct.unpack_from('<HH', header, 26)
    start = offset + 30 + name_size + extra_size
    # Preserve the compressed bytes so even deflated ZIP members can resume.
    packed = target.with_name(target.name + '.zip.part')
    done = packed.stat().st_size if packed.exists() else 0
    if done > compressed:
        raise ValueError(f'Partial file is larger than expected: {packed}')
    began, initial = time.monotonic(), done
    print(f'\n{name}: {done / 2**20:.1f} / {compressed / 2**20:.1f} MiB', flush=True)
    with packed.open('ab') as stream:
        while done < compressed:
            count = min(CHUNK, compressed - done)
            data = remotezip.get(URL, start + done, start + done + count - 1)
            stream.write(data)
            stream.flush()
            done += len(data)
            speed = (done - initial) / max(time.monotonic() - began, 0.001)
            eta = (compressed - done) / max(speed, 1)
            print(f'\r{done * 100 / max(compressed, 1):6.2f}%  '
                  f'{done / 2**20:.1f}/{compressed / 2**20:.1f} MiB  '
                  f'{speed / 2**20:.2f} MiB/s  ETA {eta / 60:.1f} min   ',
                  end='', flush=True)
    print('\nUnpacking and checking CRC...', flush=True)
    temporary = target.with_name(target.name + '.unpacking')
    inflate = zlib.decompressobj(-15) if method == 8 else None
    with packed.open('rb') as source, temporary.open('wb') as dest:
        while data := source.read(CHUNK):
            dest.write(inflate.decompress(data) if inflate else data)
        if inflate:
            dest.write(inflate.flush())
            if not inflate.eof:
                raise ValueError(f'Incomplete compressed stream: {name}')
    if temporary.stat().st_size != size or checksum(temporary) != crc:
        raise ValueError(f'CRC/size check failed: {name}; cache kept at {packed}')
    os.replace(temporary, target)
    packed.unlink()
    print(f'{name}: OK', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path,
                        default=Path(__file__).resolve().parents[1] / 'research/ipsw-x')
    args = parser.parse_args()
    print(f'Output: {args.output}\nReading Apple archive index...', flush=True)
    entries = {e[0]: e for e in remotezip.central_dir(URL)}
    selected = [entries[name] for name in FILES]
    print(f'Selected download: {sum(e[2] for e in selected) / 10**9:.2f} GB\n'
          'Ctrl+C stops. Run again to resume. Existing valid files are skipped.', flush=True)
    for entry in selected:
        download(entry, args.output)
    print('\nAll files downloaded and verified.', flush=True)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\nStopped. Run again to resume.')
        raise SystemExit(130)
    except Exception as error:
        print(f'\nError: {error}\nRun again to retry/resume.')
        raise SystemExit(1)
