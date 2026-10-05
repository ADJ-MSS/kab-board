# Fabrique l'installeur kab-board-word-setup-<version>.exe dans sortie\.
#
#   powershell -ExecutionPolicy Bypass -File .\construire.ps1
#
# Il faut Inno Setup 6 (winget install JRSoftware.InnoSetup) et un Word installe
# sur cette machine : le complement (sources dans complement\) se compile contre
# les assemblages d'interop d'Office.

$ErrorActionPreference = 'Stop'
$ici = Split-Path -Parent $MyInvocation.MyCommand.Path
$paquet = Join-Path (Split-Path -Parent $ici) 'kab-board-word-complet-0.1'
$sources = Join-Path (Split-Path -Parent $ici) 'complement'
$construction = Join-Path $ici 'construction'
New-Item -ItemType Directory -Force $construction | Out-Null

$cadre = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319'
$gac = Join-Path $env:WINDIR 'assembly\GAC_MSIL'
$office = Get-ChildItem "$gac\office" -Recurse -Filter office.dll | Select-Object -First 1
$interopWord = Get-ChildItem "$gac\Microsoft.Office.Interop.Word" -Recurse -Filter Microsoft.Office.Interop.Word.dll | Select-Object -First 1
if (-not $office -or -not $interopWord) { throw "Les assemblages d'interop d'Office sont introuvables : installez Word." }

$iscc = @("$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
          "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
          "$env:ProgramFiles\Inno Setup 6\ISCC.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw "Inno Setup 6 est introuvable : winget install JRSoftware.InnoSetup" }

Write-Host "Compilation du complément…"
$pont = Join-Path $construction 'KabBoardPont.dll'
& "$cadre\csc.exe" /nologo /codepage:65001 /target:library /reference:$($office.FullName) /reference:$($interopWord.FullName) `
    /reference:System.Windows.Forms.dll /reference:System.Drawing.dll /reference:System.Web.Extensions.dll `
    /out:$pont (Join-Path $sources '*.cs')
if ($LASTEXITCODE -ne 0) { throw "La compilation du complément a echoue." }

# RegAsm dit ce qu'il inscrirait sous HKEY_CLASSES_ROOT ; on le traduit en
# entrees Inno Setup sous HKCU\Software\Classes, dans les deux vues du registre
# (Word 64 et 32 bits). La CodeBase est calculee a l'installation.
# Seul KabBoardPont.dll est inscrit.
Write-Host "Inscriptions COM…"
$lignes = New-Object System.Collections.Generic.List[string]
$racinesPossedees = New-Object System.Collections.Generic.HashSet[string]
foreach ($dll in @($pont)) {
    $nom = Split-Path -Leaf $dll
    $fichierReg = Join-Path $construction "$nom.reg"
    & "$cadre\RegAsm.exe" /codebase /silent /regfile:$fichierReg $dll
    if ($LASTEXITCODE -ne 0) { throw "RegAsm n'a pas pu lire $nom." }

    $cle = $null
    foreach ($ligne in Get-Content $fichierReg) {
        if ($ligne -match '^\[HKEY_CLASSES_ROOT\\(.+)\]$') {
            $cle = $Matches[1]
            $morceaux = $cle -split '\\'
            $possedee = if ($morceaux[0] -in 'CLSID', 'Record') { $morceaux[0..1] -join '\' } else { $morceaux[0] }
            if ($racinesPossedees.Add($possedee)) {
                foreach ($vue in 'HKCU32', 'HKCU64') {
                    $controle = if ($vue -eq 'HKCU64') { '; Check: IsWin64' } else { '' }
                    $lignes.Add("Root: $vue; Subkey: ""Software\Classes\$($possedee -replace '\{', '{{')""; ValueType: none; Flags: uninsdeletekey$controle")
                }
            }
            foreach ($vue in 'HKCU32', 'HKCU64') {
                $controle = if ($vue -eq 'HKCU64') { '; Check: IsWin64' } else { '' }
                $lignes.Add("Root: $vue; Subkey: ""Software\Classes\$($cle -replace '\{', '{{')""; ValueType: none$controle")
            }
        } elseif ($cle -and $ligne -match '^(@|"((?:[^"\\]|\\.)*)")="((?:[^"\\]|\\.)*)"$') {
            $valeurNom = if ($Matches[1] -eq '@') { '' } else { $Matches[2] -replace '\\(.)', '$1' }
            $valeur = $Matches[3] -replace '\\(.)', '$1'
            if ($valeurNom -eq 'CodeBase') { $donnee = "{code:CodeBase|$nom}" }
            else { $donnee = $valeur -replace '\{', '{{' -replace '"', '""' }
            foreach ($vue in 'HKCU32', 'HKCU64') {
                $controle = if ($vue -eq 'HKCU64') { '; Check: IsWin64' } else { '' }
                $lignes.Add("Root: $vue; Subkey: ""Software\Classes\$($cle -replace '\{', '{{')""; ValueType: string; ValueName: ""$valeurNom""; ValueData: ""$donnee""$controle")
            }
        }
    }
    Remove-Item $fichierReg
}
$lignes | Set-Content (Join-Path $construction 'inscription.iss') -Encoding UTF8

Write-Host "Inno Setup…"
& $iscc /Q (Join-Path $ici 'kab-board.iss')
if ($LASTEXITCODE -ne 0) { throw "Inno Setup a echoue." }
Get-ChildItem (Join-Path $ici 'sortie') -Filter *.exe | ForEach-Object {
    Write-Host ("Installeur : {0}  ({1:N0} Mo)" -f $_.FullName, ($_.Length / 1MB)) -ForegroundColor Green
}
