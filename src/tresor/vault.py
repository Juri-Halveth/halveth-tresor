"""
vault.py - the encrypted core of Tresor
=======================================
Envelope encryption, following a standard envelope-encryption design (self-reviewed,
not independently audited):

  master password + PIN  --Scrypt-->  KEK  --protects-->  DEK  --protects-->  your data

Why this design:
  * Changing the password only re-wraps the small DEK, no need to re-encrypt all data.
  * The recovery key is the same DEK, wrapped a second time under a random key.
  * Saving an entry only needs the DEK, never the password again.

Building blocks (all from the audited `cryptography` library):
  * Scrypt        = memory-hard key derivation (slows down guessing attacks on the file)
  * AES-256-GCM   = encrypts AND detects any later tampering (authentication tag)

Hard rules enforced here:
  * Plaintext never touches the disk.
  * Every encryption gets a fresh random nonce (os.urandom).
  * A wrong password/PIN is indistinguishable from the auth tag, so we fail closed.
  * Randomness comes only from os.urandom / secrets, never from `random`.
"""

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
import unicodedata
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

# Lightweight aliases documenting the two dict shapes that flow through this module.
Envelope = dict[str, Any]  # the on-disk JSON structure
Entry = dict[str, Any]  # a single credential entry {id, type, title, group, fields}

# ------------------------------------------------------------------ Constants
FILE_FORMAT = "credvault"  # magic identifier written into every vault file
FORMAT_VERSION = 1  # on-disk format version (not the app version)
SCRYPT_R = 8
SCRYPT_P = 1
KEYLEN = 32  # 256 bit
NONCE = 12  # 96 bit, the standard for AES-GCM
SALT_LEN = 16


# ------------------------------------------------------------------ Error types
class VaultError(Exception):
    """Base class for all vault errors."""


class Corrupt(VaultError):
    """The file is damaged or was tampered with."""


class WrongCredentials(VaultError):
    """The password/PIN or the recovery key is wrong."""


# ------------------------------------------------------------------ base64 helpers
def b64e(b: bytes) -> str:
    """Encode bytes as a base64 ASCII string."""
    return base64.b64encode(b).decode("ascii")


def b64d(s: str) -> bytes:
    """Decode a base64 ASCII string back to bytes."""
    return base64.b64decode(s.encode("ascii"))


# ------------------------------------------------------------------ Key derivation
def _norm(s: str) -> str:
    """Normalize text so the same input always encodes identically (accents, keyboard layouts)."""
    return unicodedata.normalize("NFC", s)


def kdf_input(master: str, pin: str) -> bytes:
    """
    Combine password and PIN into ONE KDF input with a length prefix, so that
    ('ab', '123') can never collide with ('ab1', '23').
    """
    m = _norm(master).encode("utf-8")
    p = _norm(pin).encode("utf-8")
    return len(m).to_bytes(4, "big") + m + p


def derive_kek(
    master: str, pin: str, salt: bytes, n: int, r: int = SCRYPT_R, p: int = SCRYPT_P
) -> bytes:
    """Derive the 256-bit key-encryption key from (password + PIN) via Scrypt."""
    kdf = Scrypt(salt=salt, length=KEYLEN, n=n, r=r, p=p)
    return kdf.derive(kdf_input(master, pin))


def calibrate_n(target_seconds: float = 0.6, min_exp: int = 16, cap_exp: int = 19) -> int:
    """
    Pick, once at creation, the strongest Scrypt cost this machine can still run in
    roughly `target_seconds`. The chosen exponent is stored in the vault so each
    vault adapts to its own hardware. Returns the exponent (n = 2 ** exponent).
    """
    salt = os.urandom(SALT_LEN)
    probe = kdf_input("calibration", "0000")
    chosen = min_exp
    for exp in range(min_exp, cap_exp + 1):
        n = 1 << exp
        t0 = time.perf_counter()
        try:
            Scrypt(salt=salt, length=KEYLEN, n=n, r=SCRYPT_R, p=SCRYPT_P).derive(probe)
        except Exception:
            break  # older builds with a memory cap: stay at the last good level
        dt = time.perf_counter() - t0
        if exp == min_exp or dt < target_seconds:
            chosen = exp
        if dt >= target_seconds:
            break
    return chosen


# ------------------------------------------------------------------ Envelope
def _aad(label: str, hdr: dict[str, Any]) -> bytes:
    """
    Additional authenticated data. This lets no one silently downgrade the header
    (for example the Scrypt cost): any change breaks the tag. Only the 'wrap' block
    is tied to Scrypt + salt (the others stay valid across a password change).
    """
    base = {
        "format": hdr["format"],
        "version": hdr["version"],
        "vault_id": hdr["vault_id"],
        "label": label,
    }
    if label == "wrap":
        base["kdf"] = hdr["kdf"]
        base["salt"] = hdr["salt"]
    return json.dumps(base, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _hdr_of(env: Envelope) -> dict[str, Any]:
    """Extract the header fields that feed into the AAD."""
    return {
        "format": env["format"],
        "version": env["version"],
        "vault_id": env["vault_id"],
        "kdf": env["kdf"],
        "salt": env["salt"],
    }


def _checksum(env: Envelope) -> str:
    """SHA-256 over the three ciphertext blobs, for corruption detection only."""
    raw = (env["wrap"]["blob"] + env["recovery"]["blob"] + env["data"]["blob"]).encode("ascii")
    return b64e(hashlib.sha256(raw).digest())


def _encrypt(key: bytes, plaintext: bytes, aad: bytes) -> dict[str, str]:
    """AES-256-GCM encrypt with a fresh random nonce; returns {nonce, blob} as base64."""
    n = os.urandom(NONCE)
    blob = AESGCM(key).encrypt(n, plaintext, aad)
    return {"nonce": b64e(n), "blob": b64e(blob)}


def _decrypt(key: bytes, part: dict[str, str], aad: bytes) -> bytes:
    """AES-256-GCM decrypt a {nonce, blob} part; raises InvalidTag on wrong key/tamper."""
    return AESGCM(key).decrypt(b64d(part["nonce"]), b64d(part["blob"]), aad)


def _payload_bytes(entries: list[Entry]) -> bytes:
    """Serialize the entry list to the UTF-8 JSON payload that gets encrypted."""
    return json.dumps({"entries": entries}, ensure_ascii=False).encode("utf-8")


def create_envelope(
    master: str, pin: str, entries: list[Entry] | None = None, n_exp: int | None = None
) -> tuple[Envelope, bytes]:
    """Build a brand new encrypted vault. Returns (envelope, recovery_key_bytes)."""
    n = 1 << (n_exp if n_exp is not None else calibrate_n())
    salt = os.urandom(SALT_LEN)
    dek = os.urandom(KEYLEN)
    recovery_key = os.urandom(KEYLEN)

    hdr: dict[str, Any] = {
        "format": FILE_FORMAT,
        "version": FORMAT_VERSION,
        "vault_id": b64e(os.urandom(16)),
        "cipher": "AES-256-GCM",
        "kdf": {"name": "scrypt", "n": n, "r": SCRYPT_R, "p": SCRYPT_P, "length": KEYLEN},
        "salt": b64e(salt),
    }
    kek = derive_kek(master, pin, salt, n)
    try:
        env: Envelope = dict(hdr)
        env["wrap"] = _encrypt(kek, dek, _aad("wrap", hdr))
        env["recovery"] = _encrypt(recovery_key, dek, _aad("recovery", hdr))
        env["data"] = _encrypt(dek, _payload_bytes(entries or []), _aad("data", hdr))
        env["checksum"] = _checksum(env)
    finally:
        wipe(bytearray(kek))
    return env, recovery_key


def _structural_check(env: Envelope) -> None:
    """Validate the envelope shape and field sizes before any crypto is attempted."""
    try:
        assert env.get("format") == FILE_FORMAT, "format"
        assert isinstance(env.get("version"), int), "version"
        assert len(b64d(env["salt"])) == SALT_LEN, "salt length"
        kdf = env["kdf"]
        assert kdf["name"] == "scrypt" and int(kdf["n"]) >= 2, "kdf"
        for k in ("wrap", "recovery", "data"):
            assert len(b64d(env[k]["nonce"])) == NONCE, k + " nonce"
            assert len(b64d(env[k]["blob"])) >= 16, k + " blob"
        assert len(b64d(env["wrap"]["blob"])) >= KEYLEN + 16, "wrap blob"
    except (KeyError, AssertionError, ValueError, TypeError) as e:
        raise Corrupt(f"The vault file is damaged ({e})") from e


def _verify_checksum(env: Envelope) -> None:
    """Compare the stored checksum against the recomputed one (corruption detection)."""
    want = env.get("checksum", "")
    if not want or not hmac.compare_digest(want, _checksum(env)):
        raise Corrupt("Checksum does not match, the file is damaged.")


def _open_data(env: Envelope, dek: bytes, hdr: dict[str, Any]) -> list[Entry]:
    """Decrypt the data block with the DEK and return the entry list."""
    try:
        payload = _decrypt(dek, env["data"], _aad("data", hdr))
    except InvalidTag as e:
        raise Corrupt("The data block is damaged.") from e
    return json.loads(payload.decode("utf-8"))["entries"]


def unlock_envelope(env: Envelope, master: str, pin: str) -> tuple[bytes, list[Entry]]:
    """Open with password + PIN. Returns (dek_bytes, entries) or raises WrongCredentials/Corrupt."""
    _structural_check(env)
    _verify_checksum(env)
    hdr = _hdr_of(env)
    kek = derive_kek(
        master,
        pin,
        b64d(env["salt"]),
        int(env["kdf"]["n"]),
        int(env["kdf"]["r"]),
        int(env["kdf"]["p"]),
    )
    try:
        dek = _decrypt(kek, env["wrap"], _aad("wrap", hdr))
    except InvalidTag:
        raise WrongCredentials("Password or PIN is wrong.") from None
    finally:
        wipe(bytearray(kek))
    return dek, _open_data(env, dek, hdr)


def unlock_with_recovery(env: Envelope, recovery_display: str) -> tuple[bytes, list[Entry]]:
    """Open with the recovery key (Base32). Returns (dek_bytes, entries)."""
    _structural_check(env)
    _verify_checksum(env)
    hdr = _hdr_of(env)
    try:
        rk = b32_parse(recovery_display)
    except Exception:
        raise WrongCredentials("The recovery key is invalid.") from None
    if len(rk) != KEYLEN:
        raise WrongCredentials("The recovery key has the wrong length.")
    try:
        dek = _decrypt(rk, env["recovery"], _aad("recovery", hdr))
    except InvalidTag:
        raise WrongCredentials("The recovery key is wrong.") from None
    return dek, _open_data(env, dek, hdr)


def reseal_data(env: Envelope, dek: bytes, entries: list[Entry]) -> Envelope:
    """Re-encrypt only the data block with the DEK (the standard save path)."""
    hdr = _hdr_of(env)
    env = dict(env)
    env["data"] = _encrypt(dek, _payload_bytes(entries), _aad("data", hdr))
    env["checksum"] = _checksum(env)
    return env


def rewrap_credentials(env: Envelope, dek: bytes, new_master: str, new_pin: str) -> Envelope:
    """Change password/PIN: fresh salt, re-wrap the DEK under the new KEK."""
    n = int(env["kdf"]["n"])
    env = dict(env)
    env["salt"] = b64e(os.urandom(SALT_LEN))
    hdr = _hdr_of(env)
    kek = derive_kek(
        new_master, new_pin, b64d(env["salt"]), n, int(env["kdf"]["r"]), int(env["kdf"]["p"])
    )
    try:
        env["wrap"] = _encrypt(kek, dek, _aad("wrap", hdr))
    finally:
        wipe(bytearray(kek))
    env["checksum"] = _checksum(env)
    return env


# ------------------------------------------------------------------ Recovery key display
def b32_display(rk: bytes) -> str:
    """Render the recovery key as grouped, human-writable Base32."""
    s = base64.b32encode(rk).decode("ascii").rstrip("=")
    return "-".join(s[i : i + 5] for i in range(0, len(s), 5))


def b32_parse(s: str) -> bytes:
    """Parse a grouped Base32 recovery key back to bytes (tolerates spaces/dashes/case)."""
    s = s.upper().replace("-", "").replace(" ", "").strip()
    pad = (-len(s)) % 8
    return base64.b32decode(s + "=" * pad)


# ------------------------------------------------------------------ Memory wiping
def wipe(buf: bytearray | None) -> None:
    """Overwrite a bytearray buffer with zeros (best effort, see the security docs)."""
    if isinstance(buf, bytearray):
        for i in range(len(buf)):
            buf[i] = 0


# ------------------------------------------------------------------ File access (atomic)
def default_vault_path() -> str:
    """Return the per-user vault path under %APPDATA%\\Tresor (created if missing)."""
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    folder = os.path.join(base, "Tresor")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "vault.credvault")


def load_file(path: str) -> Envelope:
    """Read and JSON-parse a vault file; raises Corrupt if it is unreadable."""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise Corrupt("The vault file is unreadable.") from e


def save_file(path: str, env: Envelope) -> None:
    """Write to a temp file first (ciphertext only), fsync, then atomically replace."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(env, f, separators=(",", ":"))
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


# ------------------------------------------------------------------ Password generator
_LOWER = "abcdefghijkmnpqrstuvwxyz"  # without l, o (look-alikes)
_UPPER = "ABCDEFGHJKLMNPQRSTUVWXYZ"  # without I, O
_DIGIT = "23456789"  # without 0, 1
_SYMBOL = "!@#$%&*?-_=+"


def generate_password(
    length: int = 20,
    upper: bool = True,
    lower: bool = True,
    digits: bool = True,
    symbols: bool = True,
) -> str:
    """Generate a random password from the selected character classes (uses `secrets`)."""
    length = max(4, min(int(length), 128))
    pool = (
        (_LOWER if lower else "")
        + (_UPPER if upper else "")
        + (_DIGIT if digits else "")
        + (_SYMBOL if symbols else "")
    )
    if not pool:
        pool = _LOWER + _UPPER + _DIGIT
    return "".join(secrets.choice(pool) for _ in range(length))


# ================================================================== Session
class Session:
    """Holds the open vault in memory and wraps every operation the app needs."""

    def __init__(self, path: str | None = None):
        self.path = path or default_vault_path()
        self.env: Envelope | None = None
        self._dek: bytearray | None = None  # bytearray while the vault is open
        self.entries: list[Entry] | None = None
        self.fail = 0

    # --- Status ---
    def exists(self) -> bool:
        """True if a vault file exists at this path."""
        return os.path.exists(self.path)

    def is_open(self) -> bool:
        """True if the vault is currently unlocked (DEK held in memory)."""
        return self._dek is not None

    # --- Create ---
    def create(self, master: str, pin: str, n_exp: int | None = None) -> str:
        """Create a new vault on disk and return the recovery key (Base32) to show once."""
        env, rk = create_envelope(master, pin, [], n_exp=n_exp)
        save_file(self.path, env)
        return b32_display(rk)

    # --- Open ---
    def unlock(self, master: str, pin: str) -> list[Entry]:
        """Unlock with password + PIN. Applies a small backoff after repeated failures."""
        env = load_file(self.path)
        try:
            dek, entries = unlock_envelope(env, master, pin)
        except WrongCredentials:
            self.fail += 1
            if self.fail > 3:
                time.sleep(min(2 ** (self.fail - 3), 30))
            raise
        self.env = env
        self._dek = bytearray(dek)
        self.entries = entries
        self.fail = 0
        return entries

    def unlock_recovery(self, recovery_display: str) -> list[Entry]:
        """Unlock with the recovery key."""
        env = load_file(self.path)
        dek, entries = unlock_with_recovery(env, recovery_display)
        self.env = env
        self._dek = bytearray(dek)
        self.entries = entries
        self.fail = 0
        return entries

    # --- Save ---
    def _persist(self) -> None:
        """Re-seal the data block with the current DEK and write it to disk atomically."""
        self.env = reseal_data(self.env, bytes(self._dek), self.entries)
        save_file(self.path, self.env)

    def upsert(self, entry: Entry) -> Entry:
        """Insert or update an entry (by id) and persist. Returns the stored entry."""
        if not entry.get("id"):
            entry["id"] = "e" + secrets.token_hex(8)
        found = False
        for i, e in enumerate(self.entries):
            if e.get("id") == entry["id"]:
                self.entries[i] = entry
                found = True
                break
        if not found:
            self.entries.append(entry)
        self._persist()
        return entry

    def delete(self, entry_id: str) -> None:
        """Delete an entry by id and persist."""
        self.entries = [e for e in self.entries if e.get("id") != entry_id]
        self._persist()

    def change_credentials(self, new_master: str, new_pin: str) -> None:
        """Change the master password/PIN of the currently open vault."""
        self.env = rewrap_credentials(self.env, bytes(self._dek), new_master, new_pin)
        save_file(self.path, self.env)

    # --- Close ---
    def lock(self) -> None:
        """Wipe the in-memory DEK and drop all decrypted state."""
        if isinstance(self._dek, bytearray):
            wipe(self._dek)
        self._dek = None
        self.entries = None
        # The env holds ciphertext only; reset it too for cleanliness.
        self.env = None
