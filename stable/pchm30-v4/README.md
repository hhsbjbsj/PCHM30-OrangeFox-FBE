# PCHM30 TWRP 12.1 FBE V4 baseline

2026-10-26 实机基线：OPPO A11x / PCHM30，当前安装的系统与数据，未设置
锁屏密码。用户确认解密成功、功能正常；ADB 独立确认用户 0 解密状态为 1，
运行主程序的 SHA256 与成功构建一致。详细结果见 [TESTED-V4.json](TESTED-V4.json)。

已验证的最终镜像：

```text
PCHM30-TWRP12.1-FBE-STABLE-V4.img
bytes: 54530048
sha256: 2a2382b57e22554ce816594164cc00920bd43b5ab46da5da2716b0e27369ca47
recovery executable sha256:
67c2609e3003e504c0bb9e11d479e21d7ee04455034782e26aa62d90395542e7
```

成功镜像从手机 Recovery 分区只读回读，镜像有效长度的哈希与 CNB 原产物
逐字节一致。没有把手机的用户数据、明文密钥、密码或原始日志加入本归档。

## 核心修复

`TW_PREPARE_DATA_MEDIA_EARLY := true`。

V3 实机日志确认 DE 密钥刚安装时内核状态为 present、spblob 目录可见，
之后 Data 卸载并重新挂载，正常目录名消失。V4 使用 TWRP 已有的提前准备
内部存储路径，避免在 DE 密钥安装后再执行对应准备步骤。V4 首启后解密成功。

同时固定此前必要改动：BGRA 显示、libresetprop 打包、独立 vendor 布局和
OPPO 亮屏通知脚本。保留成功版本的诊断日志，没有在固化时移除功能或增加特性。

## 构建

现有 CNB Ubuntu22.04 / `/opt/twrp` TWRP12.1 环境中：

```bash
bash /workspace/stable/pchm30-v4/build.sh
```

最终产物在 `/workspace/DOWNLOAD-RECOVERY/`，名字带 `FBE-STABLE-V4`。
`build.sh` 与原 V4 用同一组准备、补丁、验证和打包实现，只统一了入口和目录。
重新构建可能受时间戳等影响而生成不同哈希；上面固定哈希对应的是已经实测
成功的那个镜像，不能把任何新构建自动视为已经实测。

完整离线包附带 `base/assets` 的固定二进制。Git 仓库仅保存其公开来源和哈希，
缺少资产时会从固定的 Golden v1.0.0 镜像恢复，并核验完整镜像及提取文件的哈希。

## 源码与运行基底

本版本是 **TWRP12.1 主程序/界面源码构建 + 已验证 Golden AB10 运行基底**。
平台运行库、init、ADB、Qualcomm 密钥服务、fstab 和启动链保留自 Golden。
它不是把所有 Qualcomm 私有组件或完整 OrangeFox 都重新从源码编译出来。

- TWRP：TeamWin `android-12.1`，精确项目版本记录在 `locks/manifest.xml`。
- 设备树：`hhsbjbsj/android_device_oppo_PCHM30`，精确提交在 `locks/revisions.txt`。
- 内核沿用设备树 prebuilt：`d83bf44d06a1ed1aeb7c8d597bbccd627458e7619e8606218f33358d145a0f1b`。
- DTBO：`b11c7c246bd74a010718124f25ff92f332304bd892b66eecd18b300417dbf270`。
- Golden：<https://github.com/hhsbjbsj/PCHM30-OrangeFox-FBE/releases/tag/v1.0.0>。
- Golden 压缩 ramdisk：`4a9a6b42fea29258141ee84ceb5c4852e25dc4a859144fd81915b4e6ee3093c7`。

精确源码清单及实际改动由成功的 CNB 环境导出到 `locks/`；锁定清单、源码
补丁和生成配置必须一起保存，不能只留下一个移动中的分支名。
`locks/config/Dockerfile` 和 `cnb.yml` 保存构建环境配置。

原构建容器已被平台回收。固化脚本会在新容器中恢复同一套补丁、导出其
精确源码清单并重新构建，再与成功镜像的内核、DTBO、启动参数以及每个
运行文件的内容、权限和所有者逐项比较；通过才提交 CNB 固定标签。
比较允许构建溯源标记、文件清单和归档时间戳不同，不把它们当成加密修复。
如果比较不通过，脚本会停下，保留原来已实测成功的镜像。

在 CNB 固化：

```bash
bash /workspace/stable/pchm30-v4/freeze.sh --publish-cnb
```

该命令会重新构建一次以验证恢复后的源码版本，随后只提交本目录并推送
到 `Anyin123f/recovery`，创建不可覆盖的 `pchm30-twrp12.1-fbe-v4` 标签。
它不刷写手机。重建产物不必再次刷入才能完成文件内容一致性的核对。

## 使用范围

实测结果针对这台 PCHM30 和当前系统/数据，测试时无锁屏密码。没有据此证明
其他 ROM、PIN、图案、密码或所有刷写组合也一定兼容。刷写镜像仍应保留可用
的恢复镜像；不要把格式化 Data 当作验证解密的方法。
