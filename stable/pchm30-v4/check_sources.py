#!/usr/bin/env python3
"""Enforce the captured project commits, and optionally patched source hashes."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent


def check(root, patched=False):
    lock = HERE / 'locks'
    assert (lock / 'manifest.xml').is_file(), 'Missing frozen manifest.xml; capture it from the successful CNB environment first'
    root = root.resolve()
    expected = {}
    for project in ET.parse(lock / 'manifest.xml').getroot().findall('.//project'):
        expected[project.get('path') or project.get('name')] = project.get('revision')
    for line in (lock / 'revisions.txt').read_text().splitlines():
        if line.strip():
            path, revision = line.split()
            if path in expected:
                assert expected[path] == revision, 'Inconsistent lock for ' + path
            expected[path] = revision
    mismatches = []
    for path, revision in expected.items():
        target = root / path
        if not target.is_dir():
            mismatches.append(path + ': missing')
            continue
        result = subprocess.run(['git', '-C', str(target), 'rev-parse', 'HEAD'], capture_output=True, text=True)
        if result.returncode or result.stdout.strip() != revision:
            mismatches.append(path + ': commit differs')
    assert not mismatches, 'Source does not match the frozen V4 manifest:\n' + '\n'.join(mismatches) + '\nInitialize a separate tree with init_sources.py; existing files were not reset.'
    if patched:
        pins = lock / 'source-sha256.json'
        if pins.is_file():
            for path, expected_sha in json.loads(pins.read_text()).items():
                assert hashlib.sha256((root / path).read_bytes()).hexdigest() == expected_sha, 'Patched source differs from successful V4: ' + path
        else:
            print('Patched-source hash snapshot is absent; project commits are pinned.')
    print('Frozen V4 project commits verified:', len(expected))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('/opt/twrp'))
    parser.add_argument('--patched', action='store_true')
    args = parser.parse_args()
    check(args.root, args.patched)
