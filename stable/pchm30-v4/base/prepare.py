#!/usr/bin/env python3
"""Prepare the source-built UI for the Golden-runtime experiment."""
import argparse
import hashlib
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET


KERNEL_SHA = "d83bf44d06a1ed1aeb7c8d597bbccd627458e7619e8606218f33358d145a0f1b"
DTBO_SHA = "b11c7c246bd74a010718124f25ff92f332304bd892b66eecd18b300417dbf270"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def put(path, text):
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def original(device, name):
    """Use the cached device repository's committed input on every run."""
    return subprocess.check_output(
        ["git", "-C", str(device), "show", "HEAD:" + name],
        text=True, encoding="utf-8",
    )


def setting(text, key, value):
    text = re.sub(
        r"^" + re.escape(key) + r"\s*(?:[:+?])?=.*(?:\n|$)",
        "", text, flags=re.MULTILINE,
    )
    return text.rstrip() + "\n" + key + " := " + value + "\n"


def prepare(root, workspace):
    root, workspace = root.resolve(), workspace.resolve()
    device = root / "device/oppo/PCHM30"
    manifest = root / ".repo/manifests/twrp-default.xml"
    assert manifest.is_file(), "Missing TWRP 12.1 manifest"
    projects = ET.parse(manifest).getroot().findall("project")
    assert any(
        p.get("path") == "bootable/recovery"
        and p.get("revision") == "android-12.1" for p in projects
    ), "This script requires the TWRP android-12.1 source"
    for relative in (
        "build/envsetup.sh", "vendor/twrp/config/common.mk",
        "build/make/target/product/core_64_bit_only.mk",
    ):
        assert (root / relative).is_file(), "Missing " + relative
    assert sha256(device / "prebuilt/kernel") == KERNEL_SHA, "Unexpected kernel"
    assert sha256(device / "prebuilt/dtbo.img") == DTBO_SHA, "Unexpected DTBO"

    names = (
        "BoardConfig.mk", "AndroidProducts.mk", "omni_PCHM30.mk",
        "device.mk", "vendorsetup.sh", "recovery/root/init.recovery.qcom.rc",
    )
    originals = {name: original(device, name) for name in names}
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup = workspace / "artifacts" / ("device-config-before-" + stamp)
    wake_path = "recovery/root/system/bin/postscreenunblank.sh"
    for name in names + ("twrp_PCHM30.mk", wake_path):
        source = device / name
        if source.is_file():
            target = backup / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

    board = originals["BoardConfig.mk"]
    board = re.sub(r"^TARGET_2ND_[A-Z0-9_]+\s*(?:[:+?])?=.*(?:\n|$)",
                   "", board, flags=re.MULTILINE)
    # The old tree excluded the stock USB init file without supplying its own.
    # Leave the switch unset so upstream 12.1 installs its default USB init.
    board = re.sub(r"^TW_EXCLUDE_DEFAULT_USB_INIT\s*(?:[:+?])?=.*(?:\n|$)",
                   "", board, flags=re.MULTILINE)
    board = setting(board, "TARGET_RECOVERY_PIXEL_FORMAT", '"BGRA_8888"')
    board = setting(board, "TARGET_RECOVERY_FSTAB",
                    "$(DEVICE_PATH)/recovery.fstab")
    board = setting(board, "TARGET_COPY_OUT_VENDOR", "vendor")
    board = setting(board, "TW_INCLUDE_LIBRESETPROP", "true")
    board = setting(board, "TARGET_NO_BOOTLOADER", "true")
    board += "\nTARGET_RECOVERY_DEVICE_MODULES += libresetprop.recovery\n"
    board += "\n# Startup test: retain the existing prebuilt kernel and DTBO.\n"
    put(device / "BoardConfig.mk", board)

    product = originals["omni_PCHM30.mk"]
    product = product.replace("omni_PCHM30", "twrp_PCHM30")
    product = product.replace("product/core_64_bit.mk",
                              "product/core_64_bit_only.mk")
    base = "$(call inherit-product, $(SRC_TARGET_DIR)/product/base.mk)"
    assert base in product, "Unrecognized product base"
    common = "$(call inherit-product, vendor/twrp/config/common.mk)"
    if common not in product:
        product = product.replace(base, base + "\n" + common)
    product += "\n# Install the recovery variant into the recovery ramdisk.\n"
    product += "PRODUCT_PACKAGES += libresetprop.recovery\n"
    put(device / "twrp_PCHM30.mk", product)
    put(
        device / "AndroidProducts.mk",
        originals["AndroidProducts.mk"].replace("omni_PCHM30", "twrp_PCHM30"),
    )
    put(
        device / "vendorsetup.sh",
        "# Lunch products are registered by AndroidProducts.mk.\n",
    )

    device_mk = originals["device.mk"]
    dtbo_copy = (
        "PRODUCT_COPY_FILES += \\\n"
        "    $(LOCAL_PATH)/prebuilt/dtbo.img:$(PRODUCT_OUT)/dtbo.img"
    )
    assert dtbo_copy in device_mk, "Unrecognized DTBO copy rule"
    device_mk = device_mk.replace(
        dtbo_copy, "# DTBO is installed by BOARD_PREBUILT_DTBOIMAGE.")
    # Preserve init files in TARGET_ROOT_OUT, as expected by ramdisk assembly.
    put(device / "device.mk", device_mk)
    put(device / "recovery/root/init.recovery.qcom.rc",
        originals["recovery/root/init.recovery.qcom.rc"])
    # Same panel notification used by the user's working OrangeFox ramdisk.
    # Upstream gui/blanktimer.cpp calls this script after unblanking.
    wake_script = device / wake_path
    wake_script.parent.mkdir(parents=True, exist_ok=True)
    put(wake_script,
        '#!/system/bin/sh\n'
        'NODE=/sys/kernel/oppo_display/notify_panel_blank\n'
        '[ -e "$NODE" ] && echo 1 > "$NODE"\n'
        'exit 0\n')
    wake_script.chmod(0o755)

    # Migrate the generated link left by the old system/vendor layout.
    # Only the link itself is moved; its target and recovery/vendor are untouched.
    generated_vendor = (
        root / "out-pchm30-twrp12-boot-test/target/product/PCHM30/root/vendor"
    )
    parent = generated_vendor.parent.resolve()
    assert parent == root or root in parent.parents, "Output escaped source root"
    if generated_vendor.is_symlink():
        shutil.move(
            str(generated_vendor), str(backup / "generated-root-vendor.symlink")
        )
        generated_vendor.mkdir()
        print("Archived old generated vendor symlink:", backup)
    elif generated_vendor.exists():
        assert generated_vendor.is_dir(), "Unexpected vendor output type"

    snapshot = workspace / "artifacts" / "twrp12-boot-test-device-config"
    for name in ("BoardConfig.mk", "AndroidProducts.mk", "twrp_PCHM30.mk",
                 "device.mk", "vendorsetup.sh"):
        snapshot.mkdir(parents=True, exist_ok=True)
        shutil.copy2(device / name, snapshot / name)
    print("Prepared twrp_PCHM30-eng: TWRP 12.1, arm64, BGRA_8888, default USB init.")
    print("Original kernel and DTBO unchanged.")
    print("Installed reference postscreenunblank.sh; touch resume needs device testing.")
    print("This source step builds the TWRP UI. make_image.py applies the reference FBE runtime afterward.")
    print("Configuration backup:", backup)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("/opt/twrp"))
    parser.add_argument("--workspace", type=Path, default=Path("/workspace"))
    args = parser.parse_args()
    prepare(args.root, args.workspace)
