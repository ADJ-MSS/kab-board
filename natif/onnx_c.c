// Pont C vers ONNX Runtime 1.20.1, pour la dictée (pont_onnx.py).
// En C et non en C++ : un runtime C++ embarqué intercepterait les exceptions
// internes d'ONNX Runtime.

#define _POSIX_C_SOURCE 200809L   /* strdup */
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#include "onnxruntime_c_api.h"

#define EXPORTE __attribute__((visibility("default")))

static const OrtApi *api(void) {
  static const OrtApi *a = NULL;
  if (!a) a = OrtGetApiBase()->GetApi(ORT_API_VERSION);
  return a;
}

static int ok(OrtStatus *s) {
  if (!s) return 1;
  api()->ReleaseStatus(s);
  return 0;
}

typedef struct {
  OrtEnv *env;
  OrtSession *session;
  char *entree;
  char *sortie;
} Session;

static void liberer(Session *s) {
  const OrtApi *a = api();
  if (s->session) a->ReleaseSession(s->session);
  if (s->env) a->ReleaseEnv(s->env);
  free(s->entree);
  free(s->sortie);
  free(s);
}

static char *nom(OrtSession *session, int entree) {
  const OrtApi *a = api();
  OrtAllocator *al = NULL;
  char *n = NULL, *copie;
  OrtStatus *st;
  if (!ok(a->GetAllocatorWithDefaultOptions(&al))) return NULL;
  st = entree ? a->SessionGetInputName(session, 0, al, &n)
              : a->SessionGetOutputName(session, 0, al, &n);
  if (!ok(st) || !n) return NULL;
  copie = strdup(n);
  a->AllocatorFree(al, n);
  return copie;
}

EXPORTE void *kab_onnx_ouvrir(const char *chemin) {
  const OrtApi *a = api();
  Session *s;
  OrtSessionOptions *options = NULL;
  int bon;
  if (!a || !chemin) return NULL;
  s = (Session *)calloc(1, sizeof(Session));
  if (!s) return NULL;
  bon = ok(a->CreateEnv(ORT_LOGGING_LEVEL_ERROR, "kab-board", &s->env)) &&
             ok(a->CreateSessionOptions(&options)) &&
             ok(a->SetSessionGraphOptimizationLevel(options, ORT_ENABLE_ALL)) &&
             ok(a->CreateSession(s->env, chemin, options, &s->session));
  if (options) a->ReleaseSessionOptions(options);
  if (bon) {
    s->entree = nom(s->session, 1);
    s->sortie = nom(s->session, 0);
  }
  if (!bon || !s->entree || !s->sortie) {
    liberer(s);
    return NULL;
  }
  return s;
}

EXPORTE void kab_onnx_fermer(void *h) {
  if (h) liberer((Session *)h);
}

// Les logits [trames × classes], à rendre par kab_onnx_liberer.
EXPORTE int kab_onnx_executer(void *h, const float *audio, int64_t n,
                              float **logits, int64_t *trames, int64_t *classes) {
  Session *s = (Session *)h;
  const OrtApi *a = api();
  OrtMemoryInfo *memoire = NULL;
  OrtValue *entree = NULL, *sortie = NULL;
  const OrtValue *entrees_valeurs[1];
  OrtTensorTypeAndShapeInfo *info = NULL;
  int resultat = -1;
  int64_t forme[2];
  const char *entrees[1], *sorties[1];
  size_t nd = 0;
  int64_t dims[4] = {0, 0, 0, 0};
  float *donnees = NULL;

  if (!h || !audio || n <= 0 || !logits || !trames || !classes) return -1;
  *logits = NULL;
  forme[0] = 1;
  forme[1] = n;
  entrees[0] = s->entree;
  sorties[0] = s->sortie;

  if (ok(a->CreateCpuMemoryInfo(OrtArenaAllocator, OrtMemTypeDefault, &memoire)) &&
      ok(a->CreateTensorWithDataAsOrtValue(memoire, (void *)audio,
                                           (size_t)n * sizeof(float), forme, 2,
                                           ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT, &entree)) &&
      ((entrees_valeurs[0] = entree), 1) &&
      ok(a->Run(s->session, NULL, entrees, entrees_valeurs, 1, sorties, 1, &sortie)) &&
      ok(a->GetTensorTypeAndShape(sortie, &info)) &&
      ok(a->GetDimensionsCount(info, &nd)) && nd >= 2 && nd <= 4 &&
      ok(a->GetDimensions(info, dims, nd)) &&
      ok(a->GetTensorMutableData(sortie, (void **)&donnees))) {
    const int64_t t = dims[nd - 2], v = dims[nd - 1];
    if (t > 0 && v > 0) {
      const size_t octets = (size_t)(t * v) * sizeof(float);
      *logits = (float *)malloc(octets);
      if (*logits) {
        memcpy(*logits, donnees, octets);
        *trames = t;
        *classes = v;
        resultat = 0;
      }
    }
  }

  if (info) a->ReleaseTensorTypeAndShapeInfo(info);
  if (sortie) a->ReleaseValue(sortie);
  if (entree) a->ReleaseValue(entree);
  if (memoire) a->ReleaseMemoryInfo(memoire);
  return resultat;
}

EXPORTE void kab_onnx_liberer(float *logits) {
  free(logits);
}
