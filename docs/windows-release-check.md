# Windows build and release check

The repository keeps the release dependency graph in `uv.lock`. A pull request
builds `Tresor.exe` with that lock on Windows and uploads the executable with
its SHA-256 and `Tresor-notices.zip` as a CI artifact. This checks packaging without publishing a
release. The Python test matrix still covers 3.10 through 3.13; the packaged
executable uses Python 3.12.

For a local reproduction on Windows:

```powershell
python -m pip install uv==0.12.1
scripts\build.bat --ci
uv run --no-sync pytest -q
Get-FileHash dist/Tresor.exe -Algorithm SHA256
```

After reviewing the CI artifact and release notes, a `v*` tag whose number
matches `pyproject.toml` triggers the separate release job. It downloads the
same build artifact, verifies its hash, and publishes it with the release
notes. A passing pull request build is packaging evidence; it is not a native
GUI acceptance test or an independent cryptographic audit.
