// Pont JNI vers KenLM, en lecture seule.

#include <jni.h>
#include <string>
#include <vector>
#include <new>
#include <cstring>
#include <algorithm>

#include "lm/model.hh"
#include "lm/state.hh"

namespace {

struct Contexte {
  lm::base::Model *modele;
  std::size_t taille_etat;
};

inline std::size_t taille_etat_de(jlong h) {
  return reinterpret_cast<Contexte *>(h)->taille_etat;
}

inline lm::base::Model *modele_de(jlong h) {
  return reinterpret_cast<Contexte *>(h)->modele;
}

inline void *etat_de(jlong h) { return reinterpret_cast<void *>(h); }

std::string vers_utf8(JNIEnv *env, jstring s) {
  if (s == nullptr) return std::string();
  const char *p = env->GetStringUTFChars(s, nullptr);
  std::string out(p ? p : "");
  if (p) env->ReleaseStringUTFChars(s, p);
  return out;
}

}  // namespace

extern "C" {

JNIEXPORT jlong JNICALL
Java_taqbaylit_moteur_ModeleLangue_ouvrir(JNIEnv *env, jclass, jstring chemin) {
  std::string p = vers_utf8(env, chemin);
  try {
    lm::ngram::Config cfg;
    cfg.load_method = util::LAZY;          // mmap, pas de copie en RAM
    Contexte *c = new Contexte();
    c->modele = lm::ngram::LoadVirtual(p.c_str(), cfg);
    c->taille_etat = c->modele->StateSize();
    return reinterpret_cast<jlong>(c);
  } catch (const std::exception &e) {
    jclass ex = env->FindClass("java/lang/RuntimeException");
    if (ex) env->ThrowNew(ex, e.what());
    return 0;
  }
}

JNIEXPORT void JNICALL
Java_taqbaylit_moteur_ModeleLangue_fermer(JNIEnv *, jclass, jlong h) {
  if (!h) return;
  Contexte *c = reinterpret_cast<Contexte *>(h);
  delete c->modele;
  delete c;
}

JNIEXPORT jint JNICALL
Java_taqbaylit_moteur_ModeleLangue_ordre(JNIEnv *, jclass, jlong h) {
  return static_cast<jint>(modele_de(h)->Order());
}

JNIEXPORT jlong JNICALL
Java_taqbaylit_moteur_ModeleLangue_etatNouveau(JNIEnv *, jclass, jlong h) {
  // Un tampon brut de la taille que le modèle demande, et non un State typé : celui du format TRIE
  // n'a pas la même disposition que celui de PROBING.
  if (!h) return 0;
  return reinterpret_cast<jlong>(new unsigned char[taille_etat_de(h)]());
}

JNIEXPORT void JNICALL
Java_taqbaylit_moteur_ModeleLangue_etatLiberer(JNIEnv *, jclass, jlong e) {
  delete[] reinterpret_cast<unsigned char *>(e);
}

JNIEXPORT void JNICALL
Java_taqbaylit_moteur_ModeleLangue_debutPhrase(JNIEnv *, jclass, jlong h, jlong e) {
  modele_de(h)->BeginSentenceWrite(etat_de(e));
}

JNIEXPORT void JNICALL
Java_taqbaylit_moteur_ModeleLangue_contexteVide(JNIEnv *, jclass, jlong h, jlong e) {
  modele_de(h)->NullContextWrite(etat_de(e));
}

JNIEXPORT void JNICALL
Java_taqbaylit_moteur_ModeleLangue_etatCopier(JNIEnv *, jclass, jlong h, jlong src, jlong dst) {
  if (!h) return;
  std::memcpy(etat_de(dst), etat_de(src), taille_etat_de(h));
}

JNIEXPORT jboolean JNICALL
Java_taqbaylit_moteur_ModeleLangue_etatEgal(JNIEnv *, jclass, jlong h, jlong a, jlong b) {
  if (!h) return JNI_FALSE;
  // Comparaison octet à octet, faute d'égalité structurelle dans l'interface polymorphe.
  return std::memcmp(etat_de(a), etat_de(b), taille_etat_de(h)) == 0 ? JNI_TRUE : JNI_FALSE;
}

// log10 P(mot | etat_entree), et écrit l'état résultant.
JNIEXPORT jfloat JNICALL
Java_taqbaylit_moteur_ModeleLangue_baseScore(JNIEnv *env, jclass, jlong h,
                                             jlong entree, jstring mot, jlong sortie) {
  lm::base::Model *m = modele_de(h);
  std::string w = vers_utf8(env, mot);
  const lm::WordIndex idx = m->BaseVocabulary().Index(w);
  return m->BaseScore(etat_de(entree), idx, etat_de(sortie));
}

// Score d'une phrase entière, équivalent de Model.score(s, bos, eos).
JNIEXPORT jfloat JNICALL
Java_taqbaylit_moteur_ModeleLangue_scorePhrase(JNIEnv *env, jclass, jlong h,
                                               jstring phrase, jboolean bos, jboolean eos) {
  lm::base::Model *m = modele_de(h);
  std::string s = vers_utf8(env, phrase);

  std::vector<unsigned char> a(m->StateSize()), b(m->StateSize());
  void *etat = a.data(), *suivant = b.data();
  if (bos) m->BeginSentenceWrite(etat); else m->NullContextWrite(etat);

  float total = 0.0f;
  size_t i = 0;
  while (i <= s.size()) {
    size_t j = s.find(' ', i);
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

}  // extern "C"
