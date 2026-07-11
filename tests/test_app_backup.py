"""
Tests for the encrypted backup export (app bridge). The native Save dialog is mocked,
so these run headless with no GUI. They guard the bug where a hyphen in the file-type
filter made every backup attempt raise before a dialog could open.
"""

import pytest

webview = pytest.importorskip("webview")

from tresor import app, vault  # noqa: E402  (import after importorskip is intentional)

NEXP = 14
ENTRY = {"id": "e1", "type": "note", "title": "Secret note", "group": "", "fields": []}


class _FakeWindow:
    """Stands in for a pywebview window: returns a preset path from the Save dialog."""

    def __init__(self, path):
        self._path = path
        self.calls = []

    def create_file_dialog(self, *args, **kwargs):
        self.calls.append(kwargs)
        return self._path


def _api_with_vault(tmp_path, window):
    api = app.Api()
    api._session = vault.Session(str(tmp_path / "vault.credvault"))
    api._session.create("pw", "1234", n_exp=NEXP)
    api._session.unlock("pw", "1234")
    api._session.upsert(dict(ENTRY))
    api._window = window
    return api


def test_export_backup_writes_decryptable_copy(tmp_path):
    dest = str(tmp_path / "backup.credvault")
    api = _api_with_vault(tmp_path, _FakeWindow(dest))

    result = api.export_backup()
    assert result["ok"] is True
    assert result["path"] == dest

    # The backup is encrypted (no plaintext) and opens with the same credentials.
    raw = open(dest, encoding="utf-8").read()
    assert "Secret note" not in raw
    got = vault.Session(dest).unlock("pw", "1234")
    assert [e["id"] for e in got] == ["e1"]


def test_export_backup_cancelled_reports_no_error(tmp_path):
    api = _api_with_vault(tmp_path, _FakeWindow(None))  # user cancels the dialog
    result = api.export_backup()
    assert result["ok"] is False
    assert result["error"] is None  # cancel is silent, not an error toast


def test_export_backup_falls_back_when_filter_rejected(tmp_path):
    """If pywebview ever rejects the filter, we retry without it and still save."""
    dest = str(tmp_path / "backup.credvault")

    class _PickyWindow:
        def __init__(self, path):
            self._path = path
            self.tried_filter = False

        def create_file_dialog(self, *args, **kwargs):
            if "file_types" in kwargs:
                self.tried_filter = True
                raise ValueError("bad filter")
            return self._path

    window = _PickyWindow(dest)
    api = _api_with_vault(tmp_path, window)
    result = api.export_backup()
    assert result["ok"] is True
    assert window.tried_filter is True  # it attempted the filter before falling back


def test_lock_clears_clipboard(tmp_path, monkeypatch):
    # Locking must actively clear a copied secret, not just cancel the auto-clear timer.
    cleared = []
    monkeypatch.setattr(app.clip, "copy", lambda text: True)
    monkeypatch.setattr(app.clip, "clear_if_ours", lambda secret: cleared.append(secret))

    api = _api_with_vault(tmp_path, _FakeWindow(None))
    api.copy_secret("s3cret-value", clear_after=999)  # long timer; must not fire on its own
    assert api._last_copied == "s3cret-value"

    api.lock()
    assert cleared == ["s3cret-value"]  # cleared immediately on lock, not left behind
    assert api._last_copied is None


def test_backup_filter_strings_are_valid():
    """The exact filter shipped in app.py must pass pywebview's own validator."""
    util = pytest.importorskip("webview.util")
    if not hasattr(util, "parse_file_type"):
        pytest.skip("pywebview file-type parser not available in this version")
    for f in app._BACKUP_FILE_TYPES:
        util.parse_file_type(f)  # must not raise
