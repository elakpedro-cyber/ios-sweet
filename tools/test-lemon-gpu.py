"""Run the imported Pixel3 DRM bridge against its fake kernel, without a phone."""
import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--linux', type=Path, required=True, help='Linux source with include/uapi/drm')
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
gpu = repo / 'gpu'
mesa = gpu / 'pixel3/mesa-ios'
with tempfile.TemporaryDirectory() as directory:
    folder = Path(directory)
    headers = folder / 'drm-uapi'
    headers.mkdir()
    for name in ('drm.h', 'drm_mode.h', 'msm_drm.h'):
        shutil.copyfile(args.linux / 'include/uapi/drm' / name, headers / name)
    (folder / 'linux').mkdir()
    shutil.copyfile(args.linux / 'include/uapi/linux/bits.h', folder / 'linux/bits.h')
    flags = ['cc', '-D_GNU_SOURCE', '-D__user=', '-DIOCPARM_LEN(x)=_IOC_SIZE(x)', '-std=c11', '-Wall', '-Wextra', '-Werror',
             '-fsanitize=address,undefined', '-pthread', '-I' + str(gpu / 'tests/include'),
             '-I' + str(mesa), '-I' + str(mesa / 'bluedrm'), '-I' + str(folder)]
    subprocess.run(flags + [str(mesa / 'bluedrm/bluedrm.c'), str(mesa / 'fake/fake_bluegpu.c'),
                           str(gpu / 'tests/transport.c'), '-o', str(folder / 'transport')], check=True)
    subprocess.run([str(folder / 'transport')], check=True)
    source = (gpu / 'pixel3/eagl-ios/src/blueeagl.c').read_text()
    start = source.index('static int\ngpu_present(void)')
    gate = source[start:source.index('\n}\n', start) + 3]
    source = (mesa / 'bluedrm/bluedrm.c').read_text()
    start = source.index('\tlong page = sysconf(_SC_PAGESIZE);')
    allocation = source[start:source.index('\n\tvoid *address', start)]
    program = (gpu / 'tests/gate.c').read_text().replace('/* GPU_GATE */', gate).replace('/* ALLOCATION */', allocation)
    (folder / 'gate.c').write_text(program)
    subprocess.run(flags + [str(folder / 'gate.c'), '-o', str(folder / 'gate')], check=True)
    subprocess.run([str(folder / 'gate')], check=True)
    cross = shutil.which('aarch64-linux-gnu-gcc')
    if cross:
        cross_flags = [f for f in flags[1:] if not f.startswith('-fsanitize=')]
        for index, source in enumerate((mesa / 'bluedrm/bluedrm.c', mesa / 'fake/fake_bluegpu.c', folder / 'gate.c')):
            subprocess.run([cross, '-mcpu=cortex-a53', '-march=armv8-a+crypto', '-mno-outline-atomics',
                            *cross_flags, '-c', str(source), '-o', str(folder / f'arm64-{index}.o')], check=True)
        print('PASS: ARMv8.0 AArch64 Linux cross-compile (not an iOS dylib build)')
