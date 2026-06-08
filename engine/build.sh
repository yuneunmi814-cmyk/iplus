#!/usr/bin/env bash
# Bundle the iPlus engine into a single binary (PyInstaller) and copy it into
# Tauri's externalBin. Blueprint §4. Tauri expects a target-triple suffixed binary.
set -euo pipefail
cd "$(dirname "$0")"

PY="${PYTHON:-python3.12}"
OUT_DIR="../frontend/src-tauri/binaries"

# target triple (exact via rustc if present, else inferred from OS/arch)
if command -v rustc >/dev/null 2>&1; then
  TRIPLE="$(rustc -Vv | sed -n 's/host: //p')"
else
  case "$(uname -s)-$(uname -m)" in
    Darwin-arm64) TRIPLE="aarch64-apple-darwin" ;;
    Darwin-x86_64) TRIPLE="x86_64-apple-darwin" ;;
    Linux-x86_64) TRIPLE="x86_64-unknown-linux-gnu" ;;
    *) echo "unknown platform; set TRIPLE manually"; exit 1 ;;
  esac
fi
echo "target triple: $TRIPLE"

# isolated build environment
"$PY" -m venv .build-venv
# shellcheck disable=SC1091
source .build-venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt pyinstaller

pyinstaller --onefile --clean --name iplus-engine \
  --hidden-import uvicorn.logging \
  --hidden-import uvicorn.protocols \
  --hidden-import uvicorn.protocols.http.auto \
  --hidden-import uvicorn.lifespan.on \
  --collect-submodules app \
  run.py

mkdir -p "$OUT_DIR"
EXT=""; [[ "$TRIPLE" == *windows* ]] && EXT=".exe"
cp "dist/iplus-engine${EXT}" "$OUT_DIR/iplus-engine-${TRIPLE}${EXT}"
echo "OK copied -> $OUT_DIR/iplus-engine-${TRIPLE}${EXT}"
