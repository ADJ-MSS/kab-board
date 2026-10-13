# Fabrique Kab-board pour Windows : le dossier portable, son archive .zip et
# l'installeur.
#
#   powershell -ExecutionPolicy Bypass -File paquet\construire.ps1 -Version 0.2
#
# Il faut :
#   - Windows 10 ou 11, 64 bits ;
#   - Python 3.12 (64 bits) de python.org : il est recopié dans le paquet, tkinter compris ;
#   - les ponts natifs et le lanceur, construits par natif\construire-dll.sh et
#     lanceur\construire.sh (mingw-w64, sous Linux ou WSL ; la CI le fait) ;
#   - le paquet Linux de kab-board 0.3 (kab-board-0.3.deb), dont on reprend les
#     ressources : téléchargé de la page des versions s'il n'est pas fourni ;
#   - Inno Setup 6 pour l'installeur (facultatif : sans lui, seulement le .zip).
#
# Sortie : sortie\Kab-board\ (le dossier), sortie\kab-board-windows-<v>-portable.zip,
#          sortie\kab-board-windows-<v>-setup.exe, sortie\SHA256SUMS.txt

param(
    [string]$Version = "0.2",
    [string]$Python = "",
    [string]$Deb = "",
    [string]$Natif = "",
    [string]$Lanceur = "",
    [switch]$SansInstalleur
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$ici = Split-Path -Parent $MyInvocation.MyCommand.Path
$depot = Split-Path -Parent $ici
$sortie = Join-Path $depot 'sortie'
$dist = Join-Path $sortie 'Kab-board'
$travail = Join-Path $depot 'construction'

$DEB_URL = 'https://github.com/ADJ-MSS/kab-board/releases/download/v0.3/kab-board-0.3.deb'
# L'empreinte que donne le fichier SHA256SUMS de la version.
$DEB_SHA256 = 'e559d731a0010b9601306a3f440371a1b8f619609e3d37315c6dc68b2f71a5df'
# Les mêmes versions que le reste de kab-board : ONNX Runtime de l'application
# Android, rapidfuzz du paquet Linux (une autre version ne retient pas les mêmes
# candidats à égalité).
$MODULES = @('numpy==2.1.3', 'onnxruntime==1.20.1', 'rapidfuzz==3.14.5')

function Etape($texte) { Write-Host ("  [{0:HH:mm:ss}] {1}" -f (Get-Date), $texte) }

if (-not $Python) { $Python = (& python -c "import sys; print(sys.base_prefix)").Trim() }
if (-not $Natif) { $Natif = Join-Path $depot 'natif\build' }
if (-not $Lanceur) { $Lanceur = Join-Path $depot 'lanceur\Kab-board.exe' }
$pythonExe = Join-Path $Python 'python.exe'
if (-not (Test-Path $pythonExe)) { throw "Python introuvable : $Python" }
$vpy = (& $pythonExe -c "import sys, struct; print('%d.%d %d' % (sys.version_info[0], sys.version_info[1], struct.calcsize('P') * 8))").Trim()
if ($vpy -ne '3.12 64') { throw "Il faut Python 3.12 en 64 bits (trouvé : $vpy)" }
foreach ($f in @('kab_lm.dll', 'kab_crf.dll')) {
    if (-not (Test-Path (Join-Path $Natif $f))) { throw "$f manque dans $Natif : lancez natif/construire-dll.sh" }
}
if (-not (Test-Path $Lanceur)) { throw "Kab-board.exe manque : lancez lanceur/construire.sh" }

Write-Host "Kab-board pour Windows $Version"
if (Test-Path $dist) { Remove-Item -Recurse -Force $dist }
New-Item -ItemType Directory -Force $dist, $travail | Out-Null

# 1. Python, tkinter compris, sans ce qui ne sert pas à l'utilisateur
Etape "Python 3.12…"
$py = Join-Path $dist 'python'
New-Item -ItemType Directory -Force $py | Out-Null
Get-ChildItem $Python -File | Where-Object { $_.Extension -in '.exe', '.dll', '.txt' -and $_.Name -notlike 'pythonw_d*' -and $_.Name -notlike 'python_d*' } |
    Copy-Item -Destination $py
Copy-Item -Recurse (Join-Path $Python 'DLLs') (Join-Path $py 'DLLs')
Copy-Item -Recurse (Join-Path $Python 'tcl') (Join-Path $py 'tcl')
$exclus = @('test', 'idlelib', 'ensurepip', 'lib2to3', 'turtledemo', 'site-packages', 'venv', 'pydoc_data', '__pycache__')
New-Item -ItemType Directory -Force (Join-Path $py 'Lib\site-packages') | Out-Null
Get-ChildItem (Join-Path $Python 'Lib') | Where-Object { $exclus -notcontains $_.Name } |
    ForEach-Object { Copy-Item -Recurse $_.FullName (Join-Path $py 'Lib') }
Get-ChildItem $py -Recurse -Directory -Filter '__pycache__' | Remove-Item -Recurse -Force
Get-ChildItem (Join-Path $py 'tcl') -Recurse -Directory | Where-Object { $_.Name -eq 'demos' } | Remove-Item -Recurse -Force

Etape "modules : $($MODULES -join ', ')…"
& $pythonExe -m pip install --quiet --disable-pip-version-check --no-deps --only-binary ':all:' `
    --target (Join-Path $py 'Lib\site-packages') @MODULES
if ($LASTEXITCODE -ne 0) { throw "pip a échoué" }

# Les bibliothèques C++ de Microsoft, à côté de python.exe : chargées d'ici en
# premier, elles servent à tous les modules, dans le bon ordre ou non.
$capi = Join-Path $py 'Lib\site-packages\onnxruntime\capi'
foreach ($f in @('msvcp140.dll', 'msvcp140_1.dll', 'vcruntime140_1.dll')) {
    $cible = Join-Path $py $f
    if (Test-Path $cible) { continue }
    $source = @((Join-Path $capi $f), (Join-Path $env:WINDIR "System32\$f")) | Where-Object { Test-Path $_ } | Select-Object -First 1
    if ($source) { Copy-Item $source $cible }
}

# 2. Le code
Etape "le code…"
New-Item -ItemType Directory -Force (Join-Path $dist 'windows'), (Join-Path $dist 'lanceur') | Out-Null
Get-ChildItem (Join-Path $depot 'windows') -File -Filter '*.py' | Copy-Item -Destination (Join-Path $dist 'windows')
Copy-Item -Recurse (Join-Path $depot 'moteur') (Join-Path $dist 'moteur')
Get-ChildItem (Join-Path $dist 'moteur') -Recurse -Filter 'test_*.py' | Remove-Item -Force
Get-ChildItem (Join-Path $dist 'moteur') -Recurse -Directory -Filter '__pycache__' | Remove-Item -Recurse -Force
Copy-Item (Join-Path $Natif 'kab_lm.dll'), (Join-Path $Natif 'kab_crf.dll') (Join-Path $dist 'moteur\pipeline')
Copy-Item (Join-Path $depot 'lanceur\kab-board.ico') (Join-Path $dist 'lanceur')
Copy-Item $Lanceur (Join-Path $dist 'Kab-board.exe')
Copy-Item (Join-Path $depot 'LICENSE'), (Join-Path $depot 'AUTHORS') $dist
Copy-Item (Join-Path $ici 'LISEZMOI.txt') $dist
Copy-Item (Join-Path $ici 'NOTICE.txt') $dist

# 3. Les ressources : celles du paquet Linux de kab-board, rien d'autre
Etape "les ressources de kab-board 0.3…"
if (-not $Deb) {
    $Deb = Join-Path $travail 'kab-board-0.3.deb'
    if (-not (Test-Path $Deb)) { Invoke-WebRequest -Uri $DEB_URL -OutFile $Deb -UseBasicParsing }
}
$empreinte = (Get-FileHash -Algorithm SHA256 $Deb).Hash.ToLower()
if ($empreinte -ne $DEB_SHA256) { throw "kab-board-0.3.deb n'a pas l'empreinte publiée ($empreinte)" }
$deballe = Join-Path $travail 'deb'
if (Test-Path $deballe) { Remove-Item -Recurse -Force $deballe }
New-Item -ItemType Directory -Force $deballe | Out-Null
Push-Location $deballe
try {
    # tar.exe (bsdtar), livré avec Windows 10 et 11, lit l'archive ar du .deb.
    & tar.exe -xf $Deb
    if ($LASTEXITCODE -ne 0) { throw "tar n'a pas pu ouvrir le .deb" }
    $donnees = Get-ChildItem -Filter 'data.tar*' | Select-Object -First 1
    & tar.exe -xf $donnees.Name
    if ($LASTEXITCODE -ne 0) { throw "tar n'a pas pu lire $($donnees.Name)" }
} finally { Pop-Location }
$ressources = Join-Path $deballe 'usr\share\kab-board'
Copy-Item -Recurse (Join-Path $ressources 'modeles') (Join-Path $dist 'modeles')
# Le nom accentué du graphe sémantique sort parfois abîmé d'une archive, sous
# Windows (« s├®mantique ») : le correcteur ne le trouverait plus.
$graphe = 'dictionnaire_sémantique_racinale_kabyle_V1.json'
$dossierGraphe = Join-Path $dist 'modeles\wordnet'
$trouve = Get-ChildItem $dossierGraphe -Filter 'dictionnaire_s*racinale_kabyle_V1.json' -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $trouve) { throw "le graphe sémantique manque dans le paquet de kab-board" }
if ($trouve.Name -ne $graphe) { Rename-Item $trouve.FullName $graphe }
# Le graphe tel que publié avec le correcteur, sans la provenance de chaque lien.
& (Join-Path $py 'python.exe') (Join-Path $ici 'graphe_sans_provenance.py') (Join-Path $dossierGraphe $graphe)
if ($LASTEXITCODE -ne 0) { throw "le graphe sémantique n'a pas pu être préparé" }
Copy-Item -Recurse (Join-Path $ressources 'assets') (Join-Path $dist 'assets')
# L'étiqueteur passe par le pont natif (pos_kab.crfsuite) : le modèle joblib,
# qui demanderait scikit-learn, ne sert pas.
Remove-Item -Force -ErrorAction SilentlyContinue (Join-Path $dist 'modeles\kab-POS-tagl.joblib')

# 4. Tout compiler d'avance : le premier démarrage n'a rien à faire
Etape "compilation…"
& (Join-Path $py 'python.exe') -m compileall -q -j 0 (Join-Path $py 'Lib') (Join-Path $dist 'windows') (Join-Path $dist 'moteur') | Out-Null

$taille = (Get-ChildItem $dist -Recurse -File | Measure-Object Length -Sum).Sum / 1MB
Write-Host ("  dossier : {0:N0} Mo" -f $taille)

# 5. L'archive portable : le même dossier, avec portable.txt
Etape "archive portable…"
Set-Content -Path (Join-Path $dist 'portable.txt') -Encoding UTF8 -Value @(
    "Ce fichier rend Kab-board portable : reglages, dictionnaire et cache restent",
    "dans le dossier donnees\, a cote. Supprimez-le pour tout ranger dans",
    "%LOCALAPPDATA%\kab-board, comme Kab-board pour Word.")
$zip = Join-Path $sortie "kab-board-windows-$Version-portable.zip"
if (Test-Path $zip) { Remove-Item $zip }
Push-Location $sortie
try {
    & tar.exe -a -c -f $zip 'Kab-board'
    if ($LASTEXITCODE -ne 0) { throw "l'archive n'a pas pu être faite" }
} finally { Pop-Location }
Remove-Item (Join-Path $dist 'portable.txt')

# 6. L'installeur
$fichiers = @($zip)
if (-not $SansInstalleur) {
    $iscc = @("$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
              "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
              "$env:ProgramFiles\Inno Setup 6\ISCC.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
    if ($iscc) {
        Etape "installeur…"
        & $iscc /Q "/DVersion=$Version" "/DSource=$dist" "/O$sortie" (Join-Path $ici 'kab-board-windows.iss')
        if ($LASTEXITCODE -ne 0) { throw "Inno Setup a échoué" }
        $fichiers += Join-Path $sortie "kab-board-windows-$Version-setup.exe"
    } else {
        Write-Host "  Inno Setup absent : pas d'installeur (winget install JRSoftware.InnoSetup)"
    }
}

$sommes = foreach ($f in $fichiers) { "{0}  {1}" -f (Get-FileHash -Algorithm SHA256 $f).Hash.ToLower(), (Split-Path -Leaf $f) }
$sommes | Set-Content -Encoding ASCII (Join-Path $sortie 'SHA256SUMS.txt')
foreach ($f in $fichiers) { Write-Host ("  {0} : {1:N0} Mo" -f (Split-Path -Leaf $f), ((Get-Item $f).Length / 1MB)) }
Write-Host "Fini."
