#!/bin/sh
# Installe Kab-board pour l'utilisateur : une entree dans le menu, rien de plus.
# Aucun droit administrateur, aucun fichier hors du dossier personnel.
set -e
ICI=$(cd "$(dirname "$0")" && pwd)
APPS="$HOME/.local/share/applications"
ICONES="$HOME/.local/share/icons/hicolor/256x256/apps"
mkdir -p "$APPS" "$ICONES"

ICONE=""
for candidate in /home/massil/kbd-taqbaylit/outils/icone/kab-board.png \
                 /home/massil/kbd-taqbaylit/outils/icone/kab-board.jpg; do
    [ -f "$candidate" ] && { cp "$candidate" "$ICONES/kab-board.png"; ICONE="kab-board"; break; }
done
[ -z "$ICONE" ] && ICONE="input-keyboard"

cat > "$APPS/kab-board.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Kab-board
GenericName=Clavier et correcteur kabyles
Comment=Écrire le kabyle : correction, propositions, graphie b ou v
Exec=/usr/bin/python3 $ICI/bureau/kab_appli.py
Icon=$ICONE
Terminal=false
Categories=Utility;Accessibility;
Keywords=kabyle;taqbaylit;clavier;correcteur;
DESKTOP
chmod +x "$ICI/bureau/kab_appli.py" "$ICI/bureau/clavier_flottant.py" "$ICI/ibus/kab_ibus.py"
update-desktop-database "$APPS" 2>/dev/null || true
echo "Kab-board installé. Cherchez « Kab-board » dans vos applications."
