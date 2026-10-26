#!/usr/bin/env bash
set -eo pipefail
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
WORKSPACE=${PCHM30_WORKSPACE:-/workspace}
cd "$WORKSPACE"
test "$(git rev-parse --show-toplevel)" = "$WORKSPACE"
test "$(git branch --show-current)" = main
python3 "$SCRIPT_DIR/freeze.py" --workspace "$WORKSPACE"
git add -- stable/pchm30-pbrp12-v1 .cnb.yml .ide/Dockerfile
git add -f -- stable/pchm30-pbrp12-v1/base/assets/reference-header.bin stable/pchm30-pbrp12-v1/base/assets/reference-ramdisk.gz stable/pchm30-pbrp12-v1/images/PCHM30-PBRP12.1-FBE-STABLE-V1.img
if ! git diff --cached --quiet -- stable/pchm30-pbrp12-v1 .cnb.yml .ide/Dockerfile; then
    git commit -m "Freeze device-tested PCHM30 PBRP12.1 FBE V1 with locked source cache" --only -- stable/pchm30-pbrp12-v1 .cnb.yml .ide/Dockerfile
fi
TAG=pchm30-pbrp12.1-fbe-v1
if git rev-parse --verify "refs/tags/$TAG" >/dev/null 2>&1; then
    test "$(git rev-parse "$TAG^{commit}")" = "$(git rev-parse HEAD)"
else
    git tag -a "$TAG" -m "Device-tested PCHM30 PBRP V1: boot, FBE, touch confirmed"
fi
git push origin HEAD:main
git push origin "refs/tags/$TAG"
echo "PBRP V1 SOURCE, TESTED IMAGE AND LOCKED CACHE COMMITTED AND TAGGED"
echo "Tag: $TAG"
echo "No compilation or phone flashing was performed."
