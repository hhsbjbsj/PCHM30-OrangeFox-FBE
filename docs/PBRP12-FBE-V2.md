# PCHM30 PBRP12.1 FBE V2 · Android 16 解密实测通过

适用设备：OPPO A11x / PCHM30。2026-10-28，机主已刷入本镜像并确认 Android 16 / LineageOS 23.2 Data 解密成功。

## 下载

- `PCHM30-PBRP12.1-FBE-V2-A16.img`：实测 Recovery 镜像，57,032,704 字节。
- `PCHM30-PBRP12.1-FBE-V2-SOURCE.zip`：设备覆盖层、静态 BusyBox、源码和重建脚本、ROM 安装器修复。
- `PCHM30-RECOVERY-A16-SOURCE-FIX.zip`：供现有 CNB 工作空间安装源码修复的便捷包。
- `DEVICE-TEST-V2.json`：后续机主实测记录；`SHA256SUMS`：附件校验值。

镜像 SHA256：`63d671f7a7cecc249330ecfe6ef94052e5946123814ba0e7c595d452e9aed50c`。
这就是已实测的 `PCHM30-PBRP-A16-INTEGRATION-TEST1.img`，发布时仅重命名，未改变镜像内容。

## 修改内容

- 永久集成静态 ARM64 BusyBox，`/sbin/sh` 使用静态 shell。
- init 和启动脚本都启用 `prepdecrypt.setpatch=true`，从实际 System/Vendor 读取版本及安全补丁日期，不再沿用过时的 2026-07-01。实测系统 SPL 为 2026-10-01。
- 修正 ext4 / fscrypt v1 wrappedkey 的 Recovery fstab 和合并脚本，避免追加其他机型的 f2fs 模板；使用 `/system_root` 避免遮住 Recovery 自身工具。
- 配套 ROM `update-binary` 可逐工具回退到 toybox 或独立命令，保留原有分区、大小、SHA256 和写后回读检查。已在手机验证工具、解包及临时文件 I/O；修改仅作用于使用新安装器生成或重新打包的 ROM ZIP。

## 安装与范围

在已验证可用的 PBRP/TWRP 中安装镜像，目标选 **Recovery 分区**，完成后重启 Recovery。无需格式化 Data；原 V1 发布保留。

本版仍是 **PBRP/TWRP 12.1 / SDK32 基底**：本次重建 ramdisk，没有重新编译全部 C++，也没有升级至 TWRP 14。内核、DTBO、Recovery 主程序和原平台库保持一致。

确认范围是本机当前 Android16 系统的解密成功；未宣称所有 ROM、所有锁屏类型及其他功能都已重新验证。镜像内或源码中的旧构建记录仍可能显示 `not tested`，它们记录生成时状态；本次后续实测以 `DEVICE-TEST-V2.json` 为准。

源码位于本标签的 `stable/pchm30-pbrp12-v2/`，许可证、BusyBox 来源与对应源码链接一并附带。已有锁定 PBRP 源码缓存时可使用目录内 `rebuild.sh`，最终必须保留设备覆盖层的 repack 步骤。
