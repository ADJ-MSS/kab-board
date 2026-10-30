// Pont WebAssembly vers KenLM, en lecture seule.
//
// Les mêmes appels que le pont JNI de l'application Android (natif/kenlm_jni.cc du
// dépôt kab-board), pour les mêmes scores. Deux différences : le modèle est lu en
// mémoire (util::READ), le navigateur n'ayant pas de mmap, et l'index d'un mot peut
// se demander une fois pour toutes, puis servir à chaque score.
//
// Construction : chrome/autonome/construire-kenlm.sh

#include <cstring>
#include <new>
#include <string>
#include <vector>

#include <emscripten/emscripten.h>

#include "lm/model.hh"
#include "lm/state.hh"

namespace {

struct Contexte {
  lm::base::Model *modele;
  std::size_t taille_etat;
};

inline Contexte *ctx(void *h) { return reinterpret_cast<Contexte *>(h); }

}  // namespace

#define EXPORTE extern "C" EMSCRIPTEN_KEEPALIVE

// Ouvre un modèle. Rend 0 si le fichier manque ou n'est pas un modèle.
EXPORTE void *kab_lm_ouvrir(const char *chemin) {
  try {
    lm::ngram::Config cfg;
    cfg.load_method = util::READ;
    Contexte *c = new Contexte();
    c->modele = lm::ngram::LoadVirtual(chemin, cfg);
    c->taille_etat = c->modele->StateSize();
    return c;
  } catch (const std::exception &) {
    return nullptr;
  }
}

EXPORTE void kab_lm_fermer(void *h) {
  if (!h) return;
  delete ctx(h)->modele;
  delete ctx(h);
}

EXPORTE int kab_lm_ordre(void *h) {
  return h ? static_cast<int>(ctx(h)->modele->Order()) : 0;
}

EXPORTE int kab_lm_taille_etat(void *h) {
  return h ? static_cast<int>(ctx(h)->taille_etat) : 0;
}

EXPORTE void *kab_etat_neuf(void *h) {
  if (!h) return nullptr;
  return new (std::nothrow) unsigned char[ctx(h)->taille_etat]();
}

EXPORTE void kab_etat_liberer(void *e) {
  delete[] reinterpret_cast<unsigned char *>(e);
}

EXPORTE void kab_debut_phrase(void *h, void *etat) {
  ctx(h)->modele->BeginSentenceWrite(etat);
}

EXPORTE void kab_contexte_vide(void *h, void *etat) {
  ctx(h)->modele->NullContextWrite(etat);
}

EXPORTE void kab_etat_copier(void *h, void *source, void *cible) {
  std::memcpy(cible, source, ctx(h)->taille_etat);
}

EXPORTE int kab_etat_egal(void *h, void *a, void *b) {
  return std::memcmp(a, b, ctx(h)->taille_etat) == 0;
}

// L'index d'un mot dans le vocabulaire du modèle (0 : inconnu).
EXPORTE unsigned kab_lm_index(void *h, const char *mot) {
  return ctx(h)->modele->BaseVocabulary().Index(mot ? mot : "");
}

// log10 P(mot | état d'entrée), et écrit l'état résultant.
EXPORTE float kab_base_score(void *h, void *entree, const char *mot, void *sortie) {
  lm::base::Model *m = ctx(h)->modele;
  return m->BaseScore(entree, m->BaseVocabulary().Index(mot ? mot : ""), sortie);
}

// La même chose, le mot donné par son index.
EXPORTE float kab_base_score_index(void *h, void *entree, unsigned idx, void *sortie) {
  return ctx(h)->modele->BaseScore(entree, idx, sortie);
}

// Le score d'une phrase entière, comme ModeleLangue.score sur le téléphone : les mots
// séparés par des espaces, et la fin de phrase si eos.
EXPORTE float kab_score_phrase(void *h, const char *phrase, int bos, int eos) {
  lm::base::Model *m = ctx(h)->modele;
  std::string s = phrase ? phrase : "";

  std::vector<unsigned char> a(m->StateSize()), b(m->StateSize());
  void *etat = a.data(), *suivant = b.data();
  if (bos) m->BeginSentenceWrite(etat); else m->NullContextWrite(etat);

  float total = 0.0f;
  std::size_t i = 0;
  while (i <= s.size()) {
    std::size_t j = s.find(' ', i);
    if (j == std::string::npos) j = s.size();
    if (j > i) {
      const std::string mot = s.substr(i, j - i);
      total += m->BaseScore(etat, m->BaseVocabulary().Index(mot), suivant);
      std::swap(etat, suivant);
    }
    if (j == s.size()) break;
    i = j + 1;
  }
  if (eos) total += m->BaseScore(etat, m->BaseVocabulary().EndSentence(), suivant);
  return total;
}
