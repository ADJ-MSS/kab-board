"""Le graphe sémantique tel que publié avec le correcteur : sans la provenance
de chaque lien ni les renvois aux dictionnaires dans les gloses. Le moteur ne
lit ni l'une ni les autres.

    python graphe_sans_provenance.py chemin/du/graphe.json
"""
import json
import sys


def nettoyer(x):
    if isinstance(x, dict):
        return {k: nettoyer(v) for k, v in x.items() if k not in ("src", "sources")}
    if isinstance(x, list):
        return [nettoyer(v) for v in x]
    return x


def glose(texte):
    debut = texte.find(" (")
    if debut != -1 and "Dallet" in texte[debut:]:
        return texte[:debut].rstrip(".")
    return texte


def main(chemin):
    with open(chemin, encoding="utf-8") as f:
        graphe = json.load(f)
    graphe["meta"].pop("src_ancrage", None)
    graphe = nettoyer(graphe)
    for mot in graphe["mots"].values():
        for g in mot.get("gloses_fr", []):
            g["fr"] = glose(g["fr"])
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(graphe, f, ensure_ascii=False)


if __name__ == "__main__":
    main(sys.argv[1])
