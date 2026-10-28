# PCHM30 TWRP12.1 FBE V5 · BusyBox / Android 16 SPL 集成测试版

适用设备：OPPO A11x / PCHM30。基于机主提供的 TWRP V4 镜像，移植已经在同机 PBRP V2 上解密成功的配置修复。**这份新 TWRP 镜像本身尚未上机验证，发布为 Pre-release。**

## 修改

- 永久集成锁定来源与 SHA256 的静态 ARM64 BusyBox；/sbin/sh 使用静态 shell。
- init 和启动脚本均启用 prepdecrypt.setpatch=true，自动读取实际 System/Vendor 的版本及补丁日期，不写死旧日期。
- 保持物理 userdata 为 ext4 / fscrypt v1 wrappedkey，修正 fstab 合并；System 使用 /system_root，防止遮住 Recovery 自身工具。
- 原 TWRP 界面程序、资源、内核、DTBO 和平台运行库不替换。仍为 SDK32 基底；不是 TWRP14/SDK34 升级。
- 附带 ROM 安装器工具回退修复和设备覆盖层源码、ramdisk 重建脚本。

## 验证范围

原始 V4 镜像 SHA256：`2a2382b57e22554ce816594164cc00920bd43b5ab46da5da2716b0e27369ca47`。
原始 recovery 主程序 SHA256：`67c2609e3003e504c0bb9e11d479e21d7ee04455034782e26aa62d90395542e7`，新版保持一致。

检查 boot image ID、64MiB 分区上限、AArch64 ELF 依赖和原平台库保持一致。相同修复的 BusyBox、toybox 回退及属性同步脚本先前在同机执行过测试，PBRP V2 的 Android16 解密由机主确认成功；**这些结果不代表新 TWRP 的启动、触控和解密已经实测通过。**

## 下载与安装

- `.img`：TWRP V5 测试镜像。
- `PCHM30-TWRP12.1-FBE-V5-SOURCE.zip`：设备配置、BusyBox、重建工具及 ROM 安装器修复。
- `BUILD-REPORT-V5.json`、`SHA256SUMS`：构建检查与附件校验。

在已验证的 Recovery 中安装镜像，目标选择 **Recovery 分区**，完成后重启 Recovery。无需格式化 Data。旧 TWRP V4 与 PBRP V2 发布保持可用。

## 重建

源码在本标签 `stable/pchm30-twrp12-v5/`。`repack.py --input 原V4.img --output 新镜像.img` 可重建 ramdisk。
现有锁定 TWRP 源码缓存可使用 `rebuild.sh` 先运行原 V4 配方再应用覆盖层；脚本会检查主程序散列，不接受未经验证的新主程序。未修改 ROM 设备树以冒充 Recovery 设备树。

BusyBox 的来源与许可证一并附带。这里是对已有编译镜像的 ramdisk 重建，没有重新编译全部 C++。
