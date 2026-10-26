#!/usr/bin/env python3
"""Add bounded, non-secret logging to TWRP12.1's fscrypt source.

No key data, authentication data or directory listings are logged. The only
new crypto ioctl is GET_ENCRYPTION_KEY_STATUS, a read-only query. Existing
success/failure returns and wrapped-key selection remain unchanged.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

MARKER = 'PCHM30_FBE_DIAG_V3'

OLD_ADD = '''    if (ioctl(fd, FS_IOC_ADD_ENCRYPTION_KEY, arg) != 0) {
        PLOG(ERROR) << "Failed to install fscrypt key to " << mountpoint;
        return false;
    }

    return true;'''

NEW_ADD = '''    // PCHM30_FBE_DIAG_V3: metadata only; never log the key payload.
    const int pchm30_entry_errno = errno;
    LOG(INFO) << "PCHM30_FBE_DIAG_V3 ADD_KEY_BEGIN mount=" << mountpoint
              << " policy_version=" << options.version
              << " hw_wrapped=" << options.use_hw_wrapped_key
              << " spec_type=" << arg->key_spec.type
              << " raw_size=" << arg->raw_size
              << " key_id=" << arg->key_id
              << " flags=" << arg->__flags
              << " args_size=" << sizeof(*arg)
              << " raw_offset=" << __builtin_offsetof(struct fscrypt_add_key_arg, raw)
              << " flags_offset=" << __builtin_offsetof(struct fscrypt_add_key_arg, __flags);
    errno = pchm30_entry_errno;
    const int pchm30_rc = ioctl(fd, FS_IOC_ADD_ENCRYPTION_KEY, arg);
    const int pchm30_add_errno = errno;
    LOG(INFO) << "PCHM30_FBE_DIAG_V3 ADD_KEY_END rc=" << pchm30_rc
              << " errno=" << (pchm30_rc == 0 ? 0 : pchm30_add_errno)
              << " spec_type=" << arg->key_spec.type;
    if (pchm30_rc != 0) {
        errno = pchm30_add_errno;
        PLOG(ERROR) << "Failed to install fscrypt key to " << mountpoint;
        return false;
    }
#if defined(FS_IOC_GET_ENCRYPTION_KEY_STATUS)
    struct fscrypt_get_key_status_arg pchm30_status = {};
    pchm30_status.key_spec = arg->key_spec;
    const int pchm30_status_rc = ioctl(fd, FS_IOC_GET_ENCRYPTION_KEY_STATUS, &pchm30_status);
    const int pchm30_status_errno = errno;
    LOG(INFO) << "PCHM30_FBE_DIAG_V3 KEY_STATUS rc=" << pchm30_status_rc
              << " errno=" << (pchm30_status_rc == 0 ? 0 : pchm30_status_errno)
              << " status=" << pchm30_status.status
              << " status_flags=" << pchm30_status.status_flags
              << " user_count=" << pchm30_status.user_count;
#else
    LOG(INFO) << "PCHM30_FBE_DIAG_V3 KEY_STATUS unavailable_in_build_headers";
#endif
    errno = pchm30_add_errno;
    return true;'''

OLD_DE = '''        if (!install_storage_key(DATA_MNT_POINT, options, de_key, &de_policy)) return false;
        auto ret = s_de_policies.insert({user_id, de_policy});'''

NEW_DE = '''        if (!install_storage_key(DATA_MNT_POINT, options, de_key, &de_policy)) return false;
        // PCHM30_FBE_DIAG_V3: existence only; do not inspect lock or key files.
        const int pchm30_de_errno = errno;
        const std::string pchm30_spblob = "/data/system_de/" + std::to_string(user_id) + "/spblob";
        const bool pchm30_spblob_visible = access(pchm30_spblob.c_str(), F_OK) == 0;
        const bool pchm30_system_users_visible = access("/data/system/users", F_OK) == 0;
        LOG(INFO) << "PCHM30_FBE_DIAG_V3 DE_VISIBLE user=" << user_id
                  << " policy_version=" << options.version
                  << " hw_wrapped=" << options.use_hw_wrapped_key
                  << " spblob=" << pchm30_spblob_visible
                  << " system_users=" << pchm30_system_users_visible;
        errno = pchm30_de_errno;
        auto ret = s_de_policies.insert({user_id, de_policy});'''

OLD_EXPORT = '''    if (!keymaster.exportKey(kmKey, &key_temp)) return false;
    *key = KeyBuffer(key_temp.size());
    memcpy(reinterpret_cast<void*>(key->data()), key_temp.c_str(), key->size());
    return true;'''

NEW_EXPORT = '''    if (!keymaster.exportKey(kmKey, &key_temp)) return false;
    *key = KeyBuffer(key_temp.size());
    memcpy(reinterpret_cast<void*>(key->data()), key_temp.c_str(), key->size());
    // PCHM30_FBE_DIAG_V3: lengths only, never key or blob contents.
    const int pchm30_export_errno = errno;
    LOG(INFO) << "PCHM30_FBE_DIAG_V3 WRAP_EXPORT input_bytes=" << kmKey.size()
              << " output_bytes=" << key->size();
    errno = pchm30_export_errno;
    return true;'''

PATCHES = {
    'KeyUtil.cpp': (OLD_ADD, NEW_ADD),
    'FsCrypt.cpp': (OLD_DE, NEW_DE),
    'KeyStorage.cpp': (OLD_EXPORT, NEW_EXPORT),
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def transform(content, filename):
    old, new = PATCHES[filename]
    if new in content:
        assert content.count(new) == 1
        return content
    assert MARKER not in content, 'Unrecognized diagnostic patch in ' + filename
    assert content.count(old) == 1, 'Source differs from supported TWRP12.1 block: ' + filename
    return content.replace(old, new, 1)


def apply(root, workspace):
    root, workspace = root.resolve(), workspace.resolve()
    sources = root / 'system/vold'
    planned = []
    for filename in PATCHES:
        path = sources / filename
        assert path.is_file(), 'Missing source: ' + str(path)
        assert root in path.resolve().parents, 'Source path leaves the source tree'
        before = path.read_bytes()
        text = before.decode('utf-8')
        updated = transform(text, filename).encode('utf-8')
        planned.append((path, before, updated))
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup = workspace / 'artifacts' / ('fbe-diag-v3-source-before-' + stamp)
    backup.mkdir(parents=True)
    report = []
    for path, before, updated in planned:
        shutil.copy2(path, backup / path.name)
        if before != updated:
            path.write_bytes(updated)
        report.append({'path': str(path.relative_to(root)), 'before_sha256': digest(before),
                       'after_sha256': digest(updated), 'changed': before != updated})
    (backup / 'changes.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print('Applied PCHM30 FBE diagnostic logging; encryption decisions unchanged.')
    print('Source backup:', backup)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('/opt/twrp'))
    parser.add_argument('--workspace', type=Path, default=Path('/workspace'))
    args = parser.parse_args()
    apply(args.root, args.workspace)
