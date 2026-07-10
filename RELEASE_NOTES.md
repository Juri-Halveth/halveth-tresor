# Tresor v1.1.1

**A local, offline credential vault for Windows. Your complete access, encrypted in a single file, with no cloud and no account.**

> New in 1.1.1: fixes a data-loss issue where two open Tresor windows could overwrite each other. Tresor now allows only one window at a time and never overwrites external changes to the vault. Version 1.1.0 added the bilingual German and English interface, still included: switch language any time with the DE/EN toggle in the top-right corner or in Settings.

Tresor is a desktop credential vault. It is more than a password manager: it stores complete access, not just passwords. Keep login credentials, websites, FTP, SFTP, SSH, API keys, databases, mail accounts (IMAP/SMTP), cards, notes, and any other secret in one place. Each entry type has fields tailored to it, entries are organized by place or purpose into groups you name (for example Work, Servers, or Personal), and every field is one click to copy. Everything is fully offline: no cloud, no account, no telemetry, and no network calls, all kept in one local encrypted file.

## Highlights

- **Bilingual, German and English:** switch language any time with the DE/EN toggle; the app remembers your choice.
- **Complete access, not just passwords:** dedicated entry types for logins, websites, FTP, SFTP, SSH, API keys, databases, mail accounts (IMAP/SMTP), cards, and notes, each with fields tailored to that type.
- **Organized by place or purpose:** group entries under names you choose, such as Work, Servers, or Personal.
- **One-click copy on every field,** with a detail view that reveals masked values on demand.
- **Built-in password generator** and **live search** across your vault.
- **Strong envelope encryption:** your master password plus a separate PIN derive a Key Encryption Key via Scrypt (calibrated to your machine), which wraps a random Data Encryption Key used with AES-256-GCM. A fresh random nonce is used on every save, and the header is bound as associated data so it cannot be silently downgraded.
- **Fail-closed by design:** a wrong master password or PIN fails the AES-256-GCM authentication check exactly like a tampered file, so the vault never opens on doubt. A SHA-256 checksum over the ciphertext tells a genuinely corrupted file apart from a merely wrong password.
- **One-time Recovery Key** (Base32) so a forgotten master password can be reset.
- **Secure clipboard:** copied secrets auto-clear after 15 seconds and are excluded from Windows clipboard history (Win+V) and cloud clipboard.
- **Auto-lock on inactivity:** the in-memory key is wiped on lock and when the window closes.
- **Encrypted backup export:** save an encrypted copy of the vault to a location you choose.
- **One local file:** the vault lives at `%APPDATA%\Tresor\vault.credvault`, ciphertext only, written atomically.

## Screenshots

**Dashboard, grouped by place or purpose**

![Tresor dashboard grouped by place or purpose](assets/screenshots/dashboard.png)

**Choosing an entry type**

![Choosing an entry type](assets/screenshots/add-type.png)

**Filling in an entry with fields tailored to its type**

![Entry form with tailored fields](assets/screenshots/add-form.png)

**Detail view with one-click copy and reveal on demand**

![Entry detail view](assets/screenshots/detail.png)

## Download

Grab **`Tresor.exe`** from the assets below.

- **No installer.** It is a single portable executable. Put it anywhere and run it. No admin rights required.
- **System requirements:** Windows 10 or 11 (x64). The WebView2 runtime is preinstalled on Windows 11 and on up-to-date Windows 10, so there is nothing extra to install.
- Optionally create a desktop shortcut for quick access.

## Verify your download

Confirm the file you downloaded matches the published hash before running it. In PowerShell, from the folder containing the file:

```powershell
Get-FileHash .\Tresor.exe -Algorithm SHA256
```

Compare the output to the hash published with this release in the attached `Tresor.exe.sha256` file. It always matches the exact `Tresor.exe` in the release assets. The two values must match before you run the file.

## Security

Tresor uses a standard envelope-encryption design (Scrypt then AES-256-GCM) and is fail-closed. It is self-reviewed and has not been independently audited. Read the full design and its honest limits in [docs/security-model.md](docs/security-model.md). In short: Tresor protects a stolen or copied vault file. It does not protect against malware or a keylogger already running on your PC while the vault is unlocked. If you lose the master password AND the PIN AND the Recovery Key, the data is gone forever, by design. Enabling BitLocker on your system drive is recommended.

## License

Tresor is released under the MIT License (Copyright (c) 2026 Juri Janovski). Bundled third-party dependencies keep their own permissive licenses; the required attribution notices, including OpenSSL (bundled through the `cryptography` wheel), are listed in [THIRD-PARTY-LICENSES.md](THIRD-PARTY-LICENSES.md).

## Known limitations

- **Windows only** for now (Windows 10 or 11, x64).
- The executable is **not yet code-signed**, so Windows SmartScreen may show a warning on first run. You can continue via "More info" then "Run anyway" after verifying the SHA-256 above.