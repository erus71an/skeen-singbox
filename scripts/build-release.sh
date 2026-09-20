#!/bin/sh

set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
DIST_DIR="${ROOT_DIR}/dist"
BUILD_DIR="${ROOT_DIR}/.build/keen-singbox-keenetic"
ARCHIVE="${DIST_DIR}/keen-singbox-keenetic.tar.gz"

rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR" "$DIST_DIR"

cp "$ROOT_DIR/src/keen-singbox" "$BUILD_DIR/keen-singbox"
cp "$ROOT_DIR/examples/settings.default.json" "$BUILD_DIR/settings.default.json"
cp "$ROOT_DIR/examples/config.default.json" "$BUILD_DIR/config.default.json"
cp "$ROOT_DIR/examples/settings.lowmem.json" "$BUILD_DIR/settings.lowmem.json"
cp "$ROOT_DIR/examples/config.lowmem.json" "$BUILD_DIR/config.lowmem.json"
cp "$ROOT_DIR/README.md" "$BUILD_DIR/README.md"
cp "$ROOT_DIR/docs/INSTALL_PLAN.md" "$BUILD_DIR/INSTALL_PLAN.md"
chmod 755 "$BUILD_DIR/keen-singbox"

tar -C "$BUILD_DIR" -czf "$ARCHIVE" .
printf '%s\n' "$ARCHIVE"
