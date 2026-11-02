#!/usr/bin/env python3
"""Le manifeste de l'extension pour Firefox, tiré de celui de Chrome : les mêmes scripts,
réglages et raccourcis, ce que Firefox fait autrement en plus.

    python3 firefox/manifeste.py chrome/extension/manifest.json firefox/extension/manifest.json

- Le fond est une page (background.scripts), pas un service worker : elle charge
  commun.js et plateforme.js, que le service worker de Chrome importe lui-même.
- Pas de document hors écran (permission offscreen) : la page de fond porte le
  correcteur.
- La clé de Chrome n'a pas cours : Firefox prend l'identifiant de
  browser_specific_settings, qui dit aussi que l'extension ne collecte aucune donnée.
- Firefox 140 au moins : storage.session, les surlignages des éléments modifiables
  (CSS.highlights) et data_collection_permissions.
"""
import json
import sys

IDENTIFIANT = "kab-board@adj-mss"
FIREFOX_MIN = "140.0"


def firefox(chrome: dict) -> dict:
    sortie = {}
    for cle, valeur in chrome.items():
        if cle in ("key", "minimum_chrome_version"):
            continue
        if cle == "background":
            valeur = {"scripts": ["commun.js", "plateforme.js", "fond.js"]}
        elif cle == "options_page":
            cle, valeur = "options_ui", {"page": valeur, "open_in_tab": True}
        elif cle == "permissions":
            valeur = [p for p in valeur if p != "offscreen"]
        elif cle == "content_scripts":
            valeur = [{k: v for k, v in c.items() if k != "match_origin_as_fallback"} for c in valeur]
        sortie[cle] = valeur
        if cle == "description":
            sortie["browser_specific_settings"] = {"gecko": {
                "id": IDENTIFIANT,
                "strict_min_version": FIREFOX_MIN,
                "data_collection_permissions": {"required": ["none"]},
            }}
    return sortie


def principal(argv) -> int:
    source, cible = argv[1:3]
    with open(source, encoding="utf-8") as f:
        chrome = json.load(f)
    with open(cible, "w", encoding="utf-8") as f:
        json.dump(firefox(chrome), f, ensure_ascii=False, indent=2)
        f.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(principal(sys.argv))
