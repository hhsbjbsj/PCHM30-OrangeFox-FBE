#!/usr/bin/env bash
set -eo pipefail
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
SOURCE_ROOT=${TWRP_ROOT:-/opt/twrp}
WORKSPACE=${PCHM30_WORKSPACE:-/workspace}
TAG=pchm30-twrp12.1-fbe-v4
python3 "$SCRIPT_DIR/base/prepare.py" --root "$SOURCE_ROOT" --workspace "$WORKSPACE"
python3 "$SCRIPT_DIR/patches/apply_diagnostics.py" --root "$SOURCE_ROOT" --workspace "$WORKSPACE"
python3 "$SCRIPT_DIR/patches/apply_early_media.py" --root "$SOURCE_ROOT" --workspace "$WORKSPACE"
python3 "$SCRIPT_DIR/capture_locks.py" --root "$SOURCE_ROOT" --workspace "$WORKSPACE"
python3 "$SCRIPT_DIR/check_sources.py" --root "$SOURCE_ROOT" --patched
python3 "$SCRIPT_DIR/fetch_assets.py"
if [ "${1:-}" != --publish-cnb ]; then
    echo "Locks captured. Use --publish-cnb to commit and push the CNB archive."
    exit 0
fi
bash "$SCRIPT_DIR/build.sh"
IMAGE=$(cat "$WORKSPACE/artifacts/latest-twrp12-stable-v4.txt")
python3 "$SCRIPT_DIR/verify_rebuild.py" "$IMAGE" "$SCRIPT_DIR/locks/REPRODUCED.json"
cd "$WORKSPACE"
test "$(git branch --show-current)" = main
test -z "$(git ls-files -u)"
python3 - <<'VERIFY_ORIGIN'
import subprocess, urllib.parse
url = subprocess.check_output(['git','remote','get-url','origin'],text=True).strip()
parts=urllib.parse.urlsplit(url)
assert parts.hostname == 'cnb.cool' and parts.path.rstrip('/').removesuffix('.git') == '/Anyin123f/recovery', 'Unexpected CNB origin; not pushing'
VERIFY_ORIGIN
git add -- stable/pchm30-v4
git add -f -- stable/pchm30-v4/base/assets/reference-header.bin stable/pchm30-v4/base/assets/reference-ramdisk.gz
if ! git diff --cached --quiet -- stable/pchm30-v4; then
    git commit -m "Archive device-tested PCHM30 TWRP12.1 FBE V4 baseline" -- stable/pchm30-v4
fi
if git rev-parse -q --verify "refs/tags/$TAG" >/dev/null; then
    test "$(git rev-parse "$TAG:stable/pchm30-v4")" = "$(git rev-parse HEAD:stable/pchm30-v4)"
else
    git tag -a "$TAG" -m "PCHM30 V4: device-tested automatic FBE decryption; early data-media"
fi
git push origin HEAD:main
git push origin "refs/tags/$TAG"
echo "CNB baseline committed and tagged: $TAG"
