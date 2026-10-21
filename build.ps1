# Build portable Windows executables (unsigned — no Authenticode certificate).
# SmartScreen may warn on first run; use "More info" -> "Run anyway" or unblock the folder.

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

python -m pip install --upgrade pip
python -m pip install pyinstaller

Write-Host "Building folder layout (recommended for USB)..." -ForegroundColor Cyan
python -m PyInstaller --clean --noconfirm file_type_copier.spec

Copy-Item -Path "Run File Type Copier.bat" -Destination "dist\FileTypeCopier\" -Force

Write-Host "Building single-file exe (optional)..." -ForegroundColor Cyan
python -m PyInstaller --clean --noconfirm file_type_copier_onefile.spec

Write-Host ""
Write-Host "Done." -ForegroundColor Green
Write-Host "  USB (recommended): copy entire folder dist\FileTypeCopier to the flash drive"
Write-Host "  USB launcher:      dist\FileTypeCopier\Run File Type Copier.bat"
Write-Host "  Single exe:        dist\FileTypeCopier.exe"
Write-Host ""
Write-Host "Do NOT run build\file_type_copier\FileTypeCopier.exe (incomplete; Python DLL error)."
Write-Host ""
Write-Host "Reduce Windows warnings (unsigned app):"
Write-Host "  - Copy to USB, then right-click FileTypeCopier.exe -> Properties -> Unblock"
Write-Host "  - Or unblock the whole folder: Unblock-File -Path 'X:\FileTypeCopier\*' -Recurse"
