"""
clipboard_win.py - secure clipboard for Windows
================================================
A normal "copy" on Windows 11 leaves the value in three places:
  * clipboard history (Win + V)
  * cloud clipboard (sync via the Microsoft account)
  * third-party clipboard managers

So when copying we additionally set the official "sensitive" clipboard formats that
tell Windows NOT to keep this content in history or the cloud. Implemented without any
extra packages, directly against the Windows API (ctypes).

If everything fails (rare system states) there is a simple fallback.
"""

import ctypes
from ctypes import wintypes

_OK = True
try:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
except Exception:
    _OK = False

CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002

if _OK:
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalLock.restype = wintypes.LPVOID
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalUnlock.restype = wintypes.BOOL
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel32.Sleep.argtypes = [wintypes.DWORD]

    user32.OpenClipboard.restype = wintypes.BOOL
    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.CloseClipboard.restype = wintypes.BOOL
    user32.CloseClipboard.argtypes = []
    user32.EmptyClipboard.restype = wintypes.BOOL
    user32.EmptyClipboard.argtypes = []
    user32.SetClipboardData.restype = wintypes.HANDLE
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    user32.GetClipboardData.restype = wintypes.HANDLE
    user32.GetClipboardData.argtypes = [wintypes.UINT]
    user32.RegisterClipboardFormatW.restype = wintypes.UINT
    user32.RegisterClipboardFormatW.argtypes = [wintypes.LPCWSTR]


def _open(retries: int = 8) -> bool:
    """Try to open the clipboard, retrying briefly if another app holds it."""
    for _ in range(retries):
        if user32.OpenClipboard(None):
            return True
        kernel32.Sleep(20)
    return False


def _alloc(data: bytes):
    """Allocate movable global memory and fill it; ownership passes to the system."""
    h = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
    if not h:
        return None
    p = kernel32.GlobalLock(h)
    if not p:
        return None
    ctypes.memmove(p, data, len(data))
    kernel32.GlobalUnlock(h)
    return h


def _set_dword_format(name: str, value: int = 0) -> None:
    """Register a named clipboard format and set it to a 4-byte DWORD value."""
    fmt = user32.RegisterClipboardFormatW(name)
    if not fmt:
        return
    h = _alloc(int(value).to_bytes(4, "little"))
    if h:
        user32.SetClipboardData(fmt, h)


def copy(text: str) -> bool:
    """Copy text and mark it as excluded from clipboard history and cloud."""
    if not _OK or text is None:
        return _fallback_copy(text)
    if not _open():
        return _fallback_copy(text)
    try:
        user32.EmptyClipboard()
        data = (text + "\0").encode("utf-16-le")
        h = _alloc(data)
        if not h:
            return False
        user32.SetClipboardData(CF_UNICODETEXT, h)
        # Tell Windows to keep this content out of history and the cloud:
        _set_dword_format("CanIncludeInClipboardHistory", 0)
        _set_dword_format("CanUploadToCloudClipboard", 0)
        _set_dword_format("ExcludeClipboardContentFromMonitorProcessing", 0)
        return True
    finally:
        user32.CloseClipboard()


def get_text():
    """Return the current clipboard text, or None if empty/unavailable."""
    if not _OK or not _open():
        return None
    try:
        h = user32.GetClipboardData(CF_UNICODETEXT)
        if not h:
            return None
        p = kernel32.GlobalLock(h)
        if not p:
            return None
        try:
            return ctypes.wstring_at(p)
        finally:
            kernel32.GlobalUnlock(h)
    finally:
        user32.CloseClipboard()


def clear() -> None:
    """Empty the clipboard."""
    if not _OK or not _open():
        return
    try:
        user32.EmptyClipboard()
    finally:
        user32.CloseClipboard()


def clear_if_ours(secret: str) -> None:
    """Clear the clipboard only if it still holds `secret` (nothing else was copied since)."""
    try:
        if get_text() == secret:
            clear()
    except Exception:
        pass  # best effort: never let a clipboard error crash the caller


def _fallback_copy(text) -> bool:
    """Last-resort copy via the built-in `clip` command (no sensitive-format support)."""
    try:
        import subprocess

        subprocess.run("clip", input=(text or "").encode("utf-16-le"), check=False, shell=True)
        return True
    except Exception:
        return False


if __name__ == "__main__":
    # Small self-test (only meaningful on Windows with a desktop session).
    probe = "tresor-clipboard-selftest-42"
    print("copy() ->", copy(probe))
    print("get_text() matches ->", get_text() == probe)
    clear_if_ours(probe)
    print("empty after clear_if_ours ->", get_text() in ("", None))
