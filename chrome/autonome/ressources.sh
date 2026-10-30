#!/bin/sh
# Ce que l'extension autonome emporte et que le dépôt ne garde pas : les ressources
# de l'APK (le correcteur, la table b/v, le modèle vocal Mmeslay) et onnxruntime-web,
# qui fait tourner le modèle vocal. Chaque fichier est vérifié (ressources.sha256) :
# ce sont ceux de l'APK 0.3.
#
#   chrome/autonome/ressources.sh <kab-board-0.3.apk>
#
# Ils vont dans chrome/extension/ressources/ et chrome/extension/ort/. Il faut unzip et
# npm (pour onnxruntime-web 1.20.1, la version d'onnxruntime de l'APK).
set -eu
[ $# -eq 1 ] || { echo "usage : $0 <kab-board-0.3.apk>" >&2; exit 2; }
ICI=$(cd "$(dirname "$0")" && pwd)
EXT=$(dirname "$ICI")/extension
APK=$(cd "$(dirname "$1")" && pwd)/$(basename "$1")
ORT=1.20.1

TRAVAIL=$(mktemp -d)
trap 'rm -rf "$TRAVAIL"' EXIT

echo "  Les ressources de l'APK…"
unzip -qo "$APK" 'assets/moteur/*' 'assets/graphie/table_bv.tsv' 'assets/voix/*' -d "$TRAVAIL"
echo "  onnxruntime-web $ORT…"
(cd "$TRAVAIL" && npm pack --silent "onnxruntime-web@$ORT" >/dev/null && tar -xzf "onnxruntime-web-$ORT.tgz")

mkdir -p "$EXT/ressources/moteur" "$EXT/ressources/graphie" "$EXT/ressources/voix" "$EXT/ort"
while read -r _ chemin; do
  case "$chemin" in
    ort/*) cp "$TRAVAIL/package/dist/${chemin#ort/}" "$EXT/$chemin" ;;
    *) cp "$TRAVAIL/assets/${chemin#ressources/}" "$EXT/$chemin" ;;
  esac
done < "$ICI/ressources.sha256"
(cd "$EXT" && sha256sum -c --quiet "$ICI/ressources.sha256")
echo "  Prêt : $(du -sh "$EXT/ressources" | cut -f1) de ressources, $(du -sh "$EXT/ort" | cut -f1) pour onnxruntime-web"
