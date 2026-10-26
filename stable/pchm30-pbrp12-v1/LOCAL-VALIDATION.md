# 本地验证记录 · 2026-10-26

已完成：

1. 对官方 PBRP recovery 提交 `c3ee88af57d32a842b2a8ff861a72a7bf24da846`
   的真实 `partition.cpp` 应用 early-media 日志补丁，确认只新增标记，重复应用无变化，
   未识别的源码会拒绝修改。
2. 读取真实 Golden ramdisk，验证 newc CPIO 序列化往返保留内容、mode、UID/GID；
   检查八个启动/解密 ELF 根的依赖闭包和带版本符号，删除 resetprop 库后确认拒绝。
3. 使用明确标为 SYNTHETIC 的临时镜像测试完整打包路径，验证镜像 ID、64MiB 上限、
   非 UI Golden 文件内容及所有权保留、只追加 PBRP 身份属性、报告仍写“未实机测试”。
   合成夹具只用于检查打包逻辑，已由临时目录清理；没有作为刷机镜像提供。
4. 输入真实 TWRP V4 镜像时，PBRP 打包器拒绝把它标记为 PBRP。
5. 用不联网的初始化夹具检查独立源码目录限制、八项版本锁定的本地清单、失效链接移除。
   默认模式缓存缺失时拒绝执行任何初始化命令；只有显式 `--populate-cache` 才允许同步；
   初始化命令不再包含 `--dissociate`；重复检查不会同步。
6. 本包全部 Python 文件通过语法编译，三个 shell 入口通过 `bash -n`。
7. 用原 TEST1 ZIP 和真实旧版 Dockerfile/.cnb.yml 测试预装模式迁移，验证旧 Dockerfile
   指令前缀保留，使用 PyYAML 解析新 YAML、核对 build.by 文件列表和 runner/services，
   启动 stage 通过 bash 语法检查；备份可用，重复安装无变化；未知配置在写入前被拒绝。
8. Golden 素材缺失且指定离线模式时，检查确认不会调用网络 API。

尚未完成：CNB 新缓存镜像构建、全量 Android 编译、PBRP 实机启动、FBE、MTP、熄屏后触控测试。
不能从上述静态检查推导这些实机功能已经可用。
