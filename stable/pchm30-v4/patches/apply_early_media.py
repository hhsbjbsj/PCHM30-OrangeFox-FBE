#!/usr/bin/env python3
"""Enable TWRP's existing early data-media path before installing FBE keys."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil

OLD = '''\t#ifdef TW_PREPARE_DATA_MEDIA_EARLY
\tif (datamedia)
\t\tSetup_Data_Media();
\t#endif
\tCan_Be_Encrypted = true;'''

NEW = '''\t#ifdef TW_PREPARE_DATA_MEDIA_EARLY
\tLOGINFO("PCHM30_FBE_V4 EARLY_MEDIA_BEFORE_DE\\n");
\tif (datamedia)
\t\tSetup_Data_Media();
\t#endif
\tCan_Be_Encrypted = true;'''


def update_board(text):
    text = re.sub(r'^TW_PREPARE_DATA_MEDIA_EARLY\s*(?:[:+?])?=.*(?:\n|$)',
                  '', text, flags=re.MULTILINE)
    return text.rstrip() + '\nTW_PREPARE_DATA_MEDIA_EARLY := true\n'


def update_source(text):
    if NEW in text:
        assert text.count(NEW) == 1
        return text
    assert 'PCHM30_FBE_V4' not in text, 'Unknown existing V4 patch'
    assert text.count(OLD) == 1, 'Unsupported Setup_Data_Partition source; no changes applied'
    return text.replace(OLD, NEW, 1)


def apply(root, workspace):
    root, workspace = root.resolve(), workspace.resolve()
    board = root / 'device/oppo/PCHM30/BoardConfig.mk'
    source = root / 'bootable/recovery/partition.cpp'
    assert board.is_file() and source.is_file()
    assert root in board.resolve().parents and root in source.resolve().parents
    originals = {board: board.read_bytes(), source: source.read_bytes()}
    updated = {
        board: update_board(originals[board].decode()).encode(),
        source: update_source(originals[source].decode()).encode(),
    }
    backup = workspace / 'artifacts' / ('fbe-v4-early-media-before-' +
              datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    backup.mkdir(parents=True)
    changes = []
    for path in (board, source):
        shutil.copy2(path, backup / path.name)
        path.write_bytes(updated[path])
        changes.append({'path': str(path.relative_to(root)),
                        'before_sha256': hashlib.sha256(originals[path]).hexdigest(),
                        'after_sha256': hashlib.sha256(updated[path]).hexdigest()})
    (backup / 'changes.json').write_text(json.dumps(changes, indent=2)+'\n', encoding='utf-8')
    (backup / 'BoardConfig-after.mk').write_bytes(updated[board])
    print('Enabled TW_PREPARE_DATA_MEDIA_EARLY := true')
    print('V4 changes data-media preparation order, not key format or encryption parameters.')
    print('Backups:', backup)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('/opt/twrp'))
    parser.add_argument('--workspace', type=Path, default=Path('/workspace'))
    args = parser.parse_args()
    apply(args.root, args.workspace)
