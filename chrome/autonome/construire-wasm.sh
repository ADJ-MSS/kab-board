#!/bin/sh
# KenLM et CRFsuite en WebAssembly, pour le correcteur dans le navigateur.
#
#   chrome/autonome/construire-wasm.sh  ->  chrome/extension/moteur/kab_lm.mjs, kab_lm.wasm,
#                                            kab_crf.mjs, kab_crf.wasm
#
# KenLM et CRFsuite viennent du dépôt kab-board (natif/amont) : KAB_BOARD=~/kab-board
# par défaut. Il faut Emscripten (emcc 3.1 ou plus récent).
#
# Les ponts (kenlm_wasm.cc, crf_wasm.cc) reprennent les appels des ponts JNI de
# l'application Android. Le modèle de langue se lit en mémoire, sans mmap.
# util/usage.cc est remplacé par usage.cc, ici ; util/parallel_read.cc, la lecture en
# plusieurs fils, n'est appelé par rien.
set -e
ICI=$(cd "$(dirname "$0")" && pwd)
NATIF="${KAB_BOARD:-$HOME/kab-board}/natif"
AMONT="$NATIF/amont"
SORTIE=$(cd "$ICI/../extension/moteur" && pwd)
OBJETS=$(mktemp -d)
trap 'rm -r "$OBJETS"' EXIT

COMMUN="-O2 -w -fwasm-exceptions -sMODULARIZE=1 -sEXPORT_ES6=1 -sENVIRONMENT=web,worker,node
        -sALLOW_MEMORY_GROWTH=1 -sINITIAL_MEMORY=32MB -sFORCE_FILESYSTEM=1
        -sEXPORTED_RUNTIME_METHODS=FS,stringToUTF8,lengthBytesUTF8,UTF8ToString
        -sEXPORTED_FUNCTIONS=_malloc,_free"
taille() { ls -l "$1" | awk '{printf "    %s, %d Ko\n", $NF, $5/1024}'; }

echo "  KenLM…"
KENLM="$AMONT/kenlm"
SOURCES="$ICI/kenlm_wasm.cc $ICI/usage.cc $(ls "$KENLM"/lm/*.cc "$KENLM"/util/*.cc "$KENLM"/util/double-conversion/*.cc \
         | grep -vE '(main|test)\.cc$|/util/usage\.cc$|/util/parallel_read\.cc$' | tr '\n' ' ')"
# shellcheck disable=SC2086
em++ -std=c++17 -DKENLM_MAX_ORDER=6 -DNDEBUG -I"$KENLM" $COMMUN \
    -sEXPORT_NAME=KenLM -sMAXIMUM_MEMORY=2GB -o "$SORTIE/kab_lm.mjs" $SOURCES
taille "$SORTIE/kab_lm.wasm"

echo "  CRFsuite…"
CRF="$AMONT/crfsuite"
INCLURE="-I$NATIF/config -I$CRF/include -I$CRF/lib/cqdb/include -I$CRF/lib/crf/src -I$AMONT/liblbfgs/include"
for c in "$CRF"/lib/crf/src/*.c "$CRF"/lib/cqdb/src/*.c "$AMONT"/liblbfgs/lib/*.c; do
    # shellcheck disable=SC2086
    emcc -std=gnu99 -O2 -w $INCLURE -c "$c" -o "$OBJETS/$(basename "$(dirname "$(dirname "$c")")")-$(basename "$c" .c).o"
done
# shellcheck disable=SC2086
em++ -std=c++17 $INCLURE $COMMUN -sEXPORT_NAME=CRFsuite -sMAXIMUM_MEMORY=256MB \
    -o "$SORTIE/kab_crf.mjs" "$ICI/crf_wasm.cc" "$OBJETS"/*.o
taille "$SORTIE/kab_crf.wasm"
