#!/bin/sh
# Installe la methode de saisie pour la session de l'utilisateur.
set -e
ICI=$(cd "$(dirname "$0")" && pwd)
DEST="$HOME/.local/share/ibus/component"
mkdir -p "$DEST"
sed "s|CHEMIN|$ICI|" "$ICI/kab-board.xml" > "$DEST/kab-board.xml"
chmod +x "$ICI/kab_ibus.py"
echo "Composant installe dans $DEST/kab-board.xml"
ibus restart 2>/dev/null || ibus-daemon -drx
echo "Ajoutez maintenant « Kabyle (kab-board) » dans Parametres > Clavier > Sources de saisie."
