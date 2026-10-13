# Le moteur, repris de kab-board

Ce dossier est le correcteur de [kab-board](https://github.com/ADJ-MSS/kab-board),
**copié tel quel** depuis sa version Linux : même pipeline, même table des
graphies, même complétion, même saisie. Le commit d'origine est dans
`AMONT-COMMIT`. Rien n'y est réécrit pour Windows : c'est le code de
`windows/` qui l'enrobe.

| Ici | Dans kab-board |
|---|---|
| `pipeline/` | `linux/pipeline/` (sans `eval_v2.py`) |
| `chemins.py`, `graphie_bv.py`, `correcteur_bv.py`, `completion.py` | `linux/` |
| `saisie.py`, `test_saisie.py` | `linux/ibus/` |
| `ressources_kab.py`, `dictee.py` | `linux/bureau/` |
| `data/lexique_categories.txt` | `linux/data/` |
| `graphie/table_bv.tsv` | `app/src/main/assets/graphie/` : la même table qu'Android et Linux |

## Les deux fichiers adaptés

- `pipeline/ressources.py` : la version Linux, plus le **cache** du lexique et du
  vivier de la version Word (`word/kab-board-word-complet-0.1/moteur/linux/pipeline/ressources.py`),
  qui fait passer le chargement d'une minute à une dizaine de secondes. Le
  dossier du cache se règle par `KAB_BOARD_CACHE` : `cache-clavier/` à côté
  des réglages, jamais le `cache/` de Word.
- `test_graphie_bv.py` : le chemin de la table, `graphie/table_bv.tsv`.

## Reprendre une nouvelle version

```
python outils/reprendre_amont.py ../kab-board
```

Le script recopie ce qui a changé, et signale les deux fichiers adaptés quand
leur original a bougé : ceux-là se reportent à la main.

## Vérifier

```
python moteur/test_graphie_bv.py    # 58 vérifications
python moteur/test_completion.py    # 17 vérifications
python moteur/test_saisie.py        # 36 vérifications
```
