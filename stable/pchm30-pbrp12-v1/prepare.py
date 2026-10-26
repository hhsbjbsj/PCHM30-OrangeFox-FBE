#!/usr/bin/env python3
"""Apply a separate PBRP product and the tested PCHM30 device settings."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import early_media

HERE = Path(__file__).resolve().parent
PINS = json.loads((HERE / 'source-pins.json').read_text())
DEVICE_LIST = Path('/tmp/pb_devices.json')


def prepare(root, workspace):
    root, workspace = root.resolve(), workspace.resolve()
    device = root / 'device/oppo/PCHM30'
    assert (root / '.pchm30-pbrp12-checkout').is_file(), 'Not an owned PBRP checkout'
    revision = subprocess.check_output(['git', '-C', str(device), 'rev-parse', 'HEAD'], text=True).strip()
    assert revision == PINS['device_commit']
    for name, expected in [('kernel', 'd83bf44d06a1ed1aeb7c8d597bbccd627458e7619e8606218f33358d145a0f1b'),
                           ('dtbo.img', 'b11c7c246bd74a010718124f25ff92f332304bd892b66eecd18b300417dbf270')]:
        assert hashlib.sha256((device / 'prebuilt' / name).read_bytes()).hexdigest() == expected, 'Wrong ' + name
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup = workspace / 'artifacts' / ('pbrp-config-before-' + stamp)
    for source in (HERE / 'device').rglob('*'):
        if not source.is_file():
            continue
        relative = source.relative_to(HERE / 'device')
        dest = device / relative
        if dest.is_file():
            previous = backup / relative
            previous.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dest, previous)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
        if dest.suffix == '.sh':
            dest.chmod(0o755)
    early_media.apply(root, workspace)
    # Avoid an unpinned network request from the vendor's envsetup hook.
    utils = root / 'vendor/utils'
    before = utils / 'vendorsetup.sh'
    saved = backup / 'vendor-utils-vendorsetup.sh'
    saved.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(before, saved)
    before.write_text('# PCHM30: use the source-pinned offline device list.\n', encoding='utf-8')
    shutil.copy2(utils / 'pb_devices.json', DEVICE_LIST)
    locks = HERE / 'locks'
    locks.mkdir(exist_ok=True)
    for project, filename in [('bootable/recovery', 'recovery.patch'), ('device/oppo/PCHM30', 'device.patch'), ('vendor/utils', 'utils.patch')]:
        patch = subprocess.check_output(['git', '-C', str(root / project), 'diff', 'HEAD', '--'])
        (locks / filename).write_bytes(patch)
    snapshot = locks / 'device'
    snapshot.mkdir(exist_ok=True)
    for source in (HERE / 'device').rglob('*'):
        if source.is_file():
            target = snapshot / source.relative_to(HERE / 'device')
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(device / source.relative_to(HERE / 'device'), target)
    print('Prepared pb_PCHM30-eng: arm64, BGRA, resetprop, early media, OPPO panel-unblank hook.')
    print('Device/runtime behavior still requires PBRP testing. Configuration backups:', backup)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root', type=Path, default=Path('/opt/pbrp'))
    ap.add_argument('--workspace', type=Path, default=Path('/workspace'))
    args = ap.parse_args()
    prepare(args.root, args.workspace)
