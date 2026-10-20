$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$iscc = "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
$testIss = Join-Path $root "_test_setup.iss"
$testOut = Join-Path $root "installer_test"
$installDir = Join-Path $env:TEMP "duAI_install_test"

$content = Get-Content (Join-Path $root "duAI_setup.iss") -Raw
$content = $content -replace 'PrivilegesRequired=admin', 'PrivilegesRequired=lowest'
$content = $content -replace 'OutputDir=installer', 'OutputDir=installer_test'
$content = $content -replace 'OutputBaseFilename=duAI-Setup-', 'OutputBaseFilename=duAI-Setup-TEST-'
Set-Content -Path $testIss -Value $content -Encoding UTF8

& $iscc $testIss 2>&1 | Select-Object -Last 2
if ($LASTEXITCODE -ne 0) { Write-Error "Fallo de compilacion"; exit 1 }
$setup = Get-ChildItem (Join-Path $testOut "*.exe") | Select-Object -First 1

# ---- PASO 1: instalar y desinstalar sin lanzar nada ----
Start-Process -FilePath $setup.FullName -ArgumentList @(
    "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-", "/DIR=`"$installDir`""
) -Wait
$exe = Join-Path $installDir "duAI.exe"
Write-Host "P1 instalado: $(Test-Path $exe)"

$unins = Join-Path $installDir "unins000.exe"
Start-Process -FilePath $unins -ArgumentList @("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART") -Wait
Start-Sleep -Seconds 4
$p1ok = -not (Test-Path $exe)
Write-Host "P1 ejecutable eliminado tras desinstalar: $p1ok" -ForegroundColor $(if ($p1ok) { "Green" } else { "Red" })
if (-not $p1ok) { Get-ChildItem $installDir -ErrorAction SilentlyContinue | ForEach-Object { "   quedo: " + $_.Name } }

# ---- PASO 2: instalar, lanzar, cerrar y desinstalar ----
Start-Process -FilePath $setup.FullName -ArgumentList @(
    "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-", "/DIR=`"$installDir`""
) -Wait
$env:QT_QPA_PLATFORM = "offscreen"
$p = Start-Process -FilePath $exe -PassThru
Start-Sleep -Seconds 10
$alive = -not $p.HasExited
Write-Host "P2 exe lanzado y vivo: $alive"
if ($alive) { Stop-Process -Id $p.Id -Force; Start-Sleep -Seconds 5 }
Get-Process duAI -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 3
Remove-Item Env:\QT_QPA_PLATFORM

Start-Process -FilePath $unins -ArgumentList @("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART") -Wait
Start-Sleep -Seconds 6
$p2ok = -not (Test-Path $exe)
Write-Host "P2 ejecutable eliminado tras desinstalar: $p2ok" -ForegroundColor $(if ($p2ok) { "Green" } else { "Red" })
if (-not $p2ok) { Get-ChildItem $installDir -ErrorAction SilentlyContinue | ForEach-Object { "   quedo: " + $_.Name } }

# Reg HKCU de autostart borrada?
$run = Get-ItemProperty "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" -ErrorAction SilentlyContinue
Write-Host "HKCU Run 'duAI' presente: $([bool]$run.duAI)"

# Limpieza
Remove-Item $testIss -ErrorAction SilentlyContinue
Remove-Item $testOut -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item $installDir -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem "$env:APPDATA\Microsoft\Windows\Start Menu\Programs" -Filter "duAI*" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
Write-Host "=== Prueba completada (P1=$p1ok P2=$p2ok) ===" -ForegroundColor Cyan
