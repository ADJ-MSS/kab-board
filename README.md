# kab-board

Clavier Android pour écrire le kabyle : correcteur orthographique, suggestions, dictée vocale et outils d'écriture. **100 % hors ligne** : tout se calcule sur le téléphone, et l'application n'a pas l'autorisation d'accéder à Internet.

- **Télécharger l'application** : [page des versions](https://github.com/ADJ-MSS/kab-board/releases) — fichier `.apk`, Android 7 ou plus récent, téléphone 64 bits.
- **Manuel d'utilisation** : [kab-board-manuel-utilisation.netlify.app](https://kab-board-manuel-utilisation.netlify.app/)

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
