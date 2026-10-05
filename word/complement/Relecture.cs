// Etat d'une relecture. A n'utiliser que sur le fil de Word.

using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.RegularExpressions;
using Word = Microsoft.Office.Interop.Word;

namespace KabBoardPont
{
    internal enum EtatMot { Ouvert, Remplace, Garde, Ajoute }

    internal sealed class Signale
    {
        public Word.Range Plage;
        public string Mot;
        public List<string> Propositions;
        public List<string> Natures;
        public EtatMot Etat = EtatMot.Ouvert;

        // Le souligne pose par nous, et celui que le mot avait avant.
        public bool Marque;
        public Word.WdUnderline AncienSouligne;
        public Word.WdColor AncienneCouleur;

        public bool ParContexte
        {
            get { return Natures.Count > 0 && Natures[0] == "contexte"; }
        }
    }

    // Un paragraphe envoye au moteur : sa plage, qui suit les modifications du
    // document, et son texte au moment de l'envoi.
    internal sealed class Morceau
    {
        public Word.Range Plage;
        public string Texte;
    }

    internal sealed class Relecture
    {
        // Vert : decide par le contexte. Bleu : candidats du mot seul.
        private const Word.WdColor Vert = (Word.WdColor)0x3F8400;
        private const Word.WdColor Bleu = (Word.WdColor)0xBB7200;
        private const int Indefini = 9999999;

        // Les mots comme les decoupe le moteur (service.py, MOT).
        private static readonly Regex MotRegex = new Regex(@"[\w\-ɣɛḍḥṭẓṣǧčṛ]+");

        public readonly Word.Document Document;
        public readonly List<Signale> Items = new List<Signale>();
        public int Position = -1;

        // Soulignes retires le temps d'un enregistrement ou d'une impression.
        public bool Masquee;
        public DateTime MasqueeDepuis;

        public Relecture(Word.Document document)
        {
            Document = document;
        }

        public Signale Courant
        {
            get { return Position >= 0 && Position < Items.Count ? Items[Position] : null; }
        }

        public int Restants
        {
            get { return Items.Count(s => s.Etat == EtatMot.Ouvert); }
        }

        // Le prochain mot encore a revoir, dans un sens ou dans l'autre, en boucle.
        public Signale Chercher(int pas)
        {
            int n = Items.Count;
            if (n == 0) return null;
            int depart = Position < 0 ? (pas > 0 ? -1 : 0) : Position;
            for (int k = 1; k <= n; k++)
            {
                int i = ((depart + pas * k) % n + n) % n;
                if (Items[i].Etat == EtatMot.Ouvert)
                {
                    Position = i;
                    return Items[i];
                }
            }
            return null;
        }

        public void Aller(Signale s)
        {
            Position = Items.IndexOf(s);
        }

        public Signale SignaleA(int position)
        {
            foreach (Signale s in Items)
            {
                if (s.Etat != EtatMot.Ouvert) continue;
                try
                {
                    if (position >= s.Plage.Start && position <= s.Plage.End) return s;
                }
                catch { }
            }
            return null;
        }

        // Un remplacement annule (Ctrl+Z) remet le mot : il redevient a revoir.
        // L'annulation ne recale pas toujours la plage sur le mot remis : on
        // regarde le texte qui commence au meme endroit, sur la longueur du mot.
        public void Resynchroniser()
        {
            foreach (Signale s in Items)
            {
                if (s.Etat != EtatMot.Remplace) continue;
                try
                {
                    int debut = s.Plage.Start;
                    Word.Range remis = Document.Range(debut, debut + s.Mot.Length);
                    if (remis.Text != s.Mot) continue;
                    s.Plage = remis;
                    s.Etat = EtatMot.Ouvert;
                    s.Marque = remis.Font.Underline == Word.WdUnderline.wdUnderlineWavy;
                }
                catch { }
            }
        }

        public void Marquer(Signale s)
        {
            if (s.Marque || s.Etat != EtatMot.Ouvert) return;
            Word.Font police = s.Plage.Font;
            s.AncienSouligne = police.Underline;
            s.AncienneCouleur = police.UnderlineColor;
            police.Underline = Word.WdUnderline.wdUnderlineWavy;
            police.UnderlineColor = s.ParContexte ? Vert : Bleu;
            s.Marque = true;
        }

        public void Demarquer(Signale s)
        {
            if (!s.Marque) return;
            s.Marque = false;
            try
            {
                Word.Font police = s.Plage.Font;
                police.Underline = (int)s.AncienSouligne == Indefini ? Word.WdUnderline.wdUnderlineNone : s.AncienSouligne;
                police.UnderlineColor = (int)s.AncienneCouleur == Indefini ? Word.WdColor.wdColorAutomatic : s.AncienneCouleur;
            }
            catch { }
        }

        public void ToutDemarquer()
        {
            foreach (Signale s in Items) Demarquer(s);
        }

        public void Masquer()
        {
            ToutDemarquer();
            Masquee = true;
            MasqueeDepuis = DateTime.UtcNow;
        }

        public void Reafficher()
        {
            Masquee = false;
            foreach (Signale s in Items) Marquer(s);
        }

        public void Remplacer(Signale s, string forme)
        {
            Demarquer(s);
            s.Plage.Text = forme;
            s.Etat = EtatMot.Remplace;
        }

        public void Clore(Signale s, EtatMot etat)
        {
            Demarquer(s);
            s.Etat = etat;
        }

        public void Trier()
        {
            Signale courant = Courant;
            Items.Sort((a, b) =>
            {
                try { return a.Plage.Start.CompareTo(b.Plage.Start); }
                catch { return 0; }
            });
            Position = courant == null ? -1 : Items.IndexOf(courant);
        }

        // Ou est, dans le document, un mot que le moteur a signale dans un
        // paragraphe ? D'abord a sa position ; si le texte a bouge depuis l'envoi,
        // ou si Word compte autrement (champs, objets), a son rang dans le
        // paragraphe, comme le moteur le compte.
        public static Word.Range Localiser(Word.Document document, Morceau morceau, MotSignale m)
        {
            try
            {
                string texte = morceau.Plage.Text ?? "";
                int debut = morceau.Plage.Start;
                if (texte == morceau.Texte && m.Debut >= 0)
                {
                    Word.Range r = document.Range(debut + m.Debut, debut + m.Debut + m.Mot.Length);
                    if (r.Text == m.Mot) return r;
                }

                int vus = 0;
                foreach (Match x in MotRegex.Matches(texte))
                {
                    if (!string.Equals(x.Value, m.Mot, StringComparison.OrdinalIgnoreCase)) continue;
                    if (vus++ != m.Rang) continue;
                    Word.Range r = document.Range(debut + x.Index, debut + x.Index + x.Length);
                    if (r.Text == m.Mot) return r;
                    break;
                }
                return Rechercher(morceau.Plage, m);
            }
            catch (Exception e)
            {
                Journal.Noter("localiser « " + m.Mot + " »", e);
                return null;
            }
        }

        // Dernier recours : la recherche de Word, mot entier.
        private static Word.Range Rechercher(Word.Range paragraphe, MotSignale m)
        {
            Word.Range r = paragraphe.Duplicate;
            int fin = paragraphe.End;
            Word.Find recherche = r.Find;
            recherche.ClearFormatting();
            recherche.Text = m.Mot;
            recherche.Forward = true;
            recherche.Wrap = Word.WdFindWrap.wdFindStop;
            recherche.MatchCase = false;
            recherche.MatchWholeWord = true;
            recherche.MatchWildcards = false;
            int vus = 0;
            while (recherche.Execute() && r.End <= fin)
            {
                if (vus++ == m.Rang) return r.Text == m.Mot ? r : null;
                r.SetRange(r.End, fin);
            }
            return null;
        }
    }

    internal static class Modification
    {
        // Toute l'operation en une seule entree d'annulation (un Ctrl+Z), sans
        // redessiner l'ecran a chaque mot ; et si seuls des soulignes changent, un
        // document enregistre le reste aux yeux de Word.
        public static void Faire(Word.Document document, string nom, bool soulignesSeulement, Action action)
        {
            Word.Application word = document.Application;
            bool enregistre = false;
            try { enregistre = document.Saved; } catch { }

            Word.UndoRecord annulation = null;
            try
            {
                annulation = word.UndoRecord;
                if (annulation.IsRecordingCustomRecord) annulation = null;
                else annulation.StartCustomRecord(nom);
            }
            catch
            {
                annulation = null;
            }

            bool ecran = true;
            try { ecran = word.ScreenUpdating; word.ScreenUpdating = false; } catch { }
            try
            {
                action();
            }
            finally
            {
                try { word.ScreenUpdating = ecran; } catch { }
                if (annulation != null) try { annulation.EndCustomRecord(); } catch { }
                if (soulignesSeulement && enregistre) try { document.Saved = true; } catch { }
            }
        }
    }
}
