#!/bin/sh
# Les ponts natifs pour Windows, depuis les sources de kab-board (son dossier natif/) :
#
#   kab_lm.dll    le modèle de langue KenLM      (pipeline/pont_kenlm.py)
#   kab_crf.dll   l'étiqueteur CRFsuite          (pipeline/pont_crf.py)
#
#   ./natif/construire-dll.sh [chemin de kab-board]     ->  natif/build/*.dll
#
# Il faut mingw-w64 :  sudo apt install g++-mingw-w64-x86-64
# Tout est lié en statique : les DLL ne demandent que ce que Windows fournit.
# Ce sont les mêmes drapeaux que natif/construire-pont.sh de kab-board.
set -e
ICI=$(cd "$(dirname "$0")" && pwd)
AMONT=${1:-$ICI/../../kab-board}
AMONT=$(cd "$AMONT" && pwd)
NATIF="$AMONT/natif"
SORTIE="$ICI/build"
mkdir -p "$SORTIE/crf"
CXX=x86_64-w64-mingw32-g++
CC=x86_64-w64-mingw32-gcc

KENLM="$NATIF/amont/kenlm"
SOURCES="$NATIF/kenlm_c.cc $(ls $KENLM/lm/*.cc $KENLM/util/*.cc $KENLM/util/double-conversion/*.cc \
         | grep -vE '(main|test)\.cc$' | tr '\n' ' ')"
DRAPEAUX="-std=c++17 -O2 -w -fexceptions -DKENLM_MAX_ORDER=6 -DNDEBUG -I$KENLM"

echo "  KenLM…"
$CXX $DRAPEAUX -static -static-libgcc -static-libstdc++ -shared -s \
    -o "$SORTIE/kab_lm.dll" $SOURCES -lws2_32

echo "  CRFsuite…"
CRF="$NATIF/amont/crfsuite"
for c in "$CRF"/lib/crf/src/*.c "$CRF"/lib/cqdb/src/*.c "$NATIF"/amont/liblbfgs/lib/*.c; do
    $CC -std=gnu99 -O2 -w \
        -I"$NATIF/config" -I"$CRF/include" -I"$CRF/lib/cqdb/include" -I"$CRF/lib/crf/src" \
        -I"$NATIF/amont/liblbfgs/include" -c "$c" -o "$SORTIE/crf/$(basename "$c" .c).o"
done
$CXX -std=c++17 -O2 -w -static -static-libgcc -static-libstdc++ -shared -s \
    -I"$CRF/include" -o "$SORTIE/kab_crf.dll" "$NATIF/crf_c.cc" "$SORTIE"/crf/*.o
rm -rf "$SORTIE/crf"

for f in kab_lm.dll kab_crf.dll; do
    ls -l "$SORTIE/$f" | awk '{printf "    %s, %d Ko\n", $NF, $5/1024}'
done
git -C "$AMONT" rev-parse HEAD > "$SORTIE/AMONT-COMMIT" 2>/dev/null || true
