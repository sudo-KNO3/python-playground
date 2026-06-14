#!/usr/bin/env bash
# Rebuild the Rust→WASM Taco Bell finder and copy artifacts to ./pkg
# so surge picks them up.
#
# Usage:
#   ./build-wasm.sh              # rebuilds WASM from current data snapshot
#   ./build-wasm.sh --refresh    # also re-fetches the Overpass data first

set -e
cd "$(dirname "$0")"

if [[ "${1:-}" == "--refresh" ]]; then
    echo "→ refreshing Overpass dataset…"
    ./rust-tacobell/refresh-data.sh
fi

echo "→ wasm-pack build…"
(cd rust-tacobell && wasm-pack build --target web --release)

echo "→ copying pkg/ into site root…"
rm -rf pkg
cp -r rust-tacobell/pkg pkg
rm -f pkg/.gitignore   # wasm-pack regenerates this; we want pkg/ committed

echo
echo "✓ build complete. WASM size:"
ls -lh pkg/tacobell_finder_bg.wasm | awk '{print "  ", $5, $9}'
echo
echo "next: surge . yesimthisgoofy.surge.sh"
