#!/usr/bin/env bash
set -eo pipefail
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
WORKSPACE=${PCHM30_WORKSPACE:-/workspace}
cd "$WORKSPACE"
test "$(git rev-parse --show-toplevel)" = "$WORKSPACE"
test "$(git branch --show-current)" = main
RELATIVE=${SCRIPT_DIR#"$WORKSPACE"/}
test "$RELATIVE" != "$SCRIPT_DIR"
git add -- "$RELATIVE"
if ! git diff --cached --quiet -- "$RELATIVE"; then
    git commit -m "Add independent PCHM30 PBRP12.1 test build configuration" --only -- "$RELATIVE"
fi
git push origin HEAD:main
