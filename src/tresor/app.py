"""
app.py - Tresor as a real desktop window
=========================================
Opens a native window (Windows WebView2) with the UI from ui/index.html and connects
every button to the encrypted core in vault.py.

Run for development:   python app.py   (from the source directory)
As the finished app:    a single .exe (see scripts/build.bat)

Note: the UI is bilingual (German and English, switchable in the app). Error results from
this API are stable string codes (for example "wrong_credentials") that the UI localizes.
Code comments and logs are English so international contributors can read the source.
"""

import datetime
import os
import shutil
import sys
import threading
import traceback

import webview

from . import clipboard_win as clip
from . import vault

# How long copied secrets stay in the clipboard (seconds) before auto-clear.
CLIPBOARD_SECONDS = 15


def resource_path(rel: str) -> str:
    """Locate bundled files whether running as a script or as a frozen .exe."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


def load_html() -> str:
    """Read the single-file UI that the window renders."""
    with open(resource_path(os.path.join("ui", "index.html")), encoding="utf-8") as f:
        return f.read()


def _log_error(context: str, exc: BaseException) -> None:
    """Append a full traceback to %APPDATA%\\Tresor\\error.log (the .exe has no console)."""
    try:
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        folder = os.path.join(base, "Tresor")
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, "error.log"), "a", encoding="utf-8") as f:
            f.write(f"\n==== {datetime.datetime.now()}  {context} ====\n")
            f.write("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))
    except Exception:
        pass  # best effort: logging must never crash the app


class Api:
    """Everything the UI can call via pywebview.api.*

    Methods return small dicts. The 'error' field is a stable string code (for example
    'wrong_credentials') that the UI localizes; unexpected exceptions are logged
    internally and reported as a generic code so no internal detail reaches the front-end.
    """

    def __init__(self):
        self._session = vault.Session()
        self._window = None
        self._clear_timer = None

    # ---------------------------------------------------------------- Status
    def get_state(self):
        """Report whether a vault already exists on disk."""
        return {"vault_exists": self._session.exists()}

    # ---------------------------------------------------------------- Create
    def create_vault(self, master, pin):
        """Create a new vault and return the one-time recovery key."""
        try:
            if self._session.exists():
                return {"ok": False, "error": "vault_exists"}
            recovery = self._session.create(master, pin)
            return {"ok": True, "recovery": recovery}
        except Exception as e:
            _log_error("create_vault", e)
            return {"ok": False, "error": "create_failed"}

    # ---------------------------------------------------------------- Open
    def unlock(self, master, pin):
        """Unlock with password + PIN; returns the decrypted entries on success."""
        try:
            entries = self._session.unlock(master, pin)
            return {"ok": True, "entries": entries}
        except vault.WrongCredentials:
            return {"ok": False, "error": "wrong_credentials"}
        except vault.Corrupt:
            return {"ok": False, "error": "corrupt"}
        except Exception as e:
            _log_error("unlock", e)
            return {"ok": False, "error": "unlock_failed"}

    def unlock_recovery(self, recovery_key):
        """Unlock with the recovery key."""
        try:
            entries = self._session.unlock_recovery(recovery_key)
            return {"ok": True, "entries": entries}
        except vault.WrongCredentials:
            return {"ok": False, "error": "recovery_wrong"}
        except vault.Corrupt:
            return {"ok": False, "error": "corrupt"}
        except Exception as e:
            _log_error("unlock_recovery", e)
            return {"ok": False, "error": "recovery_failed"}

    def lock(self):
        """Lock the vault and cancel any pending clipboard clear."""
        self._cancel_timer()
        self._session.lock()
        return {"ok": True}

    # ---------------------------------------------------------------- Entries
    def save_entry(self, entry):
        """Insert or update an entry and persist it."""
        if not self._session.is_open():
            return {"ok": False, "error": "locked"}
        try:
            saved = self._session.upsert(entry)
            return {"ok": True, "entry": saved}
        except Exception as e:
            _log_error("save_entry", e)
            return {"ok": False, "error": "save_failed"}

    def delete_entry(self, entry_id):
        """Delete an entry by id."""
        if not self._session.is_open():
            return {"ok": False, "error": "locked"}
        try:
            self._session.delete(entry_id)
            return {"ok": True}
        except Exception as e:
            _log_error("delete_entry", e)
            return {"ok": False, "error": "delete_failed"}

    def change_master(self, new_master, new_pin):
        """Change the master password and PIN of the open vault."""
        if not self._session.is_open():
            return {"ok": False, "error": "locked"}
        try:
            self._session.change_credentials(new_master, new_pin)
            return {"ok": True}
        except Exception as e:
            _log_error("change_master", e)
            return {"ok": False, "error": "change_failed"}

    # ---------------------------------------------------------------- Tools
    def generate_password(self, length, opts=None):
        """Generate a random password from the selected character classes."""
        opts = opts or {}
        pw = vault.generate_password(
            length,
            upper=opts.get("upper", True),
            lower=opts.get("lower", True),
            digits=opts.get("digits", True),
            symbols=opts.get("symbols", True),
        )
        return {"password": pw}

    def copy_secret(self, text, clear_after=CLIPBOARD_SECONDS):
        """Copy a value to the clipboard and schedule an auto-clear."""
        clip.copy(text)
        self._cancel_timer()
        try:
            secs = int(clear_after)
        except (TypeError, ValueError):
            secs = CLIPBOARD_SECONDS
        if secs <= 0:
            secs = CLIPBOARD_SECONDS
        t = threading.Timer(secs, clip.clear_if_ours, args=[text])
        t.daemon = True
        t.start()
        self._clear_timer = t
        return {"ok": True, "cleared_in": secs}

    def export_backup(self):
        """Save an encrypted copy of the vault to a user-chosen path."""
        if not self._session.exists():
            return {"ok": False, "error": "no_vault_backup"}
        try:
            result = self._window.create_file_dialog(
                webview.SAVE_DIALOG,
                save_filename="tresor-sicherung.credvault",
                file_types=("Tresor-Sicherung (*.credvault)", "Alle Dateien (*.*)"),
            )
            if not result:
                return {"ok": False, "error": None}  # cancelled, no message
            dest = result[0] if isinstance(result, (list, tuple)) else result
            shutil.copy2(self._session.path, dest)
            return {"ok": True, "path": dest}
        except Exception as e:
            _log_error("export_backup", e)
            return {"ok": False, "error": "backup_failed"}

    # ---------------------------------------------------------------- internal
    def _cancel_timer(self):
        """Cancel a pending clipboard-clear timer, if any."""
        if self._clear_timer:
            try:
                self._clear_timer.cancel()
            except Exception:
                pass  # timer may already have fired; harmless
            self._clear_timer = None


def main():
    """Create the window, wire up the API bridge, and run the event loop."""
    api = Api()
    debug = os.environ.get("TRESOR_DEBUG") == "1"
    window = webview.create_window(
        "Tresor",
        html=load_html(),
        js_api=api,
        width=1200,
        height=800,
        min_size=(940, 640),
        background_color="#0a0c12",
        text_select=True,
    )
    api._window = window

    def on_closed():
        api._cancel_timer()
        try:
            api._session.lock()  # wipe the in-memory key on close
        except Exception as e:
            _log_error("on_closed", e)

    window.events.closed += on_closed
    webview.start(debug=debug)


if __name__ == "__main__":
    try:
        main()
    except Exception as _e:
        _log_error("startup", _e)
        raise
