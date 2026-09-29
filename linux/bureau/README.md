# Kab-board bureau, sous Linux

Le correcteur kabyle en application de bureau. Même moteur que le téléphone,
mêmes six propositions, même réglage b ou v.

```sh
python3 bureau/kab_bureau.py
```

Il faut GTK 4 et PyGObject (`python3-gi`), plus les dépendances du pipeline
(`kenlm`, `sklearn-crfsuite`, `joblib`, `rapidfuzz`), déjà installées sur cette
machine.

## Ce que ça fait

Vous écrivez dans la fenêtre. Sous le texte, les propositions du mot en cours :
la correction en contexte d'abord, puis les cinq candidats du mot isolé. Un clic
remplace le mot. Deux boutons en haut, **Écrire avec b** et **Écrire avec v**,
règlent la graphie : les propositions la suivent, et le texte déjà écrit est
réécrit. **Relire** parcourt le texte et liste ce qui mérite un regard.

Mesures sur cette machine : moteur chargé en **9 s**, correction d'une phrase
courte entre **2 et 223 ms**.

```
ruhagh ghar tamettut          -> ruḥeɣ ɣer tmeṭṭut
yebgha ad iruh ghar wabrid    -> yebɣa ...   (réglage b)
                              -> yevɣa ...   (réglage v)
baba yusa-d                   -> vava yusa-d (réglage v)
```

## Ce que ça ne fait pas, et pourquoi

Ce n'est pas un clavier. Sur un ordinateur on tape sur un clavier physique : il
n'y a ni touches à l'écran, ni appui long, ni glissé sur l'espace, ni retour
haptique. Une **méthode de saisie** (IBus ou Fcitx5) donnerait les propositions
dans n'importe quelle application, sous le curseur ; c'est l'étape suivante, et
elle réutilise tout ce qui est ici.

Pas de dictée non plus pour l'instant : le modèle vocal tourne sur ONNX Runtime,
disponible sur bureau, mais il n'est pas branché.

## Les chemins des ressources

Le pipeline attend ses données dans un dossier `data/` ; sur cette machine elles
sont à plat dans le dossier du correcteur. L'application pose donc les chemins
elle-même, au démarrage, **sans modifier le pipeline** (`preparer_chemins`).

Deux ressources manquent localement et l'application s'en passe :

- le **graphe sémantique** (`dictionnaire_sémantique_racinale_kabyle_V1.json`),
  absent du dossier de travail : la cohérence sémantique est désactivée, et les
  gloses ne sont pas affichées ;
- le fichier des **catégories**, qui n'existait pas non plus : il est reconstruit
  dans `data/lexique_categories.txt` à partir des listes DiKab, 5 528 mots sur
  16 catégories. Sans lui, le correcteur rendait *tmettut* au lieu de
  *tmeṭṭut* : les catégories comptent.
