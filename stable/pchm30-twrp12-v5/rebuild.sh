#!/usr/bin/env bash
set -eo pipefail
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
WORKSPACE=${PCHM30_WORKSPACE:-/workspace}
test -f "$WORKSPACE/stable/pchm30-v4/build.sh"
bash "$WORKSPACE/stable/pchm30-v4/build.sh"
INPUT=$(cat "$WORKSPACE/artifacts/latest-twrp12-stable-v4.txt")
python3 "$HERE/repack.py" --input "$INPUT" --output "$WORKSPACE/DOWNLOAD-RECOVERY/PCHM30-TWRP12.1-FBE-V5-$(date -u +%Y%m%dT%H%M%SZ).img" --kind cnb-source-build-plus-device-overlay
