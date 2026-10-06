// Pont C vers KenLM, en lecture seule.
//
// Android appelle KenLM par JNI ; le greffon Word, lui, passe par Python, et
// le module « kenlm » de PyPI n'a pas de roue Windows : il faudrait un
// compilateur C++ sur la machine de l'utilisateur. Cette bibliothèque expose
// donc les cinq appels dont le décodeur se sert, derrière une interface C que
// ctypes atteint sans rien compiler.
//
// Construction : natif/construire-pont.sh

#include <cstring>
#include <new>
#include <string>

#include "lm/model.hh"
#include "lm/state.hh"

namespace {

struct Contexte {
  lm::base::Model *modele;
  std::size_t taille_etat;
};

inline Contexte *ctx(void *h) { return reinterpret_cast<Contexte *>(h); }

}  // namespace

#if defined(_WIN32)
#define EXPORTE extern "C" __declspec(dllexport)
#else
#define EXPORTE extern "C" __attribute__((visibility("default")))
#endif

// Ouvre un modèle. Rend 0 si le fichier manque ou n'est pas un modèle.
EXPORTE void *kab_lm_ouvrir(const char *chemin) {
  try {
    lm::ngram::Config cfg;
    cfg.load_method = util::LAZY;          // mmap, pas de copie en mémoire
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

// La taille d'un état dépend du format du modèle : TRIE et PROBING diffèrent.
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
  if (h && etat) ctx(h)->modele->BeginSentenceWrite(etat);
}

EXPORTE void kab_contexte_vide(void *h, void *etat) {
  if (h && etat) ctx(h)->modele->NullContextWrite(etat);
}

EXPORTE void kab_etat_copier(void *h, void *source, void *cible) {
  if (h && source && cible) std::memcpy(cible, source, ctx(h)->taille_etat);
}

// log10 P(mot | état d'entrée), et écrit l'état résultant.
EXPORTE float kab_base_score(void *h, void *entree, const char *mot, void *sortie) {
  if (!h || !entree || !sortie) return 0.0f;
  lm::base::Model *m = ctx(h)->modele;
  const lm::WordIndex idx = m->BaseVocabulary().Index(mot ? mot : "");
  return m->BaseScore(entree, idx, sortie);
}

// Le score d'une phrase entière, comme Model.score(texte).
EXPORTE float kab_score_phrase(void *h, const char *phrase, int debut, int fin) {
  if (!h) return 0.0f;
  lm::base::Model *m = ctx(h)->modele;
  std::size_t taille = ctx(h)->taille_etat;
  unsigned char *a = new unsigned char[taille]();
  unsigned char *b = new unsigned char[taille]();

  if (debut) m->BeginSentenceWrite(a); else m->NullContextWrite(a);

  float total = 0.0f;
  std::string mot;
  const char *p = phrase ? phrase : "";
  for (;; ++p) {
    if (*p && *p != ' ' && *p != '\t' && *p != '\n') { mot.push_back(*p); continue; }
    if (!mot.empty()) {
      total += m->BaseScore(a, m->BaseVocabulary().Index(mot), b);
      std::memcpy(a, b, taille);
      mot.clear();
    }
    if (!*p) break;
  }
  if (fin) total += m->BaseScore(a, m->BaseVocabulary().Index("</s>"), b);

  delete[] a;
  delete[] b;
  return total;
}
