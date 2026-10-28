"""Boot v1/newc and AArch64 ABI verification shared with the frozen PCHM30 build."""
from dataclasses import dataclass
import hashlib,struct,posixpath
from pathlib import PurePosixPath
from verify_support import elf_info, resolve_archive_path

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

