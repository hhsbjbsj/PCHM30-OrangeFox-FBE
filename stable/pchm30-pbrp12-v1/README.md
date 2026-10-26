# PCHM30 PBRP12.1 FBE 稳定版 V1

用户已经刷入并确认启动、解密、触控和其他功能正常。ADB 读取证实手机 Recovery 分区的镜像前缀
与归档镜像逐字节相同，运行中的 recovery 程序相同；本次 Recovery 日志报告 user 0 解密成功，
使用默认密码路径。测试范围为用户当前系统与数据，不扩展到其他 ROM 或自定义锁屏密码。

## 成功镜像

`PCHM30-PBRP12.1-FBE-STABLE-V1.img` 只是将已实测成功的 TEST1 文件重命名，未重新打包或修改。
SHA256：`e2cdd26378bf9dc0070390a7e5c1312bb5463617a08392f3c13258fa728f0aa0`。
镜像 56,119,296 字节，Recovery 分区 64 MiB。静态检查验证 Android v1 镜像 ID、原内核/DTBO、
动态依赖与带版本符号。原镜像内构建时的 not-tested 信息保留，实机结论见 TESTED-V1.json。

## CNB 固化

上传源码固化包到 `/workspace`，执行：

```bash
cd /workspace && unzip -o PCHM30-PBRP12-STABLE-V1-SOURCE-LOCKED.zip && bash stable/pchm30-pbrp12-v1/freeze.sh
```

脚本核对全部源码提交、已应用补丁及成功镜像的完整 SHA256，然后从 DOWNLOAD-PBRP 复制成功镜像，
提交 stable/pchm30-pbrp12-v1，建立不可覆盖的标签 pchm30-pbrp12.1-fbe-v1。
同时将下一次 CNB 环境镜像的 PBRP 缓存改为使用冻结的全部项目清单。
不重新编译、不刷写手机，不修改既有 TWRP V4 归档。

CNB 包含 images/ 下成功镜像与 base/assets/ 两份固定运行环境素材。
GitHub 源码目录省略这些二进制文件；成功镜像和带完整素材的源码 ZIP 在同名 Release 下载。
原始手机日志和分区尾部备份仅保存在电脑，不公开。

## 后续编译

已存在匹配源码缓存时：

```bash
bash /workspace/stable/pchm30-pbrp12-v1/start.sh
```

默认只离线核验源码，不运行 repo sync。重建环境的 Dockerfile 在镜像构建阶段使用
locks/manifest.xml 中全部固定的项目提交，继续复用 TWRP Git 对象，未使用 --dissociate。
locks/config/*.before-freeze 保留此次成功构建时的环境配置，另两份为全版本锁定后的配置。
新构建仍输出 TEST1 名称，以免把未经回归测试的新镜像当作原成功镜像；时间戳可能改变镜像哈希。

构建目标是 recoveryimage，整合 PBRP 程序与主题、完整 Golden 解密服务和库、提前准备内部存储选项，
以及原内核、DTBO、BGRA 和触控唤醒脚本。官方 pbrp 安装 ZIP 不含此整合，不能与归档镜像混用。
PBRP 附加工具 ZIP 暂未包含在镜像中。

上游：[PBRP](https://github.com/PitchBlackRecoveryProject/manifest_pb/tree/android-12.1)，
[设备树](https://github.com/hhsbjbsj/android_device_oppo_PCHM30)，
[Golden 运行环境](https://github.com/hhsbjbsj/PCHM30-OrangeFox-FBE/releases/tag/v1.0.0)。
