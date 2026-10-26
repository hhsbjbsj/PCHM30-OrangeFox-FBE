#!/usr/bin/env python3
"""Capture source locks and public build configuration, never phone data or tokens."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
DEVICE_FILES = ('BoardConfig.mk', 'AndroidProducts.mk', 'twrp_PCHM30.mk',
                'device.mk', 'vendorsetup.sh', 'system.prop', 'recovery.fstab',
                'recovery/root/init.recovery.qcom.rc',
                'recovery/root/system/bin/postscreenunblank.sh')
PATCHED = ('bootable/recovery/partition.cpp', 'system/vold/KeyUtil.cpp',
           'system/vold/FsCrypt.cpp', 'system/vold/KeyStorage.cpp')


def run(args, cwd):
    return subprocess.check_output(args, cwd=cwd, text=True, encoding='utf-8')


def capture(root, workspace):
    root, workspace = root.resolve(), workspace.resolve()
    lock = HERE / 'locks'
    lock.mkdir(exist_ok=True)
    manifest = run(['repo', 'manifest', '-r'], root)
    parsed = ET.fromstring(manifest)
    projects = parsed.findall('.//project')
    assert projects, 'Manifest has no projects'
    for project in projects:
        revision = project.get('revision', '')
        assert len(revision) == 40 and all(c in '0123456789abcdef' for c in revision), 'Manifest revision is not pinned'
    (lock / 'manifest.xml').write_text(manifest, encoding='utf-8')
    revisions = []
    for project in ('bootable/recovery', 'system/vold', 'device/oppo/PCHM30'):
        revision = run(['git', 'rev-parse', 'HEAD'], root / project).strip()
        revisions.append(project + ' ' + revision)
    (lock / 'revisions.txt').write_text('\n'.join(revisions)+'\n', encoding='ascii')
    sha = {}
    for path in PATCHED:
        sha[path] = hashlib.sha256((root / path).read_bytes()).hexdigest()
    (lock / 'source-sha256.json').write_text(json.dumps(sha, indent=2)+'\n', encoding='ascii')
    for project, files, filename in (
        ('bootable/recovery', ['partition.cpp'], 'recovery.patch'),
        ('system/vold', ['KeyUtil.cpp', 'FsCrypt.cpp', 'KeyStorage.cpp'], 'vold.patch'),
    ):
        patch = run(['git', 'diff', 'HEAD', '--', *files], root / project)
        assert patch, 'Expected applied V4 patch is missing: ' + project
        (lock / filename).write_text(patch, encoding='utf-8')
    for relative in DEVICE_FILES:
        target = lock / 'device' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / 'device/oppo/PCHM30' / relative, target)
    for relative, name in (('.cnb.yml', 'cnb.yml'), ('.ide/Dockerfile', 'Dockerfile')):
        (lock / 'config').mkdir(exist_ok=True)
        shutil.copyfile(workspace / relative, lock / 'config' / name)
    runtime = {
        'os_release': (Path('/etc/os-release').read_text() if Path('/etc/os-release').is_file() else 'unavailable'),
        'python': run(['python3', '--version'], root).strip(),
        'git': run(['git', '--version'], root).strip(),
        'manifest_projects': len(projects),
        'baseline': 'PCHM30 TWRP12.1 FBE V4; 2026-10-26 device-tested image',
        'binary_reproducibility': 'timestamps and unpinned distro package repositories can change rebuilt image hashes',
    }
    (lock / 'environment.json').write_text(json.dumps(runtime, indent=2)+'\n', encoding='utf-8')
    print('Captured', len(projects), 'pinned projects and the actual applied V4 patches.')
    print('Source locks:', lock)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('/opt/twrp'))
    parser.add_argument('--workspace', type=Path, default=Path('/workspace'))
    args = parser.parse_args()
    capture(args.root, args.workspace)
