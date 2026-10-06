#!/bin/sh
# Les ponts C vers KenLM, CRFsuite et ONNX Runtime, pour Linux et pour Windows.
#
#   ./natif/construire-pont.sh            tout ce que les compilateurs permettent
#   ./natif/construire-pont.sh linux      seulement les .so
#   ./natif/construire-pont.sh windows    seulement la .dll de KenLM
#
# Windows demande mingw-w64 :  sudo apt install mingw-w64
set -e
ICI=$(cd "$(dirname "$0")" && pwd)
AMONT="$ICI/amont"
SORTIE="$ICI/pont"
CACHE="$ICI/build"
QUOI=${1:-tout}

# Zig, pour viser glibc 2.28 quelle que soit la machine qui construit.
ZIG_VERSION=0.13.0
ZIG_NOM="zig-linux-x86_64-$ZIG_VERSION"
ZIG_SHA256=d45312e61ebcc48032b77bc4cf7fd6915c11fa16e4aad116b66c9468211230ea
CIBLE=x86_64-linux-gnu.2.28

# La version de l'application Android.
ORT_VERSION=1.20.1
ORT_NOM="onnxruntime-linux-x64-$ORT_VERSION"
ORT_SHA256=67db4dc1561f1e3fd42e619575c82c601ef89849afc7ea85a003abbac1a1a105

mkdir -p "$SORTIE" "$CACHE"

KENLM="$AMONT/kenlm"
SOURCES="$ICI/kenlm_c.cc $(ls $KENLM/lm/*.cc $KENLM/util/*.cc $KENLM/util/double-conversion/*.cc \
         | grep -vE '(main|test)\.cc$' | tr '\n' ' ')"
DRAPEAUX="-std=c++17 -O2 -w -fexceptions -DKENLM_MAX_ORDER=6 -DNDEBUG -I$KENLM"

taille() { ls -l "$1" | awk '{printf "    %s, %d Ko\n", $NF, $5/1024}'; }

if [ "$QUOI" = "tout" ] || [ "$QUOI" = "linux" ]; then
    recuperer() {   # adresse fichier sha256
        [ -f "$2" ] || curl -sSL -o "$2" "$1"
        echo "$3  $2" | sha256sum -c --quiet -
    }
    recuperer "https://ziglang.org/download/$ZIG_VERSION/$ZIG_NOM.tar.xz" \
              "$CACHE/$ZIG_NOM.tar.xz" "$ZIG_SHA256"
    [ -x "$CACHE/$ZIG_NOM/zig" ] || tar xJf "$CACHE/$ZIG_NOM.tar.xz" -C "$CACHE"
    ZIG="$CACHE/$ZIG_NOM/zig"
    export ZIG_GLOBAL_CACHE_DIR="$CACHE/zig-cache" ZIG_LOCAL_CACHE_DIR="$CACHE/zig-cache"
    CC="$ZIG cc -target $CIBLE"
    CXX="$ZIG c++ -target $CIBLE"
    EXPORTS="-Wl,--version-script=$ICI/exports.map"

    echo "  Linux : KenLM…"
    $CXX $DRAPEAUX -fPIC -fvisibility=hidden -shared -s $EXPORTS -o "$SORTIE/libkab_lm.so" $SOURCES -lpthread
    taille "$SORTIE/libkab_lm.so"

    echo "  Linux : CRFsuite…"
    CRF="$AMONT/crfsuite"
    OBJETS="$CACHE/crf-objets"
    rm -rf "$OBJETS" && mkdir -p "$OBJETS"
    for c in "$CRF"/lib/crf/src/*.c "$CRF"/lib/cqdb/src/*.c "$AMONT"/liblbfgs/lib/*.c; do
        $CC -std=gnu99 -O2 -w -fPIC -fvisibility=hidden \
            -I"$ICI/config" -I"$CRF/include" -I"$CRF/lib/cqdb/include" -I"$CRF/lib/crf/src" \
            -I"$AMONT/liblbfgs/include" -c "$c" -o "$OBJETS/$(basename "$c" .c).o"
    done
    $CXX -std=c++17 -O2 -w -fPIC -fvisibility=hidden -shared -s $EXPORTS \
        -I"$CRF/include" -o "$SORTIE/libkab_crf.so" "$ICI/crf_c.cc" "$OBJETS"/*.o -lm
    taille "$SORTIE/libkab_crf.so"

    echo "  Linux : ONNX Runtime $ORT_VERSION…"
    recuperer "https://github.com/microsoft/onnxruntime/releases/download/v$ORT_VERSION/$ORT_NOM.tgz" \
              "$CACHE/$ORT_NOM.tgz" "$ORT_SHA256"
    rm -rf "$CACHE/$ORT_NOM" && tar xzf "$CACHE/$ORT_NOM.tgz" -C "$CACHE"
    cp "$CACHE/$ORT_NOM/lib/libonnxruntime.so.$ORT_VERSION" "$SORTIE/libonnxruntime.so.1"
    $CC -std=c99 -O2 -w -fPIC -fvisibility=hidden -shared -s $EXPORTS \
        -I"$CACHE/$ORT_NOM/include" -o "$SORTIE/libkab_onnx.so" "$ICI/onnx_c.c" \
        -L"$SORTIE" -l:libonnxruntime.so.1 -Wl,-rpath,'$ORIGIN'
    taille "$SORTIE/libkab_onnx.so"
    taille "$SORTIE/libonnxruntime.so.1"
fi

if [ "$QUOI" = "tout" ] || [ "$QUOI" = "windows" ]; then
    if command -v x86_64-w64-mingw32-g++ >/dev/null; then
        echo "  Windows…"
        x86_64-w64-mingw32-g++ $DRAPEAUX -static -static-libgcc -static-libstdc++ \
            -shared -o "$SORTIE/kab_lm.dll" $SOURCES -lws2_32
        taille "$SORTIE/kab_lm.dll"
    else
        echo "  Windows : mingw-w64 absent, on saute."
    fi
fi
