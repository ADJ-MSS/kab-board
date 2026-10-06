#!/bin/sh
# Le paquet complet : le code ET les ressources, comme l'APK sur Android.
# Rien a telecharger apres l'installation.
#
#   ./paquet/construire-complet.sh 1.3    ->  kab-board-complet_1.3_amd64.deb
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
         "$ARBRE/usr/share/applications" "$ARBRE/usr/bin" "$ARBRE/usr/share/ibus/component"

echo "  ponts natifs…"
sh "$ICI/natif/construire-pont.sh" linux >/dev/null
mkdir -p "$P/natif/pont"
for f in libkab_lm.so libkab_crf.so libkab_onnx.so libonnxruntime.so.1; do
    install -m 644 "$ICI/natif/pont/$f" "$P/natif/pont/"
done
DOC="$ARBRE/usr/share/doc/kab-board-complet"
mkdir -p "$DOC/onnxruntime"
cp "$ICI/natif/build/onnxruntime-linux-x64-1.20.1/LICENSE" \
   "$ICI/natif/build/onnxruntime-linux-x64-1.20.1/ThirdPartyNotices.txt" "$DOC/onnxruntime/"

echo "  rapidfuzz, une roue par version de Python…"
ROUES="$ICI/natif/build/roues"
mkdir -p "$ROUES"
PYPI=https://files.pythonhosted.org/packages
while read -r abi sha chemin; do
    roue="$ROUES/${chemin##*/}"
    [ -f "$roue" ] || curl -sSL -o "$roue" "$PYPI/$chemin"
    echo "$sha  $roue" | sha256sum -c --quiet -
    mkdir -p "$P/vendor/$abi"
    python3 -c "import sys, zipfile; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" \
        "$roue" "$P/vendor/$abi"
done <<ROUES
cp310 dfa552338f51aec280f17b02d28bace1e162d1a84ccd80e3339a57f98aedb56b 95/ff/a42c9ce9f9e90ceb5b51136e0b8e8e6e5113ba0b45d986effbd671e7dddf/rapidfuzz-3.14.5-cp310-cp310-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl
cp311 3d50e5861872935fece391351cbb5ba21d1bced277cf5e1143d207a0a35f1925 6b/d0/4539e42a2d596e068f7738f279638a4a74edd1fbb6f8594e2458058979c6/rapidfuzz-3.14.5-cp311-cp311-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl
cp312 48bee0b91bebfaec41e1081e351000659ab7570cc4598d617aa04d5bf827f9e6 79/72/97a9728c711c7c1b06e107d3f0623880fb4ef90e147ed13c551a1730e7cc/rapidfuzz-3.14.5-cp312-cp312-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl
cp313 17a34330cd2a538c1ce5d400b61ba358c5b72c654b928ff87b362e88f8b864c7 90/79/2fc252a63bc91d3c3b234d0a3a6ad4ebc460037a23cdcdaf9285f986e6c9/rapidfuzz-3.14.5-cp313-cp313-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl
cp314 4900143d82071bdda533b00300c40b14b963ff826b3642cc463b6dd0f036585e c8/85/9535df0b78ba51f478c9ce7eb6d1f85535cc31fe356773b48fd9d3e563ca/rapidfuzz-3.14.5-cp314-cp314-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl
ROUES

echo "  code…"
cp -r "$ICI/linux" "$P/"
mkdir -p "$P/app/src/main/assets/graphie"
cp "$ICI/app/src/main/assets/graphie/table_bv.tsv" "$P/app/src/main/assets/graphie/"
find "$P" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

echo "  ressources du correcteur…"
cp "$CORRECTEUR/kabyle_lexicon_v4.csv" "$P/modeles/"
cp "$CORRECTEUR/amyag_formes.txt"      "$P/modeles/"
cp "$CORRECTEUR/kab-POS-tagl.joblib"   "$P/modeles/"
cp "$ACTIFS/moteur/pos_kab.crfsuite"   "$P/modeles/"
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
Architecture: amd64
Depends: python3 (>= 3.10), python3-gi, gir1.2-gtk-4.0, gir1.2-gtk-3.0,
 gir1.2-ibus-1.0, python3-numpy, alsa-utils, ibus, libc6 (>= 2.27), libstdc++6,
 libgcc-s1 | libgcc1
Recommends: python3-rapidfuzz
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

# IBus ne lit que /usr/share/ibus/component.
sed "s|CHEMIN|/usr/share/kab-board/linux/ibus|" "$ICI/linux/ibus/kab-board.xml" \
    > "$ARBRE/usr/share/ibus/component/kab-board.xml"
chmod 755 "$P/linux/ibus/kab_ibus.py"

cat > "$ARBRE/DEBIAN/postinst" <<'POST'
#!/bin/sh
set -e
update-desktop-database /usr/share/applications 2>/dev/null || true
echo "Kab-board installé, ressources comprises. Cherchez « Kab-board » dans vos applications."
echo "Pour écrire partout : lancez « ibus restart » (ou rouvrez la session), puis ajoutez"
echo "« Kabyle (kab-board) » dans Paramètres > Clavier > Sources de saisie."
POST
chmod 755 "$ARBRE/DEBIAN/postinst"

# pos_kab.crfsuite arrive en 600.
chmod 755 "$ARBRE"
chmod -R u+rwX,go+rX,go-w "$ARBRE/usr"

echo "  compression…"
dpkg-deb -Zgzip -z6 --root-owner-group --build "$ARBRE" \
         "$ICI/kab-board-complet_${VERSION}_amd64.deb" >/dev/null
ls -l "$ICI/kab-board-complet_${VERSION}_amd64.deb" | awk '{printf "Paquet : %.0f Mo (%d octets)\n", $5/1000000, $5}'
