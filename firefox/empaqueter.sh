#!/bin/sh
# L'archive de l'extension pour Firefox, dans sortie/ : kab-board-firefox-<version>.xpi, à
# faire signer par Mozilla (addons.mozilla.org), qui n'en accepte pas de plus de
# 200 000 000 octets, ni de plus de 250 Mio une fois décompressée. Elle part de
# firefox/extension (firefox/construire.sh).
#
#   firefox/empaqueter.sh
set -e
ICI=$(cd "$(dirname "$0")" && pwd)
DEPOT=$(dirname "$ICI")
EXTENSION="$ICI/extension"
SORTIE="$DEPOT/sortie"
[ -f "$EXTENSION/ressources/compresses.json" ] || { echo "D'abord : firefox/construire.sh" >&2; exit 1; }
VERSION=$(python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))["version"])' "$EXTENSION/manifest.json")
ARCHIVE="$SORTIE/kab-board-firefox-$VERSION.xpi"

TRAVAIL=$(mktemp -d)
trap 'rm -rf "$TRAVAIL"' EXIT
mkdir -p "$SORTIE"
cp -r "$EXTENSION/." "$TRAVAIL/"
rm -f "$ARCHIVE"
# Dates fixées et ordre trié : la même extension donne la même archive. Ce qui est déjà
# compressé (les parties xz : .xz.1, .xz.2…) est rangé tel quel.
(cd "$TRAVAIL" && find . -type f -exec touch -d 2026-01-01T00:00:00 {} + &&
  find . -type f | sort | sed 's|^\./||' | zip -q -X -D -n .1:.2:.3:.4:.5:.6:.7:.8:.9 "$ARCHIVE" -@)
TAILLE=$(wc -c < "$ARCHIVE")
DECOMPRESSEE=$(du -sb "$TRAVAIL" | cut -f1)
echo "  $(basename "$ARCHIVE") : $TAILLE octets, $DECOMPRESSEE une fois décompressée"
if [ "$TAILLE" -ge 200000000 ] || [ "$DECOMPRESSEE" -ge $((250 * 1024 * 1024)) ]; then
  echo "Trop grande pour Mozilla : 200 000 000 octets au plus, 250 Mio décompressée." >&2
  exit 1
fi
