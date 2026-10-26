#!/usr/bin/env python3
"""Verify offline runtime assets, or obtain them from the fixed Golden release."""
import argparse
import hashlib
from pathlib import Path
import struct
import tempfile
import urllib.request

HERE = Path(__file__).resolve().parent
ASSETS = HERE / 'base/assets'
URL = 'https://github.com/hhsbjbsj/PCHM30-OrangeFox-FBE/releases/download/v1.0.0/PCHM30-OrangeFox-RAMDISK-AB10-GOLDEN-RECOVERY-BINARY.img'
IMAGE_SHA = 'b3d1b6a6d711e95b8b10cf0bbe33eed5ea82cff6ce845183af9210ccc6ebb14b'
EXPECTED = {
    'reference-header.bin': 'afeb63f25b203d4aac3914fbd84547d7b3209d7b5b85a8348596c39fc282a02a',
    'reference-ramdisk.gz': '4a9a6b42fea29258141ee84ceb5c4852e25dc4a859144fd81915b4e6ee3093c7',
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def extract(image):
    assert len(image) == 67108864 and digest(image) == IMAGE_SHA, 'Golden image hash mismatch'
    assert image[:8] == b'ANDROID!' and struct.unpack_from('<I', image, 40)[0] == 1
    page = struct.unpack_from('<I', image, 36)[0]
    assert page == 4096
    kernel_size = struct.unpack_from('<I', image, 8)[0]
    ramdisk_size = struct.unpack_from('<I', image, 16)[0]
    offset = page + (kernel_size + page - 1) // page * page
    assert offset + ramdisk_size <= len(image)
    data = {'reference-header.bin': image[:page],
            'reference-ramdisk.gz': image[offset:offset+ramdisk_size]}
    assert all(digest(data[name]) == value for name, value in EXPECTED.items())
    return data


def prepare(reference_image=None):
    ASSETS.mkdir(parents=True, exist_ok=True)
    if all((ASSETS / name).is_file() and digest((ASSETS / name).read_bytes()) == value
           for name, value in EXPECTED.items()):
        print('Pinned Golden runtime assets verified (offline).')
        return
    if reference_image:
        image = reference_image.read_bytes()
    else:
        print('Runtime assets absent; downloading fixed Golden v1.0.0 image.', flush=True)
        request = urllib.request.Request(URL, headers={'User-Agent': 'PCHM30-stable-v4'})
        with urllib.request.urlopen(request, timeout=60) as response:
            image = response.read(67108865)
    files = extract(image)
    for name, data in files.items():
        path = ASSETS / name
        staged = path.with_suffix(path.suffix + '.download')
        staged.write_bytes(data)
        staged.replace(path)
    print('Golden image and extracted runtime assets verified.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference-image', type=Path)
    args = parser.parse_args()
    prepare(args.reference_image)
