# Kab-board pour Word : notes de développement

Le correcteur kabyle comme complément Microsoft Word, avec son installeur Windows.
Version : **0.3**, installée et utilisée sous Windows 11 depuis le 2026-10-05.

## Ce qu'il y a ici

| Dossier | Contenu |
|---|---|
| `complement/` | Le complément Word (C#) : ruban, volet, menu du clic droit, relecture, dictée, client du moteur. Compilé en `KabBoardPont.dll`. |
| `kab-board-word-complet-0.1/` | Le paquet installé : `moteur/` (le correcteur et la dictée, en Python), `LISEZMOI.txt`. Les dossiers `modeles/` et `python/` sont trop gros pour git : ils sont dans la release (voir plus bas). Le nom du dossier vient du paquet d'origine. |
| `setup/` | `construire.ps1` (compile le complément et fabrique l'installeur) et `kab-board.iss` (script Inno Setup). |
| `manuel/` | Le manuel d'utilisation en PDF, sa source `manuel.html` et ses captures. |

## Tout récupérer

Le code est dans le dossier `word/` du dépôt kab-board. Les gros fichiers sont dans la release **v0.3** du même dépôt :

- `kab-board-word-setup-0.3.exe` : l'installeur à distribuer (double-clic, « Installer »).
- `Kab-board-Word-manuel-0.3.pdf` : le manuel d'utilisation.
- `ressources-modeles.zip` : le dossier `modeles/`, avec le lexique, le modèle de langue, l'étiqueteur et le modèle de dictée Mmeslay (`voix/`).
- `ressources-python.zip` : le dossier `python/`, le Python embarqué avec ses modules, y compris onnxruntime 1.30 et ses deux bibliothèques Microsoft (`msvcp140.dll`, `msvcp140_1.dll`).

```
git clone https://github.com/ADJ-MSS/kab-board.git
cd kab-board/word
gh release download v0.3 -p "ressources-*.zip"
```

Décompressez ensuite les deux archives `ressources-…zip` dans `kab-board-word-complet-0.1/`.

Les modèles du correcteur viennent aussi de Zenodo, doi 10.5281/zenodo.22112059.

## Reconstruire l'installeur (Windows seulement)

Il faut :
- Windows ;
- Word installé, pour les assemblages d'interop d'Office ;
- le .NET Framework 4.8 ;
- Inno Setup 6 (`winget install JRSoftware.InnoSetup`).

```
powershell -ExecutionPolicy Bypass -File setup\construire.ps1
```

Comptez environ 15 minutes de compression. L'installeur sort dans `setup/sortie/kab-board-word-setup-<version>.exe`. La version se règle dans `setup/kab-board.iss` et dans `complement/Complement.cs` (`AssemblyVersion`).

Le code C# doit rester en C# 5, celui du `csc` du .NET Framework 4 : pas d'interpolation de chaînes, pas de `?.`.

## D'où vient le code

- Le paquet d'origine livrait une DLL `KabBoardWord.dll` **sans source**. Chargée par Word, elle le faisait planter : le `ref Array` de `IDTExtensibility2` n'était pas déclaré en SAFEARRAY. Son volet abandonnait aussi le moteur au bout de 90 secondes.
- Le complément a donc été réécrit entièrement dans `complement/`. Il garde le CLSID et le ProgId d'origine (`KabBoard.Pont`), si bien qu'une mise à jour remplace l'ancienne version sur place.
- Le moteur Python d'origine est gardé, avec deux ajouts :
  - un **cache** du lexique et du vivier (`moteur/linux/pipeline/ressources.py`), que l'installeur prépare (`moteur/preparer_cache.py`). Le chargement passe de 33 à environ 10 secondes, avec des résultats identiques ;
  - la **dictée** (`moteur/linux/dictee.py`).

## Fonctions

- **Relecture** du document ou de la sélection, avec la progression et « Annuler ». Le moteur redémarre tout seul s'il tombe.
- **Soulignés** : vert quand le contexte a tranché, bleu sinon. Ils sont retirés juste avant chaque enregistrement ou impression, puis remis, et ne laissent pas le document « modifié ».
- **Corrections** :
  - par le clic droit sur un mot souligné : ses propositions, « Garder mon mot », « Ajouter à mon dictionnaire » ;
  - par le volet : « Remplacer », « Remplacer partout », « ◀ Uzwir / Uḍfir ▶ ».
  - Chaque correction s'annule d'un seul Ctrl+Z (UndoRecord).
- **Possessifs rattachés en une fois** : pour « tamurt iw », la relecture propose « tamurt-iw » et remplace les deux mots, comme le clavier. Pas de fusion par-dessus une virgule. `normalisation.py` et `correcteur.py` sont ceux du clavier ; la portée se calcule dans `service.py`.
- **Graphie** v ou b, retenue (v par défaut), réglable dans le ruban et dans le volet.
- **« Ne pas vérifier en français »** (NoProofing), sur la sélection ou tout le document.
- **« Mon dictionnaire »** : voir, chercher, retirer et ajouter des mots (`%LOCALAPPDATA%\kab-board\mots-a-moi.txt`).
- **Dictée** : « Dicter » dans le ruban et le volet.
  - Le complément capte le micro (API waveIn, 16 kHz mono, 30 secondes au plus, `complement/Micro.cs`) et confie le fichier au moteur (`{"quoi": "dicter"}`).
  - Le moteur transcrit avec Mmeslay comme la dictée du clavier Linux, puis applique la graphie.
  - Le texte s'écrit au curseur, jamais corrigé d'office, et reste sélectionné pour « Relire la sélection ».
  - L'enregistrement est effacé après la transcription.
  - Sous Windows, `service.py` importe onnxruntime en tout premier : sinon, le `msvcp140.dll` de Windows (14.29), chargé avant par l'étiqueteur, le fait planter à l'import.

## Pas encore vérifié formellement

- Les soulignés absents du fichier enregistré : dézipper le .docx et chercher `w:u w:val="wave"` dans `word/document.xml`.
- La fermeture d'un document relu sans invite « Enregistrer ? ».
- Le Ctrl+Z après une correction faite depuis le volet (le clavier revient au document).
- Word en 32 bits, Office 2016 ou 2019.

## Pistes ouvertes

- Le dictionnaire sémantique n'est jamais chargé. Le nom du fichier a été abîmé à la décompression du zip d'origine : `modeles/wordnet/dictionnaire_s├®mantique_…json` au lieu de `dictionnaire_sémantique_…json`. Le renommer pourrait améliorer les propositions ; ce n'est pas encore fait.
- La 6e proposition varie d'un lancement à l'autre (hachage aléatoire de Python, ordre des candidats à score égal). Un `sorted(formes)` dans `pipeline/candidats.py` la stabiliserait.
- Juste après le démarrage du PC, le premier lancement du moteur prend jusqu'à une minute (disque froid).
- L'installeur n'est pas signé : Windows affiche « Windows a protégé votre ordinateur ».

## Où le complément range ses affaires

- Installation : `%LOCALAPPDATA%\Programs\Kab-board`, sans droits administrateur.
- Données : `%LOCALAPPDATA%\kab-board` : le port du moteur, `mots-a-moi.txt`, `cache/`, le journal `pont.log`.
- Réglages : `HKCU\Software\Kab-board` (Graphie).
- Déclaration à Word : `HKCU\Software\Microsoft\Office\Word\Addins\KabBoard.Pont`.
