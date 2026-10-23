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

# CDN pygbag 0.9.3 tidak lagi menyediakan browserfs.min.js (404) sehingga game
# macet di "Loading". Sajikan salinan resmi dari arsip pygame-web bersama build.
OUT="$SRC/build/web"
curl -fsSL -o "$OUT/browserfs.min.js" https://pygame-web.github.io/archives/0.9/browserfs.min.js
sed -i 's#<script src="https://pygame-web.github.io/cdn/[^"]*/browserfs.min.js"></script>#<script src="browserfs.min.js"></script>#' "$OUT/index.html"
grep -q '<script src="browserfs.min.js"></script>' "$OUT/index.html"

echo "Selesai: $OUT"
