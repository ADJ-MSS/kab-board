// Client du moteur Python : une requete JSON par ligne sur 127.0.0.1. Rejoint le
// moteur d'un autre Word s'il tourne deja, et le relance s'il tombe.

using System;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;

namespace KabBoardPont
{
    internal enum EtatMoteur { Demarrage, Pret, Panne }

    internal sealed class MotSignale
    {
        public string Mot;
        public int Rang;
        public int Debut;
        public List<string> Propositions = new List<string>();
        public List<string> Natures = new List<string>();
    }

    internal sealed class MoteurIndisponible : Exception
    {
        public MoteurIndisponible(string message) : base(message) { }
    }

    internal sealed class Moteur : IDisposable
    {
        public const string TextePret = "Correcteur prêt. Tout se calcule sur cet ordinateur.";
        private const string TexteDemarrage = "Démarrage du correcteur…";
        private const string TextePatience = "Démarrage du correcteur… Après une installation, la première fois peut prendre quelques minutes.";
        private const string TexteRelance = "Le correcteur s'est arrêté : il redémarre…";
        private const string TextePanne = "Le correcteur n'a pas pu démarrer. Fermez Word et rouvrez-le.";

        private static readonly TimeSpan AttentePort = TimeSpan.FromSeconds(60);
        private static readonly TimeSpan AvantPatience = TimeSpan.FromSeconds(20);
        private static readonly TimeSpan AttentePretMax = TimeSpan.FromMinutes(15);
        private const int RelancesMax = 5;
        private const int DelaiReponseMs = 300000;

        private readonly string _dossier;
        private readonly object _verrou = new object();
        private readonly JavaScriptSerializer _json = new JavaScriptSerializer { MaxJsonLength = int.MaxValue };
        private readonly ManualResetEvent _arret = new ManualResetEvent(false);
        private Thread _veilleur;
        private Process _processus;
        private TcpClient _lien;
        private StreamWriter _vers;
        private StreamReader _depuis;
        private volatile EtatMoteur _etat = EtatMoteur.Demarrage;
        private volatile string _message = TexteDemarrage;
        private volatile bool _rompu;
        private volatile bool _dictee;

        // Declenche sur le fil du veilleur : les abonnes repassent eux-memes sur
        // le fil de Word.
        public event EventHandler Change;

        public Moteur(string dossier)
        {
            _dossier = dossier;
        }

        public EtatMoteur Etat { get { return _etat; } }
        public string Message { get { return _message; } }
        public bool Pret { get { return _etat == EtatMoteur.Pret; } }

        public bool DicteePossible { get { return Pret && _dictee; } }

        public void Demarrer()
        {
            _veilleur = new Thread(Veiller) { IsBackground = true, Name = "Kab-board : moteur" };
            _veilleur.Start();
        }

        private void Veiller()
        {
            int relances = 0;
            while (!_arret.WaitOne(0))
            {
                try
                {
                    Brancher();
                    AttendrePret();
                    Changer(EtatMoteur.Pret, TextePret);
                    while (!_arret.WaitOne(2000))
                    {
                        if (_rompu || (_processus != null && _processus.HasExited)) break;
                    }
                    if (_arret.WaitOne(0)) return;
                    Journal.Noter("moteur", "le moteur s'est arrete, relance");
                }
                catch (OperationCanceledException)
                {
                    return;
                }
                catch (Exception e)
                {
                    Journal.Noter("moteur", e);
                }
                Fermer();
                if (++relances > RelancesMax)
                {
                    Changer(EtatMoteur.Panne, TextePanne);
                    return;
                }
                Changer(EtatMoteur.Demarrage, TexteRelance);
                if (_arret.WaitOne(2000)) return;
            }
        }

        private void Brancher()
        {
            _rompu = false;
            // Un autre Word a peut-etre deja lance le moteur.
            int port = LirePort();
            if (port > 0 && Connecter(port)) return;

            try { File.Delete(FichierPort); } catch { }
            _processus = Process.Start(Lancement());
            DateTime limite = DateTime.UtcNow + AttentePort;
            while (DateTime.UtcNow < limite)
            {
                if (_arret.WaitOne(250)) throw new OperationCanceledException();
                if (_processus.HasExited) throw new MoteurIndisponible("Le moteur s'est arrêté au démarrage.");
                port = LirePort();
                if (port > 0 && Connecter(port)) return;
            }
            throw new MoteurIndisponible("Le moteur n'a pas ouvert sa prise.");
        }

        private void AttendrePret()
        {
            DateTime debut = DateTime.UtcNow;
            Changer(EtatMoteur.Demarrage, _message == TexteRelance ? TexteRelance : TexteDemarrage);
            while (true)
            {
                Dictionary<string, object> etat = Demander(Requete("etat"));
                object pret, dictee;
                _dictee = etat.TryGetValue("dictee", out dictee) && dictee is bool && (bool)dictee;
                if (etat.TryGetValue("pret", out pret) && pret is bool && (bool)pret) return;
                if (_processus != null && _processus.HasExited) throw new MoteurIndisponible("Le moteur s'est arrêté en chargeant.");
                if (DateTime.UtcNow - debut > AttentePretMax) throw new MoteurIndisponible("Le moteur ne finit pas de charger.");
                if (DateTime.UtcNow - debut > AvantPatience && _etat == EtatMoteur.Demarrage && _message == TexteDemarrage)
                    Changer(EtatMoteur.Demarrage, TextePatience);
                if (_arret.WaitOne(500)) throw new OperationCanceledException();
            }
        }

        private ProcessStartInfo Lancement()
        {
            string exe = Path.Combine(_dossier, "moteur", "kab-moteur.exe");
            ProcessStartInfo depart;
            if (File.Exists(exe))
            {
                depart = new ProcessStartInfo(exe);
            }
            else
            {
                string service = Path.Combine(_dossier, "moteur", "service.py");
                string python = Path.Combine(_dossier, "python", "pythonw.exe");
                if (!File.Exists(service) || !File.Exists(python))
                    throw new MoteurIndisponible("Le moteur du correcteur est introuvable. Réinstallez kab-board.");
                depart = new ProcessStartInfo(python, "\"" + service + "\"");
            }
            depart.UseShellExecute = false;
            depart.CreateNoWindow = true;
            depart.WorkingDirectory = Path.GetDirectoryName(depart.FileName);
            return depart;
        }

        private static string FichierPort
        {
            get { return Path.Combine(Reglages.DossierDonnees, "port"); }
        }

        private static int LirePort()
        {
            try
            {
                int port;
                return int.TryParse(File.ReadAllText(FichierPort).Trim(), out port) ? port : 0;
            }
            catch
            {
                return 0;
            }
        }

        private bool Connecter(int port)
        {
            lock (_verrou)
            {
                FermerLien();
                try
                {
                    _lien = new TcpClient();
                    _lien.Connect("127.0.0.1", port);
                    _lien.ReceiveTimeout = DelaiReponseMs;
                    NetworkStream flux = _lien.GetStream();
                    _vers = new StreamWriter(flux, new UTF8Encoding(false)) { AutoFlush = true, NewLine = "\n" };
                    _depuis = new StreamReader(flux, new UTF8Encoding(false));
                    return true;
                }
                catch
                {
                    FermerLien();
                    return false;
                }
            }
        }

        private Dictionary<string, object> Demander(Dictionary<string, object> requete)
        {
            string envoi = _json.Serialize(requete);
            string ligne;
            lock (_verrou)
            {
                if (_vers == null) throw new MoteurIndisponible("Le correcteur n'est pas branché.");
                try
                {
                    _vers.WriteLine(envoi);
                    ligne = _depuis.ReadLine();
                    if (ligne == null) throw new IOException("Le moteur a coupé la communication.");
                }
                catch (Exception)
                {
                    // Prise fermee, delai depasse, moteur mort : le veilleur relance.
                    _rompu = true;
                    throw new MoteurIndisponible("Le correcteur ne répond plus : il redémarre.");
                }
            }
            return _json.DeserializeObject(ligne) as Dictionary<string, object> ?? new Dictionary<string, object>();
        }

        private static Dictionary<string, object> Requete(string quoi)
        {
            return new Dictionary<string, object> { { "quoi", quoi } };
        }

        public List<MotSignale> Relire(string texte, string graphie)
        {
            if (!Pret) throw new MoteurIndisponible(_message);
            Dictionary<string, object> requete = Requete("relire");
            requete["texte"] = texte;
            requete["graphie"] = graphie;
            Dictionary<string, object> reponse = Demander(requete);
            object erreur;
            if (reponse.TryGetValue("erreur", out erreur)) throw new InvalidOperationException(Convert.ToString(erreur));

            List<MotSignale> signales = new List<MotSignale>();
            object liste;
            if (!reponse.TryGetValue("signales", out liste) || !(liste is IEnumerable)) return signales;
            foreach (object element in (IEnumerable)liste)
            {
                Dictionary<string, object> s = element as Dictionary<string, object>;
                if (s == null) continue;
                MotSignale m = new MotSignale
                {
                    Mot = Convert.ToString(s["mot"]),
                    Rang = s.ContainsKey("rang") ? Convert.ToInt32(s["rang"]) : 0,
                    Debut = s.ContainsKey("debut") ? Convert.ToInt32(s["debut"]) : -1,
                };
                Chaines(s, "propositions", m.Propositions);
                Chaines(s, "natures", m.Natures);
                if (m.Propositions.Count > 0) signales.Add(m);
            }
            return signales;
        }

        public string Dicter(string fichier, string graphie)
        {
            if (!Pret) throw new MoteurIndisponible(_message);
            Dictionary<string, object> requete = Requete("dicter");
            requete["fichier"] = fichier;
            requete["graphie"] = graphie;
            Dictionary<string, object> reponse = Demander(requete);
            object erreur;
            if (reponse.TryGetValue("erreur", out erreur)) throw new InvalidOperationException(Convert.ToString(erreur));
            object texte;
            return reponse.TryGetValue("texte", out texte) ? Convert.ToString(texte) : "";
        }

        private static void Chaines(Dictionary<string, object> source, string cle, List<string> dans)
        {
            object valeur;
            if (!source.TryGetValue(cle, out valeur) || !(valeur is IEnumerable)) return;
            foreach (object o in (IEnumerable)valeur) dans.Add(Convert.ToString(o));
        }

        private void Changer(EtatMoteur etat, string message)
        {
            _etat = etat;
            _message = message;
            EventHandler change = Change;
            if (change == null) return;
            try { change(this, EventArgs.Empty); }
            catch (Exception e) { Journal.Noter("moteur : abonne", e); }
        }

        private void FermerLien()
        {
            try { if (_vers != null) _vers.Dispose(); } catch { }
            try { if (_depuis != null) _depuis.Dispose(); } catch { }
            try { if (_lien != null) _lien.Close(); } catch { }
            _vers = null;
            _depuis = null;
            _lien = null;
        }

        // Ferme la liaison et, si c'est nous qui l'avions lance, le moteur.
        private void Fermer()
        {
            lock (_verrou) FermerLien();
            if (_processus == null) return;
            try
            {
                if (!_processus.HasExited)
                {
                    _processus.Kill();
                    _processus.WaitForExit(2000);
                }
            }
            catch { }
            _processus = null;
        }

        public void Dispose()
        {
            _arret.Set();
            Fermer();
        }
    }
}
