#!/usr/bin/env bash
# Build path: PyInstaller onedir -> AppDir -> AppImage (docs/21).
# Environment-dependent tools fail with actionable messaging rather than silent fallback.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

VERSION="$(
  python3 - <<'PY'
import re
from pathlib import Path
text = Path("pyproject.toml").read_text(encoding="utf-8")
m = re.search(r'(?m)^version\s*=\s*"([^"]+)"', text)
print(m.group(1) if m else "0.0.0")
PY
)"
APP_NAME="Koffer"
DIST_DIR="${ROOT}/dist"
BUILD_DIR="${ROOT}/build"
ONEDIR="${DIST_DIR}/koffer"
APPDIR="${DIST_DIR}/${APP_NAME}.AppDir"
OUT_APPIMAGE="${DIST_DIR}/${APP_NAME}-${VERSION}-x86_64.AppImage"
SPEC="${ROOT}/packaging/koffer.spec"

DRY_RUN=0
SKIP_APPIMAGE=0

usage() {
  cat <<EOF
Usage: $(basename "$0") [--dry-run] [--skip-appimage] [--stage-only]

Build Koffer AppImage staging path:
  1) PyInstaller onedir bundle
  2) AppDir with desktop/icon/license notices
  3) appimagetool -> dist/${APP_NAME}-VERSION-x86_64.AppImage

Options:
  --dry-run        Validate inputs/tools and print the plan; do not build
  --skip-appimage  Stop after AppDir staging (useful without appimagetool)
  --stage-only     Alias for --skip-appimage
EOF
}

die() {
  echo "build_appimage.sh: ERROR: $*" >&2
  exit 1
}

need_cmd() {
  local cmd="$1"
  local hint="$2"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    die "missing required command '${cmd}'. ${hint}"
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1 ;;
    --skip-appimage|--stage-only) SKIP_APPIMAGE=1 ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown argument: $1 (see --help)" ;;
  esac
  shift
done

echo "build_appimage.sh: root=${ROOT}"
echo "build_appimage.sh: version=${VERSION}"
echo "build_appimage.sh: target=${OUT_APPIMAGE}"

need_cmd python3 "Install Python 3.12+ on the build host."
need_cmd uv "Install uv (https://docs.astral.sh/uv/) and re-run from the repo root."

if [[ ! -f "${ROOT}/packaging/koffer.desktop" ]]; then
  die "missing packaging/koffer.desktop"
fi
if [[ ! -x "${ROOT}/packaging/AppRun" ]]; then
  chmod +x "${ROOT}/packaging/AppRun" || true
fi
if [[ ! -x "${ROOT}/packaging/AppRun" ]]; then
  die "packaging/AppRun must be executable"
fi

echo "build_appimage.sh: ensuring packaging tooling (pyinstaller) via uv sync --extra packaging"
if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "build_appimage.sh: dry-run plan:"
  echo "  - uv sync --frozen --extra packaging (or --all-extras)"
  echo "  - uv run --no-sync pyinstaller --noconfirm ${SPEC}"
  echo "  - stage ${APPDIR} from ${ONEDIR}"
  echo "  - scripts/verify_licenses.py --write-notices ${APPDIR}/usr/share/doc/koffer/THIRD_PARTY_NOTICES.txt"
  if [[ "$SKIP_APPIMAGE" -eq 0 ]]; then
    echo "  - appimagetool ${APPDIR} ${OUT_APPIMAGE}"
  else
    echo "  - skip AppImage compression (--skip-appimage)"
  fi
  echo "build_appimage.sh: dry-run OK"
  exit 0
fi

uv sync --frozen --extra packaging \
  || die "uv sync --frozen --extra packaging failed. Run 'uv lock' after adding the packaging extra, or use network-enabled sync."

uv run --no-sync python -c "import PyInstaller" \
  || die "PyInstaller is not importable. Ensure pyproject optional-dependency 'packaging' includes pyinstaller and re-run uv sync --extra packaging."

mkdir -p "$DIST_DIR" "$BUILD_DIR"
rm -rf "$ONEDIR" "$APPDIR" "${DIST_DIR}/${APP_NAME}"*.AppImage

echo "build_appimage.sh: running PyInstaller onedir"
uv run --no-sync pyinstaller --noconfirm --distpath "$DIST_DIR" --workpath "$BUILD_DIR" "$SPEC" \
  || die "PyInstaller failed. Inspect build/ for logs; Qt/PySide6 collect failures usually mean missing --collect-all PySide6 in packaging/koffer.spec."

[[ -x "${ONEDIR}/koffer" ]] || die "expected PyInstaller binary missing: ${ONEDIR}/koffer"

echo "build_appimage.sh: staging AppDir"
mkdir -p \
  "${APPDIR}/usr/bin" \
  "${APPDIR}/usr/lib/koffer" \
  "${APPDIR}/usr/share/applications" \
  "${APPDIR}/usr/share/icons/hicolor/scalable/apps" \
  "${APPDIR}/usr/share/icons/hicolor/256x256/apps" \
  "${APPDIR}/usr/share/doc/koffer"

# Copy onedir payload under usr/lib/koffer and expose usr/bin/koffer wrapper target.
cp -a "${ONEDIR}/." "${APPDIR}/usr/lib/koffer/"
ln -sfn "../lib/koffer/koffer" "${APPDIR}/usr/bin/koffer"

cp -a "${ROOT}/packaging/AppRun" "${APPDIR}/AppRun"
chmod +x "${APPDIR}/AppRun"
cp -a "${ROOT}/packaging/koffer.desktop" "${APPDIR}/koffer.desktop"
cp -a "${ROOT}/packaging/koffer.desktop" "${APPDIR}/usr/share/applications/koffer.desktop"
cp -a "${ROOT}/packaging/icons/koffer.svg" "${APPDIR}/usr/share/icons/hicolor/scalable/apps/koffer.svg"
cp -a "${ROOT}/packaging/icons/koffer.svg" "${APPDIR}/koffer.svg"

# Raster placeholder for environments that ignore SVG (generated, not a design asset).
uv run --no-sync python - <<'PY'
from pathlib import Path
try:
    from PIL import Image, ImageDraw
except Exception:
    # Minimal valid 1x1 PNG fallback written via stdlib struct/zlib.
    import struct
    import zlib

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    raw = b"\x00" + b"\x3d\x9a\x6a"
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")
    Path("dist/Koffer.AppDir/usr/share/icons/hicolor/256x256/apps/koffer.png").write_bytes(png)
    Path("dist/Koffer.AppDir/koffer.png").write_bytes(png)
else:
    img = Image.new("RGB", (256, 256), "#1B1F24")
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((40, 70, 216, 200), radius=24, fill="#3D9A6A")
    draw.rounded_rectangle((88, 40, 168, 80), radius=12, fill="#2E7A54")
    draw.ellipse((108, 112, 148, 152), fill="#E8F5EE")
    out = Path("dist/Koffer.AppDir/usr/share/icons/hicolor/256x256/apps/koffer.png")
    img.save(out)
    Path("dist/Koffer.AppDir/koffer.png").write_bytes(out.read_bytes())
PY

uv run --no-sync python scripts/verify_licenses.py \
  --write-notices "${APPDIR}/usr/share/doc/koffer/THIRD_PARTY_NOTICES.txt" \
  || die "license verification failed; update packaging/license_inventory.json"

# Also keep a copy at dist for CI artifact convenience.
cp -a "${APPDIR}/usr/share/doc/koffer/THIRD_PARTY_NOTICES.txt" \
  "${DIST_DIR}/THIRD_PARTY_NOTICES.txt"

if [[ "$SKIP_APPIMAGE" -eq 1 ]]; then
  echo "build_appimage.sh: AppDir staged at ${APPDIR} (AppImage skipped)"
  exit 0
fi

if ! command -v appimagetool >/dev/null 2>&1; then
  cat >&2 <<EOF
build_appimage.sh: ERROR: missing required command 'appimagetool'.
Install appimagetool (https://github.com/AppImage/appimagetool/releases) and ensure it is on PATH,
or re-run with --skip-appimage to stop after AppDir staging.
AppDir is available at: ${APPDIR}
EOF
  exit 1
fi

echo "build_appimage.sh: compressing AppImage with appimagetool"
ARCH=x86_64 appimagetool "${APPDIR}" "${OUT_APPIMAGE}" \
  || die "appimagetool failed"

sha256sum "${OUT_APPIMAGE}" | tee "${OUT_APPIMAGE}.sha256"
echo "build_appimage.sh: OK -> ${OUT_APPIMAGE}"
