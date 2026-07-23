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

import ctypes
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

# File-type filter for the backup Save dialog. pywebview validates this with a strict
# regex that allows only word characters and spaces in the description, so a hyphen (as
# in an earlier "Tresor-Sicherung") makes the whole dialog call raise before it opens.
# Keep these descriptions plain. A regression test checks these exact strings stay valid.
_BACKUP_FILE_TYPES = ("Tresor Sicherung (*.credvault)", "Alle Dateien (*.*)")


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
        self._last_copied = None  # last secret put on the clipboard, so lock/close can wipe it

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
            return {"ok": True, "entries": entries, "focus": self._session.focus or {}}
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
            return {"ok": True, "entries": entries, "focus": self._session.focus or {}}
        except vault.WrongCredentials:
            return {"ok": False, "error": "recovery_wrong"}
        except vault.Corrupt:
            return {"ok": False, "error": "corrupt"}
        except Exception as e:
            _log_error("unlock_recovery", e)
            return {"ok": False, "error": "recovery_failed"}

    def lock(self):
        """Lock the vault and clear any secret still on the clipboard."""
        self._clear_clipboard_now()
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

    # ---------------------------------------------------------------- Focus area
    def get_focus(self):
        """Return the Focus-area data (checklists, notes, name) of the open vault."""
        if not self._session.is_open():
            return {"ok": False, "error": "locked"}
        return {"ok": True, "focus": self._session.focus or {}}

    def save_focus(self, focus):
        """Replace and persist the Focus-area data. Entries are left untouched."""
        if not self._session.is_open():
            return {"ok": False, "error": "locked"}
        try:
            saved = self._session.set_focus(focus if isinstance(focus, dict) else {})
            return {"ok": True, "focus": saved}
        except Exception as e:
            _log_error("save_focus", e)
            return {"ok": False, "error": "save_failed"}

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

    def copy_plain(self, text):
        """Copy plain, non-secret text (e.g. a Focus task) to the clipboard.

        Unlike copy_secret there is no auto-clear timer: a checklist item is not a secret,
        and clearing it after a few seconds would be surprising when the user wants to paste
        it wherever they like.
        """
        try:
            clip.copy(str(text))
            return {"ok": True}
        except Exception as e:
            _log_error("copy_plain", e)
            return {"ok": False, "error": "copy_failed"}

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
        self._last_copied = text
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
            dest = self._ask_save_path("tresor-sicherung.credvault")
            if not dest:
                return {"ok": False, "error": None}  # cancelled, no message
            shutil.copy2(self._session.path, dest)
            return {"ok": True, "path": dest}
        except Exception as e:
            _log_error("export_backup", e)
            return {"ok": False, "error": "backup_failed"}

    def _ask_save_path(self, default_name: str):
        """Show a Save dialog and return the chosen path, or None if cancelled.

        pywebview validates the file-type filter with a strict regex: the description
        may contain only word characters and spaces, so a hyphen (as in an earlier
        "Tresor-Sicherung" filter) makes the whole call raise before any dialog opens.
        We use a valid filter and, if one is ever rejected anyway, fall back to a
        dialog with no filter so a backup can always be saved.
        """
        try:
            result = self._window.create_file_dialog(
                webview.SAVE_DIALOG, save_filename=default_name, file_types=_BACKUP_FILE_TYPES
            )
        except ValueError:
            result = self._window.create_file_dialog(
                webview.SAVE_DIALOG, save_filename=default_name
            )
        if not result:
            return None
        return result[0] if isinstance(result, (list, tuple)) else result

    # ---------------------------------------------------------------- internal
    def _cancel_timer(self):
        """Cancel a pending clipboard-clear timer, if any."""
        if self._clear_timer:
            try:
                self._clear_timer.cancel()
            except Exception:
                pass  # timer may already have fired; harmless
            self._clear_timer = None

    def _clear_clipboard_now(self):
        """Cancel the pending auto-clear and wipe the clipboard now if it still holds our
        secret. Locking or closing is a deliberate "secure now" action, so the secret must
        not linger in the clipboard waiting for the timer that we are about to cancel."""
        self._cancel_timer()
        last = self._last_copied
        self._last_copied = None
        if last is not None:
            try:
                clip.clear_if_ours(last)
            except Exception:
                pass  # best effort: never let a clipboard error crash lock/close


_SINGLE_INSTANCE_MUTEX = None


def _is_only_instance() -> bool:
    """Take a session-wide named mutex; return False if another Tresor is already running.

    This prevents two windows on the same vault at once, which is what could otherwise let
    a stale window overwrite entries that were added in another window.
    """
    global _SINGLE_INSTANCE_MUTEX
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
        _SINGLE_INSTANCE_MUTEX = kernel32.CreateMutexW(None, False, "HalvethTresorSingleInstance")
        return ctypes.get_last_error() != 183  # 183 = ERROR_ALREADY_EXISTS
    except Exception:
        return True  # if the guard cannot run, never block the app


def main():
    """Create the window, wire up the API bridge, and run the event loop."""
    if not _is_only_instance():
        try:
            ctypes.windll.user32.MessageBoxW(
                None,
                "Tresor läuft bereits. Bitte nutze das bereits offene Fenster.\n\n"
                "Tresor is already running. Please use the window that is already open.",
                "Tresor",
                0x40,  # MB_ICONINFORMATION
            )
        except Exception:
            pass
        return
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
        api._clear_clipboard_now()  # wipe any secret still on the clipboard
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
