#!/usr/bin/env python3
"""Reject a cached, uninstrumented recovery image."""
import gzip
import importlib.util
from pathlib import Path
import sys

base = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(base))
from make_image import boot_parts, parse_cpio, sha

image = Path(sys.argv[2])
_, ramdisk, _ = boot_parts(image.read_bytes())
files = {r.name: r for r in parse_cpio(gzip.decompress(ramdisk))}
recovery = files['system/bin/recovery'].data
for marker in (
    b'PCHM30_FBE_DIAG_V3 ADD_KEY_BEGIN', b'PCHM30_FBE_DIAG_V3 ADD_KEY_END',
    b'PCHM30_FBE_DIAG_V3 KEY_STATUS', b'PCHM30_FBE_DIAG_V3 DE_VISIBLE',
    b'PCHM30_FBE_DIAG_V3 WRAP_EXPORT',
):
    assert marker in recovery, 'Missing diagnostic marker in actual packed executable: ' + marker.decode()
assert sha(recovery) != 'e9837c2d000ad3c21ba0a243e5d9a8eb7be5638e6803766a7aa1369baea8684c', 'Stale V2 executable'
print('Verified all V3 diagnostic markers in:', image)
print('Recovery SHA256:', sha(recovery))
