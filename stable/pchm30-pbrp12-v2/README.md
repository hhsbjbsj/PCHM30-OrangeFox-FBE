# PCHM30 PBRP12.1 FBE V2 — Android16 解密实测通过

这是 PCHM30 的独立 Recovery 设备覆盖层。不要将这里的 BoardConfig.mk 覆盖到
仓库根目录用于编 LOS 的 `device/oppo/PCHM30/BoardConfig.mk`；它们是不同产品。

## 已确认的实际问题

2026-10-28 经 ADB 只读检查：

- 原 Recovery 缺少 BusyBox，SDK32/PBRP 3.7.1_12 基底。
- Data 是物理 `/dev/block/sda10` 的 ext4，模式 `ice:aes-256-cts:v1+wrappedkey_v0`。
- Recovery 向 Keymaster 提供的 SPL 是 2026-07-01，实际已安装 System 的 SPL 是
  2026-10-01，版本号为 16。读取是在独立 tmp 挂载点 `ro,noload` 完成的。
- `pchm30-bootflow-a2.sh` 会在启动时将 `prepdecrypt.setpatch` 改回 false。
- 已发生将物理 System 挂在 `/system`、遮住 Recovery 自身 `/system/bin` 的情况，
  ADB shell 报 `Too many symbolic links encountered`。通过菜单重启 Recovery 后恢复。

## 修改

1. `device/recovery/root/sbin/busybox` 是锁定散列的静态 AArch64 BusyBox，不需要
   Android 动态链接器。设备 Android.mk 注册 `pchm30_static_busybox`；BoardConfig
   和 device.mk 引入该模块。保留 toybox，两者可以共存。
2. 最终镜像的 `/sbin/sh` 指向静态 BusyBox，ZIP 安装 shell 不依赖被挂载的 /system。
3. init.rc 和 bootflow 都设置 `prepdecrypt.setpatch true`；没有残留的 false 覆盖。
4. 原 prepdecrypt 读取实际 System/Vendor 的版本/SPL，使用独立 tmp 挂载点和
   `ro,noload`，不硬编码 2026-07-01、不把 Recovery SDK 伪装成 36。
   能识别 SAR 和非 SAR 两种 build.prop 路径。同步失败时保持 crypto.ready=0。
5. 修正 ext4 fstab 和幂等合并脚本，避免再次追加 ginkgo 的 f2fs 模板。
   System 挂载点使用 /system_root；不更改磁盘格式、分区表或已有密钥。
6. ROM 的 tools/update-binary.sh 按 applet 选择 BusyBox、toybox 或独立命令。
   所有工具先检查；真实操作失败不换工具重试。保留分区/大小/散列/回读检查。
   `--check-tools` 只测试工具，不读写分区。

`/data/unencrypted/key` 是 fscrypt 系统 DE key 的既有位置，不是 fstab 的
metadata-encryption keydirectory。这里没有将 keydirectory 指向 Data 内部，也没有
启用新的 metadata_encryption。检测到 Data 是直接可挂载的 ext4，保持其现有 FBE。

## 如何生成镜像

本次本地候选是从设备只读备份的已实测 PBRP 镜像 **重建 ramdisk**，不是重新编译
全部 C++，也不是把 SDK32 升级为 SDK34。内核、DTBO、Recovery 主程序、全部原有
运行库保持一致。输出会校验 boot ID、64 MiB 上限及动态依赖。

```bash
python3 recovery/pchm30-a16/repack.py \
  --input /path/to/tested-pbrp-recovery.img \
  --output /workspace/DOWNLOAD-RECOVERY/PCHM30-PBRP-A16-TEST1.img
```

若正在使用原先预装 PBRP 源码的 CNB IDE，并保留 stable/pchm30-pbrp12-v1：

```bash
bash recovery/pchm30-a16/rebuild.sh
```

该脚本先通过已锁定的原配方重编 Recovery，再应用本设备层。原配方会把编译结果的
非 UI 文件换回 Golden runtime，因此单独改 BoardConfig 不足以让 BusyBox 或 rc
进入最终镜像；必须保留最后的 repack 步骤。脚本不下载 Android 源码、不刷手机。

## 验证范围

手机实际执行通过：新静态 arm64 BusyBox、toybox/独立工具回退、缺工具停止。
修改后的完整 prepdecrypt 脚本在手机 RAM chroot 中运行，使用模拟挂载和属性 API：
SAR 和非 SAR 都同步到 2026-10-01，保持 SDK32；缺 System build.prop 时退出且
不放行 crypto.ready。测试没有调用真实 Keymaster、修改真实属性或触碰 Data 密钥。

2026-10-28，机主已手动刷入上述同一候选并确认解密成功。发布镜像仅改文件名，
字节及 SHA256 完全不变。后续实测结论见 DEVICE-TEST-V2.json；VALIDATION.json 中
保留的是生成镜像时尚未上机的原始记录。未单独重测的其他功能不作新增声明。

## 关于文档中的 TWRP 14 建议

fscrypt v2 并非 Android 16 才引入，本机实测仍为 v1。TWRP 14/Android 14 也不自动
保证可解密 Android 16；还涉及旧 Qualcomm Keymaster、vendor 库和密钥版本绑定。
本候选保留已实测的基底，SDK34 迁移不混入这个修复。后续若单独构建 SDK34+，
应重新验证原生 init/库 ABI、显示/触控和实际解密，不可只换属性或 UI 后冒称升级。

此外，Keymaster 错误 -38 是 INVALID_ARGUMENT；INVALID_KEY_BLOB 是 -33。
原分析文档把 -38 标为 INVALID_KEY_BLOB 的解释不准确。

## 上游依据

- https://github.com/TeamWin/android_device_qcom_twrp-common （setpatch 的正确使用）
- https://source.android.com/docs/security/features/keystore/version-binding
- https://source.android.com/docs/security/features/encryption/metadata （keydirectory）
- https://source.android.com/docs/security/features/encryption/file-based （v1/v2）
- https://android.googlesource.com/platform/hardware/interfaces/+/refs/tags/android-10.0.0_r4/keymaster/4.0/types.hal

BusyBox 的散列、来源和对应源码配置链接见 BUSYBOX-PROVENANCE.json，许可证见
BUSYBOX-LICENSE.txt。它作为独立工具集成，不安装 Magisk 模块。
