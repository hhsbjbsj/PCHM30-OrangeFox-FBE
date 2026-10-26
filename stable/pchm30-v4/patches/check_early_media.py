#!/usr/bin/env python3
import gzip
from pathlib import Path
import sys

sys.path.insert(0, sys.argv[1])
from make_image import boot_parts, parse_cpio, sha

image = Path(sys.argv[2])
_, ramdisk, _ = boot_parts(image.read_bytes())
files = {r.name: r for r in parse_cpio(gzip.decompress(ramdisk))}
main = files['system/bin/recovery'].data
assert b'PCHM30_FBE_V4 EARLY_MEDIA_BEFORE_DE' in main, 'V4 compile-time early-media path is absent from the packed executable'
assert sha(main) != '89204f3903fedffeeda30e6072d5e31fbce56d57b0652059ec29fc5e306d73ea', 'Stale V3 executable'
print('V4 early-media compile path verified:', image)
print('Recovery SHA256:', sha(main))
