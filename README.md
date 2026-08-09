# PCHM30 OrangeFox FBE Recovery

A working OrangeFox recovery build for **OPPO A11x / PCHM30 / OP4A54** based on the SM6125 platform.

## Status

Tested on the target device:

- Recovery boots normally
- Touch works
- `/data` is accessible
- Android 11 FBE decryption works
- `/sdcard` shows real filenames and directories such as `DCIM`, `Download`, and `Android`
- Dark/light OrangeFox themes work normally

## Device

| Item | Value |
|---|---|
| Device | OPPO A11x |
| Model / codename used in this project | PCHM30 / OP4A54 |
| SoC | Qualcomm SM6125 / Snapdragon 665 |
| Android | Android 11 |
| Recovery | OrangeFox 12.1-based ramdisk work |

## Final working build

Release asset:

`PCHM30-OrangeFox-RAMDISK-AB10-GOLDEN-RECOVERY-BINARY.img`

SHA256:

```text
b3d1b6a6d711e95b8b10cf0bbe33eed5ea82cff6ce845183af9210ccc6ebb14b
```

Always verify the hash before booting or flashing.

## What fixed FBE

The controlled experiments isolated the decisive FBE variable to:

```text
system/bin/recovery
```

The final AB10 experiment used the tested AB8 ramdisk baseline and replaced only
`system/bin/recovery` with the exact payload from the known-good Golden recovery.

AB10 then booted normally and showed the real decrypted filenames under `/sdcard`.

This does **not** mean the other ramdisk fixes are unnecessary. Earlier experiments
showed that the fstab/init environment was also important for reaching a usable
Recovery state. See `docs/FORENSIC_NOTES.md`.

## Recommended test method

Before permanently flashing any build, test it temporarily:

```powershell
$img="C:\path\to\PCHM30-OrangeFox-RAMDISK-AB10-GOLDEN-RECOVERY-BINARY.img"
(Get-FileHash $img -Algorithm SHA256).Hash
fastboot devices
fastboot boot $img
```

Expected SHA256:

```text
B3D1B6A6D711E95B8B10CF0BBE33EED5EA82CFF6CE845183AF9210CCC6EBB14B
```

## Repository layout

```text
scripts/
  PCHM30_RAMDISK_AB10_GOLDEN_RECOVERY_BINARY.sh
  experiments/
docs/
  FORENSIC_NOTES.md
  BUILD_MANIFEST.md
SHA256SUMS
```

The recovery image itself is distributed as a GitHub Release asset rather than
committed into Git history.

## Warning

Recovery images are device-specific. Do not use this image on unrelated devices.

Test with `fastboot boot` first whenever the bootloader supports it. Keep a known-good
recovery image available before making permanent changes.
