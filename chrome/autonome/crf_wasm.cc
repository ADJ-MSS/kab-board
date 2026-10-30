// Pont WebAssembly vers CRFsuite, en étiquetage seul.
//
// Le même étiquetage que le pont JNI de l'application Android (natif/crf_jni.cc du
// dépôt kab-board) : les traits d'un mot, nommés et pondérés, les traits inconnus du
// modèle ignorés comme le fait pycrfsuite, puis Viterbi. Les noms arrivent d'un bloc,
// séparés par des zéros, et les étiquettes repartent en numéros.
//
// Construction : chrome/autonome/construire-wasm.sh

#include <cstring>
#include <string>

#include <emscripten/emscripten.h>

extern "C" {
#include "crfsuite.h"
}

namespace {

struct Etiqueteur {
  crfsuite_model_t *modele = nullptr;
  crfsuite_tagger_t *tagger = nullptr;
  crfsuite_dictionary_t *attrs = nullptr;
  crfsuite_dictionary_t *labels = nullptr;
};

inline Etiqueteur *de(void *h) { return reinterpret_cast<Etiqueteur *>(h); }

void liberer(Etiqueteur *e) {
  if (e->labels) e->labels->release(e->labels);
  if (e->attrs) e->attrs->release(e->attrs);
  if (e->tagger) e->tagger->release(e->tagger);
  if (e->modele) e->modele->release(e->modele);
  delete e;
}

}  // namespace

#define EXPORTE extern "C" EMSCRIPTEN_KEEPALIVE

// Ouvre un modèle. Rend 0 s'il est illisible ou incomplet.
EXPORTE void *kab_crf_ouvrir(const char *chemin) {
  Etiqueteur *e = new Etiqueteur();
  if (crfsuite_create_instance_from_file(chemin, (void **)&e->modele) != 0) {
    delete e;
    return nullptr;
  }
  const int ok = e->modele->get_tagger(e->modele, &e->tagger) == 0 &&
                 e->modele->get_attrs(e->modele, &e->attrs) == 0 &&
                 e->modele->get_labels(e->modele, &e->labels) == 0;
  if (!ok || !e->tagger || !e->attrs || !e->labels) {
    liberer(e);
    return nullptr;
  }
  return e;
}

EXPORTE void kab_crf_fermer(void *h) {
  if (h) liberer(de(h));
}

EXPORTE int kab_crf_nb_etiquettes(void *h) {
  return de(h)->labels->num(de(h)->labels);
}

// Le nom de l'étiquette i, copié dans tampon. Rend sa longueur, ou -1.
EXPORTE int kab_crf_etiquette(void *h, int i, char *tampon, int taille) {
  const char *nom = nullptr;
  if (de(h)->labels->to_string(de(h)->labels, i, &nom) != 0 || !nom) return -1;
  const int n = static_cast<int>(std::strlen(nom));
  if (n < taille) std::memcpy(tampon, nom, n + 1);
  de(h)->labels->free(de(h)->labels, nom);
  return n < taille ? n : -1;
}

// Étiquette une phrase de nMots mots. noms : les traits, chacun suivi d'un zéro ;
// poids : un par trait ; bornes[i] : le nombre de traits jusqu'au mot i compris.
// Écrit le numéro de l'étiquette de chaque mot dans sortie.
EXPORTE void kab_crf_etiqueter(void *h, const char *noms, const double *poids,
                               const int *bornes, int nMots, int *sortie) {
  Etiqueteur *e = de(h);
  if (nMots <= 0) return;

  crfsuite_instance_t inst;
  crfsuite_instance_init_n(&inst, nMots);

  const char *p = noms;
  int debut = 0;
  for (int i = 0; i < nMots; ++i) {
    const int fin = bornes[i];
    crfsuite_item_t *item = &inst.items[i];
    crfsuite_item_init(item);
    for (int k = debut; k < fin; ++k) {
      int aid = e->attrs->to_id(e->attrs, p);
      if (aid >= 0) {
        crfsuite_attribute_t attr;
        crfsuite_attribute_set(&attr, aid, poids[k]);
        crfsuite_item_append_attribute(item, &attr);
      }
      p += std::strlen(p) + 1;
    }
    debut = fin;
  }

  e->tagger->set(e->tagger, &inst);
  floatval_t score = 0;
  e->tagger->viterbi(e->tagger, sortie, &score);
  crfsuite_instance_finish(&inst);
}
