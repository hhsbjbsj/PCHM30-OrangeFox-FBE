#
# Copyright (C) 2026 The Android Open Source Project
# Copyright (C) 2026 The TWRP Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

# Inherit from omni product base
$(call inherit-product, $(SRC_TARGET_DIR)/product/core_64_bit_only.mk)
$(call inherit-product, $(SRC_TARGET_DIR)/product/base.mk)
$(call inherit-product, vendor/twrp/config/common.mk)

# Inherit device configuration
$(call inherit-product, device/oppo/PCHM30/device.mk)

# Device identifier
PRODUCT_DEVICE := PCHM30
PRODUCT_NAME := twrp_PCHM30
PRODUCT_BRAND := OPPO
PRODUCT_MODEL := OPPO A11x
PRODUCT_MANUFACTURER := OPPO
PRODUCT_RELEASE_NAME := OPPO A11x (PCHM30 / CPH1937)

# Build fingerprint matching stock Android 11 base
BUILD_FINGERPRINT := OPPO/PCHM30/PCHM30:11/RKQ1.200903.002/1652688527676:user/release-keys
PRODUCT_BUILD_PROP_OVERRIDES += \
    PRODUCT_NAME=PCHM30 \
    TARGET_DEVICE=PCHM30

# Install the recovery variant into the recovery ramdisk.
PRODUCT_PACKAGES += libresetprop.recovery
