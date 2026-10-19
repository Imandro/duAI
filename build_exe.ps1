$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

Write-Host "=== duAI Build Script ===" -ForegroundColor Cyan

# 1. Crear entorno virtual si no existe
$venvPython = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "Creando entorno virtual..." -ForegroundColor Yellow
    python -m venv .venv
}

# 2. Instalar dependencias
Write-Host "Instalando dependencias..." -ForegroundColor Yellow
& $venvPython -m pip install --quiet --upgrade pip
& $venvPython -m pip install --quiet pyinstaller PySide6 pywinpty requests

# 3. Generar archivo .ico para Windows (si no existe o forzar)
$icoPath = Join-Path $root "assets\duAI.ico"
$pngPath = Join-Path $root "assets\duAI.png"
if (-not (Test-Path $icoPath) -or (Test-Path $pngPath)) {
    Write-Host "Generando icono .ico..." -ForegroundColor Yellow
    & $venvPython - <<'PY'
from PIL import Image
import os
root = os.path.dirname(os.path.abspath(__file__)) if '__file__' in dir() else os.getcwd()
png = os.path.join(root, "assets", "duAI.png")
ico = os.path.join(root, "assets", "duAI.ico")
if os.path.exists(png):
    img = Image.open(png).convert("RGBA")
    sizes = [(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)]
    img.save(ico, format="ICO", sizes=sizes)
    print("Icono generado:", ico)
else:
    print("PNG no encontrado, saltando icono")
PY
}

# 4. Construir ejecutable con PyInstaller
Write-Host "Construyendo ejecutable con PyInstaller..." -ForegroundColor Yellow
& $venvPython -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --noconsole `
    --name duAI `
    --icon "assets\duAI.ico" `
    --add-data "config;config" `
    --add-data "duai\ui\theme.qss;duai\ui" `
    --add-data "assets;assets" `
    main.py

# 5. Verificar resultado
if (Test-Path (Join-Path $root "dist\duAI.exe")) {
    Write-Host ""
    Write-Host "EJECUTABLE PORTABLE CREADO: dist\duAI.exe" -ForegroundColor Green
    $size = (Get-Item (Join-Path $root "dist\duAI.exe")).Length / 1MB
    Write-Host "Tamano: $({"{0:N2}" -f $size}) MB" -ForegroundColor Green
    Write-Host "Puedes copiarlo a un USB: modo sigilo sin instalacion." -ForegroundColor Green
} else {
    Write-Error "No se genero el ejecutable."
}

# 6. Opcional: crear instalador con Inno Setup si esta disponible
$iscc = Get-Command "ISCC" -ErrorAction SilentlyContinue
if ($iscc) {
    Write-Host ""
    Write-Host "Inno Setup detectado. Creando instalador..." -ForegroundColor Yellow
    & $iscc "duAI_setup.iss"
    if (Test-Path (Join-Path $root "installer\duAI-Setup-2.0.0.exe")) {
        Write-Host "INSTALADOR CREADO: installer\duAI-Setup-2.0.0.exe" -ForegroundColor Green
    }
} else {
    Write-Host ""
    Write-Host "Inno Setup no esta instalado. Para crear el instalador:" -ForegroundColor Yellow
    Write-Host "  1. Instala Inno Setup desde https://jrsoftware.org/isinfo.php"
    Write-Host "  2. Ejecuta: ISCC duAI_setup.iss" -ForegroundColor Yellow
}
