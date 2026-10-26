#!/usr/bin/env python3
"""Offline verification by default; populate exact locked sources in Docker only."""
import argparse
from pathlib import Path
import subprocess
import tempfile
import check_sources

HERE = Path(__file__).resolve().parent


def run(args, cwd):
    subprocess.run(list(map(str, args)), cwd=cwd, check=True)


def initialize(root, reference, jobs, populate=False):
    root, reference = root.resolve(), reference.resolve()
    assert root != reference and root not in reference.parents and reference not in root.parents
    if not (root / 'build/envsetup.sh').is_file():
        if not populate:
            raise SystemExit('Frozen PBRP source cache is missing. Recreate CNB with the locked Dockerfile; no download was attempted.')
        assert not root.exists() or not any(root.iterdir()), 'Cache target must be empty; existing trees are never reset'
        assert (reference / '.repo').is_dir(), 'Missing TWRP Git object cache'
        root.mkdir(parents=True, exist_ok=True)
        local = Path(tempfile.mkdtemp(prefix='.pchm30-pbrp-v1-manifest-', dir=root.parent))
        (local / 'default.xml').write_bytes((HERE / 'locks/manifest.xml').read_bytes())
        run(['git', 'init', '-b', 'main'], local)
        run(['git', 'add', 'default.xml'], local)
        run(['git', '-c', 'user.name=PCHM30 source lock', '-c', 'user.email=build@localhost',
             'commit', '-m', 'Frozen device-tested PBRP V1 manifest'], local)
        run(['repo', 'init', '-u', local.as_uri(), '-b', 'main', '--depth=1', '--reference=' + str(reference)], root)
        run(['repo', 'sync', '-c', '--optimized-fetch', '--no-clone-bundle', '--no-tags', '--retry-fetches=3', '-j' + str(jobs)], root)
    check_sources.check(root)
    assert (root / '.repo').is_dir()
    (root / '.pchm30-pbrp12-checkout').write_text('PCHM30 PBRP frozen V1 checkout\n')
    (root / '.pchm30-pbrp12-synced').write_text('pchm30-pbrp12.1-fbe-v1\n')
    print('Locked PBRP source cache ready; IDE verification performs no network fetch.')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root', type=Path, default=Path('/opt/pbrp'))
    ap.add_argument('--reference', type=Path, default=Path('/opt/twrp'))
    ap.add_argument('--jobs', type=int, default=8)
    ap.add_argument('--populate-cache', action='store_true')
    args = ap.parse_args()
    initialize(args.root, args.reference, args.jobs, args.populate_cache)
