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
& $venvPython -m pip install --quiet pyinstaller PySide6 pywinpty requests Pillow

# 3. Generar archivo .ico para Windows (si no existe o falta el PNG-derived)
$icoPath = Join-Path $root "assets\duAI.ico"
$pngPath = Join-Path $root "assets\duAI.png"
if (-not (Test-Path $icoPath)) {
    Write-Host "Generando icono .ico..." -ForegroundColor Yellow
    $iconScript = Join-Path $root "_gen_icon.py"
    @'
from PIL import Image
import os
root = os.getcwd()
png = os.path.join(root, "assets", "duAI.png")
ico = os.path.join(root, "assets", "duAI.ico")
if os.path.exists(png):
    img = Image.open(png).convert("RGBA")
    sizes = [(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)]
    img.save(ico, format="ICO", sizes=sizes)
    print("Icono generado:", ico)
else:
    print("PNG no encontrado, saltando icono")
'@ | Set-Content -Path $iconScript -Encoding UTF8
    & $venvPython $iconScript
    Remove-Item $iconScript -ErrorAction SilentlyContinue
}

# 4. Construir ejecutable con PyInstaller
Write-Host "Construyendo ejecutable con PyInstaller..." -ForegroundColor Yellow
$dataArgs = @(
    "--add-data", "config;config",
    "--add-data", "duai\ui\theme.qss;duai\ui",
    "--add-data", "duai\i18n\translations;duai\i18n\translations",
    "--add-data", "browser_extension;browser_extension",
    "--add-data", "assets;assets"
)
foreach ($extra in @("duai\prompts", "duai\data")) {
    if (Test-Path (Join-Path $root $extra)) {
        $dataArgs += @("--add-data", "$extra;$extra")
    }
}

& $venvPython -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --noconsole `
    --name duAI `
    --icon "assets\duAI.ico" `
    @dataArgs `
    main.py

# 5. Verificar resultado
if (Test-Path (Join-Path $root "dist\duAI.exe")) {
    Write-Host ""
    Write-Host "EJECUTABLE PORTABLE CREADO: dist\duAI.exe" -ForegroundColor Green
    $size = (Get-Item (Join-Path $root "dist\duAI.exe")).Length / 1MB
    Write-Host ("Tamano: {0:N2} MB" -f $size) -ForegroundColor Green
    Write-Host "Puedes copiarlo a un USB: modo sigilo sin instalacion." -ForegroundColor Green
} else {
    Write-Error "No se genero el ejecutable."
}

# 6. Opcional: crear instalador con Inno Setup si esta disponible
$isccCandidates = @(
    (Get-Command "ISCC" -ErrorAction SilentlyContinue | ForEach-Object { $_.Source }),
    "$env:ProgramFiles(x86)\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
) | Where-Object { $_ -and (Test-Path $_) }

$iscc = $isccCandidates | Select-Object -First 1
if ($iscc) {
    $issFile = Join-Path $root "duAI_setup.iss"
    Write-Host ""
    Write-Host "Inno Setup detectado. Creando instalador..." -ForegroundColor Yellow
    & $iscc $issFile
    if ($LASTEXITCODE -eq 0) {
        $setup = Get-ChildItem (Join-Path $root "installer\*.exe") -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($setup) {
            Write-Host ("INSTALADOR CREADO: installer\{0}" -f $setup.Name) -ForegroundColor Green
        }
    } else {
        Write-Warning "ISCC devolvio el codigo $LASTEXITCODE"
    }
} else {
    Write-Host ""
    Write-Host "Inno Setup no esta instalado. Para crear el instalador:" -ForegroundColor Yellow
    Write-Host "  1. Instala Inno Setup desde https://jrsoftware.org/isinfo.php" -ForegroundColor Yellow
    Write-Host "  2. Ejecuta: ISCC duAI_setup.iss" -ForegroundColor Yellow
}
