@echo off
setlocal
pushd "%~dp0.."
if errorlevel 1 exit /b 1

uv sync --locked --extra dev --python 3.12 || goto :failed
uv run --no-sync python scripts\check_release.py || goto :failed
uv run --no-sync python -m PyInstaller packaging\tresor.spec --clean --noconfirm || goto :failed
uv run --no-sync python scripts\package_windows_build.py dist\Tresor.exe || goto :failed

echo Windows build verified. The executable, checksum and notices are in dist.
popd
if /I not "%~1"=="--ci" pause
exit /b 0

:failed
echo Windows build failed. See the error above. 1>&2
popd
if /I not "%~1"=="--ci" pause
exit /b 1
