#!/usr/bin/env bash
set -eo pipefail
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
WORKSPACE=${PCHM30_WORKSPACE:-/workspace}
FROZEN="$WORKSPACE/stable/pchm30-pbrp12-v1"
test -f /opt/pbrp/.pchm30-pbrp12-checkout || { echo 'This recipe needs the existing PBRP source-cache IDE, not the LOS/Axion IDE.' >&2; exit 1; }
test -f "$FROZEN/start.sh"
# Recompile the pinned PBRP UI using its immutable source recipe first.
# The Golden-runtime composer discards non-UI built ramdisk files, so the device
# fixes MUST be applied afterwards rather than assuming BoardConfig alone works.
bash "$FROZEN/start.sh"
INPUT=$(cat "$WORKSPACE/artifacts/latest-pbrp12.txt")
test -f "$INPUT"
OUTPUT="$WORKSPACE/DOWNLOAD-PBRP/PCHM30-PBRP-A16-INTEGRATION-$(date -u +%Y%m%dT%H%M%SZ).img"
python3 "$HERE/repack.py" --input "$INPUT" --output "$OUTPUT" --kind cnb-source-build-plus-device-overlay
echo "RECOVERY CANDIDATE: $OUTPUT"
echo 'BusyBox is embedded in the final ramdisk. Android16 decryption still requires device testing.'
