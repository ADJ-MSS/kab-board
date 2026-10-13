Le clavier kabyle de kab-board, pour **Windows 10 et 11** (64 bits) : il écrit dans **toutes les applications**. Tout se calcule sur l'ordinateur : aucune connexion, rien n'est envoyé.

## Corrigé dans la 0.2

- **Le début des mots ne se perd plus** dans un navigateur, ni dans Word au démarrage. Le clavier ne se tait plus le temps de vérifier un champ : il suit les lettres sans rien réécrire, puis reprend. Un mot de passe reste intact.
- **Un crochet clavier retiré par Windows** (ordinateur très occupé) est reposé de lui-même.
- **« tamurt iw » → « tamurt-iw »** dans la barre, enfin : les possessifs courts (iw, ik, im, is) passaient derrière la complétion. Le correcteur est celui de kab-board 0.3.3, qui corrige la même chose sur Android et Linux.
- **Le Bloc-notes de Windows 11** ne mélange plus un mot choisi (des blancs, ou « tttt-nneɣ ») : les caractères du clavier partent comme de vraies touches.
- **La graphie b ou v** est la même que dans Kab-board pour Word.
- **Les réglages et « mon dictionnaire » partagés avec Word** se lisent même enregistrés avec un BOM.
- **Les fenêtres tiennent** sur un écran de 768 pixels de haut : les réglages passent sur deux colonnes.
- En AZERTY, les chiffres qui choisissent se tapent avec **Maj** (Maj + & donne 1) ou au pavé numérique : c'est maintenant dit partout.
- Les journaux `saisie.log` et `service.log` se remplissent enfin : ils restaient vides.
- La dernière page de l'installeur ne parle plus d'icônes sur le Bureau.
- Un **manuel** illustré : `Kab-board-Windows-manuel-0.2.pdf`.

## Ce qu'il fait

- **Les lettres kabyles au clavier ordinaire** : `gh` → ɣ, `dh` → ḍ, `kh` → x, `aa` → ɛ, `ou` → u ; AltGr + g, e, d, h, t, z, s, c, j, r. Un effacement juste après défait la conversion.
- **Vous tapez sur votre clavier**, comme d'habitude : aucun clavier à l'écran n'est nécessaire.
- **Six propositions** dans une barre sous le mot en cours : la correction en contexte d'abord, puis les candidats ; de 1 à 3 lettres, la complétion ; le mot fini, la prédiction du suivant. **1 à 6** ou un clic pour choisir. Rien n'est corrigé d'office.
- **« tamurt iw » → « tamurt-iw »** en une fois, jamais par-dessus une virgule.
- **Graphie b ou v**, qui vaut partout, Kab-board pour Word compris.
- **Le clavier à l'écran**, qui ne vole jamais le curseur, avec la dictée en kabyle, Asegzawal, fr → kab, Relire (le presse-papiers), le mot du jour.
- **Écrire et relire** : une fenêtre pour écrire, relire mot à mot et copier.
- Silencieux dans les **mots de passe**.

Le même correcteur que sur Android et Linux (kab-board 0.3.3), ses ressources comprises : lexique de 1,58 million d'entrées, modèle de langue 3-grammes, étiqueteur, graphe sémantique, modèle vocal Mmeslay.

## Installer

`kab-board-windows-…-setup.exe`, pour votre compte seulement, sans droits d'administrateur.

Il n'est pas signé : si Windows affiche « Windows a protégé votre ordinateur », cliquez « Informations complémentaires », puis « Exécuter quand même ».

Les empreintes SHA-256 sont dans `SHA256SUMS.txt`.
