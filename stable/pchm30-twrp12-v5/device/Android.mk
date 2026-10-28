LOCAL_PATH := $(call my-dir)

# Pinned static AArch64 BusyBox; no dependency on Android's mounted /system.
include $(CLEAR_VARS)
LOCAL_MODULE := pchm30_static_busybox
LOCAL_MODULE_CLASS := EXECUTABLES
LOCAL_MODULE_TAGS := optional
LOCAL_SRC_FILES := recovery/root/sbin/busybox
LOCAL_MODULE_STEM := busybox
LOCAL_MODULE_PATH := $(TARGET_RECOVERY_ROOT_OUT)/sbin
LOCAL_CHECK_ELF_FILES := false
LOCAL_STRIP_MODULE := false
include $(BUILD_PREBUILT)
