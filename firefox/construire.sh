#!/bin/sh
# L'extension pour Firefox, dans firefox/extension/ : à charger telle quelle
# (about:debugging) ou à empaqueter (firefox/empaqueter.sh). C'est celle de
# chrome/extension, avec ce qui change pour Firefox :
#
#  - le manifeste, tiré de celui de Chrome (manifeste.py) ;
#  - plateforme.js : la page de fond porte le correcteur, faute de document hors écran ;
#  - la fenêtre de la dictée (horsecran/dictee.html), où Firefox demande le micro ;
#  - onnxruntime-web 1.18.0, sa dernière version sans fils : Firefox ne donne pas de
#    mémoire partagée aux pages d'une extension, et la 1.20 l'exige ;
#  - le modèle de langue et le modèle vocal compressés (compresser.py), pour passer sous
#    les limites de Mozilla : 200 Mo l'archive, 250 Mio décompressée.
#
#   firefox/construire.sh
#   firefox/construire.sh --sans-ressources   le code seul, pour l'essai avec le faux correcteur
#
# Il faut les ressources de l'extension (chrome/autonome/ressources.sh), npm, xz et Node.
# La première compression prend quelques minutes ; elle est gardée tant que les
# ressources ne changent pas.
set -eu
ICI=$(cd "$(dirname "$0")" && pwd)
DEPOT=$(dirname "$ICI")
SOURCE="$DEPOT/chrome/extension"
CIBLE="$ICI/extension"
ORT=1.18.0
SANS_RESSOURCES=$([ "${1:-}" = --sans-ressources ] && echo 1 || true)

if [ -z "$SANS_RESSOURCES" ] && ! (cd "$SOURCE" && sha256sum -c --quiet "$DEPOT/chrome/autonome/ressources.sha256" >/dev/null 2>&1); then
  echo "Les ressources manquent : chrome/autonome/ressources.sh <kab-board-0.3.apk>" >&2
  exit 1
fi
TRAVAIL=$(mktemp -d)
trap 'rm -rf "$TRAVAIL"' EXIT

echo "  Le code…"
# Tout chrome/extension, sauf ce qui n'est qu'à Chrome. Les ressources compressées, elles,
# restent d'une construction à l'autre.
mkdir -p "$CIBLE"
find "$CIBLE" -mindepth 1 -maxdepth 1 ! -name ressources -exec rm -rf {} +
(cd "$SOURCE" && find . -type f ! -name '.*' ! -path './ressources/*' ! -path './ort/*' \
    ! -path ./manifest.json ! -path ./plateforme.js ! -path './horsecran/horsecran.*' | sort |
  while read -r f; do
    mkdir -p "$CIBLE/$(dirname "$f")"
    cp "$f" "$CIBLE/$f"
  done)
cp "$ICI/plateforme.js" "$CIBLE/"
cp "$ICI/horsecran/dictee.html" "$ICI/horsecran/dictee.js" "$CIBLE/horsecran/"
python3 "$ICI/manifeste.py" "$SOURCE/manifest.json" "$CIBLE/manifest.json"
if [ -n "$SANS_RESSOURCES" ]; then
  echo "  Prêt, sans ressources : $CIBLE"
  exit 0
fi

echo "  onnxruntime-web $ORT…"
(cd "$TRAVAIL" && npm pack --silent "onnxruntime-web@$ORT" >/dev/null && tar -xzf "onnxruntime-web-$ORT.tgz")
mkdir -p "$CIBLE/ort"
cp "$TRAVAIL/package/dist/esm/ort.wasm.min.js" "$CIBLE/ort/ort.wasm.min.mjs"
cp "$TRAVAIL/package/dist/ort-wasm-simd.wasm" "$CIBLE/ort/"
(cd "$CIBLE" && sha256sum -c --quiet "$ICI/ort.sha256")

echo "  Les ressources…"
python3 "$ICI/compresser.py" "$SOURCE/ressources" "$CIBLE/ressources" > "$TRAVAIL/compresses"
if [ -s "$TRAVAIL/compresses" ]; then
  # shellcheck disable=SC2046
  node "$ICI/verifier_ressources.mjs" "$CIBLE" $(cat "$TRAVAIL/compresses")
fi
echo "  Prêt : $CIBLE ($(du -sh "$CIBLE" | cut -f1))"
