@echo off
setlocal EnableExtensions
rem Launch from this folder so bundled DLLs resolve when run from a USB drive.
cd /d "%~dp0"

if not exist "FileTypeCopier.exe" (
    echo FileTypeCopier.exe not found in: %~dp0
    echo Copy the whole FileTypeCopier folder from dist to your flash drive.
    pause
    exit /b 1
)

if not exist "base_library.zip" (
    echo This folder is an incomplete build ^(missing base_library.zip and other runtime files^).
    echo.
    echo On your PC, close the app and run build.bat again, then copy the NEW
    echo dist\FileTypeCopier folder ^(hundreds of files, not ~20^) to the USB drive.
    echo.
    echo Do NOT run: build\file_type_copier\FileTypeCopier.exe
    pause
    exit /b 1
)

if exist "_internal\python314.dll" goto :launch
if exist "python314.dll" goto :launch

echo Python runtime files are missing from this folder.
echo.
echo Do NOT run the copy under build\file_type_copier\ — that exe is incomplete.
echo Use the full app folder:
echo   dist\FileTypeCopier
echo.
echo Copy that entire folder to your USB drive, then run this batch file again.
pause
exit /b 1

:launch
start "" "%~dp0FileTypeCopier.exe"
