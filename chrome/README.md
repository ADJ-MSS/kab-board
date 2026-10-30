# Kab-board, extension pour navigateur

Le clavier et le correcteur kabyles de Kab-board dans le navigateur (Chrome,
Edge, Brave, Opera, Chromium) : les mêmes règles et les mêmes résultats que kab-board sur Android.
**L'extension se suffit à elle-même** : le correcteur, le modèle de langue et le
modèle vocal sont dedans, et tournent dans le navigateur. Rien à installer à côté,
et **rien ne part sur Internet**.

## Ce qu'elle fait

- **Écrire comme on parle** : `gh` → ɣ, `dh` → ḍ, `kh` → x, `aa` → ɛ, `ou` → u,
  quand les deux lettres sont tapées l'une après l'autre ; un effacement juste
  après défait la conversion. **AltGr** + g, e, d, h, t, z, s, c, j, r.
- **La barre des six propositions** sous le mot, à la casse du mot tapé :
  complétion de 1 à 3 lettres (ocre), puis la correction en contexte (vert) et
  les candidats (bleu) ; le mot fini, le mot suivant (ocre). **1 à 6** ou un clic
  pour choisir, **Échap** pour la cacher. « tamurt iw » → « tamurt-iw » en une
  fois, jamais par-dessus une virgule. Au milieu d'un mot, la barre propose pour
  ce qui précède le curseur et le choix remplace le mot entier.
- **Les mots à revoir soulignés** pendant qu'on écrit, phrase par phrase : en
  rouge une faute (un mot que le correcteur ne connaît pas), en bleu un doute (un
  mot connu que la phrase écrirait autrement) ; un clic sur le mot ouvre sa
  carte : propositions, « Garder mon mot », « Ajouter à mon dictionnaire »,
  Asegzawal. Le correcteur de Chrome, qui ne connaît pas le kabyle, se tait dans
  le champ.
- **Les mêmes résultats que Kab-board sur Android** : voir plus bas.
- **La correction automatique**, si on l'allume (éteinte au départ : rien n'est
  corrigé d'office dans kab-board) : à l'espace, seulement un mot que le
  correcteur ne connaît pas, jamais un nom propre en milieu de phrase, un sigle,
  un mot de « mon dictionnaire » ; **Retour arrière** rend le mot tapé.
- **La dictée** en kabyle (Mmeslay), 30 s au plus : le micro et la transcription
  dans le navigateur, le texte écrit au curseur, jamais corrigé d'office.
- **Les outils** : Asegzawal, du français au kabyle, relire un champ ou une
  sélection (« Tout corriger »), le mot du jour, les lettres kabyles à cliquer,
  la page « Écrire et relire ».
- **La graphie b ou v**, pour les propositions, les outils et la dictée ; v au
  départ, comme sur le téléphone.
- **« Mon dictionnaire »**, gardé dans Chrome ; un fichier texte (un mot par
  ligne, celui de Kab-board pour Windows par exemple) s'y importe, et la liste
  s'exporte.
- Silencieuse dans les **mots de passe** (même rendus visibles), les codes, les
  numéros de carte, les champs d'adresse électronique ; éteinte d'un raccourci
  (**Alt+Maj+K**) ou pour un site.

## Comment c'est fait

```
 Chrome
┌──────────────────────────────────┐      ┌───────────────────────────────────────┐
│ contenu/  le champ où l'on écrit │      │ horsecran/  le document hors écran    │
│   logique.js  les règles         │      │   horsecran.js   le relais            │
│   champs.js   textarea, input,   │      │   enregistreur.js le micro            │
│               contenteditable    │      │        │                              │
│   interface.js barre, carte,     │      │        ▼  un fil à part               │
│               panneau, soulignés │      │ moteur/travailleur.js  le correcteur  │
│ fond.js  ◄──── messages ────────►│◄────►│   moteur.js, clavier.js… (JavaScript) │
│ popup/, pages/                   │      │   kab_lm.wasm (KenLM), kab_crf.wasm   │
└──────────────────────────────────┘      │   onnxruntime-web (la dictée)         │
                                          └───────────────────────────────────────┘
```

- **Le correcteur** (`extension/moteur/`) est le moteur de l'application Android
  (`moteur/src/main/kotlin` de kab-board) porté en JavaScript, avec ce que fait le
  clavier autour de lui (`ClavierKabyle`, `CorrecteurSysteme`, Asegzawal). Le
  modèle de langue (KenLM, 3-grammes) et l'étiqueteur (CRFsuite) sont leur code C++
  et C compilé en WebAssembly (`autonome/construire-wasm.sh`) ; la dictée passe par
  onnxruntime-web 1.20.1, la version d'onnxruntime de l'APK. Les ressources sont
  celles de l'APK 0.3 (`autonome/ressources.sh`, chaque fichier vérifié).
- **Le document hors écran** (`horsecran/`) charge le correcteur une fois, dans un
  fil à part, pour tous les onglets. Le fond ne l'ouvre qu'au premier champ où
  l'on écrit, pas au démarrage du navigateur, et il se ferme au bout de vingt
  minutes sans rien demander. Il écoute aussi le micro de la dictée.
- **Le fond** (`fond.js`) passe les requêtes des pages au correcteur, en ajoutant
  la graphie. L'état du correcteur (au repos, en chargement, prêt, en panne) va
  dans `chrome.storage.session`, les réglages dans `chrome.storage.sync`, « mon
  dictionnaire » dans `chrome.storage.local`.
- **Le script de contenu** suit le champ où l'on écrit. Toute écriture passe par
  `document.execCommand("insertText")`, comme la frappe : l'éditeur de la page
  (React, Lexical, ProseMirror…) suit, et **Ctrl+Z** défait. Les soulignés d'un
  élément modifiable sont des « highlights » du navigateur, qui ne touchent pas
  au DOM ; ceux d'un `<textarea>` ou d'un `<input>`, un calque posé dessus.
  L'interface vit dans une racine d'ombre et n'obéit qu'aux vrais clics : une
  page ne peut pas lancer la dictée à votre place.
- **La dictée** : le micro est écouté sans réduction du bruit ni gain automatique,
  comme la source `VOICE_RECOGNITION` de l'application Android, et en 16 kHz, le
  format de Mmeslay, Chrome l'y ramenant comme Android le fait pour l'application
  (s'il donnait un autre taux, `logique.js` l'y ramènerait : filtre passe-bas à
  sinus cardinal fenêtré, sans repliement des sifflantes). Puis les échantillons
  passent par les entiers 16 bits du micro du téléphone.

| Fichier | |
|---|---|
| `extension/manifest.json` | Manifeste V3. La clé fixe l'identifiant en mode développeur : `bdmaonaapnhmnkcealgfodhmkijkhbgg`. |
| `extension/logique.js` | Les règles, sans navigateur : digrammes, AltGr, mot en cours, choix, possessif, correction automatique, morceaux à relire, rééchantillonnage. |
| `extension/commun.js` | Les réglages et leurs valeurs de départ, « mon dictionnaire ». |
| `extension/fond.js` | Le service worker : le document hors écran, l'état, la dictée, les raccourcis, le menu du clic droit. |
| `extension/horsecran/` | Le document hors écran : le relais vers le correcteur, le micro. |
| `extension/moteur/` | Le correcteur : le moteur en JavaScript, KenLM et CRFsuite en WebAssembly, la transcription. |
| `extension/contenu/` | Le script de contenu : `champs.js`, `interface.js`, `contenu.js`, `contenu.css`. |
| `extension/popup/`, `extension/pages/` | Le bouton de la barre de Chrome, les réglages, « Écrire et relire », l'autorisation du micro. |
| `extension/ressources/`, `extension/ort/` | Les ressources de l'APK et onnxruntime-web : hors du dépôt, posés par `autonome/ressources.sh`. |
| `autonome/` | Comment l'extension est devenue autonome : la construction de KenLM et CRFsuite, les ressources, l'historique. |
| `tests/` | Les vérifications (voir plus bas). |

## Comme sur le téléphone

Relevé du 29 et du 30/10/2026, avec le moteur de l'APK 0.3 rejoué hors du
téléphone (le code Kotlin de l'application, ses ressources, ses bibliothèques
natives) contre le correcteur de l'extension, avec les mêmes ressources ;
`outils/android/` le refait :

| | identiques |
|---|---|
| KenLM en WebAssembly : scores, au bit près | 1 020 632 / 1 020 632 |
| CRFsuite en WebAssembly : étiquettes | 13 197 / 13 197 |
| la barre, lettre à lettre sur 40 phrases (complétion, propositions, prédiction), graphies v et b | 1 134 / 1 134 |
| « Relire » et les soulignés, sur 128 textes (167 mots signalés) | 128 / 128 |
| la correction seule et le top-5, sur 2 440 phrases tirées au hasard (clitiques, possessifs, fautes) | 2 440 / 2 440 |
| les fiches d'Asegzawal, en b et en v | 6 760 / 6 760 |
| du français au kabyle, en b et en v | 1 062 / 1 062 |
| les candidats du mot du jour, dans l'ordre | 1 023 / 1 023 |
| la dictée : les textes transcrits (onnxruntime-web contre onnxruntime natif) | 14 / 14 |

## Ce qu'elle demande

Mesuré dans Chromium (Linux, 4 cœurs), sur trois passages de l'essai avec le vrai
correcteur (`tests/essai_navigateur.mjs --vrai`) :

- **le chargement** du correcteur : de 4,3 à 5,6 s, une fois, au premier champ
  où l'on écrit (la frappe, gh → ɣ, marche dès le départ) ;
- **la barre** : 25 ms en médiane, de 57 à 83 ms pour les 5 % les plus lents,
  sur 100 requêtes passées par le fond et le document hors écran ;
- **la mémoire** : environ 750 Mo de plus pour Chromium avec le correcteur et
  le modèle vocal (PSS : 1 265 Mo contre 511 Mo) ;
- **l'archive** : 244 Mo (376 Mo une fois installée), sous les 2 Go du Web Store.

## Installer

**Depuis le Chrome Web Store**, une fois l'extension publiée : rien d'autre à
installer.

**En mode développeur**, depuis ce dépôt :

```sh
chrome/autonome/ressources.sh kab-board-0.3.apk    # les ressources de l'APK et onnxruntime-web
```

puis `chrome://extensions`, « Mode développeur », « Charger l'extension non
empaquetée » : `chrome/extension`.

**Les archives** : `chrome/empaqueter.sh` vérifie les ressources et fait, dans
`sortie/`, `kab-board-navigateur-<version>.zip` (à décompresser puis charger) et
`kab-board-navigateur-<version>-web-store.zip` (sans la clé, pour le Store, qui donne
son propre identifiant).

**Le manuel** : `manuel/Kab-board-Navigateur-manuel-0.2.pdf`, illustré ; la source est
`manuel/manuel.tex` (`cd chrome/manuel && pdflatex manuel.tex && pdflatex manuel.tex`).

## Ce qui ne marche pas

- **Google Docs** dessine son texte lui-même, sans champ : utilisez « Écrire et
  relire », puis copiez. De même pour les pages de Chrome et le Web Store, où
  aucune extension ne peut écrire.
- Les éditeurs de code (CodeMirror, Monaco, Ace) sont laissés tranquilles.
- AltGr se lit tel que Chrome le donne (`AltGraph`) : sur un clavier sans AltGr,
  les digrammes suffisent.
- Sur un ordinateur qui manque de mémoire, le correcteur peut ne pas se charger :
  l'icône le dit (« ! »), la page des réglages aussi, et la frappe continue sans lui.

## Vérifier

```sh
node --test chrome/tests/logique.test.mjs           # la logique : 21 groupes
node chrome/tests/essai_navigateur.mjs              # Chromium, l'extension, un faux correcteur : 59
node chrome/tests/essai_navigateur.mjs --vrai       # le vrai correcteur, et les mesures : 54
KAB_ESSAI_AUDIO=chrome/manuel/outils/voix.wav KAB_ESSAI_DICTEE="ilaq ad teččem kra n lḥaǧa" \
  node chrome/tests/essai_navigateur.mjs --vrai       # et une vraie voix kabyle au micro : 55
```

`essai_navigateur.mjs` lance un vrai Chromium (Playwright, ou `CHROME=…`),
charge l'extension et tape dans une page : conversions, barre, chiffres,
soulignés, carte, élément modifiable, mot de passe, correction automatique,
outils, dictée, popup, graphie, « mon dictionnaire » et son import, « Écrire et
relire », le document hors écran fermé au repos puis rouvert, et un correcteur
qui ne se charge pas. Sans `--vrai`, une copie de l'extension sans ses ressources,
où un faux correcteur (`tests/faux_travailleur.js`) donne, pour ces phrases-là,
les réponses du vrai : c'est ce que fait la CI. Avec `--vrai`, l'extension
elle-même, avec ses ressources. `KAB_ESSAI_AUDIO=son.wav` sert de micro à la
dictée, et `KAB_ESSAI_DICTEE` ce qu'elle doit en tirer : avec `manuel/outils/voix.wav`,
une phrase kabyle enregistrée, « ilaq ad teččem kra n lḥaǧa », comme sur le téléphone.

## Vie privée

Ce que vous écrivez ne quitte pas l'ordinateur : le correcteur et le modèle
vocal sont dans l'extension, qui n'ouvre aucune connexion vers Internet. La voix
de la dictée n'est gardée que le temps de la transcrire, en mémoire. Les
permissions demandées : `storage` (les réglages, « mon dictionnaire »),
`contextMenus` (le clic droit), `offscreen` (le document qui porte le correcteur
et écoute le micro), `scripting` et l'accès aux sites (le script de contenu dans
les champs, et dans les onglets déjà ouverts à l'installation).
