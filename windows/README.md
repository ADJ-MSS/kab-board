# Kab-board pour Windows

Le clavier kabyle de [kab-board](https://github.com/ADJ-MSS/kab-board), sur
Windows 10 et 11 : il écrit **dans toutes les applications** (navigateur,
messagerie, Word, Bloc-notes…). Correction en contexte, six propositions, complétion, prédiction du mot suivant, graphie b ou
v, clavier à l'écran, dictée en kabyle. **100 % hors ligne** : tout se calcule
sur l'ordinateur.

C'est le pendant de la version Linux : même correcteur, mêmes ressources, mêmes
règles. Rien n'est corrigé d'office ; l'espace écrit le mot tel qu'il a été
tapé.

## Ce qui est repris de Linux

| Linux | Windows | |
|---|---|---|
| `ibus/kab_ibus.py`, la méthode de saisie | `windows/kab_saisie.py` | un crochet clavier, qui voit chaque touche avant l'application |
| la liste d'IBus près du mot | `windows/barre.py` | une barre sous le curseur, qui ne prend jamais le focus |
| `bureau/clavier_flottant.py` | `windows/clavier_ecran.py` | mêmes touches, mêmes appuis longs, mêmes outils |
| `bureau/kab_appli.py` | `windows/kab_appli.py` | mêmes interrupteurs, plus « Démarrer avec Windows » |
| `bureau/kab_bureau.py` | `windows/kab_bureau.py` | écrire, relire mot à mot, copier |
| `arecord` | `windows/micro.py` | le micro par l'API waveIn, 16 kHz mono |
| la prise UNIX | `windows/liaison.py` | TCP sur 127.0.0.1, avec un jeton |
| | `windows/service.py` | le correcteur chargé une fois, à part |

Le correcteur lui-même (`moteur/`) est **celui de Linux, copié tel quel** : voir
[`moteur/AMONT.md`](moteur/AMONT.md). La table des graphies est la même que sur
Android et Linux.

## Comment le clavier écrit partout

Windows n'a pas d'IBus. Une application reçoit les lettres une à une : le mot
s'écrit donc au fil de la frappe, et une conversion (`gh` → ɣ) ou un choix
efface ce qui vient d'être tapé pour le remplacer, d'un seul envoi
(`SendInput`, en Unicode). Le mot en cours est toujours ce qui précède le
curseur. Toute la décision est dans [`windows/frappe.py`](windows/frappe.py),
sans rien de Windows, et se teste partout.

Le clavier se tait :

- dans un **mot de passe** (le style du champ, ou l'accessibilité de Windows) ;
- dans une application lancée **en administrateur**, qui refuse qu'on écrive à
  sa place ;
- après un clic, une flèche, un raccourci : il ne sait plus ce qui précède le
  curseur, et repart au mot suivant.

## Où vont les choses

`Kab-board.exe` lance le Python livré dans son dossier. Réglages, « mon
dictionnaire » et cache vont dans `%LOCALAPPDATA%\kab-board`, et « mon
dictionnaire » est celui de Kab-board pour Word.

## Construire

Sous Linux, ou dans la CI : les ponts natifs et le lanceur, avec mingw-w64.

```sh
sudo apt install gcc-mingw-w64-x86-64 g++-mingw-w64-x86-64
./natif/construire-dll.sh ../kab-board     # kab_lm.dll, kab_crf.dll
./lanceur/construire.sh                    # Kab-board.exe
```

Sous Windows, avec Python 3.12 (64 bits) et, pour l'installeur, Inno Setup 6 :

```
powershell -ExecutionPolicy Bypass -File paquet\construire.ps1 -Version 0.2
sortie\Kab-board\python\python.exe paquet\verifier.py sortie\Kab-board
```

Les ressources (lexique, modèle de langue, étiqueteur, graphe sémantique,
modèle vocal) viennent du paquet Linux de la
[version 0.3 de kab-board](https://github.com/ADJ-MSS/kab-board/releases/tag/v0.3),
vérifié par son empreinte SHA-256. Rien n'est versionné ici.

La CI (`.github/workflows/paquet.yml`) fait tout cela sur un Windows propre,
vérifie le paquet avec le vrai correcteur, puis le publie sur la page des
versions de ce dépôt.

## Vérifier

```sh
python moteur/test_graphie_bv.py           # 58 vérifications, comme kab-board
python moteur/test_completion.py           # 17
python moteur/test_saisie.py               # 36
python -m unittest discover -s windows/tests -v
```

Sous Linux, les tests de l'interface demandent un écran (`xvfb-run -a`) ; ceux
du crochet et du Bloc-notes ne tournent que sous Windows.

## Mode d'emploi

[`manuel/Kab-board-Windows-manuel-0.2.pdf`](manuel/Kab-board-Windows-manuel-0.2.pdf),
15 pages illustrées : de l'installation à la désinstallation. La source est
`manuel/manuel.tex`, ses captures dans `manuel/captures/` :

```
cd manuel && pdflatex manuel.tex && pdflatex manuel.tex
```

## Licence

Copyright © 2026 Les auteurs de kab-board (voir [AUTHORS](AUTHORS)).

Distribué sous licence GNU GPL, version 3 ou ultérieure : voir [LICENSE](LICENSE).
Les composants repris et leurs licences sont dans [`paquet/NOTICE.txt`](paquet/NOTICE.txt).
Les ressources linguistiques sont sous licence CC BY-SA 4.0
(doi [10.5281/zenodo.22112059](https://doi.org/10.5281/zenodo.22112059)) ; le
modèle vocal Mmeslay sous GNU GPL 3.
