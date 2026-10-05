// Volet lateral : affichage seulement, la logique est dans le Pont.

using System;
using System.Drawing;
using System.Runtime.InteropServices;
using System.Windows.Forms;
using Word = Microsoft.Office.Interop.Word;

namespace KabBoardPont
{
    [ComVisible(true), Guid("E4A1A78A-6B42-460F-8467-6C69F9E6C81E"), ProgId("KabBoard.VoletKabyle")]
    [ClassInterface(ClassInterfaceType.AutoDispatch)]
    public class Volet : UserControl
    {
        // Word cree le volet lui-meme (CreateCTP, par son ProgId) : le Pont depose
        // ici, juste avant, a qui le volet appartient.
        internal static Pont PontEnAttente;
        internal static Word.Window FenetreEnAttente;
        internal static Volet DernierCree;

        private static readonly Color Vert = Color.FromArgb(0, 132, 63);
        private static readonly Color Bleu = Color.FromArgb(0, 114, 187);

        internal readonly Pont Pont;
        internal readonly Word.Window Fenetre;

        private readonly ToolTip _bulles = new ToolTip();
        private Label _etat;
        private RadioButton _v, _b;
        private Button _relireDoc, _relireSel, _annuler, _dicter;
        private TableLayoutPanel _ligneProgression;
        private ProgressBar _progression;
        private Label _repere;
        private TextBox _mot;
        private ListBox _propositions;
        private Button _remplacer, _remplacerPartout, _garder, _ajouter, _precedent, _suivant, _arreter;
        private Signale _affiche;
        private bool _majGraphie;

        public Volet()
        {
            Pont = PontEnAttente;
            Fenetre = FenetreEnAttente;
            DernierCree = this;
            Batir();
        }

        private void Batir()
        {
            SuspendLayout();
            Font = new Font("Segoe UI", 9f);
            BackColor = SystemColors.Window;
            Padding = new Padding(10, 6, 10, 6);
            AutoScroll = true;

            _etat = new Label { Dock = DockStyle.Top, Height = 48, ForeColor = Color.DimGray, Text = "Démarrage du correcteur…" };

            GroupBox graphie = new GroupBox { Text = "Graphie", Dock = DockStyle.Top, Height = 70 };
            _v = new RadioButton { Text = "Écrire avec v", Location = new Point(12, 20), AutoSize = true };
            _b = new RadioButton { Text = "Écrire avec b", Location = new Point(12, 44), AutoSize = true };
            _v.CheckedChanged += delegate { if (!_majGraphie && _v.Checked) Agir(() => Pont.ChangerGraphie("v")); };
            _b.CheckedChanged += delegate { if (!_majGraphie && _b.Checked) Agir(() => Pont.ChangerGraphie("b")); };
            graphie.Controls.Add(_v);
            graphie.Controls.Add(_b);

            _relireDoc = Bouton("Relire le document", () => Pont.Relire(Fenetre, false));
            _relireSel = Bouton("Relire la sélection", () => Pont.Relire(Fenetre, true));
            _bulles.SetToolTip(_relireSel, "Relit les paragraphes sélectionnés, ou celui du curseur.");

            _dicter = Bouton("Dicter", () => Pont.BasculerDictee(Fenetre));
            _bulles.SetToolTip(_dicter, "Dictez en kabyle : le texte s'écrit au curseur, dans la graphie choisie. 30 secondes au plus.");

            _progression = new ProgressBar { Dock = DockStyle.Fill, Margin = new Padding(2, 8, 2, 8) };
            _annuler = Bouton("Annuler", () => Pont.AnnulerRelecture());
            _ligneProgression = Rangee(new[] { 70f, 30f }, _progression, _annuler);
            _ligneProgression.Visible = false;

            _repere = new Label { Dock = DockStyle.Top, Height = 24, ForeColor = Color.DimGray, TextAlign = ContentAlignment.BottomLeft };
            _mot = new TextBox
            {
                Dock = DockStyle.Top, ReadOnly = true, TextAlign = HorizontalAlignment.Center,
                Font = new Font("Segoe UI", 12f, FontStyle.Bold), BackColor = SystemColors.Control,
            };
            _propositions = new ListBox
            {
                Dock = DockStyle.Top, Height = 150, Font = new Font("Segoe UI", 11f),
                DrawMode = DrawMode.OwnerDrawFixed, ItemHeight = 24, IntegralHeight = false,
            };
            _propositions.DrawItem += DessinerProposition;
            _propositions.DoubleClick += delegate { Agir(() => Pont.Remplacer(Fenetre, PropositionChoisie, false)); };

            _remplacer = Bouton("Remplacer", () => Pont.Remplacer(Fenetre, PropositionChoisie, false));
            _remplacerPartout = Bouton("Remplacer partout", () => Pont.Remplacer(Fenetre, PropositionChoisie, true));
            _bulles.SetToolTip(_remplacerPartout, "Remplace toutes les occurrences encore à revoir de ce mot.");
            _garder = Bouton("Garder mon mot", () => Pont.Garder(Fenetre));
            _ajouter = Bouton("Ajouter à mon dictionnaire", () => Pont.Ajouter(Fenetre));
            _precedent = Bouton("◀ Uzwir", () => Pont.Naviguer(Fenetre, -1));
            _suivant = Bouton("Uḍfir ▶", () => Pont.Naviguer(Fenetre, 1));
            _bulles.SetToolTip(_precedent, "Mot précédent");
            _bulles.SetToolTip(_suivant, "Mot suivant");
            _arreter = Bouton("Arrêter la relecture", () => Pont.Arreter(Fenetre));
            _arreter.Dock = DockStyle.Top;
            _arreter.Height = 32;
            _bulles.SetToolTip(_arreter, "Retire les soulignés de Kab-board.");

            LinkLabel dico = Lien("Mon dictionnaire…", () => Pont.OuvrirDictionnaire());
            LinkLabel francais = Lien("Texte kabyle : ne pas vérifier en français", () => Pont.SansFrancais(Fenetre));
            _bulles.SetToolTip(francais, "Enlève les vagues rouges du correcteur français, sur la sélection ou tout le document.");

            // Avec Dock = Top, le dernier ajoute est tout en haut.
            Control[] ordre =
            {
                francais, dico, Espace(10), _arreter, Espace(4),
                Rangee(null, _precedent, _suivant), Haute(Rangee(null, _garder, _ajouter), 46),
                Rangee(null, _remplacer, _remplacerPartout), Espace(4), _propositions, _mot, _repere,
                Rangee(null, _dicter), _ligneProgression, Rangee(null, _relireDoc, _relireSel), Espace(6), graphie, _etat,
            };
            foreach (Control c in ordre) Controls.Add(c);
            ResumeLayout();

            MontrerGraphie(Reglages.Graphie);
            Afficher(null, false, false);
            MontrerDictee(false, false);
        }

        private string PropositionChoisie
        {
            get { return _propositions.SelectedItem as string; }
        }

        private Button Bouton(string texte, Action action)
        {
            Button b = new Button { Text = texte, Dock = DockStyle.Fill, Margin = new Padding(2), UseVisualStyleBackColor = true };
            b.Click += delegate { Agir(action); };
            return b;
        }

        private LinkLabel Lien(string texte, Action action)
        {
            LinkLabel l = new LinkLabel { Text = texte, Dock = DockStyle.Top, Height = 22, TextAlign = ContentAlignment.MiddleLeft };
            l.LinkClicked += delegate { Agir(action); };
            return l;
        }

        private static Panel Espace(int hauteur)
        {
            return new Panel { Dock = DockStyle.Top, Height = hauteur };
        }

        // « Ajouter à mon dictionnaire » tient sur deux lignes.
        private static Control Haute(Control rangee, int hauteur)
        {
            rangee.Height = hauteur;
            return rangee;
        }

        private static TableLayoutPanel Rangee(float[] largeurs, params Control[] controles)
        {
            TableLayoutPanel t = new TableLayoutPanel
            {
                Dock = DockStyle.Top, Height = 34, ColumnCount = controles.Length, RowCount = 1,
                Margin = new Padding(0), Padding = new Padding(0),
            };
            for (int i = 0; i < controles.Length; i++)
            {
                float l = largeurs != null ? largeurs[i] : 100f / controles.Length;
                t.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, l));
                t.Controls.Add(controles[i], i, 0);
            }
            t.RowStyles.Add(new RowStyle(SizeType.Percent, 100f));
            return t;
        }

        // Une erreur dans un clic ne doit jamais remonter jusqu'a Word.
        private void Agir(Action action)
        {
            if (Pont == null) return;
            try
            {
                action();
            }
            catch (Exception e)
            {
                Journal.Noter("volet", e);
                MontrerMessage("Un souci est survenu : " + e.Message);
            }
            // Le clavier retourne au document : un Ctrl+Z annule bien la correction.
            Pont.RendreLeClavier(Fenetre);
        }

        private void DessinerProposition(object envoyeur, DrawItemEventArgs e)
        {
            if (e.Index < 0) return;
            e.DrawBackground();
            bool choisi = (e.State & DrawItemState.Selected) != 0;
            bool premier = e.Index == 0;
            Color couleur = choisi ? SystemColors.HighlightText
                : premier && _affiche != null && _affiche.ParContexte ? Vert : Bleu;
            using (Font police = premier ? new Font(e.Font, FontStyle.Bold) : new Font(e.Font, FontStyle.Regular))
            using (Brush pinceau = new SolidBrush(couleur))
            {
                e.Graphics.DrawString(Convert.ToString(_propositions.Items[e.Index]), police, pinceau, e.Bounds.Left + 4, e.Bounds.Top + 3);
            }
            e.DrawFocusRectangle();
        }

        internal void MontrerMessage(string texte)
        {
            _etat.Text = texte;
        }

        internal void MontrerDictee(bool possible, bool ecoute)
        {
            _dicter.Text = ecoute ? "Arrêter la dictée" : "Dicter";
            _dicter.Enabled = possible;
        }

        internal void MontrerGraphie(string graphie)
        {
            _majGraphie = true;
            _v.Checked = graphie != "b";
            _b.Checked = graphie == "b";
            _majGraphie = false;
        }

        internal void Progression(int fait, int total)
        {
            _ligneProgression.Visible = true;
            _progression.Maximum = Math.Max(1, total);
            _progression.Value = Math.Min(fait, _progression.Maximum);
            _etat.Text = "Relecture : paragraphe " + fait + " sur " + total + "…";
        }

        internal void FinProgression()
        {
            _ligneProgression.Visible = false;
        }

        internal void Afficher(Relecture r, bool moteurPret, bool enCours)
        {
            Signale s = r == null ? null : r.Courant;
            bool ouvert = s != null && s.Etat == EtatMot.Ouvert && !enCours;

            _relireDoc.Enabled = _relireSel.Enabled = moteurPret && !enCours;
            _remplacer.Enabled = _remplacerPartout.Enabled = _garder.Enabled = _ajouter.Enabled = ouvert;
            _precedent.Enabled = _suivant.Enabled = r != null && r.Restants > 0 && !enCours;
            _arreter.Enabled = r != null && r.Items.Count > 0 && !enCours;

            _affiche = ouvert ? s : null;
            _propositions.BeginUpdate();
            _propositions.Items.Clear();
            if (_affiche != null)
            {
                foreach (string p in _affiche.Propositions) _propositions.Items.Add(p);
                if (_propositions.Items.Count > 0) _propositions.SelectedIndex = 0;
            }
            _propositions.EndUpdate();
            _mot.Text = _affiche != null ? _affiche.Mot : "";

            if (r == null || r.Items.Count == 0) _repere.Text = "";
            else if (r.Restants == 0) _repere.Text = "Tout est revu : " + r.Items.Count + " mot(s) traités.";
            else if (_affiche == null) _repere.Text = r.Restants + " mot(s) à revoir.";
            else _repere.Text = "Mot " + (r.Position + 1) + " sur " + r.Items.Count + "  ·  " + r.Restants + " à revoir";
        }
    }
}
