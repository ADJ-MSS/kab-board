"""Les processus de Kab-board : une seule instance de chacun, et qui vit encore.

Sous Windows, par les appels du noyau (ctypes) ; ailleurs, par POSIX, pour que
les tests tournent sur n'importe quelle machine.
"""
import os
import subprocess
import sys

import lieux

WINDOWS = os.name == "nt"
_gardes = []        # les verrous tenus jusqu'à la fin du processus

if WINDOWS:
    import ctypes
    from ctypes import wintypes

    _k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _k32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
    _k32.CreateMutexW.restype = wintypes.HANDLE
    _k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    _k32.OpenProcess.restype = wintypes.HANDLE
    _k32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    _k32.WaitForSingleObject.restype = wintypes.DWORD
    _k32.CloseHandle.argtypes = [wintypes.HANDLE]
    _k32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    _k32.GetConsoleMode.argtypes = [wintypes.HANDLE, ctypes.POINTER(ctypes.c_uint32)]
    _k32.GetConsoleMode.restype = wintypes.BOOL
    _ERREUR_EXISTE = 183
    _SYNCHRONIZE = 0x00100000
    _TERMINER = 0x0001
    _ATTENTE_DEPASSEE = 0x102


def instance_unique(nom: str, par_dossier: bool = False) -> bool:
    """Vrai si ce processus est le seul « nom » de la session. Le verrou tient
    jusqu'à sa fin, même brutale.

    par_dossier : le seul pour ce dossier de données. Le service se joint par
    une fiche rangée dans ce dossier : une copie portable à côté de la version
    installée a le sien. (Le clavier, lui, est seul dans la session : deux
    crochets traiteraient chaque touche deux fois.)"""
    if WINDOWS:
        if par_dossier:
            import hashlib
            empreinte = hashlib.sha1(str(lieux.DONNEES.resolve()).lower().encode()).hexdigest()
            nom = f"{nom}-{empreinte[:12]}"
        h = _k32.CreateMutexW(None, False, f"Local\\kab-board-windows-{nom}")
        if not h:
            return True
        if ctypes.get_last_error() == _ERREUR_EXISTE:
            _k32.CloseHandle(h)
            return False
        _gardes.append(h)
        return True
    import fcntl
    lieux.DONNEES.mkdir(parents=True, exist_ok=True)
    f = open(lieux.DONNEES / f".{nom}.verrou", "w")
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        f.close()
        return False
    _gardes.append(f)
    return True


def vivant(pid: int) -> bool:
    if not pid or pid <= 0:
        return False
    if WINDOWS:
        h = _k32.OpenProcess(_SYNCHRONIZE, False, pid)
        if not h:
            return False
        try:
            return _k32.WaitForSingleObject(h, 0) == _ATTENTE_DEPASSEE
        finally:
            _k32.CloseHandle(h)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    try:                                  # un processus fini que personne n'a relevé
        with open(f"/proc/{pid}/stat", "rb") as f:
            return f.read().split(b") ")[1][:1] != b"Z"
    except (OSError, IndexError):
        return True


def terminer(pid: int) -> None:
    if not vivant(pid):
        return
    if WINDOWS:
        h = _k32.OpenProcess(_TERMINER, False, pid)
        if h:
            _k32.TerminateProcess(h, 1)
            _k32.CloseHandle(h)
        return
    import signal
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        pass


def lancer(script: str, *arguments: str) -> subprocess.Popen:
    """Un morceau de Kab-board, détaché, sans fenêtre de console."""
    commande = [lieux.python_sans_console(), str(lieux.ICI / script), *arguments]
    options = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL,
               "stderr": subprocess.DEVNULL, "cwd": str(lieux.RACINE), "close_fds": True}
    if WINDOWS:
        options["creationflags"] = (subprocess.CREATE_NEW_PROCESS_GROUP
                                    | subprocess.DETACHED_PROCESS
                                    | subprocess.CREATE_NO_WINDOW)
    else:
        options["start_new_session"] = True
    return subprocess.Popen(commande, **options)


def sorties_sures():
    """Le correcteur imprime des filets (━) et du kabyle : une console ou un tube
    en cp1252 le ferait tomber à l'impression. On écrit en UTF-8, et ce qui ne
    passe pas devient un « ? » plutôt qu'une erreur."""
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def _console(flux) -> bool:
    """Une vraie console ? Lancé par lancer(), un morceau de Kab-board écrit vers
    NUL, que Python prend pour un terminal (isatty) sous Windows. Seule une
    console accepte GetConsoleMode."""
    if flux is None:
        return False
    try:
        if not flux.isatty():
            return False
        if not WINDOWS:
            return True
        import msvcrt
        mode = ctypes.c_uint32()
        return bool(_k32.GetConsoleMode(msvcrt.get_osfhandle(flux.fileno()), ctypes.byref(mode)))
    except (AttributeError, OSError, ValueError):
        return False


def journal(nom: str):
    """Ce qu'un processus sans console écrit va dans un fichier, borné à 1 Mo."""
    lieux.DONNEES.mkdir(parents=True, exist_ok=True)
    chemin = lieux.DONNEES / f"{nom}.log"
    try:
        if chemin.stat().st_size > 1_000_000:
            chemin.replace(chemin.with_suffix(".log.1"))
    except OSError:
        pass
    f = open(chemin, "a", encoding="utf-8", buffering=1, errors="replace")
    if not _console(sys.stdout):
        sys.stdout = f
    if not _console(sys.stderr):
        sys.stderr = f
    sorties_sures()
    return f
