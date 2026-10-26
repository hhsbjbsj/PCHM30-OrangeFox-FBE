#!/usr/bin/env python3
"""Initialize a new, empty source tree from the frozen manifest. Never resets existing trees."""
import argparse
from pathlib import Path
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent


def command(args, cwd):
    subprocess.run(args, cwd=cwd, check=True)


def initialize(target, jobs):
    manifest = HERE / 'locks/manifest.xml'
    assert manifest.is_file(), 'Missing frozen manifest'
    target = target.resolve()
    assert not target.exists() or not any(target.iterdir()), 'Target must be empty; no existing files will be reset'
    target.mkdir(parents=True, exist_ok=True)
    # Keep this small local manifest repository for future repo sync operations.
    manifest_repo = Path(tempfile.mkdtemp(prefix='.pchm30-v4-manifest-', dir=target.parent))
    (manifest_repo / 'default.xml').write_bytes(manifest.read_bytes())
    command(['git', 'init', '-b', 'main'], manifest_repo)
    command(['git', 'add', 'default.xml'], manifest_repo)
    command(['git', '-c', 'user.name=PCHM30 source lock', '-c', 'user.email=build@localhost',
             'commit', '-m', 'Frozen successful V4 source manifest'], manifest_repo)
    command(['repo', 'init', '-u', manifest_repo.as_uri(), '-b', 'main', '-m', 'default.xml'], target)
    command(['repo', 'sync', '-c', '-j' + str(jobs), '--no-tags'], target)
    revisions = dict(line.split() for line in (HERE / 'locks/revisions.txt').read_text().splitlines() if line.strip())
    device_revision = revisions['device/oppo/PCHM30']
    device = target / 'device/oppo/PCHM30'
    if not device.exists():
        device.parent.mkdir(parents=True, exist_ok=True)
        command(['git', 'clone', '--no-checkout', 'https://github.com/hhsbjbsj/android_device_oppo_PCHM30.git', str(device)], target)
        command(['git', 'checkout', '--detach', device_revision], device)
    command(['python3', str(HERE / 'check_sources.py'), '--root', str(target)], target)
    print('Initialized frozen source tree:', target)
    print('Build using: TWRP_ROOT=' + str(target) + ' bash ' + str(HERE / 'build.sh'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('target', type=Path)
    parser.add_argument('--jobs', type=int, default=8)
    args = parser.parse_args()
    assert 1 <= args.jobs <= 32
    initialize(args.target, args.jobs)
