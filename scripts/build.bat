@echo off
REM Rebuilds Tresor.exe from the committed PyInstaller spec. Double-click to run.
cd /d %~dp0\..
echo Building Tresor.exe ...
python -m PyInstaller packaging\tresor.spec --clean --noconfirm
echo.
echo Done. The executable is at:  dist\Tresor.exe
pause
