# Kab-board pour Linux : la méthode de saisie

Un vrai clavier système. Une fois activé, il écrit **dans toutes les
applications** (messagerie, navigateur, traitement de texte) comme le
correcteur système de kab-board sur Android.

## Installer

```sh
./installer.sh
```

Puis, dans **Paramètres → Clavier → Sources de saisie**, ajouter
**Kabyle (kab-board)**. La touche Super+Espace bascule entre les sources.

L'installation écrit un seul fichier, `~/.local/share/ibus/component/kab-board.xml`,
et redémarre IBus. Pour désinstaller, supprimer ce fichier et redémarrer IBus.

## Écrire

**Les lettres kabyles**, sans appui long, puisqu'un clavier physique n'en a pas :

| Vous tapez | Vous obtenez | | Vous tapez | Vous obtenez |
|---|---|---|---|---|
| `gh` | ɣ | | AltGr+g | ɣ |
| `dh` | ḍ | | AltGr+e | ɛ |
| `kh` | x | | AltGr+d, h, t, z, s | ḍ ḥ ṭ ẓ ṣ |
| `aa` | ɛ | | AltGr+c, j, r | č ǧ ṛ |
| `ou` | u | | | |

Un effacement juste après une conversion la défait : `gh` redevient `gh`.

**Les propositions.** Le mot en cours s'affiche souligné, et ses six
propositions dans la liste du panneau : la correction en contexte d'abord, puis
les cinq candidats du mot isolé. Une touche de **1 à 6** écrit la proposition
choisie.

**Rien n'est corrigé d'office.** L'espace écrit le mot tel qu'il a été tapé.
C'est la règle du projet : le correcteur retient seul la bonne forme dans 49 %
des cas, mais elle figure dans ses cinq premières propositions 95,5 % du temps.

**Le réglage b ou v** se change dans le menu du panneau IBus, et vaut pour les
six propositions, comme sur le téléphone. La translittération `gh → ɣ` s'y coupe
aussi.

## Ce qu'il faut savoir

Le correcteur se charge au premier usage, en arrière-plan : **environ 9 secondes**
sur cette machine. Pendant ce temps la frappe fonctionne, sans propositions.

Le contexte de correction est borné à 60 caractères, comme la barre du clavier
Android.

## Vérifier

```sh
python3 test_saisie.py     # 22 vérifications : digrammes, AltGr, effacement, choix
```

Ces vérifications portent sur la saisie, qui se teste hors session. Le
branchement IBus lui-même (panneau, liste, propriétés) ne se vérifie qu'en
l'utilisant.
