// Pont C vers CRFsuite, en étiquetage seul, pour ctypes (pont_crf.py).

#include <cstring>
#include <string>

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

#define EXPORTE extern "C" __attribute__((visibility("default")))

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
  return h ? de(h)->labels->num(de(h)->labels) : 0;
}

EXPORTE int kab_crf_etiquette(void *h, int i, char *tampon, int taille) {
  if (!h || !tampon || taille <= 0) return -1;
  const char *nom = nullptr;
  if (de(h)->labels->to_string(de(h)->labels, i, &nom) != 0 || !nom) return -1;
  const int n = static_cast<int>(std::strlen(nom));
  std::strncpy(tampon, nom, taille - 1);
  tampon[taille - 1] = '\0';
  de(h)->labels->free(de(h)->labels, nom);
  return n;
}

// bornes[i] : fin des attributs du mot i dans noms et poids. Les étiquettes
// sortent séparées par des sauts de ligne ; -1 si le tampon est trop court.
EXPORTE int kab_crf_etiqueter(void *h, const char **noms, const double *poids,
                              const int *bornes, int n_mots,
                              char *tampon, int taille) {
  if (!h || !tampon || taille <= 0) return -1;
  tampon[0] = '\0';
  if (n_mots <= 0) return 0;
  Etiqueteur *e = de(h);

  crfsuite_instance_t inst;
  crfsuite_instance_init_n(&inst, n_mots);
  int debut = 0;
  for (int i = 0; i < n_mots; ++i) {
    crfsuite_item_t *item = &inst.items[i];
    crfsuite_item_init(item);
    for (int k = debut; k < bornes[i]; ++k) {
      const int aid = e->attrs->to_id(e->attrs, noms[k]);
      if (aid >= 0) {
        crfsuite_attribute_t attr;
        crfsuite_attribute_set(&attr, aid, poids[k]);
        crfsuite_item_append_attribute(item, &attr);
      }
    }
    debut = bornes[i];
  }

  e->tagger->set(e->tagger, &inst);
  int *sortie = new int[n_mots];
  floatval_t score = 0;
  e->tagger->viterbi(e->tagger, sortie, &score);

  std::string texte;
  for (int i = 0; i < n_mots; ++i) {
    const char *nom = nullptr;
    e->labels->to_string(e->labels, sortie[i], &nom);
    if (i) texte.push_back('\n');
    texte += nom ? nom : "";
    if (nom) e->labels->free(e->labels, nom);
  }
  delete[] sortie;
  crfsuite_instance_finish(&inst);

  if (static_cast<int>(texte.size()) >= taille) return -1;
  std::memcpy(tampon, texte.c_str(), texte.size() + 1);
  return static_cast<int>(texte.size());
}
