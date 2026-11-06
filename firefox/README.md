# Kab-board pour Firefox

La même extension que pour Chrome (`chrome/extension`) : le même code, les mêmes
réglages, le même correcteur, avec les mêmes résultats que kab-board sur Android, et le
même essai de bout en bout. Seul change ce que Firefox fait autrement.
`firefox/construire.sh` assemble l'extension pour Firefox dans `firefox/extension/` à
partir de celle de Chrome ; rien n'est recopié à la main.

**L'installer** : depuis [addons.mozilla.org](https://addons.mozilla.org/fr/firefox/addon/kab-board/), ou avec
`kab-board-firefox-0.2.0.xpi`, sur la
[page des versions](https://github.com/ADJ-MSS/kab-board/releases), signé par Mozilla.
Faites glisser le fichier dans une fenêtre de Firefox (140 ou plus récent), puis
« Ajouter ». Le premier chargement du correcteur prend une vingtaine de secondes, le
temps de décompresser le modèle de langue ; les suivants, quelques secondes.

## Ce qui change pour Firefox

| | Chrome | Firefox |
|---|---|---|
| le fond | un service worker (`fond.js`) | une page, qui charge `commun.js`, `plateforme.js` et `fond.js` |
| où tourne le correcteur (`plateforme.js`) | un document hors écran (`horsecran/horsecran.html`) | la page de fond elle-même, tenue éveillée tant qu'il sert (vingt minutes après la dernière requête) |
| la dictée | le micro dans le document hors écran | une petite fenêtre de l'extension (`horsecran/dictee.html`), où Firefox peut demander le micro ; le même enregistreur (`horsecran/enregistreur.js`). La barre dit « Le micro s'ouvre… » jusqu'à ce qu'il écoute vraiment |
| l'état du correcteur | `chrome.storage.session` | `chrome.storage.local` : Firefox ne laisse pas les scripts de contenu lire la session |
| onnxruntime-web (la dictée) | 1.20.1, la version de l'APK | 1.18.0, sa dernière version sans fils : la 1.20 exige une mémoire partagée que Firefox refuse aux pages d'une extension |
| le modèle de langue, le modèle vocal | tels quels | compressés par xz, le premier sans son vocabulaire, que le correcteur recalcule (`moteur/compression.js`, `kab_xz.wasm`) ; décompressés au premier chargement, puis gardés (IndexedDB) |
| le manifeste | `chrome/extension/manifest.json` | tiré du premier (`manifeste.py`) : identifiant `kab-board@adj-mss`, Firefox 140 au moins, aucune donnée collectée (`data_collection_permissions`) |
| une racine d'ombre fermée | `chrome.dom.openOrClosedShadowRoot` | `element.openOrClosedShadowRoot` |
| les raccourcis | `chrome://extensions/shortcuts` | `chrome.commands.openShortcutSettings()` |
| le nom du navigateur, dans les pages | Chrome | Firefox (`C.navigateur()`, dans `commun.js`) |

Le reste (le script de contenu, la barre, les soulignés, les outils, le popup, les
pages, le moteur) est le même fichier.

## Les mêmes résultats

- Le moteur est celui de Chrome, qui donne ce que donne l'APK sur tout le banc
  d'équivalence (1 134 cas de barre, 128 relectures, 2 440 corrections, 6 760
  fiches…).
- Ses ressources compressées redonnent les fichiers d'origine, octet pour octet :
  `verifier_ressources.mjs` les décompresse avec le code du correcteur et compare les
  empreintes SHA-256 (le modèle de langue, 281 Mo, et le modèle vocal, 52 Mo).
- La dictée avec onnxruntime-web 1.18.0 donne ce que donne onnxruntime natif 1.20.1,
  celui de l'APK : 14 textes sur 14, 1 548 trames sur 1 548
  (dans Chromium). La phrase kabyle enregistrée du
  manuel donne « ilaq ad teččem kra n lḥaǧa ».

## Ce que Mozilla impose

Firefox n'installe que des extensions signées par Mozilla, et Mozilla ne signe que ce
qu'il valide (addons.mozilla.org, que l'extension y soit publiée ou non). D'après le
code de son service (`addons-server`, `settings_base.py`) et de son contrôle
(`addons-linter`) :

| | la limite | l'archive |
|---|---|---|
| le fichier envoyé | 200 000 000 octets | 188 757 203 octets |
| une fois décompressé | 250 Mio (262 144 000 octets) | 217 494 605 octets |
| chaque fichier | 100 Mio | 64 Mio au plus (le modèle de langue en trois parties) |

Sans compression, l'extension ferait 244 Mo (376 Mo décompressée). Le modèle de langue
compressé tel quel ferait 152 Mo : son vocabulaire, 16 Mo d'empreintes presque
aléatoires, ne se compresse pas. Comme il se déduit de la liste des mots qui termine le
fichier, l'archive l'omet : 139 Mo.

`addons-linter` 10.15.0 sur `firefox/extension` : aucune erreur, sept avertissements.
Deux portent sur `chrome.dom.openOrClosedShadowRoot`, propre à Chrome et appelé
seulement quand il existe ; quatre sur le code minifié d'onnxruntime-web ; un sur Firefox
pour Android, que l'extension ne vise pas.

Le code minifié ou produit par un outil (onnxruntime-web, `kab_lm.wasm`, `kab_crf.wasm`,
`kab_xz.wasm` et leurs `.mjs`) oblige à joindre ses sources à l'envoi : le paquet npm
`onnxruntime-web@1.18.0`, et pour les autres `chrome/autonome/construire-wasm.sh`, ses
sources (KenLM et CRFsuite du dépôt kab-board, `natif/amont` ; xz-embedded dans
`chrome/autonome/xz-embedded`).

## Le temps qu'il faut

Mesuré dans Chromium (le fil du correcteur de la version Firefox, servi tel quel ; il
n'a pas encore été mesuré dans Firefox même) :

- le premier chargement du correcteur, une fois pour toutes : 22 s, dont une dizaine
  pour décompresser le modèle de langue ;
- les suivants, depuis le cache : 3,8 s ;
- la première dictée : 7,4 s (le modèle vocal décompressé) ; les suivantes : 2,5 s.

Et dans Firefox même (Firefox 158.0.1, `essai_firefox.mjs`) : le micro de la dictée
écoute 2,3 s après le clic, le temps d'ouvrir sa fenêtre ; 0,1 s dans Chromium, sur la
même machine.

## Construire, essayer, empaqueter

```sh
chrome/autonome/ressources.sh kab-board-0.3.apk    # les ressources, une fois
firefox/construire.sh                              # firefox/extension ; quelques minutes la première fois
firefox/empaqueter.sh                              # sortie/kab-board-firefox-<version>.xpi
```

Pour l'essayer sans signature : `about:debugging`, « Ce Firefox », « Charger un module
complémentaire temporaire… », `firefox/extension/manifest.json`. Il reste jusqu'à la
fermeture de Firefox. Firefox Developer Edition et Nightly acceptent aussi l'archive non
signée (`xpinstall.signatures.required` à `false` dans `about:config`).

## Vérifier

```sh
node --test chrome/tests/logique.test.mjs           # la logique, commune
firefox/construire.sh --sans-ressources             # le code seul, pour le faux correcteur
FIREFOX=/chemin/vers/firefox node firefox/tests/essai_firefox.mjs          # faux correcteur
FIREFOX=/chemin/vers/firefox node firefox/tests/essai_firefox.mjs --vrai   # le vrai (firefox/construire.sh)
node firefox/verifier_ressources.mjs firefox/extension                     # les ressources, à l'octet près
```

`essai_firefox.mjs` lance Firefox (Puppeteer, par WebDriver BiDi), y installe
l'extension comme un module temporaire, et fait le même parcours que pour Chromium
(`chrome/tests/scenario.mjs`), sur la même page (`chrome/tests/page_essai.html`).
Firefox ne sait pas prendre un fichier pour micro : la dictée y entend le son d'essai de
Firefox.

Avec Firefox 158.0.1 : 59 vérifications sur 59 avec le faux correcteur, les mêmes que dans
Chromium, et 54 sur 54 avec le vrai (relevé du 02/11/2026). Deux choses propres à l'essai :

- Firefox ne fait tourner l'audio qu'avec une sortie audio ; sur une machine qui n'en a
  pas, on lui donne un serveur de son muet (PulseAudio). Sans sortie, la dictée le dit au bout de
  5 s (« le son ne passe pas »), plutôt que d'écouter sans rien entendre.
- WebDriver ne sait ni mettre une page de l'extension au premier plan ni y choisir un
  fichier : l'essai s'en passe, et remet le fichier à la page lui-même.
