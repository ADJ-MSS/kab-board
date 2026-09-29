#!/bin/sh
# Construit le paquet installable pour Debian et Ubuntu.
#   ./paquet/construire.sh        ->  kab-board_1.0_all.deb
set -e
ICI=$(cd "$(dirname "$0")/.." && pwd)
VERSION=${1:-1.0}
ARBRE=$(mktemp -d)
trap 'rm -rf "$ARBRE"' EXIT

mkdir -p "$ARBRE/DEBIAN" \
         "$ARBRE/usr/share/kab-board" \
         "$ARBRE/usr/share/applications" \
         "$ARBRE/usr/bin"

# Le code et la table des graphies. Les modeles du correcteur ne sont pas dans
# le paquet : ils pesent plus de 600 Mo et vivent sur Zenodo.
cp -r "$ICI/linux" "$ARBRE/usr/share/kab-board/"
mkdir -p "$ARBRE/usr/share/kab-board/app/src/main/assets/graphie"
cp "$ICI/app/src/main/assets/graphie/table_bv.tsv" \
   "$ARBRE/usr/share/kab-board/app/src/main/assets/graphie/"
find "$ARBRE/usr/share/kab-board" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

cat > "$ARBRE/DEBIAN/control" <<CONTROL
Package: kab-board
Version: $VERSION
Section: utils
Priority: optional
Architecture: all
Depends: python3 (>= 3.10), python3-gi, gir1.2-gtk-4.0, gir1.2-gtk-3.0,
 gir1.2-ibus-1.0, python3-numpy, alsa-utils, ibus
Recommends: python3-onnxruntime
Maintainer: Massil Aoudj <massil.aoudj@lecnam.net>
Homepage: https://github.com/ADJ-MSS/kab-board
Description: Clavier et correcteur kabyles
 Ecrire le kabyle sur ordinateur : correction en contexte, six propositions,
 prediction du mot suivant, dictee hors ligne et graphie b ou v.
 .
 Trois objets : une application a interrupteurs, une methode de saisie qui
 ecrit dans toutes les applications, et un clavier a l'ecran.
 .
 Les modeles du correcteur ne sont pas dans le paquet. L'application indique
 ou les prendre au premier lancement : depot Zenodo 10.5281/zenodo.22112059.
CONTROL

cat > "$ARBRE/usr/bin/kab-board" <<'LANCEUR'
#!/bin/sh
exec /usr/bin/python3 /usr/share/kab-board/linux/bureau/kab_appli.py "$@"
LANCEUR
chmod 755 "$ARBRE/usr/bin/kab-board"

cat > "$ARBRE/usr/share/applications/kab-board.desktop" <<'DESKTOP'
[Desktop Entry]
Type=Application
Name=Kab-board
GenericName=Clavier et correcteur kabyles
Comment=Écrire le kabyle : correction, propositions, graphie b ou v
Exec=kab-board
Icon=input-keyboard
Terminal=false
Categories=Utility;Accessibility;
Keywords=kabyle;taqbaylit;clavier;correcteur;
DESKTOP

cat > "$ARBRE/DEBIAN/postinst" <<'POST'
#!/bin/sh
set -e
update-desktop-database /usr/share/applications 2>/dev/null || true
echo "Kab-board installé. Cherchez « Kab-board » dans vos applications."
POST
chmod 755 "$ARBRE/DEBIAN/postinst"

dpkg-deb --root-owner-group --build "$ARBRE" "$ICI/kab-board_${VERSION}_all.deb" >/dev/null
echo "Paquet construit : kab-board_${VERSION}_all.deb"
