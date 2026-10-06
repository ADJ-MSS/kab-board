# kab-board sous Linux

Première version, livrée avec la 0.2. Le même correcteur que sur Android, sur
ordinateur. Trois objets, qui partagent le moteur, la table des graphies et les
ressources de l'application.

Le plus simple est le paquet `.deb` de la [page des versions](https://github.com/ADJ-MSS/kab-board/releases),
qui contient déjà toutes les ressources. Ce qui suit sert à travailler depuis
les sources.

```
kab_appli.py        l'application : on allume, on règle, on ferme
kab_ibus.py         la méthode de saisie : elle écrit dans toutes les applications
clavier_flottant.py le clavier à l'écran, posé au-dessus des autres fenêtres
kab_bureau.py       une fenêtre pour écrire et relire un texte
dictee.py           la dictée, avec le modèle vocal du téléphone
graphie_bv.py       la couche des graphies b et v, commune au correcteur
```

## Installer

```sh
./installer-application.sh      # une entrée « Kab-board » dans le menu
```

Puis ouvrir **Kab-board** et allumer le clavier. Rien d'autre : pas de `sudo`,
aucun fichier hors du dossier personnel.

## Ce qui est repris du téléphone

La disposition AZERTY et ses appuis longs, les six propositions avec la
correction en contexte en tête, les trois natures (vert pour la correction,
bleu pour un candidat, ocre pour une prédiction), la prédiction du mot suivant,
Asegzawal, fr → kab, Relire, le mot du jour, « écrire comme on parle », la
dictée qui n'est jamais corrigée d'office, le réglage b ou v qui vaut partout,
et le silence dans les champs de mot de passe.

**La table des graphies est celle de l'application Android**,
`app/src/main/assets/graphie/table_bv.tsv` : une seule source pour les deux
plateformes, 13 142 formes de base. Les formes fléchies y sont ramenées par les
mêmes règles qu'en Kotlin : tirets, état d'annexion, annexion en `we-`, pluriel.

## Ce qui ne se transpose pas

Un clavier de bureau n'est pas un clavier tactile : pas de retour haptique, pas
de glissé sur l'espace, pas de panneau emoji. Le soulignement dans les autres
applications n'existe pas non plus, aucune application de bureau ne laissant une
autre lire ni annoter son texte, alors qu'Android le permet par l'InputConnection.
D'où **Relire sur le presse-papiers** plutôt que sur le champ courant.

## Vérifier

```sh
python3 test_graphie_bv.py      # 58 vérifications sur les graphies
python3 test_completion.py      # 12 vérifications sur la complétion
python3 ibus/test_saisie.py     # 36 vérifications sur la saisie
```

## Les dépendances

Le paquet `.deb` (amd64) ne demande que ce que fournit la distribution : Python
3.10 ou plus récent, GTK 4 et GTK 3 (`python3-gi`), IBus, NumPy et `arecord`.
Vérifié sur des systèmes vierges, sous un compte ordinaire : Ubuntu 22.04, 24.04
et 25.10, Debian 12 et 13.

Ce qu'aucune distribution ne fournit est livré avec lui, et se charge sans rien
compiler, quelle que soit la version de Python :

| Besoin | Module Python habituel | Dans le paquet |
|---|---|---|
| modèle de langue | `kenlm` | `natif/pont/libkab_lm.so`, par `pont_kenlm.py` |
| étiqueteur | `sklearn-crfsuite`, `joblib` | `natif/pont/libkab_crf.so` et `pos_kab.crfsuite`, par `pont_crf.py` |
| dictée | `onnxruntime` | `natif/pont/libkab_onnx.so` et ONNX Runtime 1.20.1, par `pont_onnx.py` |
| candidats | `rapidfuzz` | les roues officielles 3.14.5, une par Python de 3.10 à 3.14 (`vendor/`) |

Quand le module habituel est installé, il est préféré, sauf `rapidfuzz` : la
version livrée passe devant celle du système, pour que le correcteur réponde
pareil partout. Les ponts donnent les mêmes résultats que les modules : mêmes
scores KenLM sur 3 002 phrases, mêmes étiquettes sur 115 786 mots, mêmes
décisions de dictée, et les mêmes corrections sur 500 phrases.

Les ponts se construisent par `natif/construire-pont.sh linux`, avec Zig, qui
vise glibc 2.28 : ils ne dépendent ni de la glibc ni de la libstdc++ de la
machine qui les construit. `paquet/construire-complet.sh` les reconstruit à
chaque paquet.
