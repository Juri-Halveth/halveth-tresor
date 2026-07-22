# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Optional light theme for the vault window (the current window ships with a dark theme by default).
- Import of entries from a previously exported encrypted backup.

## [1.1.3] - 2026-07-22

### Fixed

- Entry cards on the dashboard were clipped once the vault held enough entries to fill the view: the card grid's automatic row tracks collapsed (each card uses `overflow: hidden`, which makes a CSS grid item report a zero automatic minimum height), cutting off the type/group line and the one-click copy buttons so the cards looked compressed. Rows are now sized to each card's full content (`grid-auto-rows: max-content`), so every card shows its complete content at any window size.

## [1.1.2] - 2026-07-11

### Fixed

- Encrypted backup export ("Sichern" / "Back up") could never complete: the Save dialog's file-type filter contained a hyphen, which pywebview rejects, so the call raised before a dialog could open. The filter is corrected, and the export now falls back to an unfiltered dialog if a filter is ever rejected, so a backup can always be saved.

### Security

- The packaged desktop app no longer falls back to the browser-preview mock backend. If the native bridge was slow to start, the interface could briefly use a mock that stored entries unencrypted in local storage and accepted any credentials. The desktop build now uses only the real encrypted backend and shows a clear error if it cannot load, instead of silently degrading.
- Locking or closing the vault now clears any secret still on the clipboard immediately, rather than only cancelling the pending auto-clear.
- Hardened the encrypted core against tampered files: Scrypt cost parameters are bounds-checked before use, and each save writes to a per-process temporary file that is removed on failure.

## [1.1.1] - 2026-07-10

### Fixed

- Prevented possible data loss when two Tresor windows were open on the same vault at the same time: a stale window could overwrite entries added in the other. Tresor now allows only one window at a time, and every save first reloads any external change to the vault file instead of overwriting it.

## [1.1.0] - 2026-07-10

### Added

- Bilingual interface: a full English translation alongside German, with a DE/EN switch in the top-right corner and in Settings. The chosen language is remembered.
- Entry types and their field templates are now localized (German and English), so a new entry created in English gets English field names.

### Changed

- API results now use stable string error codes that the interface localizes, so error messages appear in the selected language.

## [1.0.0] - 2026-07-10

### Added

- Local encrypted vault stored as a single file, ciphertext only, written atomically to `%APPDATA%\Tresor\vault.credvault`.
- Envelope encryption: a master password and a separate PIN are combined (length prefixed, NFC normalized) and stretched with Scrypt into a Key Encryption Key (KEK) that wraps a random Data Encryption Key (DEK); the DEK encrypts all data with AES-256-GCM.
- Per-save security hardening: a fresh random nonce for every encryption, the file header (KDF cost and salt) bound as AES-GCM associated data to block silent downgrades, and a SHA-256 checksum over the ciphertext to tell a corrupted file apart from a wrong password.
- Machine-calibrated Scrypt cost chosen once at vault creation and stored in the file, so each vault adapts to its own hardware.
- Fail-closed authentication: a wrong master password or PIN is indistinguishable from a bad authentication tag, so the vault never opens on doubt.
- One-time Base32 recovery key that wraps the same DEK under a second random key, allowing a password reset when the master password is forgotten.
- Tailored entry types with fields suited to each kind: logins and websites, email accounts (IMAP and SMTP server and port), FTP and SFTP, databases, API connections (connects from, connects to, endpoint, API key, public key, private key), SSH keys, cards, and free-form notes.
- Organization of entries by place or purpose using groups the user names, for example Work, Servers, or Personal.
- One-click copy on every field with a secure clipboard that auto-clears after 15 seconds and is excluded from Windows clipboard history (Win+V) and cloud clipboard.
- Built-in password generator.
- Live search across entries.
- Detail view that reveals masked values on demand.
- Auto-lock after a configurable period of inactivity, wiping the in-memory key on lock and on window close.
- Encrypted backup export to a separate file.
- Packaged single-file Windows executable built with PyInstaller (`dist/Tresor.exe`), portable with no installer and no admin rights.

[Unreleased]: https://github.com/Juri-Halveth/halveth-tresor/compare/v1.1.3...HEAD
[1.1.3]: https://github.com/Juri-Halveth/halveth-tresor/compare/v1.1.2...v1.1.3
[1.1.2]: https://github.com/Juri-Halveth/halveth-tresor/compare/v1.1.1...v1.1.2
[1.1.1]: https://github.com/Juri-Halveth/halveth-tresor/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/Juri-Halveth/halveth-tresor/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/Juri-Halveth/halveth-tresor/releases/tag/v1.0.0
