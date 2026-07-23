# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Optional light theme for the vault window (the current window ships with a dark theme by default).
- Import of entries from a previously exported encrypted backup.

## [1.6.2] - 2026-07-23

### Changed

- Focus lists now show at most 4 columns side by side instead of squeezing in 5 on a wide window, so each list is wider and its task text has more room. The number of columns still adapts to the window width (4 → 3 → 2 → 1 as it gets narrower).

## [1.6.1] - 2026-07-23

### Fixed

- The sidebar's bottom bar (Back up / Lock / Settings) now stays pinned to the bottom in the Focus and Motivation areas too. It used to jump up there because the groups list that normally fills the space is hidden in those areas; it now sits in the same place as in the Passwords view.

## [1.6.0] - 2026-07-23

### Fixed

- Text size no longer zooms the whole window. Enlarging the text used to scale the entire interface, which could push the Settings panel out of reach with no way back. Now only the **text** grows (and reflows) while buttons, layout and especially the Settings stay at their normal, always-reachable size — you can never lock yourself out of Settings again.

### Changed

- Rewrote the motivational sayings — 149 new lines that are warmer, more personal and human, replacing the previous set (used for both the daily saying and the Motivation boosts).

## [1.5.1] - 2026-07-23

### Fixed

- Focus: long task text (and long list titles) was cut off on one line instead of wrapping, so the end was unreadable. Task text and list titles now wrap onto as many lines as needed and stay fully visible, while remaining editable in place.

## [1.5.0] - 2026-07-23

### Added

- **Text size setting** — a new "Textgröße" / "Text size" option in Settings (Normal, Large, Very large, Huge) scales the entire interface at once: passwords, notes, the Focus and Motivation areas, and every input field. The choice is remembered across restarts. Added for easier reading and better accessibility.

## [1.4.0] - 2026-07-23

### Added

- **Motivation area** — a third section in the sidebar (💪 Motivation) next to Passwords and Focus. It shows your personal saying for today and, whenever you need an extra push, an "Extra boost" button that reveals a fresh motivational line on demand (as many as you like), with a small counter of how many boosts you pulled today. All sentences come from the built-in offline collection and are addressed to you by name.

## [1.3.0] - 2026-07-23

### Added

- Focus checklists are now fully editable. Each task's text can be corrected in place (click it and type) instead of deleting and re-adding it. A copy button copies a task's text to the clipboard (without the secret auto-clear, since a task is not a secret). Tasks can be reordered by dragging the grip handle, within a list or across lists. And ticked-off tasks move out of the active list into a collapsible "Erledigt" (Done) section per list, so a long list no longer overloads — reopen the section to see or un-tick them.

### Added (backend)

- `copy_plain(text)` on the API bridge: copies plain, non-secret text to the clipboard with no auto-clear timer.

## [1.2.1] - 2026-07-23

### Fixed

- Focus: the daily-motivation card could appear compressed with its sentence clipped — as a flex item with `overflow: hidden` it collapsed below its content. The Focus sections now keep their natural height (the view scrolls instead), so the full sentence always shows.

### Changed

- Focus: list titles are now editable. Click a list's name to rename it (for example rename "Neue Liste"); the new name is saved automatically.

## [1.2.0] - 2026-07-23

### Added

- **Focus area** — a second section beside the passwords, switchable with a Passwords / Focus toggle in the sidebar. It holds checklists (lists of tasks you tick off, each with a progress bar), a free-form notepad, and a daily personalized motivation: on the first open of each day a welcome screen greets you by name with one of 200 hand-written sentences, and the sentence rotates every day. The name is asked once and can be changed any time. Designed to be calm and ADHD-friendly. All Focus data is stored **encrypted in the same vault** as the passwords, never in plain text.
- **Automatic versioned backups** — every save now also writes a timestamped copy of the vault into a `backups` folder next to it and keeps the most recent 20. Any earlier state can be restored from there, so a bad save or an accidental change can always be rolled back.

### Changed

- The on-disk payload now carries both `entries` and `focus`. Vaults created by earlier versions (which stored only `entries`) keep opening unchanged; the missing `focus` simply starts empty.

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

[Unreleased]: https://github.com/Juri-Halveth/halveth-tresor/compare/v1.6.2...HEAD
[1.6.2]: https://github.com/Juri-Halveth/halveth-tresor/compare/v1.6.1...v1.6.2
[1.6.1]: https://github.com/Juri-Halveth/halveth-tresor/compare/v1.6.0...v1.6.1
[1.6.0]: https://github.com/Juri-Halveth/halveth-tresor/compare/v1.5.1...v1.6.0
[1.5.1]: https://github.com/Juri-Halveth/halveth-tresor/compare/v1.5.0...v1.5.1
[1.5.0]: https://github.com/Juri-Halveth/halveth-tresor/compare/v1.4.0...v1.5.0
[1.4.0]: https://github.com/Juri-Halveth/halveth-tresor/compare/v1.3.0...v1.4.0
[1.3.0]: https://github.com/Juri-Halveth/halveth-tresor/compare/v1.2.1...v1.3.0
[1.2.1]: https://github.com/Juri-Halveth/halveth-tresor/compare/v1.2.0...v1.2.1
[1.2.0]: https://github.com/Juri-Halveth/halveth-tresor/compare/v1.1.3...v1.2.0
[1.1.3]: https://github.com/Juri-Halveth/halveth-tresor/compare/v1.1.2...v1.1.3
[1.1.2]: https://github.com/Juri-Halveth/halveth-tresor/compare/v1.1.1...v1.1.2
[1.1.1]: https://github.com/Juri-Halveth/halveth-tresor/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/Juri-Halveth/halveth-tresor/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/Juri-Halveth/halveth-tresor/releases/tag/v1.0.0
