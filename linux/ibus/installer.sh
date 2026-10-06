#!/bin/sh
# Installe la methode de saisie depuis le code (le paquet .deb le fait deja).
# IBus ne lit pas ~/.local/share/ibus/component.
set -e
ICI=$(cd "$(dirname "$0")" && pwd)
DEST=/usr/share/ibus/component
sed "s|CHEMIN|$ICI|" "$ICI/kab-board.xml" | sudo tee "$DEST/kab-board.xml" >/dev/null
chmod +x "$ICI/kab_ibus.py" 2>/dev/null || true
rm -f "$HOME/.local/share/ibus/component/kab-board.xml"
echo "Composant installe dans $DEST/kab-board.xml"
ibus restart 2>/dev/null || ibus-daemon -drx
echo "Ajoutez maintenant « Kabyle (kab-board) » dans Parametres > Clavier > Sources de saisie."
