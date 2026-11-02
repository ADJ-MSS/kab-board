#!/bin/sh
# Les sources que Mozilla demande avec l'extension, pour le code compilé ou minifié
# (le WebAssembly, onnxruntime-web) : dans sortie/kab-board-firefox-sources.zip.
#
#   firefox/signature/sources.sh [<dépôt kab-board>]
set -eu
ICI=$(cd "$(dirname "$0")" && pwd)
DEPOT=$(cd "$ICI/../.." && pwd)
KAB_BOARD=$(cd "${1:-${KAB_BOARD:-$HOME/kab-board}}" && pwd)
TRAVAIL=$(mktemp -d)
trap 'rm -rf "$TRAVAIL"' EXIT
mkdir -p "$TRAVAIL/kab-board-extension" "$TRAVAIL/kab-board" "$DEPOT/sortie"
(cd "$DEPOT" && git archive HEAD chrome/extension chrome/autonome/construire-wasm.sh \
  chrome/autonome/kenlm_wasm.cc chrome/autonome/crf_wasm.cc chrome/autonome/xz_wasm.cc \
  chrome/autonome/usage.cc chrome/autonome/xz-embedded chrome/autonome/ressources.sh \
  chrome/autonome/ressources.sha256 firefox) | tar -x -C "$TRAVAIL/kab-board-extension"
(cd "$KAB_BOARD" && git archive HEAD natif/amont natif/config) | tar -x -C "$TRAVAIL/kab-board"
cp "$ICI/SOURCES.md" "$TRAVAIL/"
SORTIE="$DEPOT/sortie/kab-board-firefox-sources.zip"
rm -f "$SORTIE"
(cd "$TRAVAIL" && zip -qr -X "$SORTIE" .)
echo "  $(basename "$SORTIE") : $(du -h "$SORTIE" | cut -f1)"
