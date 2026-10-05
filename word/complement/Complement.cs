// Complement Word (ProgId KabBoard.Pont). Garder le CLSID : c'est lui qui fait
// remplacer la version installee lors d'une mise a jour.
// Le moteur Python (moteur\, python\) tourne a part, joint par Moteur.cs.
// Compilation : setup\construire.ps1.

using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Text;
using System.Windows.Forms;
using Office = Microsoft.Office.Core;
using Word = Microsoft.Office.Interop.Word;

[assembly: ComVisible(false)]
[assembly: AssemblyVersion("0.3.0.0")]
[assembly: AssemblyTitle("Kab-board pour Word")]

namespace KabBoardPont
{
    [ComImport, Guid("B65AD801-ABAF-11D0-BB8B-00A0C90F2744"), InterfaceType(ComInterfaceType.InterfaceIsDual)]
    public interface IDTExtensibility2
    {
        [DispId(1)]
        void OnConnection([In, MarshalAs(UnmanagedType.IDispatch)] object application, [In] int mode,
                          [In, MarshalAs(UnmanagedType.IDispatch)] object complement,
                          [In, MarshalAs(UnmanagedType.SafeArray, SafeArraySubType = VarEnum.VT_VARIANT)] ref Array personnalise);
        [DispId(2)]
        void OnDisconnection([In] int mode,
                             [In, MarshalAs(UnmanagedType.SafeArray, SafeArraySubType = VarEnum.VT_VARIANT)] ref Array personnalise);
        [DispId(3)]
        void OnAddInsUpdate([In, MarshalAs(UnmanagedType.SafeArray, SafeArraySubType = VarEnum.VT_VARIANT)] ref Array personnalise);
        [DispId(4)]
        void OnStartupComplete([In, MarshalAs(UnmanagedType.SafeArray, SafeArraySubType = VarEnum.VT_VARIANT)] ref Array personnalise);
        [DispId(5)]
        void OnBeginShutdown([In, MarshalAs(UnmanagedType.SafeArray, SafeArraySubType = VarEnum.VT_VARIANT)] ref Array personnalise);
    }

    internal sealed class Panneau
    {
        public Office.CustomTaskPane Ctp;
        public Volet Volet;
        public Word.Window Fenetre;
    }

    internal sealed class RelectureEnCours
    {
        public Word.Document Document;
        public Word.Window Fenetre;
        public bool Selection;
        public int ZoneDebut, ZoneFin;
        public List<Morceau> Morceaux;
        public string Graphie;
        public volatile bool Annulee;
    }

    [ComVisible(true), Guid("55EF5C5B-F90E-4A75-B0BD-D3B405816891"), ProgId("KabBoard.Pont")]
    [ClassInterface(ClassInterfaceType.AutoDispatch)]
    public class Pont : IDTExtensibility2, Office.IRibbonExtensibility, Office.ICustomTaskPaneConsumer
    {
        private const int PropositionsMenu = 6;
        private const int TexteMax = 20000;  // service.py refuse au-dela
        private static readonly string[] MenusContextuels =
            { "ContextMenuText", "ContextMenuSpell", "ContextMenuGrammar", "ContextMenuTextTable" };

        private Word.Application _word;
        private Office.ICTPFactory _fabrique;
        private Office.IRibbonUI _ruban;
        private Moteur _moteur;
        private Control _fil;
        private Timer _horloge;
        private readonly List<Panneau> _panneaux = new List<Panneau>();
        private readonly List<Relecture> _relectures = new List<Relecture>();
        private RelectureEnCours _enCours;
        private bool _occupe;

        private Micro _micro;
        private Word.Window _dicteeFenetre;
        private bool _transcription;

        private Signale _menuSignale;
        private Relecture _menuRelecture;
        private Word.Window _menuFenetre;

        [DllImport("user32.dll")]
        private static extern bool IsWindowEnabled(IntPtr fenetre);

        // Word

        public void OnConnection(object application, int mode, object complement, ref Array personnalise)
        {
            try
            {
                _word = (Word.Application)application;
                _fil = new Control();
                _fil.CreateControl();
                IntPtr poignee = _fil.Handle;

                _moteur = new Moteur(Path.GetDirectoryName(typeof(Pont).Assembly.Location));
                _moteur.Change += delegate { SurFil(MoteurChange); };
                _moteur.Demarrer();

                Word.ApplicationEvents4_Event evenements = (Word.ApplicationEvents4_Event)_word;
                evenements.WindowSelectionChange += SelectionChangee;
                evenements.WindowBeforeRightClick += AvantClicDroit;
                evenements.DocumentBeforeSave += AvantEnregistrement;
                evenements.DocumentBeforePrint += AvantImpression;
                evenements.DocumentBeforeClose += AvantFermeture;

                _horloge = new Timer { Interval = 300 };
                _horloge.Tick += Horloge;
            }
            catch (Exception e)
            {
                Journal.Noter("OnConnection", e);
            }
        }

        public void OnDisconnection(int mode, ref Array personnalise)
        {
            try
            {
                if (_horloge != null) _horloge.Stop();
                if (_micro != null) { _micro.Dispose(); _micro = null; }
                if (_word != null)
                {
                    Word.ApplicationEvents4_Event evenements = (Word.ApplicationEvents4_Event)_word;
                    evenements.WindowSelectionChange -= SelectionChangee;
                    evenements.WindowBeforeRightClick -= AvantClicDroit;
                    evenements.DocumentBeforeSave -= AvantEnregistrement;
                    evenements.DocumentBeforePrint -= AvantImpression;
                    evenements.DocumentBeforeClose -= AvantFermeture;
                }
                foreach (Relecture r in _relectures.ToList())
                {
                    try { Modification.Faire(r.Document, "Kab-board : soulignés", true, r.ToutDemarquer); } catch { }
                }
                _relectures.Clear();
            }
            catch (Exception e)
            {
                Journal.Noter("OnDisconnection", e);
            }
            finally
            {
                if (_moteur != null) _moteur.Dispose();
                _moteur = null;
                if (_fil != null) _fil.Dispose();
                _word = null;
            }
        }

        public void OnAddInsUpdate(ref Array personnalise) { }
        public void OnStartupComplete(ref Array personnalise) { }
        public void OnBeginShutdown(ref Array personnalise) { }

        public void CTPFactoryAvailable(Office.ICTPFactory fabrique)
        {
            _fabrique = fabrique;
        }

        // Repasser sur le fil de Word, depuis le moteur ou une relecture.
        private void SurFil(Action action)
        {
            try
            {
                if (_fil == null || !_fil.IsHandleCreated) return;
                _fil.BeginInvoke((MethodInvoker)delegate
                {
                    try { action(); }
                    catch (Exception e) { Journal.Noter("fil de Word", e); }
                });
            }
            catch { }
        }

        private void MoteurChange()
        {
            foreach (Panneau p in PanneauxVivants())
            {
                if (_enCours == null || _moteur.Etat != EtatMoteur.Pret) p.Volet.MontrerMessage(_moteur.Message);
                RafraichirVolet(p);
            }
            InvaliderRuban();
        }

        // Ruban

        public string GetCustomUI(string identifiantRuban)
        {
            StringBuilder x = new StringBuilder();
            x.Append("<customUI xmlns=\"http://schemas.microsoft.com/office/2009/07/customui\" onLoad=\"RubanCharge\">");
            x.Append("<ribbon><tabs><tab id=\"kabOnglet\" label=\"Kab-board\">");
            x.Append("<group id=\"kabGroupe\" label=\"Kabyle\">");
            x.Append("<button id=\"kabVolet\" label=\"Correcteur kabyle\" size=\"large\" imageMso=\"SpellingAndGrammar\" onAction=\"BasculerVolet\"");
            x.Append(" screentip=\"Volet Kab-board\" supertip=\"Ouvre ou ferme le volet de relecture. Tout se calcule sur cet ordinateur.\"/>");
            x.Append("<button id=\"kabRelire\" label=\"Relire le document\" onAction=\"RelireDocumentRuban\" getEnabled=\"PeutRelire\"/>");
            x.Append("<button id=\"kabRelireSel\" label=\"Relire la sélection\" onAction=\"RelireSelectionRuban\" getEnabled=\"PeutRelire\"");
            x.Append(" supertip=\"Relit les paragraphes sélectionnés, ou celui du curseur.\"/>");
            x.Append("<button id=\"kabDicter\" getLabel=\"EtiquetteDictee\" onAction=\"DicterRuban\" getEnabled=\"PeutDicter\"");
            x.Append(" supertip=\"Dictez en kabyle : le texte s'écrit au curseur, dans la graphie choisie. 30 secondes au plus. Le son ne quitte pas cet ordinateur.\"/>");
            x.Append("<dropDown id=\"kabGraphie\" label=\"Graphie\" sizeString=\"Écrire avec v ...\" getSelectedItemIndex=\"IndexGraphie\" onAction=\"ChoisirGraphie\">");
            x.Append("<item id=\"kabGraphieV\" label=\"Écrire avec v\"/><item id=\"kabGraphieB\" label=\"Écrire avec b\"/></dropDown>");
            x.Append("</group>");
            x.Append("<group id=\"kabOutils\" label=\"Outils\">");
            x.Append("<button id=\"kabSansFr\" label=\"Ne pas vérifier en français\" size=\"large\" imageMso=\"SetLanguage\" onAction=\"SansFrancaisRuban\"");
            x.Append(" screentip=\"Texte kabyle : ne pas vérifier en français\" supertip=\"Marque la sélection, ou tout le document s'il n'y a pas de sélection, comme texte à ne pas vérifier : les vagues rouges du correcteur français disparaissent.\"/>");
            x.Append("<button id=\"kabAvecFr\" label=\"Revérifier en français\" onAction=\"AvecFrancaisRuban\"");
            x.Append(" supertip=\"Rend la sélection, ou tout le document, au correcteur de Word.\"/>");
            x.Append("<button id=\"kabDico\" label=\"Mon dictionnaire\" onAction=\"DictionnaireRuban\"");
            x.Append(" supertip=\"Les mots que le correcteur ne signale plus : les voir, en retirer, en ajouter.\"/>");
            x.Append("</group></tab></tabs></ribbon>");

            x.Append("<contextMenus>");
            foreach (string menu in MenusContextuels)
            {
                x.Append("<contextMenu idMso=\"").Append(menu).Append("\">");
                for (int i = 0; i < PropositionsMenu; i++)
                {
                    x.Append("<button id=\"kab").Append(menu).Append("P").Append(i).Append("\" tag=\"").Append(i)
                     .Append("\" getLabel=\"EtiquetteProposition\" getVisible=\"VisibleProposition\" onAction=\"ChoisirProposition\" insertBeforeMso=\"Cut\"");
                    if (i == 0) x.Append(" imageMso=\"AcceptInvitation\"");
                    x.Append("/>");
                }
                x.Append("<button id=\"kab").Append(menu).Append("Garder\" label=\"Garder mon mot\" getVisible=\"VisibleMenuMot\" onAction=\"GarderMenu\" insertBeforeMso=\"Cut\"/>");
                x.Append("<button id=\"kab").Append(menu).Append("Ajouter\" label=\"Ajouter à mon dictionnaire\" getVisible=\"VisibleMenuMot\" onAction=\"AjouterMenu\" insertBeforeMso=\"Cut\"/>");
                x.Append("</contextMenu>");
            }
            x.Append("</contextMenus></customUI>");
            return x.ToString();
        }

        public void RubanCharge(Office.IRibbonUI ruban)
        {
            _ruban = ruban;
        }

        private void InvaliderRuban()
        {
            try { if (_ruban != null) _ruban.Invalidate(); } catch { }
        }

        public void BasculerVolet(Office.IRibbonControl controle)
        {
            Proteger("BasculerVolet", () =>
            {
                Word.Window w = FenetreActive();
                if (w == null) return;
                Panneau p = PanneauDe(w);
                if (p == null) OuvrirPanneau(w);
                else p.Ctp.Visible = !p.Ctp.Visible;
            });
        }

        public void RelireDocumentRuban(Office.IRibbonControl controle)
        {
            Proteger("RelireDocument", () => { Word.Window w = FenetreActive(); if (w != null) Relire(w, false); });
        }

        public void RelireSelectionRuban(Office.IRibbonControl controle)
        {
            Proteger("RelireSelection", () => { Word.Window w = FenetreActive(); if (w != null) Relire(w, true); });
        }

        public bool PeutRelire(Office.IRibbonControl controle)
        {
            return _moteur != null && _moteur.Pret && _enCours == null;
        }

        public string EtiquetteDictee(Office.IRibbonControl controle)
        {
            return _micro != null ? "Arrêter la dictée" : "Dicter";
        }

        public bool PeutDicter(Office.IRibbonControl controle)
        {
            return DicteeAutorisee();
        }

        public void DicterRuban(Office.IRibbonControl controle)
        {
            Proteger("Dicter", () => { Word.Window w = FenetreActive(); if (w != null) BasculerDictee(w); });
        }

        public int IndexGraphie(Office.IRibbonControl controle)
        {
            return Reglages.Graphie == "b" ? 1 : 0;
        }

        public void ChoisirGraphie(Office.IRibbonControl controle, string identifiant, int index)
        {
            Proteger("ChoisirGraphie", () => ChangerGraphie(index == 1 ? "b" : "v"));
        }

        public void SansFrancaisRuban(Office.IRibbonControl controle)
        {
            Proteger("SansFrancais", () => { Word.Window w = FenetreActive(); if (w != null) SansFrancais(w); });
        }

        public void AvecFrancaisRuban(Office.IRibbonControl controle)
        {
            Proteger("AvecFrancais", () => { Word.Window w = FenetreActive(); if (w != null) Verification(w, false); });
        }

        public void DictionnaireRuban(Office.IRibbonControl controle)
        {
            Proteger("Dictionnaire", OuvrirDictionnaire);
        }

        // Menu du clic droit

        private void AvantClicDroit(Word.Selection selection, ref bool annuler)
        {
            _menuSignale = null;
            _menuRelecture = null;
            _menuFenetre = null;
            try
            {
                Relecture r = RelectureDe(selection.Document);
                if (r != null && !r.Masquee && _enCours == null)
                {
                    r.Resynchroniser();
                    Signale s = r.SignaleA(selection.Start);
                    if (s != null)
                    {
                        _menuSignale = s;
                        _menuRelecture = r;
                        _menuFenetre = FenetreActive();
                    }
                }
            }
            catch (Exception e)
            {
                Journal.Noter("clic droit", e);
            }
            InvaliderRuban();
        }

        private static int Rang(Office.IRibbonControl controle)
        {
            int i;
            return int.TryParse(controle.Tag, NumberStyles.Integer, CultureInfo.InvariantCulture, out i) ? i : -1;
        }

        public bool VisibleProposition(Office.IRibbonControl controle)
        {
            int i = Rang(controle);
            return _menuSignale != null && i >= 0 && i < _menuSignale.Propositions.Count;
        }

        public string EtiquetteProposition(Office.IRibbonControl controle)
        {
            int i = Rang(controle);
            return VisibleProposition(controle) ? _menuSignale.Propositions[i] : "";
        }

        public bool VisibleMenuMot(Office.IRibbonControl controle)
        {
            return _menuSignale != null;
        }

        public void ChoisirProposition(Office.IRibbonControl controle)
        {
            Proteger("ChoisirProposition", () =>
            {
                int i = Rang(controle);
                Signale s = _menuSignale;
                if (s == null || i < 0 || i >= s.Propositions.Count || s.Etat != EtatMot.Ouvert) return;
                RemplacerSignale(_menuFenetre, _menuRelecture, s, s.Propositions[i], false, false);
            });
        }

        public void GarderMenu(Office.IRibbonControl controle)
        {
            Proteger("GarderMenu", () =>
            {
                if (_menuSignale != null && _menuSignale.Etat == EtatMot.Ouvert)
                    GarderSignale(_menuFenetre, _menuRelecture, _menuSignale, false);
            });
        }

        public void AjouterMenu(Office.IRibbonControl controle)
        {
            Proteger("AjouterMenu", () =>
            {
                if (_menuSignale != null && _menuSignale.Etat == EtatMot.Ouvert)
                    AjouterSignale(_menuFenetre, _menuSignale, false);
            });
        }

        // Volets

        private sealed class FenetreWord : IWin32Window
        {
            public FenetreWord(IntPtr poignee) { Handle = poignee; }
            public IntPtr Handle { get; private set; }
        }

        private Word.Window FenetreActive()
        {
            try { return _word.Windows.Count > 0 ? _word.ActiveWindow : null; }
            catch { return null; }
        }

        private static Word.Document DocumentDe(Word.Window w)
        {
            try { return w.Document; }
            catch { return null; }
        }

        // Deux enveloppes .NET peuvent designer le meme objet Word : on compare l'IUnknown.
        private static bool Meme(object a, object b)
        {
            if (a == null || b == null) return false;
            if (ReferenceEquals(a, b)) return true;
            IntPtr ua = IntPtr.Zero, ub = IntPtr.Zero;
            try
            {
                ua = Marshal.GetIUnknownForObject(a);
                ub = Marshal.GetIUnknownForObject(b);
                return ua == ub;
            }
            catch
            {
                return false;
            }
            finally
            {
                if (ua != IntPtr.Zero) Marshal.Release(ua);
                if (ub != IntPtr.Zero) Marshal.Release(ub);
            }
        }

        private List<Panneau> PanneauxVivants()
        {
            foreach (Panneau p in _panneaux.ToList())
            {
                if (DocumentDe(p.Fenetre) != null) continue;
                _panneaux.Remove(p);
                try { p.Ctp.Delete(); } catch { }
            }
            return _panneaux.ToList();
        }

        private Panneau PanneauDe(Word.Window w)
        {
            return PanneauxVivants().FirstOrDefault(p => Meme(p.Fenetre, w));
        }

        private Panneau OuvrirPanneau(Word.Window w)
        {
            Panneau p = PanneauDe(w);
            if (p == null)
            {
                if (_fabrique == null) return null;
                Volet.PontEnAttente = this;
                Volet.FenetreEnAttente = w;
                Volet.DernierCree = null;
                Office.CustomTaskPane ctp;
                try
                {
                    ctp = _fabrique.CreateCTP("KabBoard.VoletKabyle", "Kab-board", w);
                }
                finally
                {
                    Volet.PontEnAttente = null;
                    Volet.FenetreEnAttente = null;
                }
                Volet v = Volet.DernierCree ?? ctp.ContentControl as Volet;
                if (v == null || v.Pont != this)
                {
                    Journal.Noter("volet", "le volet n'a pas pu etre relie au complement");
                    try { ctp.Delete(); } catch { }
                    return null;
                }
                ctp.Width = 340;
                ctp.DockPosition = Office.MsoCTPDockPosition.msoCTPDockPositionRight;
                p = new Panneau { Ctp = ctp, Volet = v, Fenetre = w };
                _panneaux.Add(p);
                v.MontrerMessage(_moteur.Message);
                RafraichirVolet(p);
            }
            p.Ctp.Visible = true;
            return p;
        }

        private void RafraichirVolet(Panneau p)
        {
            if (p == null) return;
            p.Volet.Afficher(RelectureDe(DocumentDe(p.Fenetre)), _moteur != null && _moteur.Pret, _enCours != null);
            p.Volet.MontrerDictee(DicteeAutorisee(), _micro != null);
        }

        private void RafraichirVolets()
        {
            foreach (Panneau p in PanneauxVivants()) RafraichirVolet(p);
        }

        private void Message(Word.Window w, string texte)
        {
            Panneau p = w == null ? null : PanneauDe(w);
            if (p != null) p.Volet.MontrerMessage(texte);
        }

        private Relecture RelectureDe(Word.Document document)
        {
            if (document == null) return null;
            return _relectures.FirstOrDefault(r => Meme(r.Document, document));
        }

        private void Proteger(string ou, Action action)
        {
            try { action(); }
            catch (Exception e) { Journal.Noter(ou, e); }
        }

        // Relecture

        internal void Relire(Word.Window w, bool selection)
        {
            if (_enCours != null || _moteur == null || !_moteur.Pret) return;
            Word.Document document = DocumentDe(w);
            if (document == null) return;
            Panneau p = OuvrirPanneau(w);

            List<Morceau> morceaux = new List<Morceau>();
            int zoneDebut = int.MaxValue, zoneFin = 0, tropLongs = 0;
            Word.Paragraphs paragraphes = selection ? w.Selection.Range.Paragraphs : document.Paragraphs;
            foreach (Word.Paragraph paragraphe in paragraphes)
            {
                Word.Range plage = paragraphe.Range;
                zoneDebut = Math.Min(zoneDebut, plage.Start);
                zoneFin = Math.Max(zoneFin, plage.End);
                string texte = plage.Text;
                if (string.IsNullOrWhiteSpace(texte)) continue;
                if (texte.Length > TexteMax) { tropLongs++; continue; }
                morceaux.Add(new Morceau { Plage = plage, Texte = texte });
            }
            if (tropLongs > 0) Journal.Noter("relecture", tropLongs + " paragraphe(s) trop long(s) ignores");

            RelectureEnCours tache = new RelectureEnCours
            {
                Document = document, Fenetre = w, Selection = selection, ZoneDebut = zoneDebut, ZoneFin = zoneFin,
                Morceaux = morceaux, Graphie = Reglages.Graphie,
            };
            _enCours = tache;
            RafraichirVolets();
            InvaliderRuban();
            if (p != null) p.Volet.Progression(0, morceaux.Count);
            System.Threading.ThreadPool.QueueUserWorkItem(delegate { Travailler(tache); });
        }

        internal void AnnulerRelecture()
        {
            if (_enCours != null) _enCours.Annulee = true;
        }

        // Hors du fil de Word.
        private void Travailler(RelectureEnCours tache)
        {
            List<KeyValuePair<Morceau, List<MotSignale>>> resultats = new List<KeyValuePair<Morceau, List<MotSignale>>>();
            string souci = null;
            int total = tache.Morceaux.Count;
            for (int i = 0; i < total && !tache.Annulee && souci == null; i++)
            {
                int fait = i + 1;
                SurFil(() => { Panneau p = PanneauDe(tache.Fenetre); if (p != null && _enCours == tache) p.Volet.Progression(fait, total); });
                Morceau m = tache.Morceaux[i];
                for (int essai = 0; essai < 2; essai++)
                {
                    try
                    {
                        List<MotSignale> signales = _moteur.Relire(m.Texte, tache.Graphie);
                        if (signales.Count > 0) resultats.Add(new KeyValuePair<Morceau, List<MotSignale>>(m, signales));
                        break;
                    }
                    catch (MoteurIndisponible e)
                    {
                        // Le moteur redemarre : on l'attend, puis on reprend ce paragraphe.
                        if (essai == 1 || !AttendreMoteur(tache)) souci = e.Message;
                    }
                    catch (Exception e)
                    {
                        Journal.Noter("relecture d'un paragraphe", e);
                        break;
                    }
                }
            }
            SurFil(() => TerminerRelecture(tache, resultats, souci));
        }

        private bool AttendreMoteur(RelectureEnCours tache)
        {
            SurFil(() => Message(tache.Fenetre, "Le correcteur redémarre, la relecture reprendra toute seule…"));
            DateTime limite = DateTime.UtcNow.AddMinutes(5);
            while (DateTime.UtcNow < limite && !tache.Annulee)
            {
                if (_moteur.Pret) return true;
                if (_moteur.Etat == EtatMoteur.Panne) return false;
                System.Threading.Thread.Sleep(500);
            }
            return false;
        }

        private void TerminerRelecture(RelectureEnCours tache, List<KeyValuePair<Morceau, List<MotSignale>>> resultats, string souci)
        {
            _enCours = null;
            Panneau p = PanneauDe(tache.Fenetre);
            if (p != null) p.Volet.FinProgression();
            Word.Document document = tache.Document;

            if (tache.Annulee || DocumentDe(tache.Fenetre) == null)
            {
                Message(tache.Fenetre, "Relecture annulée.");
                RafraichirVolets();
                InvaliderRuban();
                return;
            }

            Relecture r = RelectureDe(document);
            if (r == null)
            {
                r = new Relecture(document);
                _relectures.Add(r);
            }
            Modification.Faire(document, "Kab-board : relecture", true, () =>
            {
                // Une relecture du document remplace la precedente ; celle d'une
                // selection ne remplace que ce qu'elle a relu.
                foreach (Signale ancien in r.Items.ToList())
                {
                    bool dansZone;
                    try { dansZone = !tache.Selection || (ancien.Plage.Start >= tache.ZoneDebut && ancien.Plage.End <= tache.ZoneFin); }
                    catch { dansZone = true; }
                    if (!dansZone) continue;
                    r.Demarquer(ancien);
                    r.Items.Remove(ancien);
                }
                HashSet<int> poses = new HashSet<int>(r.Items.Select(s => s.Plage.Start));
                foreach (KeyValuePair<Morceau, List<MotSignale>> kv in resultats)
                {
                    foreach (MotSignale m in kv.Value)
                    {
                        Word.Range plage = Relecture.Localiser(document, kv.Key, m);
                        if (plage == null || !poses.Add(plage.Start)) continue;
                        Signale s = new Signale { Plage = plage, Mot = m.Mot, Propositions = m.Propositions, Natures = m.Natures };
                        r.Items.Add(s);
                        r.Marquer(s);
                    }
                }
            });
            r.Trier();

            Signale premier = r.Items.FirstOrDefault(s =>
            {
                try { return s.Etat == EtatMot.Ouvert && s.Plage.Start >= tache.ZoneDebut; }
                catch { return false; }
            }) ?? r.Chercher(1);

            if (souci != null) Message(tache.Fenetre, "La relecture s'est arrêtée : " + souci);
            else if (r.Restants == 0) Message(tache.Fenetre, "Rien à signaler.");
            else Message(tache.Fenetre, r.Restants + " mot(s) à revoir. Cliquez sur un mot souligné, ou faites un clic droit dessus.");

            if (premier != null) Montrer(tache.Fenetre, r, premier, true);
            RafraichirVolets();
            InvaliderRuban();
        }

        private void Montrer(Word.Window w, Relecture r, Signale s, bool selectionner)
        {
            r.Aller(s);
            if (selectionner)
            {
                _occupe = true;
                try { s.Plage.Select(); }
                catch { }
                finally { _occupe = false; }
            }
            RafraichirVolet(PanneauDe(w));
        }

        private void Avancer(Word.Window w, Relecture r, bool selectionner)
        {
            Signale s = r.Restants > 0 ? r.Chercher(1) : null;
            if (s != null) Montrer(w, r, s, selectionner);
            else RafraichirVolet(PanneauDe(w));
        }

        private Relecture RelectureDeFenetre(Word.Window w)
        {
            Relecture r = RelectureDe(DocumentDe(w));
            if (r != null) r.Resynchroniser();
            return r;
        }

        internal void Naviguer(Word.Window w, int pas)
        {
            Relecture r = RelectureDeFenetre(w);
            if (r == null || r.Masquee) return;
            Signale s = r.Chercher(pas);
            if (s != null) Montrer(w, r, s, true);
            else RafraichirVolet(PanneauDe(w));
        }

        internal void Remplacer(Word.Window w, string forme, bool partout)
        {
            Relecture r = RelectureDeFenetre(w);
            if (r == null || r.Courant == null || r.Courant.Etat != EtatMot.Ouvert || string.IsNullOrEmpty(forme)) return;
            RemplacerSignale(w, r, r.Courant, forme, partout, true);
        }

        private void RemplacerSignale(Word.Window w, Relecture r, Signale s, string forme, bool partout, bool avancer)
        {
            List<Signale> cibles = partout
                ? r.Items.Where(x => x.Etat == EtatMot.Ouvert && x.Mot == s.Mot).ToList()
                : new List<Signale> { s };
            Modification.Faire(r.Document, partout ? "Kab-board : remplacer partout" : "Kab-board : remplacer", false,
                () => { foreach (Signale c in cibles) r.Remplacer(c, forme); });
            r.Aller(s);
            Message(w, partout
                ? "« " + s.Mot + " » remplacé par « " + forme + " » : " + cibles.Count + " fois."
                : "« " + s.Mot + " » remplacé par « " + forme + " ».");
            Avancer(w, r, avancer);
        }

        internal void Garder(Word.Window w)
        {
            Relecture r = RelectureDeFenetre(w);
            if (r == null || r.Courant == null || r.Courant.Etat != EtatMot.Ouvert) return;
            GarderSignale(w, r, r.Courant, true);
        }

        private void GarderSignale(Word.Window w, Relecture r, Signale s, bool avancer)
        {
            Modification.Faire(r.Document, "Kab-board : garder mon mot", true, () => r.Clore(s, EtatMot.Garde));
            r.Aller(s);
            Avancer(w, r, avancer);
        }

        internal void Ajouter(Word.Window w)
        {
            Relecture r = RelectureDeFenetre(w);
            if (r == null || r.Courant == null || r.Courant.Etat != EtatMot.Ouvert) return;
            AjouterSignale(w, r.Courant, true);
        }

        private void AjouterSignale(Word.Window w, Signale s, bool avancer)
        {
            Reglages.AjouterMot(s.Mot);
            foreach (Relecture r in _relectures)
            {
                List<Signale> memes = r.Items.Where(x => x.Etat == EtatMot.Ouvert
                    && string.Equals(x.Mot, s.Mot, StringComparison.OrdinalIgnoreCase)).ToList();
                if (memes.Count == 0) continue;
                Modification.Faire(r.Document, "Kab-board : ajouter à mon dictionnaire", true,
                    () => { foreach (Signale x in memes) r.Clore(x, EtatMot.Ajoute); });
            }
            Message(w, "« " + s.Mot + " » est dans votre dictionnaire.");
            Relecture courante = RelectureDe(DocumentDe(w));
            if (courante != null)
            {
                courante.Aller(s);
                Avancer(w, courante, avancer);
            }
            RafraichirVolets();
        }

        internal void Arreter(Word.Window w)
        {
            Relecture r = RelectureDe(DocumentDe(w));
            if (r == null) return;
            Modification.Faire(r.Document, "Kab-board : fin de la relecture", true, r.ToutDemarquer);
            _relectures.Remove(r);
            Message(w, "Relecture arrêtée : les soulignés sont retirés.");
            RafraichirVolets();
        }

        internal void RendreLeClavier(Word.Window w)
        {
            if (w == null) return;
            try { w.SetFocus(); }
            catch
            {
                try { w.Activate(); } catch { }
            }
        }

        // Dictee

        private bool DicteeAutorisee()
        {
            if (_micro != null) return true;   // pour pouvoir l'arreter
            return _moteur != null && _moteur.DicteePossible && !_transcription && _enCours == null;
        }

        internal void BasculerDictee(Word.Window w)
        {
            if (_micro != null) { FinirDictee(); return; }
            if (!DicteeAutorisee()) return;
            if (!Micro.Disponible)
            {
                Message(w, "Aucun micro n'est branché sur cet ordinateur.");
                return;
            }
            Micro m = new Micro();
            m.Plein += delegate { SurFil(FinirDictee); };
            try
            {
                m.Demarrer();
            }
            catch (Exception e)
            {
                m.Dispose();
                Journal.Noter("micro", e);
                Message(w, e.Message);
                return;
            }
            _micro = m;
            _dicteeFenetre = w;
            Message(w, "Je vous écoute… Cliquez sur « Arrêter la dictée » quand vous avez fini (" + Micro.DureeMaxSecondes + " secondes au plus).");
            RafraichirVolets();
            InvaliderRuban();
        }

        private void FinirDictee()
        {
            Micro m = _micro;
            Word.Window w = _dicteeFenetre;
            if (m == null) return;
            _micro = null;
            byte[] wav;
            try { wav = m.Arreter(); }
            finally { m.Dispose(); }

            if (wav.Length - 44 < Micro.Taux * 2 / 5)
            {
                Message(w, "Rien n'a été entendu.");
                RafraichirVolets();
                InvaliderRuban();
                return;
            }
            string fichier = Path.Combine(Reglages.DossierDonnees, "dictee.wav");
            Directory.CreateDirectory(Reglages.DossierDonnees);
            File.WriteAllBytes(fichier, wav);
            _transcription = true;
            Message(w, "Transcription…");
            RafraichirVolets();
            InvaliderRuban();

            string graphie = Reglages.Graphie;
            System.Threading.ThreadPool.QueueUserWorkItem(delegate
            {
                string texte = null, souci = null;
                try { texte = _moteur.Dicter(fichier, graphie); }
                catch (Exception e) { souci = e.Message; Journal.Noter("dictée", e); }
                finally { try { File.Delete(fichier); } catch { } }
                SurFil(() => InsererDictee(w, texte, souci));
            });
        }

        // Le texte dicte n'est pas corrige ; il reste selectionne pour « Relire la selection ».
        private void InsererDictee(Word.Window w, string texte, string souci)
        {
            _transcription = false;
            try
            {
                if (souci != null) { Message(w, "La dictée n'a pas abouti : " + souci); return; }
                if (string.IsNullOrEmpty(texte)) { Message(w, "Rien n'a été reconnu. Parlez un peu plus près du micro."); return; }
                Word.Document document = DocumentDe(w);
                if (document == null) return;
                Word.Range ici = w.Selection.Range;
                int debut = ici.Start;
                string avant = debut > 0 ? document.Range(debut - 1, debut).Text : "";
                string espace = !string.IsNullOrEmpty(avant) && !char.IsWhiteSpace(avant[0]) ? " " : "";
                Modification.Faire(document, "Kab-board : dictée", false, () => { ici.Text = espace + texte; });
                int fin = debut + espace.Length + texte.Length;
                _occupe = true;
                try { document.Range(fin - texte.Length, fin).Select(); }
                catch { }
                finally { _occupe = false; }
                Message(w, "Dictée insérée et sélectionnée : « Relire la sélection » la vérifie.");
            }
            finally
            {
                RafraichirVolets();
                InvaliderRuban();
            }
        }

        internal void ChangerGraphie(string graphie)
        {
            if (Reglages.Graphie == graphie) return;
            Reglages.Graphie = graphie;
            foreach (Panneau p in PanneauxVivants())
            {
                p.Volet.MontrerGraphie(graphie);
                if (RelectureDe(DocumentDe(p.Fenetre)) != null)
                    p.Volet.MontrerMessage("Graphie « " + graphie + " » : relisez le document pour l'appliquer.");
            }
            InvaliderRuban();
        }

        internal void OuvrirDictionnaire()
        {
            Word.Window w = FenetreActive();
            IntPtr poignee = IntPtr.Zero;
            try { if (w != null) poignee = new IntPtr(w.Hwnd); } catch { }
            using (Dictionnaire d = new Dictionnaire())
            {
                if (poignee != IntPtr.Zero) d.ShowDialog(new FenetreWord(poignee));
                else d.ShowDialog();
            }
        }

        internal void SansFrancais(Word.Window w)
        {
            Verification(w, true);
        }

        // NoProofing sur la selection, ou sur tout le document s'il n'y en a pas.
        private void Verification(Word.Window w, bool sansFrancais)
        {
            Word.Document document = DocumentDe(w);
            if (document == null) return;
            Word.Selection selection = w.Selection;
            bool zone = selection.Start != selection.End;
            Word.Range cible = zone ? selection.Range : document.Content;
            Modification.Faire(document, sansFrancais ? "Kab-board : ne pas vérifier en français" : "Kab-board : revérifier en français",
                false, () => cible.NoProofing = sansFrancais ? -1 : 0);
            Message(w, sansFrancais
                ? (zone ? "La sélection n'est plus vérifiée en français." : "Le document n'est plus vérifié en français.")
                : (zone ? "La sélection est de nouveau vérifiée en français." : "Le document est de nouveau vérifié en français."));
        }

        // Evenements de Word

        // Le volet suit le mot a revoir sous le curseur, sans deplacer le curseur.
        private void SelectionChangee(Word.Selection selection)
        {
            if (_occupe || _enCours != null) return;
            _occupe = true;
            try
            {
                Word.Window w = FenetreActive();
                Panneau p = PanneauDe(w);
                if (p == null || !p.Ctp.Visible) return;
                Relecture r = RelectureDe(DocumentDe(w));
                if (r == null || r.Masquee) return;
                r.Resynchroniser();
                Signale s = r.SignaleA(selection.Start);
                if (s == null || s == r.Courant) return;
                r.Aller(s);
                RafraichirVolet(p);
            }
            catch (Exception e)
            {
                Journal.Noter("selection", e);
            }
            finally
            {
                _occupe = false;
            }
        }

        // Les soulignes sont du vrai formatage : on les retire juste avant
        // d'enregistrer ou d'imprimer, et l'horloge les remet ensuite.
        private void AvantEnregistrement(Word.Document document, ref bool sousDialogue, ref bool annuler)
        {
            Masquer(document);
        }

        private void AvantImpression(Word.Document document, ref bool annuler)
        {
            Masquer(document);
        }

        private void Masquer(Word.Document document)
        {
            try
            {
                Relecture r = RelectureDe(document);
                if (r == null || r.Masquee || !r.Items.Any(s => s.Marque)) return;
                Modification.Faire(document, "Kab-board : soulignés", true, r.Masquer);
                _horloge.Start();
            }
            catch (Exception e)
            {
                Journal.Noter("masquer", e);
            }
        }

        // On remet les soulignes une fois l'enregistrement fini : quand aucune
        // boite de dialogue n'est plus ouverte (Enregistrer sous, Imprimer), et que
        // le document est enregistre, ou que l'utilisateur a renonce.
        private void Horloge(object envoyeur, EventArgs e)
        {
            bool attente = false;
            try
            {
                bool libre = FenetreLibre();
                foreach (Relecture r in _relectures.ToList())
                {
                    if (!r.Masquee) continue;
                    bool enregistre = false;
                    try { enregistre = r.Document.Saved; } catch { }
                    if (!libre || (!enregistre && DateTime.UtcNow - r.MasqueeDepuis < TimeSpan.FromSeconds(2)))
                    {
                        attente = true;
                        continue;
                    }
                    Modification.Faire(r.Document, "Kab-board : soulignés", true, r.Reafficher);
                }
            }
            catch (Exception ex)
            {
                Journal.Noter("horloge", ex);
            }
            if (!attente) _horloge.Stop();
        }

        private bool FenetreLibre()
        {
            try
            {
                Word.Window w = FenetreActive();
                return w == null || IsWindowEnabled(new IntPtr(w.Hwnd));
            }
            catch
            {
                return true;
            }
        }

        // Retirer les soulignes avant la fermeture evite l'invite « Enregistrer ? ».
        private void AvantFermeture(Word.Document document, ref bool annuler)
        {
            try
            {
                Relecture r = RelectureDe(document);
                if (r == null) return;
                Modification.Faire(document, "Kab-board : soulignés", true, r.ToutDemarquer);
                _relectures.Remove(r);
                RafraichirVolets();
            }
            catch (Exception e)
            {
                Journal.Noter("fermeture", e);
            }
        }
    }
}
