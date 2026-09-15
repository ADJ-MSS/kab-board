#!/bin/bash
# Dépose les sources amont dans natif/amont/ : KenLM, CRFsuite, liblbfgs. Leurs licences respectives
# sont conservées dans leurs arborescences (COPYING, LICENSE).
set -e
D="$(cd "$(dirname "$0")/.." && pwd)/natif/amont"
mkdir -p "$D" && cd "$D"
recuperer() {   # dépôt, nom
  [ -d "$2" ] && { echo "  $2 déjà présent"; return; }
  curl -sL -o "$2.zip" "https://github.com/$1/archive/refs/heads/master.zip"
  unzip -qo "$2.zip" && mv "$2-master" "$2" && rm "$2.zip"
  echo "  $2 récupéré"
}
recuperer kpu/kenlm         kenlm
recuperer chokkan/crfsuite  crfsuite
recuperer chokkan/liblbfgs  liblbfgs

# --- Correctif C++17 --------------------------------------------------- std::binary_function a ete
# supprime en C++17.
echo "  correctif std::binary_function"
for f in $(grep -rl 'std::binary_function' "$D/kenlm" --include='*.hh' --include='*.cc' 2>/dev/null); do
  perl -0pi -e 's/\s*:\s*public\s+std::binary_function<[^>]*>//g;
                s/\s*:\s*std::binary_function<[^>]*>//g' "$f"
  echo "    $(basename "$f")"
done
