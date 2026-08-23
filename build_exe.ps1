$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$venvPython = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    python -m venv .venv
}

& $venvPython -m pip install --quiet pyinstaller PySide6

& $venvPython -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --noconsole `
    --name duAI `
    --add-data "config;config" `
    --add-data "duai\ui\theme.qss;duai\ui" `
    main.py

if (Test-Path (Join-Path $root "dist\duAI.exe")) {
    Write-Host ""
    Write-Host "EJECUTABLE PORTABLE CREADO: dist\duAI.exe"
    Write-Host "Puedes copiarlo a un USB: modo sigilo sin instalacion."
} else {
    Write-Error "No se genero el ejecutable."
}
