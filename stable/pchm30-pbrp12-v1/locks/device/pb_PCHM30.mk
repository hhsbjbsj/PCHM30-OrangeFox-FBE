# PCHM30 PBRP12.1 test product; derived from the phone-tested TWRP V4 configuration.
$(call inherit-product, $(SRC_TARGET_DIR)/product/core_64_bit_only.mk)
$(call inherit-product, $(SRC_TARGET_DIR)/product/base.mk)
TARGET_VENDOR := OPPO
PB_CODE := PCHM30
$(call inherit-product, vendor/pb/config/common.mk)
$(call inherit-product, device/oppo/PCHM30/device.mk)

PRODUCT_DEVICE := PCHM30
PRODUCT_NAME := pb_PCHM30
PRODUCT_BRAND := OPPO
PRODUCT_MODEL := OPPO A11x
PRODUCT_MANUFACTURER := OPPO
PRODUCT_RELEASE_NAME := OPPO A11x (PCHM30 / CPH1937)
MAINTAINER := hhsbjbsj
PB_OFFICIAL := false
BETA_BUILD := false

BUILD_FINGERPRINT := OPPO/PCHM30/PCHM30:11/RKQ1.200903.002/1652688527676:user/release-keys
PRODUCT_BUILD_PROP_OVERRIDES += PRODUCT_NAME=PCHM30 TARGET_DEVICE=PCHM30
PRODUCT_PACKAGES += libresetprop.recovery
