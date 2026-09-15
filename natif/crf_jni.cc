// Pont JNI vers CRFsuite, en étiquetage seul.

#include <jni.h>
#include <string>
#include <vector>
#include <cstring>

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

inline Etiqueteur *de(jlong h) { return reinterpret_cast<Etiqueteur *>(h); }

std::string utf8(JNIEnv *env, jstring s) {
  if (!s) return std::string();
  const char *p = env->GetStringUTFChars(s, nullptr);
  std::string out(p ? p : "");
  if (p) env->ReleaseStringUTFChars(s, p);
  return out;
}

}  // namespace

extern "C" {

JNIEXPORT jlong JNICALL
Java_taqbaylit_moteur_Etiqueteur_ouvrir(JNIEnv *env, jclass, jstring chemin) {
  std::string p = utf8(env, chemin);
  Etiqueteur *e = new Etiqueteur();
  if (crfsuite_create_instance_from_file(p.c_str(), (void **)&e->modele) != 0) {
    delete e;
    jclass ex = env->FindClass("java/lang/RuntimeException");
    if (ex) env->ThrowNew(ex, "CRFsuite : modele illisible");
    return 0;
  }
  // Les trois accesseurs peuvent echouer sur un modele tronque : sans ce
  // controle ils laissent des pointeurs nuls que etiqueter() dereference.
  const int ok = e->modele->get_tagger(e->modele, &e->tagger) == 0 &&
                 e->modele->get_attrs(e->modele, &e->attrs) == 0 &&
                 e->modele->get_labels(e->modele, &e->labels) == 0;
  if (!ok || !e->tagger || !e->attrs || !e->labels) {
    if (e->labels) e->labels->release(e->labels);
    if (e->attrs) e->attrs->release(e->attrs);
    if (e->tagger) e->tagger->release(e->tagger);
    if (e->modele) e->modele->release(e->modele);
    delete e;
    jclass ex = env->FindClass("java/lang/RuntimeException");
    if (ex) env->ThrowNew(ex, "CRFsuite : modele incomplet");
    return 0;
  }
  return reinterpret_cast<jlong>(e);
}

JNIEXPORT void JNICALL
Java_taqbaylit_moteur_Etiqueteur_fermer(JNIEnv *, jclass, jlong h) {
  if (!h) return;
  Etiqueteur *e = de(h);
  if (e->labels) e->labels->release(e->labels);
  if (e->attrs) e->attrs->release(e->attrs);
  if (e->tagger) e->tagger->release(e->tagger);
  if (e->modele) e->modele->release(e->modele);
  delete e;
}

JNIEXPORT jint JNICALL
Java_taqbaylit_moteur_Etiqueteur_nbEtiquettes(JNIEnv *, jclass, jlong h) {
  Etiqueteur *e = de(h);
  return e->labels->num(e->labels);
}

/** Étiquette une phrase. */
JNIEXPORT jobjectArray JNICALL
Java_taqbaylit_moteur_Etiqueteur_etiqueter(JNIEnv *env, jclass, jlong h,
                                           jobjectArray plat, jdoubleArray poids,
                                           jintArray bornes) {
  Etiqueteur *e = de(h);
  const jsize nMots = env->GetArrayLength(bornes);
  jclass cs = env->FindClass("java/lang/String");
  // Phrase vide : rien a etiqueter, et crfsuite n'a pas a etre sollicite.
  if (nMots <= 0) return env->NewObjectArray(0, cs, nullptr);

  jint *fins = env->GetIntArrayElements(bornes, nullptr);
  jdouble *w = env->GetDoubleArrayElements(poids, nullptr);

  crfsuite_instance_t inst;
  crfsuite_instance_init_n(&inst, nMots);

  jsize debut = 0;
  for (jsize i = 0; i < nMots; ++i) {
    const jsize fin = fins[i];
    crfsuite_item_t *item = &inst.items[i];
    crfsuite_item_init(item);
    for (jsize k = debut; k < fin; ++k) {
      jstring js = (jstring)env->GetObjectArrayElement(plat, k);
      std::string nom = utf8(env, js);
      env->DeleteLocalRef(js);
      // Un attribut inconnu du modèle est ignoré, comme le fait pycrfsuite.
      int aid = e->attrs->to_id(e->attrs, nom.c_str());
      if (aid >= 0) {
        crfsuite_attribute_t attr;
        crfsuite_attribute_set(&attr, aid, w[k]);
        crfsuite_item_append_attribute(item, &attr);
      }
    }
    debut = fin;
  }

  e->tagger->set(e->tagger, &inst);
  int *sortie = new int[nMots];
  floatval_t score = 0;
  e->tagger->viterbi(e->tagger, sortie, &score);

  jobjectArray res = env->NewObjectArray(nMots, cs, nullptr);
  for (jsize i = 0; i < nMots; ++i) {
    const char *nom = nullptr;
    e->labels->to_string(e->labels, sortie[i], &nom);
    jstring js = env->NewStringUTF(nom ? nom : "");
    env->SetObjectArrayElement(res, i, js);
    // La table des references locales n'est garantie que pour seize entrees.
    env->DeleteLocalRef(js);
    if (nom) e->labels->free(e->labels, nom);
  }

  delete[] sortie;
  crfsuite_instance_finish(&inst);
  env->ReleaseIntArrayElements(bornes, fins, JNI_ABORT);
  env->ReleaseDoubleArrayElements(poids, w, JNI_ABORT);
  return res;
}

}  // extern "C"
