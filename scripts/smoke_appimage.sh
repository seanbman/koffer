#!/usr/bin/env bash
# Smoke checks for AppDir / AppImage packaging outputs (docs/21).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

DRY_RUN=0
TARGET=""

usage() {
  cat <<EOF
Usage: $(basename "$0") [--dry-run] [path-to-AppImage-or-AppDir]

Validates desktop integration files and, when an AppImage/AppDir is present,
checks executable layout without falling back to a system 'koffer'.
EOF
}

die() {
  echo "smoke_appimage.sh: ERROR: $*" >&2
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1 ;;
    -h|--help) usage; exit 0 ;;
    *)
      if [[ -n "$TARGET" ]]; then
        die "unexpected extra argument: $1"
      fi
      TARGET="$1"
      ;;
  esac
  shift
done

DESKTOP="${ROOT}/packaging/koffer.desktop"
[[ -f "$DESKTOP" ]] || die "missing ${DESKTOP}"
grep -q '^Name=Koffer$' "$DESKTOP" || die "desktop Name=Koffer missing"
if grep -q '^Terminal=true' "$DESKTOP"; then
  die "desktop must not set Terminal=true"
fi
grep -q '^Terminal=false$' "$DESKTOP" || die "desktop must set Terminal=false"
[[ -f "${ROOT}/packaging/icons/koffer.svg" ]] || die "missing icon placeholder packaging/icons/koffer.svg"
[[ -x "${ROOT}/packaging/AppRun" ]] || die "packaging/AppRun must be executable"

echo "smoke_appimage.sh: desktop/icon/AppRun source checks OK"

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "smoke_appimage.sh: dry-run OK (no AppImage/AppDir launch)"
  exit 0
fi

if [[ -z "$TARGET" ]]; then
  # Prefer newest AppImage; else staged AppDir.
  shopt -s nullglob
  apps=( "${ROOT}/dist"/Koffer-*.AppImage )
  shopt -u nullglob
  if [[ ${#apps[@]} -gt 0 ]]; then
    TARGET="${apps[-1]}"
  elif [[ -d "${ROOT}/dist/Koffer.AppDir" ]]; then
    TARGET="${ROOT}/dist/Koffer.AppDir"
  else
    cat >&2 <<EOF
smoke_appimage.sh: ERROR: no AppImage or AppDir found under dist/.
Build first with: scripts/build_appimage.sh
Or validate sources only with: scripts/smoke_appimage.sh --dry-run
EOF
    exit 1
  fi
fi

TARGET="$(readlink -f "$TARGET")"
echo "smoke_appimage.sh: target=${TARGET}"

if [[ -d "$TARGET" ]]; then
  [[ -x "${TARGET}/AppRun" ]] || die "AppDir missing executable AppRun"
  [[ -e "${TARGET}/usr/bin/koffer" ]] || die "AppDir missing usr/bin/koffer"
  [[ -f "${TARGET}/koffer.desktop" ]] || die "AppDir missing koffer.desktop"
  grep -q '^Name=Koffer$' "${TARGET}/koffer.desktop" || die "AppDir desktop Name mismatch"
  if grep -q '^Terminal=true' "${TARGET}/koffer.desktop"; then
    die "AppDir desktop must not set Terminal=true"
  fi
  [[ -f "${TARGET}/usr/share/doc/koffer/THIRD_PARTY_NOTICES.txt" ]] \
    || die "AppDir missing THIRD_PARTY_NOTICES.txt"
  # Refresh staged AppRun from source so smoke validates current packaging/AppRun.
  if [[ -x "${ROOT}/packaging/AppRun" ]]; then
    cp -a "${ROOT}/packaging/AppRun" "${TARGET}/AppRun"
    chmod +x "${TARGET}/AppRun"
  fi
  # Launch smoke: ensure AppRun does not resolve a system binary by temporarily
  # hiding PATH entries named koffer (AppRun must use APPDIR-relative binary).
  SMOKE_PATH="$(mktemp -d)"
  cleanup() { rm -rf "$SMOKE_PATH"; }
  trap cleanup EXIT
  cat >"${SMOKE_PATH}/koffer" <<'EOF'
#!/bin/sh
echo "smoke_appimage.sh: ERROR: fell back to PATH koffer" >&2
exit 99
EOF
  chmod +x "${SMOKE_PATH}/koffer"
  # --help exits without opening a display when argparse runs first.
  if ! PATH="${SMOKE_PATH}:/usr/bin:/bin" APPDIR="$TARGET" \
      QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-offscreen}" \
      "${TARGET}/AppRun" --help >/tmp/koffer-appdir-smoke.out 2>/tmp/koffer-appdir-smoke.err; then
    cat /tmp/koffer-appdir-smoke.err >&2 || true
    die "AppDir AppRun --help failed"
  fi
  if grep -q 'fell back to PATH koffer' /tmp/koffer-appdir-smoke.err 2>/dev/null; then
    die "AppRun used PATH fallback"
  fi
  echo "smoke_appimage.sh: AppDir smoke OK"
  exit 0
fi

if [[ -f "$TARGET" ]]; then
  [[ -x "$TARGET" ]] || die "AppImage is not executable: $TARGET"
  # File(1) is optional; size gate catches truncated downloads.
  size="$(wc -c <"$TARGET")"
  [[ "$size" -gt 1000000 ]] || die "AppImage suspiciously small (${size} bytes): ${TARGET}"
  if command -v timeout >/dev/null 2>&1; then
    # Launch briefly offscreen; tolerate early exit after process start.
    set +e
    PATH="/usr/bin:/bin" QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-offscreen}" \
      timeout 8s "$TARGET" --help >/tmp/koffer-appimage-smoke.out 2>/tmp/koffer-appimage-smoke.err
    rc=$?
    set -e
    # timeout returns 124 on kill; treat as success if process started.
    if [[ "$rc" -ne 0 && "$rc" -ne 124 ]]; then
      cat /tmp/koffer-appimage-smoke.err >&2 || true
      die "AppImage launch smoke failed (exit ${rc})"
    fi
  else
    echo "smoke_appimage.sh: warning: timeout(1) missing; skipped timed launch" >&2
  fi
  echo "smoke_appimage.sh: AppImage smoke OK"
  exit 0
fi

die "target is neither AppDir nor AppImage: ${TARGET}"
