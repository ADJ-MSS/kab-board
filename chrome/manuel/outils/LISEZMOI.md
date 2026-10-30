# Les captures du manuel, et les essais de champs

Un Chrome sans tête, en français, l'extension chargée dans un profil jetable, avec
ses ressources (`chrome/autonome/ressources.sh`) et le vrai correcteur. Rien n'est
lu ni écrit dans le profil de l'utilisateur. Google Chrome s'il est installé
(`/usr/bin/google-chrome`), sinon le Chromium de Playwright, ou `CHROME=…`.

```sh
npm install --prefix /tmp/pw playwright
NODE_PATH=/tmp/pw/node_modules node capturer.mjs   # les 28 captures, dans ../captures/
NODE_PATH=/tmp/pw/node_modules node champs.mjs     # 24 genres de champs
NODE_PATH=/tmp/pw/node_modules node sites.mjs      # quelques vrais sites
```

- `decor.mjs` : le décor commun. La page d'exemple (« Tabrat tamaynut ») est
  servie sous un nom fictif, `tabrat.exemple`, que le popup affiche. Avec
  `panne: true`, une copie de l'extension dont le correcteur ne se charge pas
  (son fil manque) : les captures 26 à 28.
- Les captures sont prises par le protocole de débogage, à l'échelle 2 :
  Playwright la ramènerait à 1. Le popup, lui, est le vrai, ouvert par
  `chrome.action.openPopup()` et capturé par son propre WebSocket.
- L'encart publicitaire de `chrome://extensions` est masqué avant la capture,
  comme l'avis d'un navigateur géré par une organisation (celui d'une machine
  d'essai).
- Les captures du 30/10/2026 viennent du Chromium de Playwright (Chrome for
  Testing, d'où le petit « Test » sur le logo de la 01), avec les polices Noto ;
  `02-raccourcis.png` est restée celle de Google Chrome, les raccourcis n'ayant
  pas changé.
- `voix.wav` sert de micro à la dictée : « Ilaq ad teččem kra n lḥaǧa », du
  jeu `kabyle-ljspeech-22khz` (CC0), mis à 48 kHz.
- `sites.mjs` : DeepL, Reddit, GitHub et Le Bon Coin opposent une vérification
  anti-robot à un navigateur piloté ; ce n'est pas l'extension.
