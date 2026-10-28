#!/system/bin/sh
# Idempotent PCHM30 table: do not append ginkgo's f2fs/dynamic templates.
set -e
cp /system/etc/recovery.fstab.pchm30_a16 /system/etc/recovery.fstab
setprop ro.twrp.rom_is_dynamic false
