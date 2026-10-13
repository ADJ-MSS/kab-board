; Installeur de Kab-board pour Windows.
;
; Ne se compile pas seul : construire.ps1 prépare le dossier et appelle Inno
; Setup avec /DVersion=… et /DSource=…
;
; Tout s'installe dans le compte de l'utilisateur (%LOCALAPPDATA%\Programs) :
; aucun droit d'administrateur n'est demandé. Réglages et « mon dictionnaire »
; vont dans %LOCALAPPDATA%\kab-board, comme pour Word.

#ifndef Version
  #define Version "0.2"
#endif
#ifndef Source
  #define Source "..\sortie\Kab-board"
#endif

[Setup]
AppId={{5E0C2B1A-6F1D-4E4B-9D3C-0B7A3C1F9E21}
AppName=Kab-board pour Windows
AppVersion={#Version}
AppVerName=Kab-board pour Windows {#Version}
AppPublisher=kab-board
AppPublisherURL=https://github.com/ADJ-MSS/kab-board
UninstallDisplayName=Kab-board, clavier kabyle pour Windows
UninstallDisplayIcon={app}\Kab-board.exe
DefaultDirName={autopf}\Kab-board Windows
DisableWelcomePage=yes
DisableProgramGroupPage=yes
DisableDirPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputBaseFilename=kab-board-windows-{#Version}-setup
SetupIconFile=..\lanceur\kab-board.ico
Compression=lzma2/max
SolidCompression=yes
; Le modèle de langue et le modèle vocal pèsent lourd : quatre fils compressent.
LZMAUseSeparateProcess=yes
LZMANumBlockThreads=4
WizardStyle=modern
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "fr"; MessagesFile: "compiler:Languages\French.isl"

[Messages]
fr.ReadyLabel1=Le clavier kabyle va s'installer pour votre compte.
fr.ReadyLabel2b=Cliquez sur Installer. Aucun droit d'administrateur n'est nécessaire, et rien n'est envoyé sur Internet : tout se calcule sur cet ordinateur.
; Le texte d'origine parle d'icônes sur le Bureau : l'installeur n'en crée pas.
fr.FinishedLabel=L'assistant a terminé l'installation de [name] sur votre ordinateur.%n%nKab-board est dans le menu Démarrer. Ouvert, il allume le clavier kabyle : vous tapez sur votre clavier, dans toutes les applications.
fr.FinishedLabelNoIcons=L'assistant a terminé l'installation de [name] sur votre ordinateur.

[Tasks]
Name: "demarrage"; Description: "Allumer le clavier kabyle à l'ouverture de la session"; Flags: unchecked

[Files]
Source: "{#Source}\*"; DestDir: "{app}"; Excludes: "donnees"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{userprograms}\Kab-board"; Filename: "{app}\Kab-board.exe"; Comment: "Clavier et correcteur kabyles"
Name: "{userprograms}\Écrire et relire (Kab-board)"; Filename: "{app}\Kab-board.exe"; Parameters: "--bureau"

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "Kab-board"; ValueData: """{app}\Kab-board.exe"" --clavier"; Tasks: demarrage; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: none; ValueName: "Kab-board"; Flags: uninsdeletevalue dontcreatekey

[UninstallRun]
; Le clavier, s'il tourne, s'arrête avant que ses fichiers partent : seulement
; les Python de ce dossier, aucun autre.
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -Command ""Get-Process pythonw,python -ErrorAction SilentlyContinue | Where-Object {{ $_.Path -like '{app}\*' }} | Stop-Process -Force"""; Flags: runhidden; RunOnceId: "ArretClavier"

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
; Le cache se refait tout seul ; « mon dictionnaire » reste.
Type: filesandordirs; Name: "{localappdata}\kab-board\cache-clavier"

[Run]
Filename: "{app}\Kab-board.exe"; Description: "Ouvrir Kab-board"; Flags: nowait postinstall skipifsilent
