// Les ressources compressées de l'extension, rendues telles qu'elles étaient : un décodeur
// xz (xz-embedded), et le vocabulaire du modèle de langue, recalculé.
//
// Le vocabulaire d'un modèle KenLM en trie (SortedVocabulary) est le tableau trié des
// empreintes de ses mots (MurmurHash64A), juste après l'en-tête. Ces 16 Mo, presque
// aléatoires, ne se compressent pas ; or la liste des mots, en clair, termine le fichier.
// L'archive les omet donc, et ils sont recalculés ici avec la fonction de KenLM elle-même.
//
// Construction : chrome/autonome/construire-wasm.sh

#include <cstdint>
#include <cstring>

#include <emscripten/emscripten.h>

#include "util/murmur_hash.hh"

extern "C" {
#include "xz.h"
}

namespace {

// L'en-tête d'un modèle KenLM (format 5) : 88 octets de contrôle, 20 de paramètres, puis
// le nombre de n-grammes de chaque ordre, aligné sur 8.
const std::size_t kEnTeteSansComptes = 88 + 20;
const char kUnk[] = "<unk>";

std::size_t EnTete(unsigned ordre) {
  return (kEnTeteSansComptes + 8 * ordre + 7) & ~std::size_t(7);
}

}  // namespace

extern "C" {

/** Un décodeur xz, pour une fenêtre de 64 Mio au plus (xz -9). */
EMSCRIPTEN_KEEPALIVE void *kab_xz_neuf() {
  xz_crc32_init();
  xz_crc64_init();
  return xz_dec_init(XZ_DYNALLOC, 1u << 26);
}

EMSCRIPTEN_KEEPALIVE void kab_xz_fermer(void *d) {
  xz_dec_end(static_cast<xz_dec *>(d));
}

/**
 * Décompresse ce qui entre dans ce qui sort, autant que possible. Renvoie le code de
 * xz_dec_run (0 : à suivre, 1 : fini, au-delà : une erreur) ; lus[0] et ecrits[0] disent
 * ce qui a été pris et donné.
 */
EMSCRIPTEN_KEEPALIVE int kab_xz_avancer(void *d, const uint8_t *entree, std::size_t n_entree,
                                        uint8_t *sortie, std::size_t n_sortie,
                                        std::size_t *lus, std::size_t *ecrits) {
  xz_buf b;
  b.in = entree;
  b.in_pos = 0;
  b.in_size = n_entree;
  b.out = sortie;
  b.out_pos = 0;
  b.out_size = n_sortie;
  const int r = xz_dec_run(static_cast<xz_dec *>(d), &b);
  *lus = b.in_pos;
  *ecrits = b.out_pos;
  return r;
}

/** La place du vocabulaire dans un modèle, d'après son en-tête : son début, sa taille. */
EMSCRIPTEN_KEEPALIVE int kab_kenlm_vocabulaire_place(const uint8_t *entete, std::size_t *debut,
                                                     std::size_t *taille) {
  const unsigned ordre = entete[88];
  if (ordre == 0 || ordre > 6) return 0;
  uint64_t n;
  std::memcpy(&n, entete + EnTete(ordre), 8);
  *debut = EnTete(ordre) + 8;
  *taille = 8 * n;
  return 1;
}

/**
 * Remplit le vocabulaire d'un modèle entier en mémoire : les empreintes des mots de la
 * liste finale, <unk> excepté. Renvoie 1, ou 0 si le fichier n'a pas la forme attendue
 * (pas de liste, empreintes qui ne sont pas triées).
 */
EMSCRIPTEN_KEEPALIVE int kab_kenlm_vocabulaire(uint8_t *modele, std::size_t taille) {
  std::size_t debut, octets;
  if (!kab_kenlm_vocabulaire_place(modele, &debut, &octets)) return 0;
  const std::size_t n = octets / 8;
  // La liste : <unk> puis les n mots, chacun terminé par un zéro, jusqu'au bout.
  std::size_t zeros = 0, p = taille;
  while (p > debut + octets && zeros < n + 1) {
    --p;
    if (modele[p] == 0) ++zeros;
  }
  if (zeros != n + 1 || p < sizeof(kUnk) - 1) return 0;
  p -= sizeof(kUnk) - 1;
  if (std::memcmp(modele + p, kUnk, sizeof(kUnk)) != 0) return 0;
  const char *mot = reinterpret_cast<const char *>(modele + p + sizeof(kUnk));
  uint64_t precedent = 0;
  for (std::size_t i = 0; i < n; ++i) {
    const std::size_t longueur = std::strlen(mot);
    const uint64_t h = util::MurmurHash64A(mot, longueur, 0);
    if (i > 0 && h <= precedent) return 0;
    std::memcpy(modele + debut + 8 * i, &h, 8);
    precedent = h;
    mot += longueur + 1;
  }
  return 1;
}

}  // extern "C"
