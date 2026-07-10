"""
Manual native end-to-end smoke test (opens a real window).

This is NOT a pytest test (the filename avoids collection) because it launches a real
WebView2 window and needs a desktop session. Run it directly:

    python tests/e2e/native_smoke.py

It drives the full flow (set up, show recovery key, add an entry, lock, unlock) against
a TEMPORARY vault and prints a JSON result. It never touches the real vault.
"""

import os
import sys
import tempfile
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

import webview

from tresor import app, vault

FLOW = r"""
(async function () {
  window.__t = { steps: [] };
  const $ = s => document.querySelector(s);
  const vis = id => !document.getElementById(id).classList.contains('hidden');
  const wait = (c, n = 60) => new Promise(async r => {
    for (let i = 0; i < n; i++) { if (c()) return r(true); await new Promise(x => setTimeout(x, 80)); } r(false);
  });
  try {
    await wait(() => vis('screen-setup'));
    $('#stPass').value = 'Test-Password-123'; $('#stPass2').value = 'Test-Password-123';
    $('#stPin').value = '2468'; $('#stBtn').click();
    window.__t.steps.push('setup-submitted');
    await wait(() => vis('screen-recovery'));
    window.__t.recoveryKey = $('#rvKey').textContent;
    $('#rvChk').checked = true; $('#rvChk').dispatchEvent(new Event('change')); $('#rvBtn').click();
    await wait(() => vis('screen-app'));
    window.__t.steps.push('app-open');
    const e = { type: 'ftp', title: 'Example FTP', group: 'Example Host',
                fields: [{ key: 'Host', value: 'ftp.example.com', secret: false },
                         { key: 'Password', value: 'secret-123', secret: true }] };
    const r = await window.pywebview.api.save_entry(e);
    window.__t.saveOk = !!(r && r.ok);
    await window.pywebview.api.lock();
    const u = await window.pywebview.api.unlock('Test-Password-123', '2468');
    window.__t.reopenCount = (u && u.entries || []).length;
    window.__t.done = true;
  } catch (err) { window.__t.error = String(err); window.__t.done = true; }
})();
"""


def main():
    session_path = os.path.join(tempfile.gettempdir(), "tresor_native_smoke.credvault")
    try:
        os.remove(session_path)
    except OSError:
        pass

    api = app.Api()
    api._session = vault.Session(session_path)
    window = webview.create_window(
        "Tresor Smoke Test", html=app.load_html(), js_api=api, width=1200, height=800
    )
    api._window = window

    def run():
        window.evaluate_js(FLOW)
        result = None
        for _ in range(50):
            time.sleep(0.5)
            r = window.evaluate_js(
                "window.__t && window.__t.done ? JSON.stringify(window.__t) : null"
            )
            if r and r != "null":
                result = r
                break
        print("NATIVE SMOKE:", result)
        try:
            os.remove(session_path)
        except OSError:
            pass
        window.destroy()

    window.events.loaded += lambda: threading.Timer(1.2, run).start()
    webview.start(debug=False)


if __name__ == "__main__":
    main()
