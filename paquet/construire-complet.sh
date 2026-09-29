#!/bin/sh
# Le paquet complet : le code ET les ressources, comme l'APK sur Android.
# Rien a telecharger apres l'installation.
#
#   ./paquet/construire-complet.sh        ->  kab-board-complet_1.0_all.deb
set -e
ICI=$(cd "$(dirname "$0")/.." && pwd)
VERSION=${1:-1.0}
ACTIFS=${ACTIFS:-$ICI/app/src/main/assets}
CORRECTEUR=${CORRECTEUR:-$HOME/Téléchargements/Téléchargements/OneDrive_2_02-04-2026/correcteur_kabyle}
SEMANTIQUE=${SEMANTIQUE:-$CORRECTEUR/WORLD NET/dictionnaire_sémantique_racinale_kabyle_V1.json}
ARBRE=$(mktemp -d)
trap 'rm -rf "$ARBRE"' EXIT

P="$ARBRE/usr/share/kab-board"
mkdir -p "$ARBRE/DEBIAN" "$P/modeles" "$P/assets/moteur" "$P/assets/voix" \
         "$ARBRE/usr/share/applications" "$ARBRE/usr/bin"

echo "  code…"
cp -r "$ICI/linux" "$P/"
mkdir -p "$P/app/src/main/assets/graphie"
cp "$ICI/app/src/main/assets/graphie/table_bv.tsv" "$P/app/src/main/assets/graphie/"
find "$P" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

echo "  ressources du correcteur…"
cp "$CORRECTEUR/kabyle_lexicon_v4.csv" "$P/modeles/"
cp "$CORRECTEUR/amyag_formes.txt"      "$P/modeles/"
cp "$CORRECTEUR/kab-POS-tagl.joblib"   "$P/modeles/"
cp "$ICI/linux/data/lexique_categories.txt" "$P/modeles/"
# Le modele de langue compact du telephone : 281 Mo au lieu de 538, meme ordre 3.
cp "$ACTIFS/moteur/kabyle_3gram.binary" "$P/modeles/"
# Le graphe semantique, la ou preparer_chemins() le cherche. Sans lui, le
# pipeline demarre quand meme et annonce « semantique desactivee ».
mkdir -p "$P/modeles/wordnet"
cp "$SEMANTIQUE" "$P/modeles/wordnet/"

echo "  ressources des outils et de la dictee…"
for f in wordnet.formes wordnet.gloses pool.frequents; do
    cp "$ACTIFS/moteur/$f" "$P/assets/moteur/"
done
cp "$ACTIFS/voix/mmeslay.onnx" "$ACTIFS/voix/jetons.txt" "$P/assets/voix/"

cat > "$ARBRE/DEBIAN/control" <<CONTROL
Package: kab-board-complet
Version: $VERSION
Section: utils
Priority: optional
Architecture: all
Depends: python3 (>= 3.10), python3-gi, gir1.2-gtk-4.0, gir1.2-gtk-3.0,
 gir1.2-ibus-1.0, python3-numpy, alsa-utils, ibus
Recommends: python3-kenlm, python3-onnxruntime
Conflicts: kab-board
Replaces: kab-board
Maintainer: Massil Aoudj <massil.aoudj@lecnam.net>
Homepage: https://github.com/ADJ-MSS/kab-board
Description: Clavier et correcteur kabyles, ressources comprises
 Ecrire le kabyle sur ordinateur : correction en contexte, six propositions,
 prediction du mot suivant, dictee hors ligne et graphie b ou v.
 .
 Tout est dans le paquet, comme dans l'application Android : le lexique de
 1,58 million d'entrees, le modele de langue 3-grammes, l'etiqueteur, le
 graphe semantique et le modele vocal. Rien a telecharger ensuite, rien a
 envoyer : tout se calcule sur la machine.
 .
 Ressources publiees sur Zenodo, doi 10.5281/zenodo.22112059, sous MIT pour
 le logiciel et CC BY-SA 4.0 pour les donnees. Modele vocal Mmeslay, GPL-3.0.
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
echo "Kab-board installé, ressources comprises. Cherchez « Kab-board » dans vos applications."
POST
chmod 755 "$ARBRE/DEBIAN/postinst"

echo "  compression…"
dpkg-deb -Zgzip -z6 --root-owner-group --build "$ARBRE" \
         "$ICI/kab-board-complet_${VERSION}_all.deb" >/dev/null
ls -l "$ICI/kab-board-complet_${VERSION}_all.deb" | awk '{printf "Paquet : %.0f Mo (%d octets)\n", $5/1000000, $5}'
