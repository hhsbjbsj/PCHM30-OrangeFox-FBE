#!/usr/bin/env python3
"""Build an explicitly experimental TWRP UI on the user's working runtime.

The reference ramdisk stays coherent: no individual platform libraries are mixed.
Only the freshly compiled recovery executable and its theme/resources are used.
All Android archives are parsed in memory and are never extracted or executed.
"""
import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path, PurePosixPath
import posixpath
import struct

from verify_support import elf_info, resolve_archive_path


HERE = Path(__file__).resolve().parent
KERNEL_SHA = 'd83bf44d06a1ed1aeb7c8d597bbccd627458e7619e8606218f33358d145a0f1b'
DTBO_SHA = 'b11c7c246bd74a010718124f25ff92f332304bd892b66eecd18b300417dbf270'
RAMDISK_SHA = '4a9a6b42fea29258141ee84ceb5c4852e25dc4a859144fd81915b4e6ee3093c7'
HEADER_SHA = 'afeb63f25b203d4aac3914fbd84547d7b3209d7b5b85a8348596c39fc282a02a'
LIMIT = 67108864


def sha(data):
    return hashlib.sha256(data).hexdigest()


def aligned(size, page=4096):
    return (size + page - 1) // page * page


@dataclass
class Record:
    name: str
    fields: list
    data: bytes

    @property
    def mode(self):
        return self.fields[1]


def parse_cpio(data):
    records, names, cursor = [], set(), 0
    while cursor + 110 <= len(data):
        header = data[cursor:cursor + 110]
        assert header[:6] == b'070701', 'Expected newc CPIO'
        fields = [int(header[6+i*8:14+i*8], 16) for i in range(13)]
        size, name_size = fields[6], fields[11]
        cursor += 110
        assert 0 < name_size <= len(data) - cursor
        name_bytes = data[cursor:cursor + name_size]
        assert name_bytes[-1:] == b'\0'
        name = name_bytes[:-1].decode('utf-8')
        while name.startswith('./'):
            name = name[2:]
        cursor = aligned(cursor + name_size, 4)
        assert cursor + size <= len(data), 'Truncated CPIO entry'
        content = data[cursor:cursor + size]
        cursor = aligned(cursor + size, 4)
        if name == 'TRAILER!!!':
            return records
        assert not name.startswith('/') and '..' not in PurePosixPath(name).parts
        assert name not in names, 'Duplicate CPIO path: ' + name
        names.add(name)
        # Unique inodes can be assigned only when regular files are not hardlinks.
        if fields[1] & 0xF000 == 0x8000:
            assert fields[4] == 1, 'Unsupported regular hardlink: ' + name
        records.append(Record(name, fields, content))
    raise AssertionError('CPIO trailer not found')


def serialize_cpio(records):
    output = bytearray()
    trailer = Record('TRAILER!!!', [0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 11, 0], b'')
    for inode, record in enumerate([*records, trailer], 1):
        name = record.name.encode() + b'\0'
        fields = record.fields.copy()
        fields[0], fields[6], fields[11], fields[12] = inode, len(record.data), len(name), 0
        output.extend(b'070701' + b''.join(f'{n:08x}'.encode() for n in fields))
        output.extend(name)
        output.extend(bytes((-len(output)) % 4))
        output.extend(record.data)
        output.extend(bytes((-len(output)) % 4))
    output.extend(bytes((-len(output)) % 512))
    return bytes(output)


def boot_parts(image):
    assert image[:8] == b'ANDROID!' and len(image) >= 4096
    u32 = lambda offset: struct.unpack_from('<I', image, offset)[0]
    page, version = u32(36), u32(40)
    assert page == 4096 and version == 1
    assert u32(24) == 0, 'Second-stage image is not expected'
    kernel_size, ramdisk_size = u32(8), u32(16)
    ramdisk_offset = page + aligned(kernel_size, page)
    dtbo_size = u32(1632)
    dtbo_offset = struct.unpack_from('<Q', image, 1636)[0]
    assert ramdisk_offset + ramdisk_size <= len(image)
    assert dtbo_size and dtbo_offset + dtbo_size <= len(image)
    kernel = image[page:page + kernel_size]
    ramdisk = image[ramdisk_offset:ramdisk_offset + ramdisk_size]
    dtbo = image[dtbo_offset:dtbo_offset + dtbo_size]
    boot_id = hashlib.sha1()
    for part in (kernel, ramdisk, b'', dtbo):
        boot_id.update(part)
        boot_id.update(struct.pack('<I', len(part)))
    assert boot_id.digest() == image[576:596], 'Invalid Android boot image ID'
    return kernel, ramdisk, dtbo


def symbol_sets(data):
    """Read dynamic symbol names, including version requirements/definitions."""
    elf_info(data)  # Reject non-AArch64 and malformed program tables.
    shoff = struct.unpack_from('<Q', data, 40)[0]
    shsize, count = struct.unpack_from('<HH', data, 58)
    assert shoff and shsize >= 64 and shoff + shsize * count <= len(data)
    sections = []
    for i in range(count):
        values = struct.unpack_from('<IIQQQQIIQQ', data, shoff + i * shsize)
        # NOBITS sections occupy no file bytes.
        if values[1] != 8:
            assert values[4] + values[5] <= len(data)
        sections.append(values)

    def string(section, offset):
        table = sections[section]
        start, size = table[4], table[5]
        assert offset < size
        end = data.find(b'\0', start + offset, start + size)
        assert end >= start + offset
        return data[start + offset:end].decode()

    version_names = {}
    for section in sections:
        kind, start, size, link = section[1], section[4], section[5], section[6]
        pos = start
        if kind == 0x6FFFFFFD:  # SHT_GNU_verdef
            while pos < start + size:
                _, _, index, _, _, aux, nxt = struct.unpack_from('<HHHHIII', data, pos)
                name_offset = struct.unpack_from('<I', data, pos + aux)[0]
                version_names[index & 0x7FFF] = string(link, name_offset)
                if not nxt:
                    break
                pos += nxt
        elif kind == 0x6FFFFFFE:  # SHT_GNU_verneed
            while pos < start + size:
                _, aux_count, _, aux, nxt = struct.unpack_from('<HHIII', data, pos)
                ap = pos + aux
                for _ in range(aux_count):
                    _, _, index, name_offset, anext = struct.unpack_from('<IHHII', data, ap)
                    version_names[index & 0x7FFF] = string(link, name_offset)
                    if not anext:
                        break
                    ap += anext
                if not nxt:
                    break
                pos += nxt
    exports, imports = set(), set()
    for index, section in enumerate(sections):
        if section[1] != 11:
            continue
        start, size, strings, entry = section[4], section[5], section[6], section[9]
        assert entry >= 24 and size % entry == 0
        versions = next((s for s in sections if s[1] == 0x6FFFFFFF and s[6] == index), None)
        for i, pos in enumerate(range(start, start + size, entry)):
            name_offset, info, other, defined = struct.unpack_from('<IBBH', data, pos)
            name = string(strings, name_offset)
            if not name:
                continue
            binding, visibility = info >> 4, other & 3
            version = None
            if versions:
                assert (i+1) * 2 <= versions[5]
                number = struct.unpack_from('<H', data, versions[4]+i*2)[0] & 0x7FFF
                if number > 1:
                    assert number in version_names, 'Unknown ELF symbol version'
                    version = version_names[number]
            if not defined and binding == 1:
                imports.add((name, version))
            elif defined and binding in (1, 2, 10) and visibility in (0, 3):
                exports.add((name, version))
                # Unversioned lookups may use a library's exported default symbols.
                exports.add((name, None))
    return exports, imports


def abi_preflight(records):
    files = {r.name: (r.mode, r.data) for r in records}
    roots = [
        'system/bin/recovery', 'system/bin/adbd', 'system/bin/keystore2',
        'system/bin/hwservicemanager', 'system/bin/qseecomd',
        'system/bin/android.hardware.keymaster@4.0-service-qti',
        'system/bin/android.hardware.gatekeeper@1.0-service-qti',
        'vendor/lib64/hw/android.hardware.gatekeeper@1.0-impl-qti.so',
    ]
    symbol_cache, checked_counts = {}, {}
    for root in roots:
        vendor_first = root.startswith('vendor/') or root in roots[4:7]
        search = ['vendor/lib64', 'system/lib64'] if vendor_first else ['system/lib64', 'vendor/lib64']
        search += ['system/lib64/bootstrap', 'sbin']
        pending, checked = [root, 'system/bin/linker64'], set()
        while pending:
            requested = pending.pop()
            actual = resolve_archive_path(files, requested)
            assert actual, 'Missing dependency: ' + requested
            if actual in checked:
                continue
            checked.add(actual)
            needed, runpaths, interpreter = elf_info(files[actual][1])
            if interpreter:
                pending.append(interpreter)
            origin = posixpath.dirname(actual)
            extra = [p.replace('$ORIGIN', origin).lstrip('/') for p in runpaths]
            for library in needed:
                candidates = [library] if '/' in library else [p+'/'+library for p in extra+search]
                found = next((resolved for candidate in candidates
                              for resolved in [resolve_archive_path(files, candidate)] if resolved), None)
                assert found, root + ': ' + actual + ' needs ' + library
                pending.append(found)
        available = set()
        for path in checked:
            if path not in symbol_cache:
                symbol_cache[path] = symbol_sets(files[path][1])
            available.update(symbol_cache[path][0])
        missing = []
        for path in checked:
            for symbol in symbol_cache[path][1] - available:
                missing.append(path + ' -> ' + symbol[0] + ('@'+symbol[1] if symbol[1] else ''))
        assert not missing, 'Unresolved versioned dynamic symbols:\n' + '\n'.join(sorted(missing))
        checked_counts[root] = len(checked)
    return checked_counts


def is_ui(name):
    return name in ('twres', 'res') or name.startswith(('twres/', 'res/'))


def make_image(built_path, output, build_kind):
    built = built_path.read_bytes()
    kernel, ramdisk, dtbo = boot_parts(built)
    assert sha(kernel) == KERNEL_SHA, 'Unexpected compiled-image kernel'
    assert sha(dtbo) == DTBO_SHA, 'Unexpected compiled-image DTBO'
    built_records = parse_cpio(gzip.decompress(ramdisk))
    built_files = {r.name: r for r in built_records}
    recovery = built_files['system/bin/recovery']
    assert recovery.mode & 0o111 and recovery.data.startswith(b'\x7fELF\x02')
    assert b'/system/bin/postscreenunblank.sh' in recovery.data
    assert b'ro.build.version.sdk=32' in built_files['prop.default'].data.splitlines()
    assert 'twres/ui.xml' in built_files or any(n.startswith('twres/') and n.endswith('.xml') for n in built_files)
    reference_gz = (HERE / 'assets/reference-ramdisk.gz').read_bytes()
    reference_header = (HERE / 'assets/reference-header.bin').read_bytes()
    assert sha(reference_gz) == RAMDISK_SHA and sha(reference_header) == HEADER_SHA
    reference = parse_cpio(gzip.decompress(reference_gz))
    reference_map = {r.name: r for r in reference}
    for path in (
        'system/lib64/libresetprop.so', 'system/bin/postscreenunblank.sh',
        'system/bin/pchm30-bootflow-a2.sh', 'system/bin/pchm30-precrypto.sh',
        'system/bin/prepdecrypt.sh', 'init.recovery.qcom_decrypt.rc',
        'init.recovery.qcom_decrypt.fbe.rc', 'init.recovery.usb.rc',
    ):
        assert path in reference_map, 'Reference is missing ' + path
    assert b'/sys/kernel/oppo_display/notify_panel_blank' in reference_map['system/bin/postscreenunblank.sh'].data
    records = [r for r in reference if r.name != 'system/bin/recovery' and not is_ui(r.name)]
    records += [recovery] + [r for r in built_records if is_ui(r.name)]
    marker = {
        'experiment': 'PCHM30 TWRP12.1 UI with Golden AB10 runtime',
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'build_kind': build_kind, 'built_input_sha256': sha(built),
        'twrp_recovery_sha256': sha(recovery.data),
        'reference_ramdisk_sha256': RAMDISK_SHA,
        'changed_from_reference': ['system/bin/recovery', 'res/**', 'twres/**',
                                   'system/etc/pchm30-experiment.json',
                                   'ramdisk-files.txt', 'ramdisk-files.sha256sum'],
        'runtime_libraries': 'all retained from the user-tested Golden reference',
        'device_boot': 'not tested', 'decryption': 'not tested',
    }
    marker_data = (json.dumps(marker, indent=2)+'\n').encode()
    marker_fields = [0, 0o100644, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0]
    records.append(Record('system/etc/pchm30-experiment.json', marker_fields, marker_data))
    # Refresh informational inventories after changing the executable and theme.
    inventories = ('ramdisk-files.txt', 'ramdisk-files.sha256sum')
    records = [r for r in records if r.name not in inventories]
    file_names = [r.name for r in records] + list(inventories)
    listing = ('\n'.join(file_names)+'\n').encode()
    sums = ''.join(sha(r.data)+'  ./'+r.name+'\n' for r in records
                   if r.mode & 0xF000 == 0x8000).encode()
    records += [Record(inventories[0], marker_fields, listing),
                Record(inventories[1], marker_fields, sums)]
    output_map = {r.name: r for r in records}
    assert len(output_map) == len(records)
    for name, record in reference_map.items():
        if name == 'system/bin/recovery' or is_ui(name) or name in inventories:
            continue
        assert name in output_map and output_map[name].data == record.data
        assert output_map[name].mode == record.mode
    dependency_counts = abi_preflight(records)
    new_cpio = serialize_cpio(records)
    reparsed = parse_cpio(new_cpio)
    assert [(r.name, r.mode, r.data) for r in reparsed] == [(r.name, r.mode, r.data) for r in records]
    new_ramdisk = gzip.compress(new_cpio, compresslevel=9, mtime=0)
    dtbo_offset = 4096 + aligned(len(kernel)) + aligned(len(new_ramdisk))
    header = bytearray(reference_header)
    struct.pack_into('<I', header, 8, len(kernel))
    struct.pack_into('<I', header, 16, len(new_ramdisk))
    struct.pack_into('<I', header, 24, 0)
    struct.pack_into('<I', header, 1632, len(dtbo))
    struct.pack_into('<Q', header, 1636, dtbo_offset)
    boot_id = hashlib.sha1()
    for part in (kernel, new_ramdisk, b'', dtbo):
        boot_id.update(part)
        boot_id.update(struct.pack('<I', len(part)))
    header[576:608] = boot_id.digest() + bytes(12)
    image = bytes(header) + kernel + bytes((-len(kernel)) % 4096)
    image += new_ramdisk + bytes((-len(new_ramdisk)) % 4096)
    assert len(image) == dtbo_offset
    image += dtbo + bytes((-len(dtbo)) % 4096)
    assert len(image) <= LIMIT, 'Image exceeds the 64 MiB recovery partition'
    assert boot_parts(image) == (kernel, new_ramdisk, dtbo)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(image)
    report = dict(marker, image=output.name, sha256=sha(image), bytes=len(image),
                  kernel_sha256=sha(kernel), dtbo_sha256=sha(dtbo),
                  boot_image_id_valid=True, dependency_files_by_root=dependency_counts,
                  versioned_dynamic_symbols_resolved=True,
                  reference_non_ui_files_unchanged=True)
    output.with_suffix('.img.verification.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    output.with_suffix('.img.sha256').write_text(sha(image)+'  '+output.name+'\n', encoding='ascii')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--built', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--build-kind', choices=['cnb-source-build', 'existing-compiled-binary-repack'], required=True)
    args = parser.parse_args()
    make_image(args.built, args.output, args.build_kind)
