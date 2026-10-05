// Reglages persistants et journal du complement.

using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using Microsoft.Win32;

namespace KabBoardPont
{
    internal static class Reglages
    {
        private const string Cle = @"Software\Kab-board";

        // %LOCALAPPDATA%\kab-board : le port du moteur, « mon dictionnaire », le cache.
        public static string DossierDonnees
        {
            get
            {
                return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "kab-board");
            }
        }

        public static string FichierMesMots
        {
            get { return Path.Combine(DossierDonnees, "mots-a-moi.txt"); }
        }

        // v par defaut.
        public static string Graphie
        {
            get
            {
                try
                {
                    using (RegistryKey k = Registry.CurrentUser.OpenSubKey(Cle))
                    {
                        return k != null && Convert.ToString(k.GetValue("Graphie")) == "b" ? "b" : "v";
                    }
                }
                catch
                {
                    return "v";
                }
            }
            set
            {
                try
                {
                    using (RegistryKey k = Registry.CurrentUser.CreateSubKey(Cle))
                    {
                        k.SetValue("Graphie", value == "b" ? "b" : "v");
                    }
                }
                catch (Exception e)
                {
                    Journal.Noter("graphie", e);
                }
            }
        }

        // Meme format que service.py (mes_mots) : un mot par ligne. Le moteur relit
        // le fichier a chaque relecture.
        public static void AjouterMot(string mot)
        {
            mot = mot.Trim();
            if (mot.Length == 0) return;
            Directory.CreateDirectory(DossierDonnees);
            File.AppendAllText(FichierMesMots, mot + "\n", new UTF8Encoding(false));
        }

        public static void OublierMot(string mot)
        {
            string cle = mot.Trim().ToLowerInvariant();
            List<string> restants = MesMots().Where(m => m.ToLowerInvariant() != cle).ToList();
            Directory.CreateDirectory(DossierDonnees);
            File.WriteAllText(FichierMesMots, string.Join("\n", restants) + (restants.Count > 0 ? "\n" : ""),
                new UTF8Encoding(false));
        }

        public static List<string> MesMots()
        {
            try
            {
                return File.ReadAllLines(FichierMesMots, Encoding.UTF8)
                    .Select(l => l.Trim()).Where(l => l.Length > 0)
                    .Distinct(StringComparer.OrdinalIgnoreCase)
                    .OrderBy(l => l, StringComparer.CurrentCultureIgnoreCase).ToList();
            }
            catch
            {
                return new List<string>();
            }
        }
    }

    internal static class Journal
    {
        private static readonly object Verrou = new object();

        public static void Noter(string ou, Exception e)
        {
            Noter(ou, e.ToString());
        }

        public static void Noter(string ou, string message)
        {
            try
            {
                lock (Verrou)
                {
                    Directory.CreateDirectory(Reglages.DossierDonnees);
                    string fichier = Path.Combine(Reglages.DossierDonnees, "pont.log");
                    // Taille du journal bornee.
                    FileInfo info = new FileInfo(fichier);
                    if (info.Exists && info.Length > 1024 * 1024) info.Delete();
                    File.AppendAllText(fichier, DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss") + "  " + ou + " : " + message
                        + Environment.NewLine + Environment.NewLine, Encoding.UTF8);
                }
            }
            catch { }
        }
    }
}
