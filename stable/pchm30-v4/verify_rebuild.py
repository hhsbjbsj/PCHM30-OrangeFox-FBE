#!/usr/bin/env python3
"""Compare rebuilt runtime payloads to the exact phone-tested V4 image."""
import gzip
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'base'))
from make_image import boot_parts, parse_cpio


def digest(data):
    return hashlib.sha256(data).hexdigest()


def verify(path, report_path=None):
    baseline = json.loads(gzip.decompress((HERE / 'known-good-tree.json.gz').read_bytes()))
    image = path.read_bytes()
    kernel, ramdisk, dtbo = boot_parts(image)
    assert digest(kernel) == baseline['kernel_sha256'], 'Rebuilt kernel differs'
    assert digest(dtbo) == baseline['dtbo_sha256'], 'Rebuilt DTBO differs'
    header = bytearray(image[:4096])
    header[16:20] = bytes(4)
    header[576:608] = bytes(32)
    header[1636:1644] = bytes(8)
    assert digest(header) == baseline['normalized_header_sha256'], 'Rebuilt boot parameters differ'
    files = {r.name: {'mode': r.mode, 'uid': r.fields[2], 'gid': r.fields[3], 'sha256': digest(r.data)}
             for r in parse_cpio(gzip.decompress(ramdisk))
             if r.name not in baseline['ignored_nonruntime_files']}
    differences = [name for name in sorted(set(files) | set(baseline['files']))
                   if files.get(name) != baseline['files'].get(name)]
    assert not differences, 'Rebuilt runtime differs from phone-tested V4:\n' + '\n'.join(differences[:30])
    report = {'phone_tested_image_sha256': baseline['image_sha256'],
              'rebuilt_image_sha256': digest(image),
              'runtime_payloads_match': True, 'entries_compared': len(files),
              'boot_parameters_match': True,
              'ignored_nonruntime_files': baseline['ignored_nonruntime_files'],
              'note': 'Runtime file contents, owners, modes, kernel, DTBO and boot parameters match. Archive timestamps, provenance marker, inventories and compression bytes may differ. This is a rebuild comparison, not a new phone boot test.'}
    if report_path:
        report_path.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print('Runtime matches the phone-tested V4:', len(files), 'entries')
    return report


if __name__ == '__main__':
    assert len(sys.argv) in (2, 3)
    verify(Path(sys.argv[1]), Path(sys.argv[2]) if len(sys.argv) == 3 else None)
