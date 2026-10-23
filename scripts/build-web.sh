#!/usr/bin/env bash
# Build versi web (WebAssembly) dengan pygbag.
# Hanya main.py dan paket snakegame/ yang dikemas, agar tests/, docs/, dll. tidak ikut.
# Hasil: build/web-src/snakegame/build/web (index.html + snakegame.apk)
set -euo pipefail

cd "$(dirname "$0")/.."
SRC=build/web-src/snakegame
rm -rf build/web-src
mkdir -p "$SRC"
cp main.py "$SRC/"
cp -r snakegame "$SRC/"
find "$SRC" -name "__pycache__" -type d -prune -exec rm -rf {} +

python -m pygbag --build --title "Snake Game" "$@" "$SRC"
echo "Selesai: $SRC/build/web"
