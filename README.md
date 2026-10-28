# PCHM30 OrangeFox FBE Recovery

A working OrangeFox recovery build for **OPPO A11x / PCHM30 / OP4A54** based on the SM6125 platform.

## PBRP V2：Android 16 Data 解密已实测（2026-10-28）

[下载新发布 pchm30-pbrp12.1-fbe-v2](https://github.com/hhsbjbsj/PCHM30-OrangeFox-FBE/releases/tag/pchm30-pbrp12.1-fbe-v2)。
集成静态 BusyBox、真实系统 SPL 同步和 ext4 修复，仍为 SDK32 基底。
详见 [发布说明](docs/PBRP12-FBE-V2.md) 和 [源码](stable/pchm30-pbrp12-v2/README.md)。下文保留原 OrangeFox 基线记录。

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


## TWRP 12.1 FBE V4（2026-10-26）

PCHM30 新增 TWRP V4 基线：[构建、补丁与实测记录](stable/pchm30-v4/README.md)。
用户已在当前系统、无锁屏密码的条件下确认自动解密成功及功能正常；
ADB 确认用户 0 解密状态为 1。核心配置为 `TW_PREPARE_DATA_MEDIA_EARLY := true`。

这是 TWRP 主程序/界面源码构建与既有 Golden AB10 运行基底的组合。
本目录保留现有橙狐基线；新 TWRP 记录位于独立的 `stable/pchm30-v4` 目录。

实测镜像 SHA256：`2a2382b57e22554ce816594164cc00920bd43b5ab46da5da2716b0e27369ca47`。


V4 固定版本与源码锁定记录：

- [镜像与完整离线源码包](https://github.com/hhsbjbsj/PCHM30-OrangeFox-FBE/releases/tag/pchm30-twrp12.1-fbe-v4)
- [249 个项目的固定清单及实际补丁](stable/pchm30-v4/locks/manifest.xml)
- [新环境重建后 828 个运行文件一致的核对记录](stable/pchm30-v4/locks/REPRODUCED.json)
- CNB 同名标签：`pchm30-twrp12.1-fbe-v4`，提交 `3e1b1d5380f3b5abf63c557b6f1746dabd378c1a`。
