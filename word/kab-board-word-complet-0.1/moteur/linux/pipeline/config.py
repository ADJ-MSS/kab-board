"""Chemins, seuils et poids."""
from pathlib import Path

V2_DIR = Path(__file__).resolve().parent
ROOT   = V2_DIR.parents[1]        # racine du dépôt
BASE   = ROOT / "data"            # ressources partagées avec la v1

# Fichiers de données (partagés avec la v1)
LEXICON_FILES = ["kabyle_lexicon_v4.csv", "kabyle_lexicon_v5.csv"]
KENLM_BIN     = BASE / "kabyle_3gram.binary"
AMYAG_FORMES  = BASE / "amyag_formes.txt"
POS_MODEL     = BASE / "kab-POS-tagl.joblib"

# mot <TAB> catégorie. Un mot qui figure dans plusieurs catégories garde la
# première rencontrée, d'où l'ordre du fichier.
LEXCAT_FILE = BASE / "lexique_categories.txt"
LEXCAT_CONTENT_CATS = {"masc", "fem", "fem_pl", "adj_masc", "adj_fem", "adverb", "ambig"}

# WordNet kabyle : racines → mots → concepts WOLF
WORDNET_JSON = BASE / "wordnet" / "dictionnaire_sémantique_racinale_kabyle_V1.json"

# Fiabilité : la v1 se contentait de freq >= 50, ici on compte les sources
# indépendantes qui attestent le mot (colonne `sources`).
MIN_SOURCES_FIABLE = 3      # attesté dans ≥ 3 sources indépendantes
FREQ_FIABLE        = 300    # ou très fréquent malgré peu de sources
FREQ_MIN_CANDIDAT  = 10     # fréquence minimale pour entrer dans le vivier

# Génération de candidats
MAX_DIST_BRUTE   = 2        # distance DL brute maximale (comme v1)
LIMIT_EXTRACT    = 60       # candidats rapidfuzz avant re-scorage pondéré
MAX_CAND_BEAM    = 6        # candidats par token entrant dans le beam

def seuil_dist_ponderee(longueur: int) -> float:
    if longueur <= 3:  return 1.0
    if longueur <= 5:  return 1.8
    return 2.4

# Abréviations usuelles développées par le décodeur (le LM tranche)
ABREVIATIONS = {"ɣ": ("ɣer", "ɣef")}

# Poids du score local d'un candidat
W_DIST       = 2.0          # × distance pondérée kabyle (pénalité)
W_FREQ       = 0.6          # × log10(fréquence) normalisé [0..1]
W_NSRC       = 0.4          # × nb de sources normalisé [0..1]
W_SDX        = 0.35         # même code sonore : un bonus, plus une porte
W_POS        = 0.5          # pénalité si la source contredit le tag POS
PEN_DOUTEUX  = 0.7          # pénalité candidat hors Amyag/Lexique et peu attesté

# Plancher pour les formes de dictionnaire, souvent à fréquence 0
FREQ_PLANCHER_DICO = 50
NSRC_PLANCHER_DICO = 4

# Variante de dictionnaire : même code sonore et très proche (lhif -> lḥif)
BONUS_VARIANTE  = 1.2
VAR_MAX_DIST_P  = 0.7

# Bonus « garder tel quel », par niveau de confiance du token
BONUS_KEEP_DICO   = 2.2     # attesté dans Amyag ou Lexique
BONUS_KEEP_SEMI   = 1.2     # multi-sources ou très fréquent dans le lexique
BONUS_KEEP_VALIDE = 0.1     # validé seulement par affixe productif
BONUS_KEEP_OOV    = -1.4    # inconnu : là on veut vraiment corriger

# Décodage global
W_LM  = 0.5                 # poids du log10 KenLM dans le beam
BEAM  = 8                   # largeur du faisceau

# Sémantique : bonus quand le candidat partage un concept avec la phrase.
# Le KenLM ne voit que 3 mots, ça va plus loin.
W_SEM = 0.6

# Annexion : on annule la réécriture si elle fait chuter le score KenLM de
# plus que ce seuil. Le LM n'est qu'un garde-fou, la règle prime.
LM_REJET_CHAKER = 2.5
