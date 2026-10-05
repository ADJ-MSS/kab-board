#!/usr/bin/env python3
"""Évaluation de la v2, protocole identique à eval_metrics.py.

Usage : python3 eval_v2.py [--quick]
"""
import sys
import random
import difflib
import argparse
from pathlib import Path

V2_DIR = Path(__file__).resolve().parent
ROOT   = V2_DIR.parents[1]
V1_DIR = ROOT / "pipeline" / "v1"
DATA   = ROOT / "data"
sys.path.insert(0, str(V1_DIR))   # protocole d'évaluation réutilisé de la v1
sys.path.insert(0, str(V2_DIR))

from rapidfuzz.distance import Levenshtein

# On reprend le protocole v1 sans y toucher : phrases, typos, regex, appariement
from eval_metrics import TESTS, editions, spans, prf, _typo, _BON_MOT, _BON_TOK

from correcteur import KabyleCorrecteurV2
from normalisation import tokenize, normalize

# Les chiffres v1, pour comparaison (eval_metrics.py, 09/07/2026)
V1 = {
    "exact": "18/24 = 75.0%",
    "det":   "P 61.5%  R 88.9%  F1 72.7%",
    "corr":  "P 53.8%  R 77.8%  F1 63.6%  F0.5 57.4%",
    "wer":   "15.9% → 10.1%  (ERR 36.4%)",
    "surcorr": "3/15 = 20.0%",
    "iso":   "retrouvé 32.9%   top-5 89.1%",
    "ctx":   "retrouvé 27.0%   top-5 95.0%",
}

# La v1 ajoutait ces mots à la main, son lexique était bâti sans ḥ
MOTS_MANUELS_V1 = {
    "taqbaylit", "amaziɣ", "tamaziɣt", "tafransist",
    "taɛrabt", "yevɣa", "yebɣa", "massil", "dihya", "ferhat",
    "masin", "tiziri", "lezzayer", "tmurt", "takabylit",
    "ruḥeɣ", "truḥeḍ", "iruḥ", "truḥ", "nuḥu", "truḥem", "ruḥen",
    "yeḥder", "teḥder", "ḥedreɣ", "yeḥdeṛ", "yeḥdaṛ",
    "muḥend", "lḥusin", "muḥemmed", "ḥmed", "ḥsisen", "muḥend-u-lḥusin",
}


def toks(s):
    return tokenize(normalize(s))


def eval_phrases(cor):
    d_tp = d_fp = d_fn = 0
    c_tp = c_fp = c_fn = 0
    sent_ok = 0
    wer_sys = wer_base = wer_den = 0
    clean_total = clean_touched = 0
    sug_total = sug_at1 = sug_at5 = 0
    fails = []

    for entree, gold in TESTS:
        obtenu = cor.corriger(entree).texte_corrige
        s, g, o = toks(entree), toks(gold), toks(obtenu)

        ge, se = editions(s, g), editions(s, o)
        c_tp += len(ge & se); c_fp += len(se - ge); c_fn += len(ge - se)
        gs, ss = spans(ge), spans(se)
        d_tp += len(gs & ss); d_fp += len(ss - gs); d_fn += len(gs - ss)

        for (i1, i2, repl) in ge:
            if i2 - i1 == 1 and len(repl) == 1:
                cand = [c["candidat"] for c in cor.top_candidats(s[i1], nb=5)]
                sug_total += 1
                if cand[:1] == [repl[0]]:
                    sug_at1 += 1
                if repl[0] in cand:
                    sug_at5 += 1

        exact = (o == g)
        sent_ok += int(exact)
        if not exact:
            fails.append((entree, gold, obtenu))

        wer_sys += Levenshtein.distance(o, g)
        wer_base += Levenshtein.distance(s, g)
        wer_den += max(len(g), 1)

        if s == g:
            clean_total += 1
            if o != s:
                clean_touched += 1

    n = len(TESTS)
    dp, dr, df1, _ = prf(d_tp, d_fp, d_fn)
    cp, cr, cf1, cf05 = prf(c_tp, c_fp, c_fn)
    wer_b, wer_s = wer_base / wer_den, wer_sys / wer_den
    err = (wer_b - wer_s) / wer_b if wer_b else 0.0

    print(f"\n  ── Phrases gold ({n}) ──                    │ v1 (référence)")
    print(f"     Exact match : {sent_ok}/{n} = {sent_ok/n:.1%}"
          f"{'':<14}│ {V1['exact']}")
    print(f"     Détection   : P {dp:5.1%}  R {dr:5.1%}  F1 {df1:5.1%}  │ {V1['det']}")
    print(f"     Correction  : P {cp:5.1%}  R {cr:5.1%}  F1 {cf1:5.1%}  "
          f"F0.5 {cf05:5.1%}  │ {V1['corr']}")
    print(f"     WER         : {wer_b:.1%} → {wer_s:.1%}  (ERR {err:.1%})"
          f"{'':<6}│ {V1['wer']}")
    tx = clean_touched / clean_total if clean_total else 0.0
    print(f"     Sur-correction : {clean_touched}/{clean_total} = {tx:.1%}"
          f"{'':<13}│ {V1['surcorr']}")
    if sug_total:
        print(f"     Gold dans top-5 candidats : {sug_at5}/{sug_total}"
              f"  (recall@1 {sug_at1}/{sug_total})")
    return fails


def filet_iso(cor, n=1000, seed=0):
    """Fautes d'un caractère sur des mots isolés des dictionnaires."""
    rng = random.Random(seed)
    vocab = sorted(m for m in (set(cor.res.lexcat) | cor.res.amyag)
                   if _BON_MOT.match(m))
    rng.shuffle(vocab)
    vocab = vocab[:n]
    tot = n_ok = n_in5 = n_fail = n_fail_in5 = 0
    for w in vocab:
        t = _typo(rng, w)
        if t == w:
            continue
        tot += 1
        out = normalize(cor.corriger(t).texte_corrige)
        cands = [c["candidat"] for c in cor.top_candidats(t, nb=5)]
        ok, in5 = (out == w), (w in cands)
        n_ok += ok; n_in5 += in5
        if not ok:
            n_fail += 1; n_fail_in5 += in5
    return tot, n_ok, n_in5, n_fail, n_fail_in5


def filet_corpus(cor, n=200, seed=1, max_scan=200000):
    """Fautes injectées dans de vraies phrases du corpus (contexte réel)."""
    rng = random.Random(seed)
    corpus = next((DATA / f for f in ("corpus_kabylen.txt", "corpus_kenlm.txt")
                   if (DATA / f).exists()), None)
    if corpus is None:
        return None, None
    # Même ensemble de mots valides que la v1, sinon on ne compare plus rien
    lex_v1 = ({m for m, f in cor.res.freq.items() if f >= 50}
              | MOTS_MANUELS_V1 | set(cor.res.lexcat))
    phrases = []
    with open(corpus, encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i >= max_scan or len(phrases) >= n * 30:
                break
            t = toks(line)
            if 5 <= len(t) <= 14:
                phrases.append(t)
    rng.shuffle(phrases)
    tot = n_ok = n_in5 = n_fail = n_fail_in5 = 0
    for orig_toks in phrases:
        if tot >= n:
            break
        idxs = [i for i, w in enumerate(orig_toks)
                if _BON_TOK.match(w) and (w in lex_v1 or w in cor.res.amyag)]
        if not idxs:
            continue
        idx = rng.choice(idxs)
        orig = orig_toks[idx]
        t = _typo(rng, orig)
        if t == orig:
            continue
        s_typo = list(orig_toks); s_typo[idx] = t
        s = toks(" ".join(s_typo))
        g = toks(" ".join(orig_toks))
        o = toks(cor.corriger(" ".join(s_typo)).texte_corrige)
        ge, se = editions(s, g), editions(s, o)
        if not ge:
            continue
        tot += 1
        pipeline_ok = len(ge - se) == 0
        in5 = orig in [c["candidat"] for c in cor.top_candidats(t, nb=5)]
        n_ok += pipeline_ok; n_in5 += in5
        if not pipeline_ok:
            n_fail += 1; n_fail_in5 += in5
    return corpus.name, (tot, n_ok, n_in5, n_fail, n_fail_in5)


def _print_filet(titre, res, ref):
    tot, n_ok, n_in5, n_fail, n_fail_in5 = res
    print(f"\n  ── {titre} ──")
    print(f"     Pipeline retrouve le mot  : {n_ok}/{tot} = {n_ok/tot:.1%}"
          f"     │ v1 : {ref}")
    print(f"     Bon mot dans le top-5     : {n_in5}/{tot} = {n_in5/tot:.1%}")
    if n_fail:
        print(f"     Raté mais dans le top-5   : "
              f"{n_fail_in5}/{n_fail} = {n_fail_in5/n_fail:.1%}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true",
                    help="filet réduit (150 mots isolés, 40 phrases corpus)")
    args = ap.parse_args()
    n_iso, n_ctx = (150, 40) if args.quick else (1000, 200)

    print("━" * 70)
    cor = KabyleCorrecteurV2(verbose=False).charger()
    print("━" * 70)

    fails = eval_phrases(cor)

    _print_filet(f"Filet mots isolés (n={n_iso})",
                 filet_iso(cor, n=n_iso), V1["iso"])
    name, cres = filet_corpus(cor, n=n_ctx)
    if cres:
        _print_filet(f"Filet en contexte « {name} » (n={cres[0]})",
                     cres, V1["ctx"])

    if fails:
        print("\n  ── Phrases non exactes (v2) ──")
        for e, g, o in fails:
            print(f"     entrée   : {e}")
            print(f"       attendu: {g}")
            print(f"       obtenu : {o}")
    print("━" * 70)


if __name__ == "__main__":
    main()
