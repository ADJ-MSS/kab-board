#!/bin/sh
# Les deux archives de l'extension, dans sortie/ :
#
#   kab-board-chrome-<version>.zip            à décompresser, puis « Charger l'extension
#                                             non empaquetée » (mode développeur)
#   kab-board-chrome-<version>-web-store.zip  pour le Chrome Web Store, sans la clé : le
#                                             Store donne son propre identifiant
#
# L'extension emporte ses ressources (chrome/autonome/ressources.sh), vérifiées d'abord.
#
#   chrome/empaqueter.sh
set -e
ICI=$(cd "$(dirname "$0")" && pwd)
DEPOT=$(dirname "$ICI")
SORTIE="$DEPOT/sortie"
VERSION=$(python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))["version"])' "$ICI/extension/manifest.json")

if ! (cd "$ICI/extension" && sha256sum -c --quiet "$ICI/autonome/ressources.sha256" >/dev/null 2>&1); then
  echo "Les ressources manquent ou ont changé : chrome/autonome/ressources.sh <kab-board-0.3.apk>" >&2
  exit 1
fi

TRAVAIL=$(mktemp -d)
trap 'rm -rf "$TRAVAIL"' EXIT
mkdir -p "$SORTIE"

copier() {
  mkdir -p "$1"
  (cd "$ICI/extension" && find . -type f ! -name '.*' | sort | while read -r f; do
    mkdir -p "$1/$(dirname "$f")"
    cp "$f" "$1/$f"
  done)
}

empaqueter() {
  rm -f "$2"
  # Dates fixées et ordre trié : la même extension donne la même archive.
  (cd "$1" && find . -type f -exec touch -d 2026-01-01T00:00:00 {} + &&
    find . -type f | sort | sed 's|^\./||' | zip -q -X -D "$2" -@)
  echo "  $(basename "$2") : $(du -h "$2" | cut -f1)"
}

copier "$TRAVAIL/avec-cle"
empaqueter "$TRAVAIL/avec-cle" "$SORTIE/kab-board-chrome-$VERSION.zip"

copier "$TRAVAIL/web-store"
python3 - "$TRAVAIL/web-store/manifest.json" <<'FIN'
import json, sys
chemin = sys.argv[1]
manifeste = json.load(open(chemin, encoding="utf-8"))
manifeste.pop("key", None)
if len(manifeste["description"]) > 132:
    sys.exit("La description dépasse les 132 caractères qu'accepte le Chrome Web Store.")
json.dump(manifeste, open(chemin, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
FIN
ARCHIVE="$SORTIE/kab-board-chrome-$VERSION-web-store.zip"
empaqueter "$TRAVAIL/web-store" "$ARCHIVE"
if [ "$(wc -c < "$ARCHIVE")" -ge 2000000000 ]; then
  echo "L'archive dépasse les 2 Go qu'accepte le Chrome Web Store." >&2
  exit 1
fi
