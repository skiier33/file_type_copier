# Build portable Windows executables (unsigned — no Authenticode certificate).
# SmartScreen may warn on first run; use "More info" -> "Run anyway" or unblock the folder.

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

python -m pip install --upgrade pip
python -m pip install pyinstaller

Write-Host "Close File Type Copier if it is open..." -ForegroundColor Yellow
Get-Process -Name "FileTypeCopier" -ErrorAction SilentlyContinue | Stop-Process -Force

Write-Host "Building folder layout (recommended for USB)..." -ForegroundColor Cyan
python -m PyInstaller --clean --noconfirm file_type_copier.spec
if ($LASTEXITCODE -ne 0) {
    Write-Host "Build failed. Close FileTypeCopier.exe and any Explorer window in dist\FileTypeCopier, then retry." -ForegroundColor Red
    exit $LASTEXITCODE
}

Copy-Item -Path "Run File Type Copier.bat" -Destination "dist\FileTypeCopier\" -Force

if (-not (Test-Path "dist\FileTypeCopier\base_library.zip")) {
    Write-Host "dist\FileTypeCopier is incomplete (missing base_library.zip). Do not copy to USB." -ForegroundColor Red
    exit 1
}

$vc1 = Join-Path (python -c "import sys; print(sys.base_prefix)") "vcruntime140_1.dll"
if ((Test-Path $vc1) -and -not (Test-Path "dist\FileTypeCopier\VCRUNTIME140_1.dll")) {
    Copy-Item -Path $vc1 -Destination "dist\FileTypeCopier\VCRUNTIME140_1.dll" -Force
}

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
