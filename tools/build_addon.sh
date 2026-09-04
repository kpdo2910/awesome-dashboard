#!/usr/bin/env bash
# Build the .ankiaddon zip -- run from anywhere:
#
#     tools/build_addon.sh                                    # ../awesome_dashboard-<version>.ankiaddon
#     tools/build_addon.sh dist/awesome_dashboard-1.6.0-dev.ankiaddon
#
# The release workflow and a hand-rolled dev build go through this one file on
# purpose. The exclude list is the whole product here: a zip that ships docs/ is
# five times the size, and one whose manifest.json sits a directory down is
# rejected by both Anki and AnkiWeb without a useful message. Two copies of that
# list would eventually stop agreeing.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

version="$(python3 tools/release_check.py --print-version)"
out="${1:-../awesome_dashboard-${version}.ankiaddon}"

find . -name '__pycache__' -type d -prune -exec rm -rf {} +

# Zip into a temp dir, not into the destination: an output directory inside the
# repo (dist/) would otherwise exist while zip runs and be archived as an empty
# folder. The destination is created below, after the archive is closed.
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
pkg="$tmp/package.ankiaddon"

# .git/* does NOT cover .github/* -- the wildcard sits after the literal ".git/",
# so the workflows would otherwise ship inside every user's add-on folder.
zip -rq "$pkg" . \
    -x '.git/*' \
    -x '.github/*' \
    -x '__pycache__/*' -x '*/__pycache__/*' -x '*.pyc' \
    -x '.DS_Store' -x '*/.DS_Store' \
    -x 'docs/*' \
    -x 'tools/*' \
    -x 'dist/*' \
    -x '.gitignore' \
    -x 'meta.json' \
    -x '*.ankiaddon'

entries="$(unzip -Z1 "$pkg")"

# Anki reads manifest.json from the root of the archive and nowhere else.
if ! printf '%s\n' "$entries" | grep -qx 'manifest.json'; then
    echo "FAILED: manifest.json is not at the root of the zip" >&2
    exit 1
fi

# meta.json is written by Anki at install time from config.json; shipping one
# would overwrite whatever the user had already configured.
junk="$(printf '%s\n' "$entries" | grep -E \
    '^(\.git|\.github|docs|tools|dist)/|(^|/)(__pycache__|\.DS_Store|meta\.json|\.gitignore)(/|$)|\.pyc$' \
    || true)"
if [ -n "$junk" ]; then
    echo "FAILED: these should not ship:" >&2
    printf '%s\n' "$junk" >&2
    exit 1
fi

mkdir -p "$(dirname "$out")"
out="$(cd "$(dirname "$out")" && pwd)/$(basename "$out")"
rm -f "$out"
mv "$pkg" "$out"

count="$(printf '%s\n' "$entries" | grep -cv '/$' || true)"
echo "$out"
echo "  version $version, $count files, $(du -h "$out" | cut -f1)"
