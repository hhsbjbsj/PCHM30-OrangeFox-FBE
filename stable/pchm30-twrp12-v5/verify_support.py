#!/usr/bin/env python3
"""Inspect the actual packed image, without extracting or executing its files."""
import gzip
import hashlib
import json
from pathlib import Path, PurePosixPath
import posixpath
import struct
import sys


def digest(data):
    return hashlib.sha256(data).hexdigest()


def entries(blob):
    result = {}
    off = 0
    while off + 110 <= len(blob):
        header = blob[off:off + 110]
        assert header[:6] in (b"070701", b"070702"), "Invalid CPIO header"
        size = int(header[54:62], 16)
        namesize = int(header[94:102], 16)
        mode = int(header[14:22], 16)
        off += 110
        assert 0 < namesize <= len(blob) - off, "Invalid CPIO name"
        raw_name = blob[off:off + namesize]
        assert raw_name.endswith(b"\0"), "Unterminated CPIO name"
        name = raw_name[:-1].decode("utf-8", errors="surrogateescape")
        while name.startswith("./"):
            name = name[2:]
        assert not name.startswith("/") and ".." not in PurePosixPath(name).parts
        off = (off + namesize + 3) & ~3
        assert off + size <= len(blob), "Truncated CPIO payload"
        data = blob[off:off + size]
        off = (off + size + 3) & ~3
        if name == "TRAILER!!!":
            return result
        assert name not in result, "Duplicate archive path: " + name
        result[name] = (mode, data)
    raise AssertionError("Missing CPIO trailer")


def elf_info(data):
    assert data[:6] == b"\x7fELF\x02\x01", "Expected little-endian arm64 ELF"
    assert struct.unpack_from("<H", data, 18)[0] == 183, "Expected AArch64 machine"
    phoff = struct.unpack_from("<Q", data, 32)[0]
    phsize, phcount = struct.unpack_from("<HH", data, 54)
    assert phsize >= 56 and phoff + phsize * phcount <= len(data)
    loads, dynamic, interpreter = [], None, None
    for index in range(phcount):
        ph = phoff + index * phsize
        kind = struct.unpack_from("<I", data, ph)[0]
        offset, address = struct.unpack_from("<QQ", data, ph + 8)
        size = struct.unpack_from("<Q", data, ph + 32)[0]
        assert offset + size <= len(data)
        if kind == 1:
            loads.append((address, offset, size))
        elif kind == 2:
            dynamic = (offset, size)
        elif kind == 3:
            interpreter = data[offset:offset + size].split(b"\0", 1)[0].decode()
    tags = []
    if dynamic:
        offset, size = dynamic
        for cursor in range(offset, offset + size, 16):
            kind, value = struct.unpack_from("<qQ", data, cursor)
            if kind == 0:
                break
            tags.append((kind, value))
    pointers = [value for kind, value in tags if kind == 5]
    if not pointers:
        return [], [], interpreter
    pointer = pointers[0]
    string_size = next(value for kind, value in tags if kind == 10)
    segment = next(
        item for item in loads if item[0] <= pointer < item[0] + item[2])
    start = segment[1] + pointer - segment[0]
    assert start + string_size <= len(data)
    pool = data[start:start + string_size]

    def string(index):
        assert index < len(pool)
        end = pool.find(b"\0", index)
        assert end >= index
        return pool[index:end].decode()

    needed = [string(value) for kind, value in tags if kind == 1]
    runpaths = [
        part for kind, value in tags if kind in (15, 29)
        for part in string(value).split(":") if part
    ]
    return needed, runpaths, interpreter


def resolve_archive_path(files, path):
    """Follow archive symlinks in memory, never against the host filesystem."""
    pending = path.lstrip("/").split("/")
    resolved, links = [], 0
    while pending:
        part = pending.pop(0)
        if part in ("", "."):
            continue
        if part == "..":
            if not resolved:
                return None
            resolved.pop()
            continue
        resolved.append(part)
        record = files.get("/".join(resolved))
        if record and record[0] & 0xF000 == 0xA000:
            links += 1
            assert links <= 64, "Archive symlink loop"
            target = record[1].decode()
            resolved.pop()
            if target.startswith("/"):
                resolved = []
            pending = target.split("/") + pending
    result = "/".join(resolved)
    return result if result in files else None


def check_dependency_files(files):
    roots = ["system/bin/recovery", "system/bin/adbd"]
    search = ["system/lib64", "vendor/lib64",
              "system/lib64/bootstrap", "sbin"]
    pending, checked, missing = roots[:], set(), []
    while pending:
        requested = pending.pop()
        path = resolve_archive_path(files, requested)
        assert path is not None, "Missing executable/interpreter: " + requested
        if path in checked:
            continue
        checked.add(path)
        needed, runpaths, interpreter = elf_info(files[path][1])
        if interpreter:
            pending.append(interpreter)
        origin = posixpath.dirname(path)
        extra = [p.replace("$ORIGIN", origin).lstrip("/") for p in runpaths]
        for library in needed:
            candidates = (
                [library] if "/" in library else
                [p + "/" + library for p in extra + search]
            )
            actual = next(
                (result for candidate in candidates
                 for result in [resolve_archive_path(files, candidate)]
                 if result is not None), None)
            if actual:
                pending.append(actual)
            else:
                missing.append(path + " -> " + library)
    assert not missing, "Unresolved ELF dependencies:\n" + "\n".join(missing)
    return roots, len(checked)


def verify(path):
    image = path.read_bytes()
    assert image[:8] == b"ANDROID!", "Invalid boot magic"
    u32 = lambda offset: struct.unpack_from("<I", image, offset)[0]
    assert u32(40) == 1, "Unexpected boot header version"
    page, kernel_size, ramdisk_size = u32(36), u32(8), u32(16)
    assert page == 4096, "Unexpected page size"
    assert len(image) <= 67108864, "Image exceeds the recovery partition"
    ramdisk_offset = page + ((kernel_size + page - 1) // page) * page
    dtbo_size = u32(1632)
    dtbo_offset = struct.unpack_from("<Q", image, 1636)[0]
    assert ramdisk_offset + ramdisk_size <= len(image), "Truncated ramdisk"
    assert dtbo_size and dtbo_offset + dtbo_size <= len(image), "Truncated DTBO"
    kernel_sha = digest(image[page:page + kernel_size])
    dtbo_sha = digest(image[dtbo_offset:dtbo_offset + dtbo_size])
    assert kernel_sha == "d83bf44d06a1ed1aeb7c8d597bbccd627458e7619e8606218f33358d145a0f1b"
    assert dtbo_sha == "b11c7c246bd74a010718124f25ff92f332304bd892b66eecd18b300417dbf270"
    second_size = u32(24)
    second_offset = ramdisk_offset + (
        (ramdisk_size + page - 1) // page) * page
    assert second_offset + second_size <= len(image), "Truncated second stage"
    boot_id = hashlib.sha1()
    for data in (
        image[page:page + kernel_size],
        image[ramdisk_offset:ramdisk_offset + ramdisk_size],
        image[second_offset:second_offset + second_size],
        image[dtbo_offset:dtbo_offset + dtbo_size],
    ):
        boot_id.update(data)
        boot_id.update(struct.pack("<I", len(data)))
    assert image[576:596] == boot_id.digest(), "Invalid boot image SHA1 ID"
    ramdisk = gzip.decompress(
        image[ramdisk_offset:ramdisk_offset + ramdisk_size])
    files = entries(ramdisk)
    assert "vendor" in files and files["vendor"][0] & 0xF000 == 0x4000, \
        "The ramdisk vendor mount point is not a real directory"
    required = ("init.recovery.usb.rc", "init.recovery.qcom.rc",
                "system/etc/recovery.fstab", "system/bin/recovery",
                "system/bin/adbd", "system/lib64/libminuitwrp.so",
                "system/lib64/libresetprop.so",
                "system/bin/postscreenunblank.sh")
    for name in required:
        assert name in files and files[name][1], "Missing image file: " + name
    wake_mode, wake_data = files["system/bin/postscreenunblank.sh"]
    assert wake_mode & 0o111, "Screen-unblank script is not executable"
    assert b"/sys/kernel/oppo_display/notify_panel_blank" in wake_data, \
        "Missing OPPO panel notification in screen-unblank script"
    assert b"echo 1" in wake_data, "Missing panel-unblank notification"
    assert b"/system/bin/postscreenunblank.sh" in files["system/bin/recovery"][1], \
        "Recovery does not include the screen-unblank hook"
    assert b"RECOVERY_BGRA" in files["system/lib64/libminuitwrp.so"][1], \
        "The packed display library was not built with RECOVERY_BGRA"
    prop = files.get("prop.default", (0, b""))[1]
    assert b"ro.build.version.sdk=32" in prop.splitlines(), \
        "The packed image is not Android SDK 32"
    executable = files["system/bin/recovery"][1]
    assert executable[:5] == b"\x7fELF\x02", "Recovery is not a 64-bit ELF"
    dependency_roots, dependency_count = check_dependency_files(files)
    report = {
        "image": path.name, "sha256": digest(image),
        "bytes": len(image), "header_version": 1, "pagesize": page,
        "boot_image_id_valid": True,
        "kernel_sha256": kernel_sha, "dtbo_sha256": dtbo_sha,
        "android_sdk": 32, "display_bgra": True,
        "oppo_screen_unblank_hook_present": True,
        "usb_init_present": True, "required_files_present": list(required),
        "elf_dependency_roots": dependency_roots,
        "elf_dependency_files_checked": dependency_count,
        "unresolved_elf_dependency_files": [],
        "purpose": "startup and ADB validation; FBE is not yet validated",
        "device_test": "not performed",
    }
    path.with_suffix(path.suffix + ".verification.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8")
    path.with_suffix(path.suffix + ".sha256").write_text(
        report["sha256"] + "  " + path.name + "\n", encoding="ascii")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    assert len(sys.argv) == 2, "Usage: verify.py recovery.img"
    verify(Path(sys.argv[1]))
