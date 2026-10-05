// Capture du micro par l'API waveIn : 16 kHz, mono, 16 bits, le format attendu
// par Mmeslay (moteur\linux\dictee.py).

using System;
using System.Collections.Generic;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;

namespace KabBoardPont
{
    internal sealed class Micro : IDisposable
    {
        public const int Taux = 16000;
        public const int DureeMaxSecondes = 30;

        private const int NbTampons = 8;
        private const int OctetsParTampon = Taux * 2 / 10;   // un dixieme de seconde
        private const uint WaveMapper = 0xFFFFFFFF;
        private const uint WhdrDone = 0x00000001;

        [StructLayout(LayoutKind.Sequential)]
        private struct WaveFormatEx
        {
            public ushort wFormatTag;
            public ushort nChannels;
            public uint nSamplesPerSec;
            public uint nAvgBytesPerSec;
            public ushort nBlockAlign;
            public ushort wBitsPerSample;
            public ushort cbSize;
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct WaveHdr
        {
            public IntPtr lpData;
            public uint dwBufferLength;
            public uint dwBytesRecorded;
            public IntPtr dwUser;
            public uint dwFlags;
            public uint dwLoops;
            public IntPtr lpNext;
            public IntPtr reserved;
        }

        [DllImport("winmm.dll")]
        private static extern int waveInOpen(out IntPtr poignee, uint peripherique, ref WaveFormatEx format,
                                             IntPtr rappel, IntPtr instance, uint options);
        [DllImport("winmm.dll")]
        private static extern int waveInPrepareHeader(IntPtr poignee, IntPtr entete, int taille);
        [DllImport("winmm.dll")]
        private static extern int waveInUnprepareHeader(IntPtr poignee, IntPtr entete, int taille);
        [DllImport("winmm.dll")]
        private static extern int waveInAddBuffer(IntPtr poignee, IntPtr entete, int taille);
        [DllImport("winmm.dll")]
        private static extern int waveInStart(IntPtr poignee);
        [DllImport("winmm.dll")]
        private static extern int waveInReset(IntPtr poignee);
        [DllImport("winmm.dll")]
        private static extern int waveInClose(IntPtr poignee);
        [DllImport("winmm.dll")]
        private static extern uint waveInGetNumDevs();

        private readonly int _tailleEntete = Marshal.SizeOf(typeof(WaveHdr));
        private readonly List<IntPtr> _entetes = new List<IntPtr>();
        private readonly List<IntPtr> _donnees = new List<IntPtr>();
        private readonly MemoryStream _son = new MemoryStream();
        private readonly object _verrou = new object();
        private IntPtr _poignee = IntPtr.Zero;
        private Thread _collecteur;
        private volatile bool _enCours;
        // Le prochain tampon que Windows rendra : il les remplit dans l'ordre de la
        // file, et on les lit dans ce meme ordre, sans quoi des morceaux de son
        // s'intervertiraient quand deux tampons sont prets ensemble.
        private int _suivant;

        // Declenche sur le fil du collecteur quand les 30 secondes sont atteintes.
        public event EventHandler Plein;

        public static bool Disponible
        {
            get
            {
                try { return waveInGetNumDevs() > 0; }
                catch { return false; }
            }
        }

        public bool EnCours { get { return _enCours; } }

        public double Secondes
        {
            get { lock (_verrou) return _son.Length / (2.0 * Taux); }
        }

        public void Demarrer()
        {
            WaveFormatEx format = new WaveFormatEx
            {
                wFormatTag = 1,   // PCM
                nChannels = 1,
                nSamplesPerSec = Taux,
                wBitsPerSample = 16,
                nBlockAlign = 2,
                nAvgBytesPerSec = Taux * 2,
                cbSize = 0,
            };
            int erreur = waveInOpen(out _poignee, WaveMapper, ref format, IntPtr.Zero, IntPtr.Zero, 0);
            if (erreur != 0)
            {
                _poignee = IntPtr.Zero;
                throw new InvalidOperationException("Le micro n'a pas pu s'ouvrir (code " + erreur + "). Vérifiez qu'un micro est branché et que Windows autorise les applications de bureau à l'utiliser.");
            }
            for (int i = 0; i < NbTampons; i++)
            {
                IntPtr donnees = Marshal.AllocHGlobal(OctetsParTampon);
                IntPtr entete = Marshal.AllocHGlobal(_tailleEntete);
                WaveHdr h = new WaveHdr { lpData = donnees, dwBufferLength = OctetsParTampon };
                Marshal.StructureToPtr(h, entete, false);
                waveInPrepareHeader(_poignee, entete, _tailleEntete);
                waveInAddBuffer(_poignee, entete, _tailleEntete);
                _donnees.Add(donnees);
                _entetes.Add(entete);
            }
            _enCours = true;
            waveInStart(_poignee);
            _collecteur = new Thread(Collecter) { IsBackground = true, Name = "Kab-board : micro" };
            _collecteur.Start();
        }

        private void Collecter()
        {
            bool plein = false;
            while (_enCours)
            {
                while (_enCours)
                {
                    IntPtr entete = _entetes[_suivant];
                    WaveHdr h = (WaveHdr)Marshal.PtrToStructure(entete, typeof(WaveHdr));
                    if ((h.dwFlags & WhdrDone) == 0) break;
                    Recopier(h);
                    h.dwFlags &= ~WhdrDone;
                    h.dwBytesRecorded = 0;
                    Marshal.StructureToPtr(h, entete, false);
                    waveInAddBuffer(_poignee, entete, _tailleEntete);
                    _suivant = (_suivant + 1) % _entetes.Count;
                }
                if (!plein && Secondes >= DureeMaxSecondes)
                {
                    plein = true;
                    EventHandler e = Plein;
                    if (e != null) try { e(this, EventArgs.Empty); } catch (Exception ex) { Journal.Noter("micro : plein", ex); }
                }
                Thread.Sleep(40);
            }
        }

        private void Recopier(WaveHdr h)
        {
            if (h.dwBytesRecorded == 0) return;
            byte[] morceau = new byte[h.dwBytesRecorded];
            Marshal.Copy(h.lpData, morceau, 0, morceau.Length);
            lock (_verrou)
            {
                long reste = (long)DureeMaxSecondes * Taux * 2 - _son.Length;
                if (reste > 0) _son.Write(morceau, 0, (int)Math.Min(reste, morceau.Length));
            }
        }

        public byte[] Arreter()
        {
            if (_poignee == IntPtr.Zero) return Wav(new byte[0]);
            _enCours = false;
            if (_collecteur != null) _collecteur.Join(1000);
            // waveInReset rend tous les tampons, y compris celui en cours de remplissage :
            // on les lit dans l'ordre de la file, a partir du prochain attendu.
            waveInReset(_poignee);
            for (int k = 0; k < _entetes.Count; k++)
            {
                IntPtr entete = _entetes[(_suivant + k) % _entetes.Count];
                WaveHdr h = (WaveHdr)Marshal.PtrToStructure(entete, typeof(WaveHdr));
                if ((h.dwFlags & WhdrDone) != 0) Recopier(h);
            }
            Liberer();
            byte[] pcm;
            lock (_verrou) pcm = _son.ToArray();
            return Wav(pcm);
        }

        private void Liberer()
        {
            if (_poignee != IntPtr.Zero)
            {
                foreach (IntPtr entete in _entetes)
                {
                    try { waveInUnprepareHeader(_poignee, entete, _tailleEntete); } catch { }
                }
                try { waveInClose(_poignee); } catch { }
                _poignee = IntPtr.Zero;
            }
            foreach (IntPtr p in _entetes) Marshal.FreeHGlobal(p);
            foreach (IntPtr p in _donnees) Marshal.FreeHGlobal(p);
            _entetes.Clear();
            _donnees.Clear();
        }

        // En-tete RIFF minimal, lisible par le module wave de Python.
        public static byte[] Wav(byte[] pcm)
        {
            using (MemoryStream m = new MemoryStream())
            using (BinaryWriter w = new BinaryWriter(m, Encoding.ASCII))
            {
                w.Write(Encoding.ASCII.GetBytes("RIFF"));
                w.Write(36 + pcm.Length);
                w.Write(Encoding.ASCII.GetBytes("WAVE"));
                w.Write(Encoding.ASCII.GetBytes("fmt "));
                w.Write(16);
                w.Write((short)1);          // PCM
                w.Write((short)1);          // mono
                w.Write(Taux);
                w.Write(Taux * 2);          // octets par seconde
                w.Write((short)2);          // octets par echantillon
                w.Write((short)16);         // bits par echantillon
                w.Write(Encoding.ASCII.GetBytes("data"));
                w.Write(pcm.Length);
                w.Write(pcm);
                w.Flush();
                return m.ToArray();
            }
        }

        public void Dispose()
        {
            _enCours = false;
            if (_poignee != IntPtr.Zero)
            {
                try { waveInReset(_poignee); } catch { }
                Liberer();
            }
        }
    }
}
