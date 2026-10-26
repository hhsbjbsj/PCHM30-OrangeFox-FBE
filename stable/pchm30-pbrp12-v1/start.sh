#!/usr/bin/env bash
set -eo pipefail
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
WORKSPACE=${PCHM30_WORKSPACE:-/workspace}
SOURCE_ROOT=${PBRP_ROOT:-/opt/pbrp}
STAMP=$(date +%Y%m%d-%H%M%S)
mkdir -p "$WORKSPACE/artifacts" "$WORKSPACE/DOWNLOAD-PBRP"
LOG="$WORKSPACE/artifacts/pbrp12-$STAMP.log"
exec > >(tee "$LOG") 2>&1
echo "PCHM30 PBRP12.1 UNOFFICIAL test build. Log: $LOG"
for command in repo git python3 rsync make; do command -v "$command" >/dev/null; done
df -h "$WORKSPACE" "$(dirname -- "$SOURCE_ROOT")"
python3 "$SCRIPT_DIR/init_sources.py" --root "$SOURCE_ROOT" --reference /opt/twrp
python3 "$SCRIPT_DIR/fetch_assets.py" --offline
python3 "$SCRIPT_DIR/prepare.py" --root "$SOURCE_ROOT" --workspace "$WORKSPACE"
python3 "$SCRIPT_DIR/check_sources.py" --root "$SOURCE_ROOT" --patched
# Frozen recipes are immutable. Keep fresh logs and images outside this folder.
cd "$SOURCE_ROOT"
export OUT_DIR=out-pchm30-pbrp12
export ALLOW_MISSING_DEPENDENCIES=true
source build/envsetup.sh
lunch pb_PCHM30-eng
# Build the image first. The upstream pbrp target also creates an installer ZIP;
# that ZIP contains the source runtime rather than this Golden-runtime candidate.
mka recoveryimage -j"${BUILD_JOBS:-8}"
BUILT="$SOURCE_ROOT/$OUT_DIR/target/product/PCHM30/recovery.img"
python3 "$SCRIPT_DIR/base/verify_support.py" "$BUILT"
DEST="$WORKSPACE/DOWNLOAD-PBRP/PCHM30-PBRP12.1-FBE-TEST1-$STAMP.img"
python3 "$SCRIPT_DIR/base/make_image.py" --built "$BUILT" --output "$DEST" --build-kind cnb-source-build
# The packer verifies final boot ID, size, kernel, DTBO, early-media/PBRP markers,
# versioned ELF symbols and unchanged non-UI Golden runtime files.
cp "$SCRIPT_DIR/locks/manifest.xml" "$WORKSPACE/DOWNLOAD-PBRP/PBRP-SOURCE-MANIFEST-$STAMP.xml"
printf '%s\n' "$DEST" > "$WORKSPACE/artifacts/latest-pbrp12.txt"
echo "PBRP BUILD AND STATIC CHECKS PASSED"
echo "Final candidate: $DEST"
echo "Phone boot, FBE, MTP and touch-resume are not yet tested for PBRP."
