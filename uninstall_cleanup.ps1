# duAI Uninstall Cleanup Script
# Este script se ejecuta después de desinstalar duAI para limpiar
# los datos de usuario en %LOCALAPPDATA%\duAI
$ErrorActionPreference = "SilentlyContinue"

$duaiDir = Join-Path $env:LOCALAPPDATA "duAI"

if (Test-Path $duaiDir) {
    # Detener cualquier proceso duAI en ejecucion
    Get-Process duAI -ErrorAction SilentlyContinue | Stop-Process -Force

    # Remover tarea programada si existe
    schtasks /Delete /TN "duAI_AutoClean" /F 2>$null

    # Eliminar directorio completo de duAI
    Remove-Item -Recurse -Force $duaiDir

    Write-Host "duAI datos de usuario eliminados de $duaiDir"
} else {
    Write-Host "No se encontraron datos de duAI en $duaiDir"
}
