# Tresor Security Model

This document is the detailed threat model and security architecture for Tresor. It is the deep reference that the README and SECURITY.md link to. It is an English consolidation of the application's internal security notes into one place.

The goal here is to be rigorous and honest. Where a protection is strong, this document says so. Where a limit exists, this document states it plainly rather than hiding it. Tresor is a local, offline credential vault; it is not a magic box, and it cannot defend a machine that is already compromised.

## Contents

- [Overview](#overview)
- [What Tresor protects against](#what-tresor-protects-against)
- [What Tresor does NOT protect against](#what-tresor-does-not-protect-against)
- [The "master password + PIN" model, framed honestly](#the-master-password--pin-model-framed-honestly)
- [Key derivation](#key-derivation)
- [Encryption at rest](#encryption-at-rest)
- [Wrong credentials vs a corrupted file, and fail-closed behavior](#wrong-credentials-vs-a-corrupted-file-and-fail-closed-behavior)
- [Recovery key](#recovery-key)
- [Clipboard handling](#clipboard-handling)
- [Auto-lock and in-memory key wiping](#auto-lock-and-in-memory-key-wiping)
- [Where data is stored and atomic saves](#where-data-is-stored-and-atomic-saves)
- [Backup and recovery](#backup-and-recovery)
- [Recommendations to the user](#recommendations-to-the-user)
- [Summary of the trust boundary](#summary-of-the-trust-boundary)

## Overview

Tresor stores all of your access, not only passwords. A single local file holds your login credentials, websites, FTP, SFTP, SSH, API keys, databases, mail accounts (IMAP/SMTP), cards, notes, and any other secret. That file is always encrypted on disk. There is no cloud, no account, no telemetry, and no network activity of any kind.

The cryptographic design is envelope encryption, which can be read as a short chain:

```
master password + PIN  --Scrypt-->  KEK  --wraps-->  DEK  --encrypts-->  your data
```

- Your master password and PIN are combined into one secret and stretched with Scrypt into a Key Encryption Key (KEK).
- The KEK does one job: it wraps (encrypts) a random Data Encryption Key (DEK).
- The DEK does the real work: it encrypts the actual entries with AES-256-GCM.

This indirection is deliberate. Because the KEK only ever protects the small DEK, changing your password re-wraps a 32-byte key instead of re-encrypting your entire vault, and the recovery key can be a second independent wrapping of the very same DEK.

The design is fail-closed. When there is any doubt about the password, the PIN, the recovery key, or the integrity of the file, Tresor refuses to open rather than guessing. It never returns partial or "best effort" plaintext.

## What Tresor protects against

Tresor is built to protect the confidentiality of a **stolen or copied vault file**. Concretely:

- Someone copies `vault.credvault` off your disk (USB theft, a backup that leaked, a shared or synced folder, a discarded drive, a forensic image).
- Someone gains read access to the file on a powered-off or logged-out machine.
- Someone tampers with the file and hopes Tresor will load the altered contents.

In all of these cases an attacker holds ciphertext only. To recover anything they must derive the correct KEK, which requires both your master password and your PIN, run through Scrypt at the cost level stored in the file. There is no plaintext, no password hash, and no key material sitting in the file that shortcuts this work.

Tamper resistance is covered too. Every ciphertext block carries an AES-GCM authentication tag, and the file header (the KDF cost and salt) is bound into that tag as associated data (see [Encryption at rest](#encryption-at-rest)). An attacker cannot flip bytes in your data, swap in a weaker Scrypt cost, or splice blocks from another file without the authentication tag failing. When it fails, Tresor treats the file as damaged and refuses to open it.

## What Tresor does NOT protect against

This is the part that is easy to oversell, so it is stated bluntly.

**Malware or a keylogger running on the machine while the vault is unlocked.** Tresor is a normal desktop application. If hostile code is already running under your user account, it can log your keystrokes as you type the master password and PIN, read the decrypted entries out of the running process, watch the clipboard when you copy a secret, or capture the screen. No local password manager can win against code that already runs as you. Tresor does not claim to.

**A compromised operating system.** If Windows itself is backdoored, if you are running as a user whose session is under someone else's control, or if the hardware is untrusted, the trust boundary is already broken beneath the application. Tresor assumes the OS it runs on is honest. If that assumption is false, the guarantees above do not hold.

**Forgetting all of your credentials.** There is no backdoor and no master override. If you lose the master password **and** the PIN **and** the recovery key, the DEK can never be unwrapped and the data is gone forever. This is not a bug to be worked around later; it is the direct consequence of there being no secret held by anyone but you. Treat the recovery key as the last line and store it somewhere safe and separate.

Put simply: Tresor protects a file at rest. It does not protect a machine that is actively compromised while you are using it.

## The "master password + PIN" model, framed honestly

It is tempting to describe the master password and PIN as "two-factor". That would be misleading, so here is the accurate framing.

The master password and the PIN are **two secrets you know**. They are not two independent factors in the security sense, and the PIN is emphatically **not** hardware 2FA (there is no token, no phone, no separate device). Cryptographically, the two are combined into **one longer secret** before any key derivation happens. They are joined with a length prefix on the password so that, for example, `("ab", "123")` can never produce the same combined input as `("ab1", "23")`. That combined value is what Scrypt consumes.

What this buys you, honestly:

- **The strength comes from the master password.** Its length and unpredictability are what make an offline guessing attack against a stolen file expensive. Choose it accordingly.
- **The PIN adds a second required secret.** An attacker (or a bystander) who somehow learns only one of the two still cannot open the vault. Both are required, always.
- **The PIN adds shoulder-surf resistance in practice.** Password and PIN are entered separately, so a single glance over your shoulder or a single leaked value is less likely to hand over full access.

What it does not buy you: it is not a substitute for a strong master password. Two weak secrets combined are still weak. Think of the PIN as a second lock on the same door, not as a hardware key on a different door.

## Key derivation

The combined secret is turned into the 256-bit KEK with **Scrypt**, a memory-hard key derivation function. Memory hardness matters because it makes large-scale guessing on GPUs and custom hardware costly, which is exactly the attack that applies to a stolen file.

- **Input normalization.** Both the master password and the PIN are Unicode NFC-normalized before use, so the same characters typed on different keyboard layouts or with different accent encodings always derive the same key. The normalized password and PIN are then length-prefixed and concatenated into a single byte string, as described above.
- **Per-machine calibration.** The Scrypt cost parameter is not a fixed constant. When you first create the vault, Tresor calibrates the cost to your hardware: it picks the strongest cost exponent the machine can still run in roughly 0.6 seconds, within a fixed range (2 to the power of 16 at the low end, 2 to the power of 19 at the cap), with the standard block-size and parallelism parameters (r = 8, p = 1). A faster machine gets a harder KDF for free; an older machine stays usable.
- **The cost travels with the file.** The chosen cost, along with the random 16-byte salt, is written into the file header so the vault can always be reopened on any machine. Because that header is authenticated (see below), an attacker cannot quietly lower the cost to make guessing cheaper.

## Encryption at rest

The actual encryption is **AES-256-GCM**, an authenticated cipher that both hides the data and detects any later modification through its authentication tag.

The on-disk file is a small JSON envelope. At a high level it contains:

- A header: a fixed format identifier and format version, a random per-vault id, the cipher name, the KDF description (Scrypt cost, block size, parallelism, key length), and the salt.
- Three independent ciphertext blocks, each stored as a fresh nonce plus the AES-GCM output:
  - **`wrap`**: the DEK encrypted under the KEK (this is what your password and PIN unlock).
  - **`recovery`**: the same DEK encrypted under the recovery key.
  - **`data`**: your actual entries, encrypted under the DEK.
- A SHA-256 checksum over the three ciphertext blocks, used only to tell corruption apart from a wrong password (see the next section).

Two properties are worth calling out:

**A fresh random nonce for every encryption, on every save.** Each time a block is written, a new 96-bit nonce is drawn from the operating system CSPRNG (`os.urandom`). Nonces are never reused, never derived from a counter you could predict, and never depend on the plaintext. All randomness in the vault (nonces, salts, the DEK, the recovery key, generated passwords) comes from `os.urandom` or `secrets`, never from a general-purpose random generator.

**The header is bound against silent downgrade.** Each block's authentication tag is computed over associated data (AAD) that includes the format, version, vault id, and a label naming the block. The `wrap` block additionally binds the KDF description and the salt. Because the Scrypt cost and salt are authenticated, any attempt to edit the header (for instance, to weaken the KDF or point at a different salt) breaks the tag on the wrapped DEK, and the vault refuses to open. The design intentionally binds only the `wrap` block to the KDF and salt, so that a normal password change (which draws a fresh salt) does not invalidate the `recovery` and `data` blocks.

## Wrong credentials vs a corrupted file, and fail-closed behavior

A vault can fail to open for two very different reasons: you typed the wrong password or PIN, or the file itself is damaged or tampered with. Tresor distinguishes them so the message you see is truthful, and it never confuses one for the other.

- **Corruption is detected first.** Before any key is derived, Tresor runs a structural check (are the fields present, are the salt and nonce the right lengths, is the wrapped block at least large enough to hold a key plus a tag) and then verifies the stored SHA-256 checksum against a freshly computed one using a constant-time comparison. If the structure is wrong or the checksum does not match, the file is reported as **damaged**. Note that this checksum is a corruption signal only; it is not what provides integrity. Real integrity comes from the AES-GCM authentication tags.
- **Wrong credentials are a clean, separate outcome.** If the file is intact but unwrapping the DEK fails (the GCM tag does not verify), that is reported as a **wrong password or PIN**. Cryptographically, an incorrect password and an incorrect PIN are indistinguishable from a bad authentication tag, so the vault simply does not open. There is no oracle that says "the password was right but the PIN was wrong", and no way to tell how close a guess was.

This is what **fail-closed** means in practice: on any doubt, Tresor stops. It does not attempt recovery, it does not return partial plaintext, and it does not fall back to a weaker check. To slow down automated guessing against the live application, repeated wrong attempts within a session add a short, growing backoff before the next try is allowed. (This in-app delay does not slow an attacker working offline against a copied file; the defense there is your master password strength combined with the Scrypt cost.)

## Recovery key

When you create a vault, Tresor generates a one-time **recovery key** and shows it to you exactly once. It is displayed as grouped Base32 so it can be written down or printed without ambiguity.

Mechanically, the recovery key is a second, independent 32-byte random key, and the `recovery` block is the **same DEK wrapped a second time** under it. That is why it works: unwrapping via the recovery key yields the identical DEK that the password path yields, so it decrypts exactly the same data. With it you can reopen the vault and set a new master password and PIN even if you have forgotten the old ones.

Two honest consequences follow:

- The recovery key is as powerful as your password and PIN together. Anyone who holds it can open the vault. Store it offline, apart from the machine (a safe, a sealed envelope, a separate password manager you already trust).
- It is not a backdoor for anyone else. It is derived from randomness generated on your machine at creation time and shown only to you; Tresor keeps no copy. If you lose it along with your password and PIN, no one, including the author, can help you recover the data.

## Clipboard handling

Copying a secret is the most common way sensitive values leak on Windows, because a normal copy can persist in three places at once: the clipboard history (Win+V), the cloud clipboard synced through a Microsoft account, and any third-party clipboard manager.

Tresor's copy is hardened against this:

- **Excluded from history and cloud.** When Tresor places a value on the clipboard, it also sets the official Windows "sensitive content" clipboard formats that instruct the OS not to keep the value in clipboard history and not to upload it to the cloud clipboard. This is done directly against the Windows clipboard API, with no extra packages.
- **Automatic clearing.** A copied secret is scheduled to be wiped from the clipboard after 15 seconds. The clear is conditional: it only empties the clipboard if the value is still the one Tresor copied. If you copied something else in the meantime, Tresor leaves your newer clipboard content alone. Copying a different secret resets the timer, and locking the vault cancels any pending clear.

The honest limit: these are cooperation signals to a well-behaved operating system and to well-behaved clipboard managers. A malicious clipboard monitor running on the machine can still read a value during the seconds it is on the clipboard. This is the same trust boundary as the rest of the app: it protects against the normal Windows clipboard surface, not against active malware.

## Auto-lock and in-memory key wiping

While the vault is open, the DEK is held in process memory so that saves and reads do not require your password each time. Tresor minimizes how long and how exposed that key is.

- **Auto-lock on inactivity.** The vault locks itself after a period of no activity. This is configurable in the settings (1, 5, or 15 minutes, or off), and defaults to 5 minutes. Mouse movement, keystrokes, clicks, and scrolling reset the idle timer.
- **Wiped on lock and on close.** When the vault locks, whether manually, by the idle timer, or by closing the window, the in-memory DEK buffer is overwritten with zeros and all decrypted entries are dropped. After that point the process holds ciphertext only again, exactly as it does before you unlock.

**The realistic limit of zeroization in Python.** Tresor holds the DEK in a mutable byte buffer specifically so it can be overwritten on lock, and it does overwrite it. But Python is a managed, garbage-collected language and this cannot be a hard guarantee. Your master password and PIN arrive as ordinary Python strings, which are immutable and cannot be wiped in place; the runtime, the garbage collector, and the WebView bridge may keep transient copies of sensitive values that Tresor cannot reach to erase; and nothing prevents the operating system from paging process memory to disk. Overwriting the DEK is a genuine and worthwhile best effort that shrinks the window of exposure. It is not, and honestly cannot be, a promise that no secret byte lingers anywhere in memory. The strong protection remains the file at rest; in-memory hardening is defense in depth on top of it.

## Where data is stored and atomic saves

The vault lives at:

```
%APPDATA%\Tresor\vault.credvault
```

That file contains **ciphertext only**: the header, the three encrypted blocks, and the checksum. There is no plaintext copy written anywhere by design, and plaintext never touches the disk.

Saves are **atomic**. When Tresor writes the vault, it writes the full new contents to a temporary file, flushes and fsyncs it to storage, and only then atomically replaces the real file. If power is lost or the process is killed mid-write, you are left with either the complete old file or the complete new file, never a half-written vault. A normal save only re-encrypts the small `data` block with the DEK already in memory; it does not touch the wrapped DEK or the recovery block, and it does not need your password again.

## Backup and recovery

Because the file is encrypted and self-contained, backing up Tresor is simple and safe.

- **Copy the encrypted file.** You can copy `vault.credvault` anywhere: another drive, a USB stick, a backup system. The copy is just as encrypted as the original and is worthless without your master password and PIN. Tresor also offers an in-app export that writes an encrypted copy to a location you choose. Keeping an occasional copy protects you against disk failure and accidental deletion.
- **Keep the recovery key.** Store the one-time recovery key offline and separate from the machine. It lets you regain access if you forget the master password and PIN.

There is **no backdoor**. Recovery works only through secrets you hold: the master password plus PIN, or the recovery key. If all of them are lost, the data cannot be recovered by anyone. This is the price of there being no third party who can open your vault.

## Recommendations to the user

- **Use a strong master password.** This is the single most important control. The strength of everything downstream rests on it. Prefer a long passphrase you can remember over a short complex string you cannot.
- **Keep the PIN and password distinct and private.** Enter them as two separate secrets. Do not reuse one as the other.
- **Store the recovery key safely and separately.** Offline, away from the computer, treated as if it were the password itself.
- **Keep a backup copy of the encrypted file.** It costs nothing and protects against hardware failure.
- **Enable BitLocker for your system drive.** Full-disk encryption is the right complement to Tresor: it protects the broader machine and adds a layer beneath the vault file, which is especially valuable on a laptop that could be lost or stolen.
- **Keep the machine itself clean.** Because Tresor cannot defend against malware running while the vault is unlocked, ordinary hygiene (updates, no untrusted software, a standard user account) is part of your real security posture.

## Summary of the trust boundary

Tresor's promise is precise, and its precision is the point:

- It **protects a stolen or copied vault file** with modern, authenticated, memory-hardened encryption, and it fails closed on any doubt.
- It **does not protect** a machine that is already compromised while the vault is open, and it **cannot recover** data if every secret you hold is lost.

Everything in this document follows from those two lines. Where a stronger claim would be convenient, this document declines to make it.