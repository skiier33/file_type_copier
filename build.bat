@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo.
echo Building File Type Copier for USB flash drive ^(folder layout^)...
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo Python is not on PATH. Install Python 3 and try again.
    exit /b 1
)

python -m pip install --upgrade pip
if errorlevel 1 exit /b 1

python -m pip install -r requirements-build.txt
if errorlevel 1 exit /b 1

python -m PyInstaller --clean --noconfirm file_type_copier.spec
if errorlevel 1 exit /b 1

copy /Y "Run File Type Copier.bat" "dist\FileTypeCopier\" >nul
if errorlevel 1 (
    echo Failed to copy launcher into dist\FileTypeCopier
    exit /b 1
)

if not exist "dist\FileTypeCopier\python314.dll" (
    if not exist "dist\FileTypeCopier\_internal\python314.dll" (
        echo Build finished but python314.dll is missing from dist\FileTypeCopier.
        exit /b 1
    )
)

(
echo This FileTypeCopier.exe is a PyInstaller intermediate file.
echo It does NOT include the Python runtime and will show "Failed to load Python DLL".
echo.
echo Run the complete build instead:
echo   dist\FileTypeCopier\Run File Type Copier.bat
)>"build\file_type_copier\DO_NOT_RUN_THIS_EXE.txt"

echo.
echo Done.
echo   IMPORTANT: Do not run build\file_type_copier\FileTypeCopier.exe
echo   Use this folder instead:
echo     %~dp0dist\FileTypeCopier
echo   On the USB drive, double-click:
echo     Run File Type Copier.bat
echo.
echo Optional: unblock after copy ^(PowerShell^):
echo   Unblock-File -Path 'E:\FileTypeCopier\*' -Recurse
echo.
