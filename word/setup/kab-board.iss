; Installeur du correcteur kabyle pour Word.
;
; Ne se compile pas seul : lancez construire.ps1, qui prepare le pont et les
; inscriptions COM (construction\inscription.iss) puis appelle Inno Setup.
;
; Tout s'installe dans le compte de l'utilisateur (%LOCALAPPDATA%\Programs) :
; aucun droit d'administrateur n'est demande.

#define Version "0.3"
#define Paquet "..\kab-board-word-complet-0.1"

[Setup]
AppId={{A7C568C9-947F-4E02-8656-218E208803C1}
AppName=Kab-board pour Word
AppVersion={#Version}
AppVerName=Kab-board pour Word {#Version}
AppPublisher=kab-board
AppPublisherURL=https://github.com/ADJ-MSS/kab-board
AppSupportURL=https://github.com/ADJ-MSS/kab-board
UninstallDisplayName=Kab-board, correcteur kabyle pour Word
DefaultDirName={autopf}\Kab-board
; Le moins de pages possible : double-clic, « Installer », « Terminer ».
DisableWelcomePage=yes
DisableProgramGroupPage=yes
DisableDirPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=6.3
OutputDir=sortie
OutputBaseFilename=kab-board-word-setup-{#Version}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "fr"; MessagesFile: "compiler:Languages\French.isl"

[Messages]
; Inno Setup demande toujours une confirmation : c'est la seule page avant l'installation.
fr.ReadyLabel1=Le correcteur kabyle va s'ajouter à Microsoft Word.
fr.ReadyLabel2b=Cliquez sur Installer. Aucun droit d'administrateur n'est nécessaire, et rien n'est envoyé sur Internet : tout se calcule sur cet ordinateur.
; Sans raccourci dans le menu Demarrer, c'est ce message-ci qu'Inno Setup affiche a la fin.
fr.FinishedLabelNoIcons=Le correcteur kabyle est installé.%n%nOuvrez Word : l'onglet « Kab-board » est dans le ruban. Le correcteur se prépare à chaque ouverture de Word : comptez une quinzaine de secondes, jusqu'à une minute juste après le démarrage de l'ordinateur, avant que « Relire le document » soit prêt.

[Files]
; Les __pycache__ restent : sans eux, le premier demarrage du moteur recompile
; scipy et scikit-learn et prend plusieurs minutes.
; KabBoardWord.dll, livree par la 0.1, n'est plus installee.
Source: "{#Paquet}\*"; DestDir: "{app}"; Excludes: "KabBoardPont.dll,KabBoardPont.cs,KabBoardWord.dll,installer.ps1,desinstaller.ps1"; Flags: recursesubdirs ignoreversion
Source: "construction\KabBoardPont.dll"; DestDir: "{app}"; Flags: ignoreversion

[InstallDelete]
; Ce que la 0.1 avait installe et qui ne sert plus.
Type: files; Name: "{app}\KabBoardWord.dll"
Type: files; Name: "{app}\KabBoardPont.cs"

[Registry]
; L'ancienne entree, qui chargeait KabBoardWord.dll directement, fait planter Word.
Root: HKCU; Subkey: "Software\Microsoft\Office\Word\Addins\KabBoard.Correcteur"; ValueType: none; Flags: deletekey
; La declaration du complement a Word : c'est le pont que Word charge.
Root: HKCU; Subkey: "Software\Microsoft\Office\Word\Addins\KabBoard.Pont"; ValueType: string; ValueName: "FriendlyName"; ValueData: "Kab-board"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Microsoft\Office\Word\Addins\KabBoard.Pont"; ValueType: string; ValueName: "Description"; ValueData: "Correcteur kabyle kab-board"
Root: HKCU; Subkey: "Software\Microsoft\Office\Word\Addins\KabBoard.Pont"; ValueType: dword; ValueName: "LoadBehavior"; ValueData: 3
; Les reglages du complement (la graphie choisie).
Root: HKCU; Subkey: "Software\Kab-board"; ValueType: none; Flags: uninsdeletekey
; Les classes COM du complement, generees par construire.ps1 a partir de RegAsm.
#include "construction\inscription.iss"

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
; Le cache du moteur se refait tout seul ; « mon dictionnaire » reste.
Type: filesandordirs; Name: "{localappdata}\kab-board\cache"

[Run]
; Ce qui manquerait encore se compile ici, pendant l'installation, plutot qu'au
; premier demarrage de Word.
Filename: "{app}\python\python.exe"; Parameters: "-m compileall -q -j 0 ""{app}\python\Lib"" ""{app}\moteur"""; StatusMsg: "Préparation du correcteur…"; Flags: runhidden
; Le cache du lexique et du vivier (voir moteur\linux\pipeline\ressources.py) :
; sans lui, le premier demarrage dans Word prendrait 40 secondes de plus.
Filename: "{app}\python\python.exe"; Parameters: """{app}\moteur\preparer_cache.py"""; StatusMsg: "Préparation du correcteur (une minute environ)…"; Flags: runhidden
Filename: "{app}\LISEZMOI.txt"; Description: "Lire le mode d'emploi"; Flags: postinstall shellexec skipifsilent unchecked

[Code]
const
  NetFx472 = 461808;

// La CodeBase des classes COM : l'adresse file:/// de la DLL installee.
function CodeBase(Fichier: String): String;
begin
  Result := ExpandConstant('{app}\') + Fichier;
  StringChangeEx(Result, '\', '/', True);
  Result := 'file:///' + Result;
end;

function WordOuvert(): Boolean;
begin
  Result := FindWindowByClassName('OpusApp') <> 0;
end;

function InitializeSetup(): Boolean;
var
  Version: Cardinal;
begin
  Result := True;
  if not RegQueryDWordValue(HKLM, 'SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full', 'Release', Version)
     or (Version < NetFx472) then
  begin
    MsgBox('Kab-board a besoin du .NET Framework 4.7.2 ou plus récent.' + #13#10 +
           'Installez-le depuis le site de Microsoft, puis relancez cette installation.', mbError, MB_OK);
    Result := False;
    Exit;
  end;
  if not DirExists(ExpandConstant('{win}\assembly\GAC_MSIL\Microsoft.Office.Interop.Word')) then
  begin
    Result := MsgBox('Word ne semble pas installé sur cet ordinateur (ou sans sa « Prise en charge de la programmabilité .NET »).' + #13#10 +
                     'Le correcteur ne pourra pas fonctionner sans. Installer quand même ?', mbConfirmation, MB_YESNO) = IDYES;
  end;
end;

// Word tient les DLL ouvertes : il faut le fermer pour les retirer.
function InitializeUninstall(): Boolean;
begin
  Result := True;
  // En mode silencieux, la reponse par defaut est Annuler : pas de boucle sans fin.
  while Result and WordOuvert() do
    Result := SuppressibleMsgBox('Fermez Word avant de désinstaller Kab-board, puis cliquez sur OK.',
                                 mbInformation, MB_OKCANCEL, IDCANCEL) = IDOK;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Code: Integer;
begin
  // Le moteur du correcteur peut survivre a Word quelques secondes.
  if CurUninstallStep = usUninstall then
    Exec('powershell.exe',
         '-NoProfile -Command "Get-Process pythonw -ErrorAction SilentlyContinue | Where-Object { $_.Path -like ''' +
         ExpandConstant('{app}') + '\*'' } | Stop-Process -Force"',
         '', SW_HIDE, ewWaitUntilTerminated, Code);
end;
