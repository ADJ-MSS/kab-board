# kab-board

Clavier pour écrire le kabyle, sur Android et sur Linux, et correcteur pour Microsoft Word sous Windows : correcteur orthographique, suggestions, dictée vocale et outils d'écriture. **100 % hors ligne** : tout se calcule sur l'appareil, et l'application Android n'a pas l'autorisation d'accéder à Internet.

- **Télécharger** : [page des versions](https://github.com/ADJ-MSS/kab-board/releases) : `.apk` pour Android 7 ou plus récent sur téléphone 64 bits, `.deb` pour Debian et Ubuntu, `kab-board-word-setup-0.3.exe` pour Word sous Windows 10 ou 11.
- **Manuel d'utilisation** : [kab-board-manuel-utilisation.netlify.app](https://kab-board-manuel-utilisation.netlify.app/)
- **Le code Linux** : [`linux/`](linux/), application, méthode de saisie et clavier à l'écran.
- **Le code Word** : [`word/`](word/), complément pour Word, moteur et installeur ; voir [`word/NOTES-DEV.md`](word/NOTES-DEV.md).

## Version 0.3

- **La barre complète le mot**, de 1 à 3 lettres tapées : les mots qui commencent ainsi, choisis d'après la phrase. Dès la 4e lettre, elle corrige comme avant. Mesuré sur 400 phrases : 24 % de frappes en moins, sans rien perdre en correction.
- **« tamurt iw » devient « tamurt-iw » en une fois.** La correction qui rattache un possessif au mot d'avant remplace désormais les deux mots, dans la barre comme dans Relire.
- La graphie **v** est le réglage de départ, sur Android comme sur Linux ; un choix déjà fait est respecté.
- **Kab-board pour Word**, première version publique : un onglet dans le ruban, la relecture du document ou de la sélection, les propositions au clic droit, « Mon dictionnaire », la graphie b ou v et la dictée en kabyle. Comme sur le téléphone, tout se calcule sur l'ordinateur.

## Version 0.2

- **Graphie b ou v.** Un réglage, et il vaut pour tout ce qui s'affiche : voir plus bas.
- **kab-board sur Linux**, première version : l'application avec ses interrupteurs, la méthode de saisie qui écrit dans toutes les applications, le clavier à l'écran, la dictée et les outils du téléphone. Le paquet `.deb` contient toutes les ressources, rien à télécharger ensuite.
- **Un bouton Réglages sur le clavier**, au bout de la rangée d'outils : l'écran de l'application s'ouvre sans quitter ce qu'on écrit.
- Le choix de graphie **se coche** au lieu d'être deux boutons muets.
- La fiche d'Asegzawal affiche son mot dans la graphie réglée, et non plus tel qu'il a été tapé.

## Écrire avec b ou avec v

Certains écrivent *abrid*, d'autres *avrid*. Un réglage tranche, et il vaut pour
tout ce qui s'affiche : la correction, les cinq candidats, la prédiction du mot
suivant, la fiche d'un mot, la recherche depuis le français, le mot du jour et la
dictée. La table compte 13 142 formes, dans
[`app/src/main/assets/graphie/table_bv.tsv`](app/src/main/assets/graphie/table_bv.tsv) :
5 352 viennent de la liste des mots en v, 7 790 de la propagation aux paradigmes
verbaux, sur 287 verbes. **Android et Linux lisent le même fichier.**

La table ne liste que des formes de base. Un mot fléchi est donc ramené à une
forme qu'elle connaît, sans quoi une même phrase mêlerait les deux graphies :
les segments d'un mot à tirets séparément (`baba-s` → `vava-s`), l'état
d'annexion par les règles du correcteur (`ubrid` → `uvrid`), l'annexion en
`we-` (`weqbu` → `weqvu`) et le pluriel dont le singulier est dans la table
(`iɣriben` → `iɣriven`). Mesuré sur le lexique le 28/09/2026 : 343 630
occurrences de plus que la table seule. Un mot que rien de tout cela ne
reconnaît ne change jamais, comme les emprunts `belli`, `ṛebbi` ou `mebla`.

## Projets liés

- Correcteur kabyle, dont le moteur est porté ici en Kotlin : [doi.org/10.5281/zenodo.22112059](https://doi.org/10.5281/zenodo.22112059)
- Modèle de reconnaissance vocale kabyle : [Mmeslay](https://github.com/G1ya777/Mmeslay_backend-CLI)

## Construire

Outils : JDK 21, Gradle 8.9, Android SDK 35, NDK 28.2.13676358, CMake 3.22.1.

Les ressources linguistiques et les modèles ne sont pas versionnés. Avant de construire, placez les ressources du correcteur et `kabyle_3gram.binary` dans `app/src/main/assets/moteur/`, puis `mmeslay.onnx` et `jetons.txt` dans `app/src/main/assets/voix/` (voir `outils/`).

```sh
gradle assembleDebug
gradle testDebugUnitTest
```

## Licence

Copyright © 2026 Les auteurs de kab-board (voir [AUTHORS](AUTHORS)).

Distribué sous licence GNU GPL, version 3 ou ultérieure : voir [LICENSE](LICENSE). Les composants repris et leurs licences sont détaillés dans [`app/src/main/assets/NOTICE.txt`](app/src/main/assets/NOTICE.txt). Les ressources linguistiques embarquées dans l'application sont sous licence CC BY-SA 4.0.

Pour citer ce logiciel, voir [CITATION.cff](CITATION.cff).
