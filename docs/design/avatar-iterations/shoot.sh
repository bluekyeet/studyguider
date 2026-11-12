#!/bin/sh
# Draws the contact sheets and photographs them: shoot.sh <round name> [sheet ...]
# CHROME is any Chromium-based browser; the sheets land in docs/design/avatar-iterations/<round name>/ as PNG.
set -e
here="$(cd "$(dirname "$0")" && pwd)"
round="$1"; shift
work="${SHEET_TMP:-$here/.sheets}"
python "$here/sheet.py" "$work" >/dev/null
mkdir -p "$here/$round"
[ $# -gt 0 ] || set -- base base-light combos zoom icons-a icons-b icons-light worn-background worn-aura worn-back worn-bottom worn-shoes worn-top worn-face worn-hair worn-hat worn-held worn-pet
for sheet in "$@"; do
  case "$sheet" in
    icons-light) size=1500,3050 ;; icons-a) size=1500,1500 ;; icons-b) size=1500,2060 ;; base-light) size=1500,1480 ;; base) size=1500,820 ;; combos) size=1500,760 ;; zoom) size=1500,500 ;;
    worn-top|worn-hat) size=1500,870 ;; *) size=1500,590 ;;
  esac
  url="file:///$(cd "$work" && pwd -W 2>/dev/null || pwd)/$sheet.html"
  "${CHROME:-chrome}" --headless --disable-gpu --hide-scrollbars --force-device-scale-factor=1 --window-size=$size --screenshot="$here/$round/$sheet.png" "$url" >/dev/null 2>&1
done
echo "sheets in $here/$round"
