# Contributing to Tresor

Thanks for your interest in Tresor. Tresor is a local, offline credential vault for Windows. It stores complete access (login credentials, websites, FTP, SFTP, SSH, API keys, databases, mail accounts, cards, and notes), not just passwords, in a single encrypted file with no cloud and no account. Contributions that make it clearer, faster, safer, or easier to use are very welcome, whether that is a bug fix, a new entry type, a documentation improvement, or a test.

This guide explains how to get set up, how to run and build the project, and what we expect from a good pull request. If anything here is unclear, open an issue and ask. Friendly questions are always fine.

## Ways to contribute

- Report a bug or a confusing behavior.
- Suggest or implement a feature (for example a new entry type with tailored fields).
- Improve the documentation or the on-screen wording.
- Add or strengthen tests, especially around the encrypted core.

For anything larger than a small fix, please open an issue first so we can agree on the approach before you invest time.

## Development environment

You will need:

- Windows 10 or 11 (x64). The native window uses the Windows WebView2 runtime, which is preinstalled on Windows 11 and on up-to-date Windows 10.
- Python 3.10 or newer. The project is developed and tested on Python 3.13.
- Git.

Clone the repository and install it in editable mode with the development extras:

```bash
git clone https://github.com/Juri-Halveth/halveth-tresor
cd halveth-tresor
pip install -e ".[dev]"
```

The `dev` extra pulls in pytest (tests), PyInstaller (building the exe), and Pillow (icon tooling only).

Run the app from source:

```bash
python -m tresor
```

This opens the native window. Your working vault lives at `%APPDATA%\Tresor\vault.credvault` and is never touched by the test suite, so you can develop safely against your own data.

## Running the tests

The unit tests are pytest based and fast. Run them from the repository root:

```bash
pytest
```

The tests focus on the encrypted core in `src/tresor/vault.py`. They cover:

- Roundtrip encryption and decryption, and a check that no plaintext is ever written to disk.
- A wrong master password or PIN fails closed (it is indistinguishable from a bad authentication tag, so the vault never opens on doubt).
- Tamper detection on a modified file.
- A blocked Scrypt cost downgrade (the KDF parameters are bound as associated data and cannot be silently weakened).
- The one-time recovery key path.
- Changing the master password while keeping the existing data intact.
- The in-memory key being wiped on lock.
- Assorted helpers.

These tests are the guardrail for the security core. Please keep them green (see the security note below).

## Manual native smoke test

Some behavior only shows up in the real native window (window creation, the JavaScript bridge in `src/tresor/app.py`, and the secure clipboard in `src/tresor/clipboard_win.py`). For that we keep a manual smoke test:

```bash
python tests/e2e/native_smoke.py
```

It opens a real window and requires the WebView2 runtime, so it is not run in CI. Run it by hand when you change the window, the bridge, the UI, or clipboard handling, and confirm the window opens and behaves as expected before you send your pull request.

## Building the executable

Tresor ships as one portable `.exe` built with PyInstaller from the committed spec. Either double-click or run:

```bash
scripts\build.bat
```

or run the spec directly:

```bash
python -m PyInstaller packaging/tresor.spec --clean --noconfirm
```

The result is `dist/Tresor.exe`. Pillow is used at build time for icon tooling only and is not shipped inside the exe.

## Project layout

A quick map so you know where things live:

- `src/tresor/__init__.py`: holds `__version__`.
- `src/tresor/__main__.py`: entry point, enables `python -m tresor`.
- `src/tresor/app.py`: the native window and the JavaScript bridge.
- `src/tresor/vault.py`: the encrypted core (Scrypt key derivation plus AES-256-GCM). This is the security-critical file.
- `src/tresor/clipboard_win.py`: the secure clipboard (auto-clear, excluded from Windows clipboard history and cloud clipboard).
- `src/tresor/ui/index.html`: the entire user interface.
- `tests/test_vault.py`: the pytest suite.
- `tests/e2e/native_smoke.py`: the manual native smoke test.
- `docs/security-model.md`: the design of the encryption and threat model.
- `scripts/`, `packaging/`, `assets/`: build scripts, the PyInstaller spec, and icons plus screenshots.

## Code style

- Follow PEP 8. Keep functions small and readable.
- Write all code comments and docstrings in English.
- Keep the product UI strings in German. The app interface is intentionally German for product reasons, so please do not translate on-screen text to English. New user-facing strings should also be German and should match the tone of the existing UI.
- Prefer clear names over clever ones. When touching cryptography, favor explicitness.
- Sample or example data must be generic (for example `example.com`). Do not commit personal data, real credentials, or local paths that contain a username.

## The security core must never regress

`src/tresor/vault.py` implements the envelope encryption (Scrypt derives a Key Encryption Key from the master password and PIN, the KEK wraps a random Data Encryption Key, and the DEK encrypts the data with AES-256-GCM using a fresh nonce on every save). Changes here demand extra care:

- Keep changes to this file behavior preserving unless a change to the security behavior is the explicit, reviewed goal of the pull request.
- Always run `pytest` before and after your change and make sure every test stays green.
- If you intentionally change on-disk format, key derivation, or the authentication model, say so clearly in the pull request, explain why, and add or update tests to lock in the new behavior. Silent changes to the vault format or the fail-closed guarantee will not be accepted.
- If you are unsure whether a change affects security, open an issue first and describe it.

The tests are not a formality here. They are the contract that a stolen or copied vault file stays protected.

## Opening issues

Good issues are easy to act on. When you report a bug, please include:

- What you did, what you expected, and what actually happened.
- Your Windows version and Python version.
- The Tresor version (see `__version__`), or the release you downloaded.
- Any relevant error text. Never paste real secrets, master passwords, PINs, or recovery keys into an issue.

For feature requests, describe the problem you want to solve, not only the solution you have in mind.

## Pull requests

We favor small, focused pull requests. They are easier to review and faster to merge.

1. Create a branch for your change.
2. Make the change, keeping it tightly scoped to one thing.
3. Run `pytest` and make sure it is green. If you touched the window, the bridge, the UI, or the clipboard, also run the manual native smoke test.
4. Update documentation and, where it makes sense, add or adjust tests.
5. In the pull request description, explain what you changed, why, and exactly how you tested it (which commands you ran and what you observed). If your change affects `vault.py`, call that out explicitly.

Continuous integration runs the unit tests on every pull request (see `.github/workflows/ci.yml`). Please make sure CI passes. The native smoke test is manual and does not run in CI, so describe your manual testing in the pull request text.

Keep the commit history readable. Clear commit messages that describe the intent are appreciated.

## Licensing of contributions

Tresor is released under the MIT License (Copyright (c) 2026 Juri Janovski). By contributing, you agree that your contribution is your own work (or that you have the right to submit it) and that it is licensed under the MIT License, the same terms as the rest of the project. This is a lightweight Developer Certificate of Origin style agreement: contribute what you are allowed to contribute, and let it be MIT.

Third party dependency notices are tracked separately in `THIRD-PARTY-LICENSES.md`.

Thank you for helping make Tresor better.