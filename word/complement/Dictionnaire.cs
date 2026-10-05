// Fenetre « Mon dictionnaire » : voir, ajouter et retirer des mots.

using System;
using System.Collections.Generic;
using System.Drawing;
using System.Linq;
using System.Windows.Forms;

namespace KabBoardPont
{
    internal sealed class Dictionnaire : Form
    {
        private readonly TextBox _filtre;
        private readonly ListBox _liste;
        private readonly Label _compte;
        private readonly TextBox _nouveau;
        private List<string> _mots = new List<string>();

        public Dictionnaire()
        {
            Text = "Mon dictionnaire (Kab-board)";
            Font = new Font("Segoe UI", 9f);
            FormBorderStyle = FormBorderStyle.FixedDialog;
            MaximizeBox = MinimizeBox = false;
            ShowInTaskbar = false;
            StartPosition = FormStartPosition.CenterParent;
            ClientSize = new Size(380, 470);
            Padding = new Padding(12);

            Label explication = new Label
            {
                Dock = DockStyle.Top, Height = 36,
                Text = "Le correcteur ne signale plus ces mots. Ils sont rangés dans un fichier à vous, sur cet ordinateur.",
            };
            _filtre = new TextBox { Dock = DockStyle.Top };
            _filtre.TextChanged += delegate { Remplir(); };
            Label chercher = new Label { Dock = DockStyle.Top, Height = 20, Text = "Chercher :", TextAlign = ContentAlignment.BottomLeft };

            _liste = new ListBox { Dock = DockStyle.Fill, Font = new Font("Segoe UI", 11f), IntegralHeight = false, SelectionMode = SelectionMode.MultiExtended };
            _liste.KeyDown += (s, e) => { if (e.KeyCode == Keys.Delete) Retirer(); };
            _compte = new Label { Dock = DockStyle.Bottom, Height = 22, ForeColor = Color.DimGray, TextAlign = ContentAlignment.MiddleLeft };

            Button retirer = new Button { Text = "Retirer de mon dictionnaire", Dock = DockStyle.Bottom, Height = 30 };
            retirer.Click += delegate { Retirer(); };

            _nouveau = new TextBox { Dock = DockStyle.Fill, Margin = new Padding(0, 4, 4, 4) };
            Button ajouter = new Button { Text = "Ajouter", Dock = DockStyle.Fill, Margin = new Padding(0, 2, 0, 2) };
            ajouter.Click += delegate { Ajouter(); };
            _nouveau.KeyDown += (s, e) => { if (e.KeyCode == Keys.Enter) { Ajouter(); e.SuppressKeyPress = true; } };
            TableLayoutPanel ligneAjout = new TableLayoutPanel { Dock = DockStyle.Bottom, Height = 34, ColumnCount = 2 };
            ligneAjout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 70f));
            ligneAjout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 30f));
            ligneAjout.Controls.Add(_nouveau, 0, 0);
            ligneAjout.Controls.Add(ajouter, 1, 0);
            Label ajoutTitre = new Label { Dock = DockStyle.Bottom, Height = 22, Text = "Ajouter un mot :", TextAlign = ContentAlignment.BottomLeft };

            Button fermer = new Button { Text = "Fermer", Dock = DockStyle.Bottom, Height = 30, DialogResult = DialogResult.OK };
            CancelButton = fermer;

            // Le dernier ajoute est le plus a l'exterieur : la liste remplit ce qui reste.
            Controls.Add(_liste);
            Controls.Add(_compte);
            Controls.Add(retirer);
            Controls.Add(new Panel { Dock = DockStyle.Bottom, Height = 8 });
            Controls.Add(ajoutTitre);
            Controls.Add(ligneAjout);
            Controls.Add(new Panel { Dock = DockStyle.Bottom, Height = 8 });
            Controls.Add(fermer);
            Controls.Add(_filtre);
            Controls.Add(chercher);
            Controls.Add(explication);

            Recharger();
        }

        private void Recharger()
        {
            _mots = Reglages.MesMots();
            Remplir();
        }

        private void Remplir()
        {
            string f = _filtre.Text.Trim();
            _liste.BeginUpdate();
            _liste.Items.Clear();
            foreach (string m in _mots.Where(m => f.Length == 0 || m.IndexOf(f, StringComparison.CurrentCultureIgnoreCase) >= 0))
                _liste.Items.Add(m);
            _liste.EndUpdate();
            _compte.Text = _mots.Count == 0 ? "Aucun mot pour l'instant."
                : _mots.Count + " mot(s)" + (f.Length > 0 ? ", " + _liste.Items.Count + " affiché(s)" : "") + ".";
        }

        private void Retirer()
        {
            List<string> choisis = _liste.SelectedItems.Cast<string>().ToList();
            if (choisis.Count == 0) return;
            foreach (string m in choisis) Reglages.OublierMot(m);
            Recharger();
        }

        private void Ajouter()
        {
            string mot = _nouveau.Text.Trim();
            if (mot.Length == 0) return;
            if (!_mots.Any(m => string.Equals(m, mot, StringComparison.OrdinalIgnoreCase))) Reglages.AjouterMot(mot);
            _nouveau.Clear();
            _filtre.Clear();
            Recharger();
            _liste.SelectedItem = _mots.FirstOrDefault(m => string.Equals(m, mot, StringComparison.OrdinalIgnoreCase));
        }
    }
}
