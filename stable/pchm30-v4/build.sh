#!/usr/bin/env bash
set -eo pipefail
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
BASE="$SCRIPT_DIR/base"
PATCHES="$SCRIPT_DIR/patches"
SOURCE_ROOT=${TWRP_ROOT:-/opt/twrp}
WORKSPACE=${PCHM30_WORKSPACE:-/workspace}
STAMP=$(date +%Y%m%d-%H%M%S)
if ! test -f "$SOURCE_ROOT/build/envsetup.sh"; then
    echo "Missing $SOURCE_ROOT/build/envsetup.sh. Use the existing CNB TWRP12.1 environment or initialize a new tree from locks/manifest.xml." >&2
    exit 1
fi
python3 "$SCRIPT_DIR/fetch_assets.py"
python3 "$SCRIPT_DIR/check_sources.py" --root "$SOURCE_ROOT"
mkdir -p "$WORKSPACE/artifacts" "$WORKSPACE/DOWNLOAD-RECOVERY"
LOG="$WORKSPACE/artifacts/twrp12-stable-v4-$STAMP.log"
exec > >(tee "$LOG") 2>&1
echo "PCHM30 TWRP12.1 V4 baseline: early data-media; retained Golden runtime."
echo "Log: $LOG"
python3 "$BASE/prepare.py" --root "$SOURCE_ROOT" --workspace "$WORKSPACE"
python3 "$PATCHES/apply_diagnostics.py" --root "$SOURCE_ROOT" --workspace "$WORKSPACE"
python3 "$PATCHES/apply_early_media.py" --root "$SOURCE_ROOT" --workspace "$WORKSPACE"
python3 "$SCRIPT_DIR/check_sources.py" --root "$SOURCE_ROOT" --patched
cd "$SOURCE_ROOT"
export OUT_DIR=out-pchm30-twrp12-boot-test
export ALLOW_MISSING_DEPENDENCIES=true
source build/envsetup.sh
lunch twrp_PCHM30-eng
mka recoveryimage -j8
BUILT="$SOURCE_ROOT/$OUT_DIR/target/product/PCHM30/recovery.img"
python3 "$BASE/verify_support.py" "$BUILT"
python3 "$PATCHES/check_diagnostics.py" "$BASE" "$BUILT"
python3 "$PATCHES/check_early_media.py" "$BASE" "$BUILT"
DEST="$WORKSPACE/DOWNLOAD-RECOVERY/PCHM30-TWRP12.1-FBE-STABLE-V4-$STAMP.img"
python3 "$BASE/make_image.py" --built "$BUILT" --output "$DEST" --build-kind cnb-source-build
python3 "$PATCHES/check_diagnostics.py" "$BASE" "$DEST"
python3 "$PATCHES/check_early_media.py" "$BASE" "$DEST"
printf '%s\n' "$DEST" > "$WORKSPACE/artifacts/latest-twrp12-stable-v4.txt"
echo "BUILD AND STATIC BASELINE CHECKS PASSED"
echo "Image: $DEST"
echo "A fresh rebuild can have different timestamps/hashes and needs a device regression test."
