"""Les appels de Windows dont Kab-board a besoin, par ctypes : rien à compiler.

    crochets      voir chaque touche et chaque clic avant les applications
    taper()       écrire dans l'application active (SendInput, en Unicode)
    caractere()   ce qu'écrit une touche dans la disposition de l'application
    curseur()     où est le curseur de texte, pour y poser la barre
    sans_focus()  une fenêtre qui ne prend jamais le focus (clavier, barre)
    mot_de_passe()  le champ actif est-il un mot de passe ?
    IconeNotification  l'icône près de l'horloge, et son menu

Ce module ne se charge que sous Windows.
"""
import ctypes
import os
import threading
import time
from ctypes import wintypes

if os.name != "nt":                      # pragma: no cover
    raise ImportError("win32 : Windows seulement")

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)
ole32 = ctypes.WinDLL("ole32")
oleaut32 = ctypes.WinDLL("oleaut32")
try:
    oleacc = ctypes.WinDLL("oleacc")
except OSError:                          # pragma: no cover
    oleacc = None

LRESULT = ctypes.c_ssize_t
LONG_PTR = ctypes.c_ssize_t
ULONG_PTR = ctypes.c_size_t
HRESULT = ctypes.c_long

# Ce que nous tapons porte cette marque : le crochet ne le reprend pas pour lui.
MARQUE = 0x4B414242                      # « KABB »

WH_KEYBOARD_LL, WH_MOUSE_LL, HC_ACTION = 13, 14, 0
WM_KEYDOWN, WM_KEYUP, WM_SYSKEYDOWN, WM_SYSKEYUP = 0x100, 0x101, 0x104, 0x105
WM_LBUTTONDOWN, WM_RBUTTONDOWN, WM_MBUTTONDOWN, WM_XBUTTONDOWN = 0x201, 0x204, 0x207, 0x20B
WM_QUIT, WM_APP, WM_NULL, WM_COMMAND, WM_DESTROY = 0x12, 0x8000, 0x0, 0x111, 0x2
WM_LBUTTONUP, WM_RBUTTONUP, WM_LBUTTONDBLCLK, WM_CONTEXTMENU = 0x202, 0x205, 0x203, 0x7B
LLKHF_INJECTED = 0x10

INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP, KEYEVENTF_UNICODE = 0x2, 0x4
VK_BACK, VK_TAB, VK_RETURN = 0x08, 0x09, 0x0D
VK_SHIFT, VK_CONTROL, VK_MENU, VK_CAPITAL = 0x10, 0x11, 0x12, 0x14
VK_LWIN, VK_RWIN, VK_RMENU, VK_LCONTROL = 0x5B, 0x5C, 0xA5, 0xA2
VK_LSHIFT, VK_RSHIFT = 0xA0, 0xA1

GWL_STYLE, GWL_EXSTYLE = -16, -20
ES_PASSWORD = 0x20
WS_EX_TOOLWINDOW, WS_EX_TOPMOST, WS_EX_NOACTIVATE, WS_EX_APPWINDOW = 0x80, 0x8, 0x08000000, 0x40000
GA_ROOT = 2
MONITOR_DEFAULTTONEAREST = 2

EVENT_SYSTEM_FOREGROUND, EVENT_OBJECT_FOCUS = 0x0003, 0x8005
WINEVENT_OUTOFCONTEXT, WINEVENT_SKIPOWNPROCESS = 0x0, 0x2


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class RECT(ctypes.Structure):
    _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG),
                ("right", wintypes.LONG), ("bottom", wintypes.LONG)]


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("vkCode", wintypes.DWORD), ("scanCode", wintypes.DWORD),
                ("flags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ULONG_PTR)]


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("pt", POINT), ("mouseData", wintypes.DWORD), ("flags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ULONG_PTR)]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD),
                ("wParamH", wintypes.WORD)]


class _ENTREE(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _ENTREE)]


class GUITHREADINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("flags", wintypes.DWORD),
                ("hwndActive", wintypes.HWND), ("hwndFocus", wintypes.HWND),
                ("hwndCapture", wintypes.HWND), ("hwndMenuOwner", wintypes.HWND),
                ("hwndMoveSize", wintypes.HWND), ("hwndCaret", wintypes.HWND),
                ("rcCaret", RECT)]


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", RECT), ("rcWork", RECT),
                ("dwFlags", wintypes.DWORD)]


class MSG(ctypes.Structure):
    _fields_ = [("hwnd", wintypes.HWND), ("message", wintypes.UINT),
                ("wParam", wintypes.WPARAM), ("lParam", wintypes.LPARAM),
                ("time", wintypes.DWORD), ("pt", POINT), ("lPrivate", wintypes.DWORD)]


class GUID(ctypes.Structure):
    _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD), ("Data3", wintypes.WORD),
                ("Data4", ctypes.c_ubyte * 8)]

    @classmethod
    def de(cls, texte: str) -> "GUID":
        import uuid
        u = uuid.UUID(texte)
        g = cls()
        g.Data1, g.Data2, g.Data3 = u.time_low, u.time_mid, u.time_hi_version
        for i, octet in enumerate(u.bytes[8:]):
            g.Data4[i] = octet
        return g


class VARIANT(ctypes.Structure):
    _fields_ = [("vt", wintypes.USHORT), ("r1", wintypes.WORD), ("r2", wintypes.WORD),
                ("r3", wintypes.WORD), ("valeur", ctypes.c_longlong), ("valeur2", ctypes.c_longlong)]


HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
WINEVENTPROC = ctypes.WINFUNCTYPE(None, wintypes.HANDLE, wintypes.DWORD, wintypes.HWND,
                                  wintypes.LONG, wintypes.LONG, wintypes.DWORD, wintypes.DWORD)
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM,
                             wintypes.LPARAM)


def _signer(dll, nom, retour, *arguments):
    f = getattr(dll, nom)
    f.restype = retour
    f.argtypes = list(arguments)
    return f


H, W = wintypes.HANDLE, wintypes.HWND
_signer(user32, "SetWindowsHookExW", H, ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD)
_signer(user32, "UnhookWindowsHookEx", wintypes.BOOL, H)
_signer(user32, "CallNextHookEx", LRESULT, H, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
_signer(user32, "SetWinEventHook", H, wintypes.DWORD, wintypes.DWORD, wintypes.HMODULE,
        WINEVENTPROC, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD)
_signer(user32, "UnhookWinEvent", wintypes.BOOL, H)
_signer(user32, "GetMessageW", wintypes.BOOL, ctypes.POINTER(MSG), W, wintypes.UINT, wintypes.UINT)
_signer(user32, "TranslateMessage", wintypes.BOOL, ctypes.POINTER(MSG))
_signer(user32, "DispatchMessageW", LRESULT, ctypes.POINTER(MSG))
_signer(user32, "PostThreadMessageW", wintypes.BOOL, wintypes.DWORD, wintypes.UINT,
        wintypes.WPARAM, wintypes.LPARAM)
_signer(user32, "PostMessageW", wintypes.BOOL, W, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
_signer(user32, "SendInput", wintypes.UINT, wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
_signer(user32, "GetForegroundWindow", W)
_signer(user32, "SetForegroundWindow", wintypes.BOOL, W)


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


_signer(user32, "GetLastInputInfo", wintypes.BOOL, ctypes.POINTER(LASTINPUTINFO))
_signer(kernel32, "GetTickCount", wintypes.DWORD)


def derniere_entree() -> int:
    """L'instant (GetTickCount) de la dernière touche ou du dernier geste de souris,
    que nos crochets les aient vus ou non."""
    info = LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(LASTINPUTINFO)
    return info.dwTime if user32.GetLastInputInfo(ctypes.byref(info)) else 0


def ecart(apres: int, avant: int) -> int:
    """apres - avant, en millisecondes, par-dessus le tour du compteur (49 jours)."""
    d = (apres - avant) & 0xFFFFFFFF
    return d - 0x100000000 if d >= 0x80000000 else d
_signer(user32, "GetWindowThreadProcessId", wintypes.DWORD, W, ctypes.POINTER(wintypes.DWORD))
_signer(user32, "GetKeyboardLayout", wintypes.HKL, wintypes.DWORD)
_signer(user32, "VkKeyScanExW", ctypes.c_short, wintypes.WCHAR, wintypes.HKL)
_signer(user32, "ToUnicodeEx", ctypes.c_int, wintypes.UINT, wintypes.UINT,
        ctypes.POINTER(ctypes.c_ubyte), wintypes.LPWSTR, ctypes.c_int, wintypes.UINT, wintypes.HKL)
_signer(user32, "GetAsyncKeyState", ctypes.c_short, ctypes.c_int)
_signer(user32, "GetKeyState", ctypes.c_short, ctypes.c_int)
_signer(user32, "GetGUIThreadInfo", wintypes.BOOL, wintypes.DWORD, ctypes.POINTER(GUITHREADINFO))
_signer(user32, "ClientToScreen", wintypes.BOOL, W, ctypes.POINTER(POINT))
_signer(user32, "GetWindowLongW", wintypes.LONG, W, ctypes.c_int)
try:
    _signer(user32, "GetWindowLongPtrW", LONG_PTR, W, ctypes.c_int)
    _signer(user32, "SetWindowLongPtrW", LONG_PTR, W, ctypes.c_int, LONG_PTR)
    _lire_style, _ecrire_style = user32.GetWindowLongPtrW, user32.SetWindowLongPtrW
except AttributeError:                   # Python 32 bits
    _signer(user32, "SetWindowLongW", wintypes.LONG, W, ctypes.c_int, wintypes.LONG)
    _lire_style, _ecrire_style = user32.GetWindowLongW, user32.SetWindowLongW
_signer(user32, "GetClassNameW", ctypes.c_int, W, wintypes.LPWSTR, ctypes.c_int)
_signer(user32, "GetWindowTextW", ctypes.c_int, W, wintypes.LPWSTR, ctypes.c_int)
_signer(user32, "GetAncestor", W, W, wintypes.UINT)
_signer(user32, "GetParent", W, W)
_signer(user32, "GetWindowRect", wintypes.BOOL, W, ctypes.POINTER(RECT))
_signer(user32, "IsWindowVisible", wintypes.BOOL, W)
_signer(user32, "SetWindowPos", wintypes.BOOL, W, W, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        ctypes.c_int, wintypes.UINT)
_signer(user32, "MonitorFromPoint", wintypes.HMONITOR, POINT, wintypes.DWORD)
_signer(user32, "MonitorFromWindow", wintypes.HMONITOR, W, wintypes.DWORD)
_signer(user32, "GetMonitorInfoW", wintypes.BOOL, wintypes.HMONITOR, ctypes.POINTER(MONITORINFO))
_signer(user32, "GetCursorPos", wintypes.BOOL, ctypes.POINTER(POINT))
_signer(user32, "CreateWindowExW", W, wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR,
        wintypes.DWORD, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, W,
        wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID)
_signer(user32, "DestroyWindow", wintypes.BOOL, W)
_signer(user32, "DefWindowProcW", LRESULT, W, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
_signer(user32, "RegisterWindowMessageW", wintypes.UINT, wintypes.LPCWSTR)
_signer(user32, "CreatePopupMenu", wintypes.HMENU)
_signer(user32, "AppendMenuW", wintypes.BOOL, wintypes.HMENU, wintypes.UINT, ULONG_PTR,
        wintypes.LPCWSTR)
_signer(user32, "TrackPopupMenu", wintypes.BOOL, wintypes.HMENU, wintypes.UINT, ctypes.c_int,
        ctypes.c_int, ctypes.c_int, W, ctypes.c_void_p)
_signer(user32, "DestroyMenu", wintypes.BOOL, wintypes.HMENU)
_signer(user32, "LoadImageW", H, wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT,
        ctypes.c_int, ctypes.c_int, wintypes.UINT)
_signer(user32, "LoadIconW", wintypes.HICON, wintypes.HINSTANCE, ctypes.c_void_p)
_signer(user32, "DestroyIcon", wintypes.BOOL, wintypes.HICON)
_signer(user32, "MessageBoxW", ctypes.c_int, W, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.UINT)
_signer(kernel32, "GetModuleHandleW", wintypes.HMODULE, wintypes.LPCWSTR)
_signer(kernel32, "GetCurrentThreadId", wintypes.DWORD)
_signer(kernel32, "GetCurrentProcessId", wintypes.DWORD)
_signer(ole32, "CoInitializeEx", HRESULT, ctypes.c_void_p, wintypes.DWORD)
_signer(ole32, "CoCreateInstance", HRESULT, ctypes.POINTER(GUID), ctypes.c_void_p,
        wintypes.DWORD, ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p))
_signer(oleaut32, "VariantClear", HRESULT, ctypes.POINTER(VARIANT))
if oleacc is not None:
    _signer(oleacc, "AccessibleObjectFromWindow", HRESULT, W, wintypes.DWORD,
            ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p))

MOI = kernel32.GetCurrentProcessId()


# La netteté sur les écrans à haute densité

def net_sur_tous_les_ecrans():
    """Des coordonnées en vrais pixels, partout : celles du curseur des autres
    applications comme celles de nos fenêtres. À appeler avant tout tkinter."""
    try:
        user32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
        if user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):   # par écran, v2
            return
    except AttributeError:
        pass
    try:
        ctypes.WinDLL("shcore").SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        user32.SetProcessDPIAware()


def initialiser_com():
    """Pour les fils qui interrogent l'accessibilité (curseur, mot de passe)."""
    ole32.CoInitializeEx(None, 0x2)          # COINIT_APARTMENTTHREADED


# Les fenêtres

def fenetre_active():
    return user32.GetForegroundWindow()


def processus_de(hwnd) -> int:
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def fil_de(hwnd) -> int:
    return user32.GetWindowThreadProcessId(hwnd, None)


def classe(hwnd) -> str:
    tampon = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, tampon, 256)
    return tampon.value


def titre(hwnd) -> str:
    tampon = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(hwnd, tampon, 512)
    return tampon.value


def racine(hwnd):
    return user32.GetAncestor(hwnd, GA_ROOT) or hwnd


def rectangle(hwnd):
    r = RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(r)):
        return None
    return r.left, r.top, r.right, r.bottom


def zone_de_travail(x: int, y: int):
    """Le rectangle utile de l'écran qui contient ce point : sans la barre des tâches."""
    m = user32.MonitorFromPoint(POINT(x, y), MONITOR_DEFAULTTONEAREST)
    info = MONITORINFO()
    info.cbSize = ctypes.sizeof(MONITORINFO)
    if not user32.GetMonitorInfoW(m, ctypes.byref(info)):
        return 0, 0, 1920, 1080
    r = info.rcWork
    return r.left, r.top, r.right, r.bottom


def zone_de_la_fenetre(hwnd):
    m = user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
    info = MONITORINFO()
    info.cbSize = ctypes.sizeof(MONITORINFO)
    if not user32.GetMonitorInfoW(m, ctypes.byref(info)):
        return 0, 0, 1920, 1080
    r = info.rcWork
    return r.left, r.top, r.right, r.bottom


def souris():
    p = POINT()
    user32.GetCursorPos(ctypes.byref(p))
    return p.x, p.y


def sans_focus(hwnd_tk: int) -> int:
    """La fenêtre Tk ne prendra jamais le focus : un clic dessus laisse le curseur
    dans l'application où l'on écrit. Sans cela, le clavier à l'écran volerait la
    saisie à chaque touche. Rend le vrai HWND de la fenêtre."""
    hwnd = user32.GetParent(hwnd_tk) or hwnd_tk
    style = _lire_style(hwnd, GWL_EXSTYLE)
    style = (style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW | WS_EX_TOPMOST) & ~WS_EX_APPWINDOW
    _ecrire_style(hwnd, GWL_EXSTYLE, style)
    # HWND_TOPMOST, sans bouger ni redimensionner ni activer.
    user32.SetWindowPos(hwnd, wintypes.HWND(-1), 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010 | 0x0020)
    return hwnd


advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
_signer(kernel32, "OpenProcess", H, wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
_signer(kernel32, "CloseHandle", wintypes.BOOL, H)
_signer(kernel32, "GetCurrentProcess", H)
_signer(advapi32, "OpenProcessToken", wintypes.BOOL, H, wintypes.DWORD, ctypes.POINTER(H))
_signer(advapi32, "GetTokenInformation", wintypes.BOOL, H, ctypes.c_int, ctypes.c_void_p,
        wintypes.DWORD, ctypes.POINTER(wintypes.DWORD))


def _eleve(processus_) -> bool:
    jeton = H()
    if not advapi32.OpenProcessToken(processus_, 0x8, ctypes.byref(jeton)):    # TOKEN_QUERY
        return True
    try:
        valeur, taille = wintypes.DWORD(), wintypes.DWORD()
        if not advapi32.GetTokenInformation(jeton, 20, ctypes.byref(valeur), 4,
                                            ctypes.byref(taille)):        # TokenElevation
            return False
        return bool(valeur.value)
    finally:
        kernel32.CloseHandle(jeton)


_moi_eleve = None


def peut_ecrire_dans(hwnd) -> bool:
    """Windows interdit d'écrire dans une application lancée en administrateur
    quand on ne l'est pas soi-même. Le clavier s'y tait, plutôt que de retenir
    une touche qu'il ne pourrait pas réécrire."""
    global _moi_eleve
    if _moi_eleve is None:
        _moi_eleve = _eleve(kernel32.GetCurrentProcess())
    pid = processus_de(hwnd)
    if not pid or pid == MOI or _moi_eleve:
        return True
    h = kernel32.OpenProcess(0x1000, False, pid)          # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return False
    try:
        return not _eleve(h)
    finally:
        kernel32.CloseHandle(h)


_signer(user32, "FindWindowW", W, wintypes.LPCWSTR, wintypes.LPCWSTR)
_signer(user32, "ShowWindow", wintypes.BOOL, W, ctypes.c_int)


def montrer_fenetre(titre_: str) -> bool:
    """Ramène devant la fenêtre de ce titre, si elle existe déjà."""
    hwnd = user32.FindWindowW(None, titre_)
    if not hwnd:
        return False
    user32.ShowWindow(hwnd, 9)                     # SW_RESTORE
    user32.SetForegroundWindow(hwnd)
    return True


def message(titre_: str, texte: str, icone: int = 0x40):
    user32.MessageBoxW(None, texte, titre_, icone)


# Écrire dans l'application active

def _touche(vk=0, scan=0, drapeaux=0) -> INPUT:
    i = INPUT()
    i.type = INPUT_KEYBOARD
    i.ki = KEYBDINPUT(vk, scan, drapeaux, 0, MARQUE)
    return i


_touches_de = {}


def touche_de(c: str, hkl):
    """La touche de la disposition qui écrit c, avec ou sans Maj, sans AltGr :
    (vk, maj), ou None (ɣ, ḍ, une touche morte, AltGr…)."""
    if not hkl or len(c) != 1 or c in "\r\n\t":
        return None
    cle = (c, int(hkl))
    if cle not in _touches_de:
        trouvee = None
        r = user32.VkKeyScanExW(c, hkl)
        if r != -1:
            vk, etat = r & 0xFF, (r >> 8) & 0xFF
            if etat in (0, 1) and caractere(vk, 0, bool(etat), False, False, hkl) == (1, c):
                trouvee = (vk, bool(etat))
        _touches_de[cle] = trouvee
    return _touches_de[cle]


def entrees(effacer: int, texte: str, hkl=None):
    """Les évènements à envoyer : n effacements, puis le texte.

    Avec la disposition du clavier (hkl), un caractère qu'elle a sous une touche
    part comme cette touche : une application occupée (le Bloc-notes de Windows
    11, après une suite d'effacements) mélange les caractères Unicode qui
    l'attendent, jamais les touches. Les autres, ɣ et ḍ compris, passent en
    Unicode (KEYEVENTF_UNICODE) : ils s'écrivent tels quels, quelle que soit la
    disposition. L'entrée et la tabulation restent des touches.
    """
    liste = []
    for _ in range(effacer):
        liste += [_touche(VK_BACK), _touche(VK_BACK, drapeaux=KEYEVENTF_KEYUP)]
    for c in texte:
        if c in "\r\n":
            if c == "\n":
                liste += [_touche(VK_RETURN), _touche(VK_RETURN, drapeaux=KEYEVENTF_KEYUP)]
            continue
        if c == "\t":
            liste += [_touche(VK_TAB), _touche(VK_TAB, drapeaux=KEYEVENTF_KEYUP)]
            continue
        t = touche_de(c, hkl)
        if t:
            vk, maj = t
            if maj:
                liste.append(_touche(VK_LSHIFT))
            liste += [_touche(vk), _touche(vk, drapeaux=KEYEVENTF_KEYUP)]
            if maj:
                liste.append(_touche(VK_LSHIFT, drapeaux=KEYEVENTF_KEYUP))
            continue
        code = c.encode("utf-16-le")
        for k in range(0, len(code), 2):
            unite = int.from_bytes(code[k:k + 2], "little")
            liste += [_touche(0, unite, KEYEVENTF_UNICODE),
                      _touche(0, unite, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP)]
    return liste


def taper(effacer: int = 0, texte: str = "", verr_maj=None) -> bool:
    """Efface puis tape, d'un seul envoi : rien ne s'intercale.

    Les vraies touches ne valent que si rien ne les change : Ctrl, Alt ou le
    verrouillage des majuscules tenus, tout part en Unicode. Une
    Maj tenue (Maj + 1 en AZERTY pour choisir) est relâchée d'abord : elle
    mettrait le mot choisi en majuscules."""
    m = modificateurs()
    if verr_maj is None:
        verr_maj = verrouillage_majuscules()
    hkl = None
    if texte and not (m["ctrl"] or m["alt"] or m["win"] or verr_maj):
        hkl = disposition_active()
    liste = entrees(effacer, texte, hkl)
    if not liste:
        return True
    if hkl and m["maj"]:
        liste = [_touche(VK_LSHIFT, drapeaux=KEYEVENTF_KEYUP),
                 _touche(VK_RSHIFT, drapeaux=KEYEVENTF_KEYUP)] + liste
    tableau = (INPUT * len(liste))(*liste)
    return user32.SendInput(len(liste), tableau, ctypes.sizeof(INPUT)) == len(liste)


# Ce qu'écrit une touche

_altgr_par_disposition = {}


def disposition_active():
    return user32.GetKeyboardLayout(fil_de(user32.GetForegroundWindow()))


def a_altgr(hkl) -> bool:
    """La disposition a-t-elle une touche AltGr ? Sur un clavier américain, Alt
    droite est un Alt comme l'autre, et Alt droite + g ne doit pas donner ɣ."""
    cle = int(hkl or 0)
    if cle not in _altgr_par_disposition:
        etat = (ctypes.c_ubyte * 256)()
        etat[VK_CONTROL] = etat[VK_MENU] = 0x80
        tampon = ctypes.create_unicode_buffer(8)
        trouve = False
        for vk in list(range(0x30, 0x5B)) + list(range(0xBA, 0xC1)) + list(range(0xDB, 0xE0)):
            if user32.ToUnicodeEx(vk, 0, etat, tampon, 8, 4, hkl) > 0:
                trouve = True
                break
        _altgr_par_disposition[cle] = trouve
    return _altgr_par_disposition[cle]


def _enfoncee(vk) -> bool:
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)


def modificateurs():
    """Ce qui est tenu enfoncé au moment de la touche. Le crochet passe avant la
    mise à jour de l'état du clavier : on lit donc celui d'avant, juste pour les
    modificateurs, qui ont été enfoncés avant la lettre."""
    return {"maj": _enfoncee(VK_SHIFT), "ctrl": _enfoncee(VK_CONTROL),
            "alt": _enfoncee(VK_MENU), "alt_droite": _enfoncee(VK_RMENU),
            "win": _enfoncee(VK_LWIN) or _enfoncee(VK_RWIN)}


def caractere(vk: int, scan: int, maj: bool, verr_maj: bool, altgr: bool, hkl) -> tuple:
    """Ce que la touche écrit dans la disposition donnée, sans toucher à l'état du
    clavier (drapeau 4, Windows 10 1607 et après) : un accent en attente dans
    l'application reste en attente. Rend (n, texte) : n < 0 pour une touche morte."""
    etat = (ctypes.c_ubyte * 256)()
    if maj:
        etat[VK_SHIFT] = 0x80
    if verr_maj:
        etat[VK_CAPITAL] = 0x01
    if altgr:
        etat[VK_CONTROL] = etat[VK_MENU] = 0x80
    tampon = ctypes.create_unicode_buffer(8)
    n = user32.ToUnicodeEx(vk, scan, etat, tampon, 8, 4, hkl)
    if n > 0:
        return n, tampon[:n]
    return n, ""


def verrouillage_majuscules() -> bool:
    return bool(user32.GetKeyState(VK_CAPITAL) & 1)


# Le curseur de texte

def _rappeler(objet, rang, prototype, *arguments):
    """Appelle la méthode n° rang de l'interface COM `objet`."""
    vtable = ctypes.cast(objet, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]
    return prototype(vtable[rang])(objet, *arguments)


_LIBERER = ctypes.WINFUNCTYPE(wintypes.ULONG, ctypes.c_void_p)
IID_IACCESSIBLE = GUID.de("618736e0-3c3d-11cf-810c-00aa00389b71")
OBJID_CARET = 0xFFFFFFF8
_ACC_LOCATION = ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p, ctypes.POINTER(wintypes.LONG),
                                   ctypes.POINTER(wintypes.LONG), ctypes.POINTER(wintypes.LONG),
                                   ctypes.POINTER(wintypes.LONG), VARIANT)


def _curseur_accessible(hwnd):
    """Le curseur selon l'accessibilité (navigateurs, Word, applications récentes)."""
    if oleacc is None or not hwnd:
        return None
    objet = ctypes.c_void_p()
    if oleacc.AccessibleObjectFromWindow(hwnd, OBJID_CARET, ctypes.byref(IID_IACCESSIBLE),
                                         ctypes.byref(objet)) != 0 or not objet:
        return None
    try:
        x, y, larg, h = (wintypes.LONG() for _ in range(4))
        enfant = VARIANT()
        enfant.vt = 3                          # VT_I4, CHILDID_SELF
        if _rappeler(objet, 22, _ACC_LOCATION, ctypes.byref(x), ctypes.byref(y),
                     ctypes.byref(larg), ctypes.byref(h), enfant) != 0:
            return None
        if x.value == 0 and y.value == 0 and h.value == 0:
            return None
        return x.value, y.value, max(h.value, 1)
    finally:
        _rappeler(objet, 2, _LIBERER)


def curseur():
    """(x, y, hauteur) du curseur de texte de l'application active, à l'écran, ou None."""
    fg = user32.GetForegroundWindow()
    if not fg:
        return None
    info = GUITHREADINFO()
    info.cbSize = ctypes.sizeof(GUITHREADINFO)
    if user32.GetGUIThreadInfo(fil_de(fg), ctypes.byref(info)) and info.hwndCaret:
        r = info.rcCaret
        if r.bottom > r.top:
            p = POINT(r.left, r.top)
            user32.ClientToScreen(info.hwndCaret, ctypes.byref(p))
            return p.x, p.y, r.bottom - r.top
    try:
        return _curseur_accessible(info.hwndFocus or fg)
    except OSError:
        return None


# Les mots de passe

CLSID_CUIAUTOMATION = GUID.de("ff48dba4-60ef-4201-aa87-54103eef594e")
IID_IUIAUTOMATION = GUID.de("30cbe57d-d9d0-452a-ab13-7ac5ac4825ee")
UIA_ISPASSWORD = 30019
_FOCUS = ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))
_PROPRIETE = ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(VARIANT))
_uia = threading.local()


def _automation():
    if getattr(_uia, "objet", None) is None:
        objet = ctypes.c_void_p()
        if ole32.CoCreateInstance(ctypes.byref(CLSID_CUIAUTOMATION), None, 0x1 | 0x4,
                                  ctypes.byref(IID_IUIAUTOMATION), ctypes.byref(objet)) != 0:
            return None
        _uia.objet = objet
    return _uia.objet


def mot_de_passe() -> bool:
    """Le champ qui a le focus attend-il un mot de passe ? Le clavier se tait alors,
    comme sous Linux et sur le téléphone : ni conversion, ni propositions."""
    fg = user32.GetForegroundWindow()
    info = GUITHREADINFO()
    info.cbSize = ctypes.sizeof(GUITHREADINFO)
    if fg and user32.GetGUIThreadInfo(fil_de(fg), ctypes.byref(info)) and info.hwndFocus:
        if user32.GetWindowLongW(info.hwndFocus, GWL_STYLE) & ES_PASSWORD \
                and classe(info.hwndFocus).lower().startswith("edit"):
            return True
    uia = _automation()
    if uia is None:
        return False
    element = ctypes.c_void_p()
    if _rappeler(uia, 8, _FOCUS, ctypes.byref(element)) != 0 or not element:
        return False
    try:
        v = VARIANT()
        if _rappeler(element, 10, _PROPRIETE, UIA_ISPASSWORD, ctypes.byref(v)) != 0:
            return False
        resultat = v.vt == 11 and (v.valeur & 0xFFFF) != 0      # VT_BOOL, VARIANT_TRUE
        oleaut32.VariantClear(ctypes.byref(v))
        return resultat
    finally:
        _rappeler(element, 2, _LIBERER)


# Les crochets

class Crochets:
    """Le crochet clavier, le crochet souris et les changements de fenêtre, dans
    un fil à eux, qui fait tourner la boucle de messages dont ils ont besoin.

    Les rappels doivent répondre vite : Windows retire sans prévenir un crochet
    trop lent. Ils ne font que décider ; tout le reste part dans d'autres fils.
    Et si Windows en retire un quand même (l'ordinateur très occupé, Word qui
    démarre), la veille le voit : une touche ou un geste que Windows a reçus et
    que nos crochets n'ont pas vus. Elle les repose aussitôt.
    """

    ECART_MAX = 400           # ms : une entrée plus récente que ce que nous avons vu
    REPOS_MIN = 2.0           # s entre deux reposes de la veille
    VEILLE = 0.25             # s entre deux regards

    def __init__(self, sur_touche, sur_clic, sur_fenetre, a_l_arret=None):
        self.sur_touche = sur_touche        # (message, KBDLLHOOKSTRUCT) -> bloquer ?
        self.sur_clic = sur_clic            # (x, y) -> None
        self.sur_fenetre = sur_fenetre      # (evenement, hwnd) -> None
        self.a_l_arret = a_l_arret
        self.fil = None
        self.id_fil = 0
        self.pret = threading.Event()
        self._crochets = []
        self._rappels = []                  # gardés en vie : ctypes ne le fait pas
        self.taches = []                    # ce que d'autres fils demandent à celui-ci
        self._verrou = threading.Lock()
        self.erreur = None
        self.vu = kernel32.GetTickCount()   # la dernière entrée vue par nos crochets
        self.reposes = 0                    # par la veille
        self._fin = threading.Event()

    def demarrer(self):
        self.fil = threading.Thread(target=self._tourner, name="crochets", daemon=True)
        self.fil.start()
        self.pret.wait(5)
        if not self.erreur:
            threading.Thread(target=self._veiller, name="veille", daemon=True).start()
        return self

    def arreter(self):
        self._fin.set()
        if self.id_fil:
            user32.PostThreadMessageW(self.id_fil, WM_QUIT, 0, 0)

    def _veiller(self):
        dernier_repos = 0.0
        while not self._fin.wait(self.VEILLE):
            vu = self.vu
            if self.verifier() and time.monotonic() - dernier_repos >= self.REPOS_MIN:
                dernier_repos = time.monotonic()
                self.reposes += 1
                print(f"crochets : une entrée que nous n'avons pas vue "
                      f"({ecart(self.vu, vu)} ms, {classe(fenetre_active() or 0)}) : reposés",
                      flush=True)
                self.reposer()

    def verifier(self) -> bool:
        """Vrai si Windows a reçu une entrée que nos crochets n'ont pas vue."""
        recue = derniere_entree()
        if recue and ecart(recue, self.vu) > self.ECART_MAX:
            self.vu = recue                 # une seule fois par entrée manquée
            # Une application en administrateur : Windows ne nous montre pas ses
            # touches, nos crochets n'ont rien perdu.
            return peut_ecrire_dans(fenetre_active() or 0)
        return False

    def dans_le_fil(self, fonction):
        """Fait exécuter fonction par le fil des crochets (création de fenêtres)."""
        with self._verrou:
            self.taches.append(fonction)
        if self.id_fil:
            user32.PostThreadMessageW(self.id_fil, WM_APP + 1, 0, 0)

    def reposer(self):
        """Remet les crochets : Windows a pu en retirer un qui a tardé une fois."""
        self.dans_le_fil(self._reposer)

    def _clavier(self, code, wparam, lparam):
        if code == HC_ACTION:
            k = KBDLLHOOKSTRUCT.from_address(lparam)
            self.vu = k.time
            if k.dwExtraInfo != MARQUE:
                try:
                    if self.sur_touche(wparam, k):
                        return 1
                except Exception as erreur:      # jamais une touche perdue pour une erreur
                    print(f"crochet clavier : {erreur!r}", flush=True)
        return user32.CallNextHookEx(None, code, wparam, lparam)

    def _souris(self, code, wparam, lparam):
        if code == HC_ACTION:
            m = MSLLHOOKSTRUCT.from_address(lparam)
            self.vu = m.time
        if code == HC_ACTION and wparam in (WM_LBUTTONDOWN, WM_RBUTTONDOWN,
                                            WM_MBUTTONDOWN, WM_XBUTTONDOWN):
            try:
                self.sur_clic(m.pt.x, m.pt.y)
            except Exception as erreur:
                print(f"crochet souris : {erreur!r}", flush=True)
        return user32.CallNextHookEx(None, code, wparam, lparam)

    def _fenetre(self, _crochet, evenement, hwnd, _objet, _enfant, _fil, _temps):
        try:
            self.sur_fenetre(evenement, hwnd)
        except Exception as erreur:
            print(f"crochet fenêtres : {erreur!r}", flush=True)

    def _poser(self):
        module = kernel32.GetModuleHandleW(None)
        rappel_clavier = HOOKPROC(self._clavier)
        rappel_souris = HOOKPROC(self._souris)
        self._rappels += [rappel_clavier, rappel_souris]
        c = user32.SetWindowsHookExW(WH_KEYBOARD_LL, rappel_clavier, module, 0)
        s = user32.SetWindowsHookExW(WH_MOUSE_LL, rappel_souris, module, 0)
        if not c:
            raise OSError(ctypes.get_last_error(), "crochet clavier refusé")
        self._crochets = [x for x in (c, s) if x]

    def _reposer(self):
        anciens = self._crochets
        self._poser()
        for h in anciens:
            user32.UnhookWindowsHookEx(h)
        self._rappels = self._rappels[-2:]

    def _tourner(self):
        self.id_fil = kernel32.GetCurrentThreadId()
        initialiser_com()
        try:
            self._poser()
        except OSError as erreur:
            self.erreur = erreur
            self.pret.set()
            return
        rappel_fenetre = WINEVENTPROC(self._fenetre)
        self._rappels.append(rappel_fenetre)
        drapeaux = WINEVENT_OUTOFCONTEXT | WINEVENT_SKIPOWNPROCESS
        evenements = [user32.SetWinEventHook(e, e, None, rappel_fenetre, 0, 0, drapeaux)
                      for e in (EVENT_SYSTEM_FOREGROUND, EVENT_OBJECT_FOCUS)]
        self.rappel_fenetre = rappel_fenetre
        self.pret.set()
        msg = MSG()
        try:
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.hwnd is None and msg.message == WM_APP + 1:
                    with self._verrou:
                        taches, self.taches = self.taches, []
                    for tache in taches:
                        try:
                            tache()
                        except Exception as erreur:
                            print(f"crochets : {erreur!r}", flush=True)
                    continue
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
        finally:
            for h in self._crochets:
                user32.UnhookWindowsHookEx(h)
            for h in evenements:
                if h:
                    user32.UnhookWinEvent(h)
            if self.a_l_arret:
                self.a_l_arret()


# L'icône près de l'horloge

class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("hWnd", wintypes.HWND), ("uID", wintypes.UINT),
                ("uFlags", wintypes.UINT), ("uCallbackMessage", wintypes.UINT),
                ("hIcon", wintypes.HICON), ("szTip", wintypes.WCHAR * 128),
                ("dwState", wintypes.DWORD), ("dwStateMask", wintypes.DWORD),
                ("szInfo", wintypes.WCHAR * 256), ("uVersion", wintypes.UINT),
                ("szInfoTitle", wintypes.WCHAR * 64), ("dwInfoFlags", wintypes.DWORD),
                ("guidItem", GUID), ("hBalloonIcon", wintypes.HICON)]


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("style", wintypes.UINT), ("lpfnWndProc", WNDPROC),
                ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
                ("hInstance", wintypes.HINSTANCE), ("hIcon", wintypes.HICON),
                ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HBRUSH),
                ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR),
                ("hIconSm", wintypes.HICON)]


_signer(user32, "RegisterClassExW", wintypes.ATOM, ctypes.POINTER(WNDCLASSEXW))
_signer(shell32, "Shell_NotifyIconW", wintypes.BOOL, wintypes.DWORD,
        ctypes.POINTER(NOTIFYICONDATAW))

NIM_ADD, NIM_MODIFY, NIM_DELETE, NIM_SETVERSION = 0, 1, 2, 4
NIF_MESSAGE, NIF_ICON, NIF_TIP, NIF_INFO, NIF_SHOWTIP = 0x1, 0x2, 0x4, 0x10, 0x80
MF_STRING, MF_SEPARATOR, MF_CHECKED, MF_GRAYED = 0x0, 0x800, 0x8, 0x1
TPM_RETURNCMD, TPM_RIGHTBUTTON, TPM_BOTTOMALIGN = 0x100, 0x2, 0x20


class IconeNotification:
    """L'icône de Kab-board près de l'horloge : un clic droit ouvre le menu.

    Se crée dans le fil des crochets, qui a déjà sa boucle de messages.
    `menu()` rend la liste des entrées : (identifiant, libellé, coché, actif),
    ou None pour un séparateur. `choisir(identifiant)` est appelé au choix ;
    `double_clic()` au clic gauche.
    """

    MESSAGE = WM_APP + 7

    def __init__(self, icone_ico, infobulle, menu, choisir, double_clic):
        self.icone_ico = icone_ico
        self.infobulle = infobulle
        self.menu = menu
        self.choisir = choisir
        self.double_clic = double_clic
        self.hwnd = None
        self.hicon = None
        self._proc = WNDPROC(self._procedure)
        self._recree = user32.RegisterWindowMessageW("TaskbarCreated")

    def creer(self):
        module = kernel32.GetModuleHandleW(None)
        classe_ = WNDCLASSEXW()
        classe_.cbSize = ctypes.sizeof(WNDCLASSEXW)
        classe_.lpfnWndProc = self._proc
        classe_.hInstance = module
        classe_.lpszClassName = "KabBoardIcone"
        user32.RegisterClassExW(ctypes.byref(classe_))
        self.hwnd = user32.CreateWindowExW(0, "KabBoardIcone", "Kab-board", 0, 0, 0, 0, 0,
                                           None, None, module, None)
        if self.icone_ico and os.path.exists(self.icone_ico):
            self.hicon = user32.LoadImageW(None, self.icone_ico, 1, 0, 0, 0x10 | 0x40)
        if not self.hicon:
            self.hicon = user32.LoadIconW(None, ctypes.c_void_p(32512))   # IDI_APPLICATION
        self._ajouter()

    def _donnees(self, drapeaux):
        d = NOTIFYICONDATAW()
        d.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        d.hWnd = self.hwnd
        d.uID = 1
        d.uFlags = drapeaux
        d.uCallbackMessage = self.MESSAGE
        d.hIcon = self.hicon
        d.szTip = self.infobulle[:127]
        return d

    def _ajouter(self):
        d = self._donnees(NIF_MESSAGE | NIF_ICON | NIF_TIP)
        shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(d))

    def changer_infobulle(self, texte):
        self.infobulle = texte
        if self.hwnd:
            d = self._donnees(NIF_TIP)
            shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(d))

    def annoncer(self, titre_, texte):
        """Une bulle de notification, une seule fois : « le correcteur est prêt »."""
        if not self.hwnd:
            return
        d = self._donnees(NIF_INFO)
        d.szInfo = texte[:255]
        d.szInfoTitle = titre_[:63]
        d.dwInfoFlags = 0x1                    # NIIF_INFO
        shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(d))

    def retirer(self):
        if self.hwnd:
            d = self._donnees(0)
            shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(d))
            user32.DestroyWindow(self.hwnd)
            self.hwnd = None

    def _montrer_menu(self):
        h = user32.CreatePopupMenu()
        for entree in self.menu():
            if entree is None:
                user32.AppendMenuW(h, MF_SEPARATOR, 0, None)
                continue
            ident, libelle, coche, actif = entree
            drapeaux = MF_STRING | (MF_CHECKED if coche else 0) | (0 if actif else MF_GRAYED)
            user32.AppendMenuW(h, drapeaux, ident, libelle)
        x, y = souris()
        # Sans cela, le menu ne se ferme pas quand on clique ailleurs.
        user32.SetForegroundWindow(self.hwnd)
        choix = user32.TrackPopupMenu(h, TPM_RETURNCMD | TPM_RIGHTBUTTON | TPM_BOTTOMALIGN,
                                      x, y, 0, self.hwnd, None)
        user32.PostMessageW(self.hwnd, WM_NULL, 0, 0)
        user32.DestroyMenu(h)
        if choix:
            self.choisir(choix)

    def _procedure(self, hwnd, msg, wparam, lparam):
        if msg == self.MESSAGE:
            evenement = lparam & 0xFFFF
            try:
                if evenement in (WM_RBUTTONUP, WM_CONTEXTMENU):
                    self._montrer_menu()
                elif evenement == WM_LBUTTONUP:
                    self.double_clic()
            except Exception as erreur:
                print(f"icône : {erreur!r}", flush=True)
            return 0
        if msg == self._recree and self._recree:
            self._ajouter()                    # l'Explorateur a redémarré
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)
