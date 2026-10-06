"""Chargement du lexique, des dictionnaires et des modèles."""
import csv
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set

# rapidfuzz livré avec le paquet, prioritaire : une autre version ne retient pas
# les mêmes candidats à égalité.
_VENDU = (Path(__file__).resolve().parent.parent.parent / "vendor"
          / f"cp{sys.version_info.major}{sys.version_info.minor}")
if _VENDU.is_dir() and str(_VENDU) not in sys.path:
    sys.path.insert(0, str(_VENDU))

import config
from normalisation import normalize
from phonologie import soundex_kabyle
from semantique import WordNetKabyle

try:
    from rapidfuzz import process, distance as rf_dist
    RAPIDFUZZ_OK = True
except ImportError:
    RAPIDFUZZ_OK = False

try:
    import kenlm as _kenlm
    KENLM_OK = True
except ImportError:
    # Pas de module compilé : le pont ctypes vers la bibliothèque natif/pont
    # rend le même service, et n'exige aucun compilateur sur la machine.
    try:
        import pont_kenlm as _kenlm
        KENLM_OK = True
    except Exception:
        KENLM_OK = False

try:
    from joblib import load as _joblib_load
    JOBLIB_OK = True
except ImportError:
    JOBLIB_OK = False


# Tags POS kabyle (KabyleNLP / Belkacem 2019)
POS_VERB_TAGS = {
    "VAI", "VP", "VAF", "VPN", "VAIT", "VPPP",
    "VS", "VII", "VPA", "VPPN", "VPAIP", "VPAIN",
}
POS_NOUN_TAGS = {"NMC", "NMP", "NCM", "NC", "ADJ"}


def _pos_features(sentence: list, index: int) -> dict:
    w = sentence[index]
    return {
        'word':             w,
        'is_one_letter':    len(w) == 1,
        'is_first':         index == 0,
        'is_last':          index == len(sentence) - 1,
        'is_capitalized':   w[0].upper() == w[0],
        'is_all_caps':      w.upper() == w,
        'is_all_lower':     w.lower() == w,
        'prefix-1':         w[0],
        'prefix-2':         w[:2],
        'prefix-3':         w[:3],
        'prefix-4':         w[:4],
        'prefix-5':         w[:5],
        'suffix-1':         w[-1],
        'suffix-2':         w[-2:],
        'suffix-3':         w[-3:],
        'suffix-4':         w[-4:],
        'prev_word':        '' if index == 0 else sentence[index - 1],
        'next_word':        '' if index == len(sentence) - 1 else sentence[index + 1],
        'is_numeric':       w.isdigit(),
        'capitals_inside':  w[1:].lower() != w[1:],
    }


class Ressources:
    """Toutes les données chargées + index, partagées par les générateurs."""

    PREF = ["y", "t", "n", "tt", "d", "i", "a", "u", "m", "ms", "s"]
    SUFF = ["en", "ent", "iɣ", "eɣ", "aɣ", "iḍ", "id", "an", "in"]

    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.freq:  Dict[str, int] = {}
        self.nsrc:  Dict[str, int] = {}
        self.amyag: Set[str] = set()
        self.lexcat: Dict[str, str] = {}          # mot → catégorie
        self.lexcat_content: Set[str] = set()
        self.pool:  List[str] = []               # vivier de candidats (union)
        self.pool_set: Set[str] = set()
        self.sdx_index: Dict[str, List[str]] = {}
        self.kenlm = None
        self.pos_model = None
        self.wn: Optional[WordNetKabyle] = None
        self._fiable_cache: Dict[str, bool] = {}

    def _log(self, msg: str):
        if self.verbose:
            print(msg)

    def charger(self):
        self._charger_lexique()
        self._charger_amyag()
        self._charger_lexcat()
        self.wn = WordNetKabyle().charger(config.WORDNET_JSON, verbose=self.verbose)
        self._construire_pool()
        self._charger_kenlm()
        self._charger_pos()
        return self

    def _charger_lexique(self):
        path = None
        for fname in config.LEXICON_FILES:
            p = config.BASE / fname
            if p.exists():
                path = p
                break
        if path is None:
            raise FileNotFoundError("kabyle_lexicon_v4.csv introuvable !")
        self._log(f"  Chargement {path.name}…")
        with open(path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                mot = row.get("mot", "")
                if not isinstance(mot, str) or not mot:
                    continue
                try:
                    fq = int(row["frequence"])
                except (KeyError, ValueError):
                    continue
                self.freq[mot] = fq
                s = row.get("sources") or ""
                self.nsrc[mot] = (s.count("|") + 1) if s else 0
        self._log(f"  Lexique : {len(self.freq):,} entrées (avec nb de sources)")

    def _charger_amyag(self):
        path = config.AMYAG_FORMES
        if not path.exists():
            self._log("  amyag_formes.txt absent")
            return
        with open(path, encoding="utf-8") as f:
            for line in f:
                mot = line.strip()
                if len(mot) >= 2:
                    self.amyag.add(normalize(mot))
        self._log(f"  Amyag : {len(self.amyag):,} formes conjuguées")

    def _charger_lexcat(self):
        if config.LEXCAT_FILE.exists():
            with open(config.LEXCAT_FILE, encoding="utf-8") as f:
                for line in f:
                    brut, _, cat = line.rstrip("\n").partition("\t")
                    mot = normalize(brut.strip())
                    if len(mot) < 2 or " " in mot:
                        continue
                    if mot not in self.lexcat:
                        self.lexcat[mot] = cat.strip()
        self.lexcat_content = {w for w, c in self.lexcat.items()
                              if c in config.LEXCAT_CONTENT_CATS}
        self._log(f"  Lexique : {len(self.lexcat):,} mots "
                  f"({len(self.lexcat_content):,} content)")

    def _construire_pool(self):
        """Vivier de candidats, indexé par code sonore."""
        pool = {m for m, f in self.freq.items()
                if f >= config.FREQ_MIN_CANDIDAT and len(m) >= 2}
        pool |= self.amyag
        pool |= self.lexcat_content
        if self.wn is not None:
            pool |= self.wn.formes
        self.pool_set = pool
        self.pool = sorted(pool)
        for w in self.pool:
            self.sdx_index.setdefault(soundex_kabyle(w), []).append(w)
        self._log(f"  Vivier candidats : {len(self.pool):,} formes "
                  f"({len(self.sdx_index):,} buckets soundex)")

    def _charger_kenlm(self):
        if not KENLM_OK:
            self._log("  module kenlm absent → décodage sans LM")
            return
        if not config.KENLM_BIN.exists():
            self._log("  kabyle_3gram.binary introuvable → décodage sans LM")
            return
        self.kenlm = _kenlm.Model(str(config.KENLM_BIN))
        self._log("  KenLM 3-gram chargé")

    def _charger_pos(self):
        if JOBLIB_OK and config.POS_MODEL.exists():
            try:
                self.pos_model = _joblib_load(str(config.POS_MODEL))
                self._log(f"  POS CRF chargé ({len(self.pos_model.classes_)} classes)")
                return
            except Exception:
                pass        # sklearn-crfsuite absent
        natif = getattr(config, "POS_CRFSUITE", config.POS_MODEL.with_name("pos_kab.crfsuite"))
        if natif.exists():
            try:
                import pont_crf
                self.pos_model = pont_crf.Etiqueteur(natif)
                self._log(f"  POS CRF chargé par le pont ({len(self.pos_model.classes_)} classes)")
                return
            except Exception:
                pass
        self._log("  tagger POS indisponible")

    def fiable(self, mot: str) -> bool:
        """Mot de confiance : Amyag, Lexique, multi-sources ou très fréquent."""
        r = self._fiable_cache.get(mot)
        if r is None:
            r = (mot in self.amyag or mot in self.lexcat
                 or self.nsrc.get(mot, 0) >= config.MIN_SOURCES_FIABLE
                 or self.freq.get(mot, 0) >= config.FREQ_FIABLE)
            self._fiable_cache[mot] = r
        return r

    def valide_par_affixe(self, mot: str) -> bool:
        """Préfixe/suffixe productif + racine fiable (morphologie légère)."""
        for p in self.PREF:
            if mot.startswith(p) and len(mot) - len(p) >= 2 \
                    and self.fiable(mot[len(p):]):
                return True
        for s in self.SUFF:
            if mot.endswith(s) and len(mot) - len(s) >= 2 \
                    and self.fiable(mot[:-len(s)]):
                return True
        return False

    def pos_tags(self, tokens: List[str]) -> Dict[int, str]:
        if self.pos_model is None or not tokens:
            return {}
        try:
            feats = [_pos_features(tokens, i) for i in range(len(tokens))]
            tags = self.pos_model.predict([feats])[0]
            return {i: t for i, t in enumerate(tags)}
        except Exception:
            return {}
