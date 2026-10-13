/* Kab-board.exe : lance Kab-board avec le Python livré dans son dossier.
 *
 *   Kab-board.exe             l'application de réglages, et le clavier allumé
 *   Kab-board.exe --clavier   le clavier seul (démarrage avec Windows)
 *   Kab-board.exe --bureau    la fenêtre « Écrire et relire »
 *
 * Rien n'est écrit ailleurs que dans le dossier : copié sur une clé USB, il
 * fonctionne tel quel sur un autre ordinateur. */
#ifndef UNICODE
#define UNICODE
#endif
#ifndef _UNICODE
#define _UNICODE
#endif
#include <windows.h>
#include <wchar.h>

#define TAILLE 4096

static void ajouter(wchar_t *dest, const wchar_t *texte) {
    size_t n = wcslen(dest);
    if (n + wcslen(texte) + 1 < TAILLE) wcscat(dest, texte);
}

static int contient(const wchar_t *arguments, const wchar_t *mot) {
    return arguments && wcsstr(arguments, mot) != NULL;
}

int WINAPI wWinMain(HINSTANCE instance, HINSTANCE precedente, PWSTR arguments, int montrer) {
    (void)instance; (void)precedente; (void)montrer;
    wchar_t dossier[TAILLE] = {0}, python[TAILLE] = {0}, ligne[TAILLE] = {0};
    DWORD n = GetModuleFileNameW(NULL, dossier, TAILLE);
    if (n == 0 || n >= TAILLE) return 1;
    wchar_t *barre = wcsrchr(dossier, L'\\');
    if (barre) *barre = L'\0';

    ajouter(python, dossier);
    ajouter(python, L"\\python\\pythonw.exe");
    if (GetFileAttributesW(python) == INVALID_FILE_ATTRIBUTES) {
        MessageBoxW(NULL,
            L"Kab-board ne trouve pas son Python, dans le dossier « python » "
            L"à côté de Kab-board.exe.\n\nReprenez le dossier complet de Kab-board "
            L"pour Windows (l'archive entière, décompressée).",
            L"Kab-board", MB_ICONERROR);
        return 2;
    }

    const wchar_t *script = L"kab_appli.py\" --allumer";
    if (contient(arguments, L"--clavier")) script = L"kab_saisie.py\"";
    else if (contient(arguments, L"--bureau")) script = L"kab_bureau.py\"";

    ajouter(ligne, L"\"");
    ajouter(ligne, python);
    ajouter(ligne, L"\" \"");
    ajouter(ligne, dossier);
    ajouter(ligne, L"\\windows\\");
    ajouter(ligne, script);

    STARTUPINFOW si;
    PROCESS_INFORMATION pi;
    ZeroMemory(&si, sizeof si);
    si.cb = sizeof si;
    ZeroMemory(&pi, sizeof pi);
    if (!CreateProcessW(python, ligne, NULL, NULL, FALSE, CREATE_NO_WINDOW, NULL, dossier,
                        &si, &pi)) {
        MessageBoxW(NULL, L"Kab-board n'a pas pu démarrer.", L"Kab-board", MB_ICONERROR);
        return 3;
    }
    CloseHandle(pi.hThread);
    CloseHandle(pi.hProcess);
    return 0;
}
