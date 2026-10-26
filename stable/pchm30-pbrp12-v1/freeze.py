#!/usr/bin/env python3
"""Verify the existing successful image and source cache, then archive them."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import check_sources

HERE = Path(__file__).resolve().parent
EXPECTED = 'e2cdd26378bf9dc0070390a7e5c1312bb5463617a08392f3c13258fa728f0aa0'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def freeze(workspace):
    root = Path('/opt/pbrp')
    check_sources.check(root, patched=True)
    # Only the exact phone-tested artifact can become the stable image.
    image = HERE / 'images/PCHM30-PBRP12.1-FBE-STABLE-V1.img'
    candidates = [image] + sorted((workspace / 'DOWNLOAD-PBRP').glob('*.img'))
    selected = next((p for p in candidates if p.is_file() and p.stat().st_size == 56119296 and digest(p) == EXPECTED), None)
    assert selected, 'The exact successful image was not found. No rebuild is used as a substitute.'
    sys.path.insert(0, str(HERE / 'base'))
    import make_image as packed
    import gzip
    kernel, ramdisk, dtbo = packed.boot_parts(selected.read_bytes())
    assert packed.sha(kernel) == packed.KERNEL_SHA and packed.sha(dtbo) == packed.DTBO_SHA
    files = {r.name: r for r in packed.parse_cpio(gzip.decompress(ramdisk))}
    tested = json.loads((HERE / 'TESTED-V1.json').read_text())
    assert packed.sha(files['system/bin/recovery'].data) == tested['recovery_binary_sha256']
    packed.abi_preflight(list(files.values()))
    for name in ('reference-header.bin', 'reference-ramdisk.gz'):
        assert (HERE / 'base/assets' / name).is_file()
    changes = []
    for dest, new_name, old_name in [('.ide/Dockerfile', 'Dockerfile', 'Dockerfile.before-freeze'), ('.cnb.yml', 'cnb.yml', 'cnb.before-freeze.yml')]:
        current = (workspace / dest).read_bytes()
        new = (HERE / 'locks/config' / new_name).read_bytes()
        old = (HERE / 'locks/config' / old_name).read_bytes()
        assert current in (old, new), 'Environment config changed unexpectedly: ' + dest
        changes.append((workspace / dest, new))
    image.parent.mkdir(exist_ok=True)
    if selected != image:
        shutil.copy2(selected, image)
    assert digest(image) == EXPECTED
    for dest, data in changes:
        dest.write_bytes(data)
    print('Exact tested image and all locked source commits verified. Frozen environment config installed.')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--workspace', type=Path, default=Path('/workspace'))
    freeze(ap.parse_args().workspace.resolve())
