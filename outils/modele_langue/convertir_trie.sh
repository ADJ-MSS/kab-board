#!/bin/bash
# Convertit le modele 3-grammes du correcteur au format KenLM TRIE, sans perte.
set -euo pipefail

ARPA=${1:?chemin du modele ARPA}
SORTIE=${2:?chemin du binaire TRIE a produire}
RACINE="$(cd "$(dirname "$0")/../.." && pwd)"
TRAVAIL="$(mktemp -d)"
trap 'rm -rf "$TRAVAIL"' EXIT

cd "$RACINE/natif/amont/kenlm"
SOURCES=$(ls lm/*.cc util/*.cc util/double-conversion/*.cc | grep -vE '_test\.cc|_main\.cc|test_')
echo "compilation de build_binary ($(echo "$SOURCES" | wc -l) fichiers)"
# shellcheck disable=SC2086
g++ -O2 -std=c++17 -I. -DKENLM_MAX_ORDER=6 -DNDEBUG \
    lm/build_binary_main.cc $SOURCES -o "$TRAVAIL/build_binary" -lpthread -lz

echo "conversion vers TRIE"
"$TRAVAIL/build_binary" trie "$ARPA" "$SORTIE"
ls -l "$SORTIE" | awk '{printf "TRIE : %.0f Mio\n", $5 / 1048576}'
