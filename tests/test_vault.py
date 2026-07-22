"""
Unit tests for the encrypted core (vault.py). Run with: pytest

Uses a small Scrypt cost (n_exp=14) so the suite is fast; production calibrates a much
higher cost. All sample data is generic (example.com), no real credentials.
"""

import copy
import json
import os

import pytest

from tresor import vault as V

NEXP = 14
MASTER = "A-strong-master-password"

SAMPLE = [
    {
        "id": "e1",
        "type": "ftp",
        "title": "Example FTP",
        "group": "Example",
        "fields": [
            {"key": "Host", "value": "ftp.example.com", "secret": False},
            {"key": "Password", "value": "Xk9-mR2p-Qw7", "secret": True},
        ],
    },
    {
        "id": "e2",
        "type": "email",
        "title": "Example Mail",
        "group": "Example",
        "fields": [{"key": "Password", "value": "N7t-Vb3s-Lp2", "secret": True}],
    },
]


@pytest.fixture
def vault_path(tmp_path):
    return str(tmp_path / "test.credvault")


def test_roundtrip_and_persistence(vault_path):
    s = V.Session(vault_path)
    recovery = s.create(MASTER, "1234", n_exp=NEXP)
    assert isinstance(recovery, str) and len(recovery) > 20
    assert os.path.exists(vault_path)

    # Nothing readable is written to disk.
    raw = open(vault_path, encoding="utf-8").read()
    assert "ftp.example.com" not in raw
    assert "Password" not in raw

    assert V.Session(vault_path).unlock(MASTER, "1234") == []

    s2 = V.Session(vault_path)
    s2.unlock(MASTER, "1234")
    s2.upsert(copy.deepcopy(SAMPLE[0]))
    s2.upsert(copy.deepcopy(SAMPLE[1]))
    assert len(s2.entries) == 2

    got = V.Session(vault_path).unlock(MASTER, "1234")
    assert len(got) == 2
    hosts = [f["value"] for e in got for f in e["fields"] if f["key"] == "Host"]
    assert hosts == ["ftp.example.com"]


@pytest.mark.parametrize(
    "master,pin",
    [
        ("wrong-password", "1234"),  # wrong password
        (MASTER, "9999"),  # wrong PIN
        ("A-strong-master-passwor", "d1234"),  # shifted boundary vs (MASTER, "1234")
    ],
)
def test_wrong_credentials_fail_closed(vault_path, master, pin):
    V.Session(vault_path).create(MASTER, "1234", n_exp=NEXP)
    with pytest.raises(V.WrongCredentials):
        V.Session(vault_path).unlock(master, pin)


def test_correct_credentials_open(vault_path):
    V.Session(vault_path).create(MASTER, "1234", n_exp=NEXP)
    assert V.Session(vault_path).unlock(MASTER, "1234") == []


def test_tampered_byte_detected(vault_path):
    s = V.Session(vault_path)
    s.create("pw", "1234", n_exp=NEXP)
    s.unlock("pw", "1234")
    s.upsert(copy.deepcopy(SAMPLE[0]))

    env = V.load_file(vault_path)
    blob = bytearray(V.b64d(env["data"]["blob"]))
    blob[0] ^= 0x01
    env["data"]["blob"] = V.b64e(bytes(blob))
    V.save_file(vault_path, env)

    with pytest.raises((V.Corrupt, V.WrongCredentials)):
        V.Session(vault_path).unlock("pw", "1234")


def test_scrypt_downgrade_blocked(vault_path):
    V.Session(vault_path).create("pw", "1234", n_exp=NEXP)
    env = V.load_file(vault_path)
    env["kdf"]["n"] = 2  # trivial cost, IF it were accepted
    V.save_file(vault_path, env)
    with pytest.raises((V.WrongCredentials, V.Corrupt)):
        V.Session(vault_path).unlock("pw", "1234")


def test_recovery_key(vault_path):
    s = V.Session(vault_path)
    recovery = s.create("forgotten", "1234", n_exp=NEXP)
    s.unlock("forgotten", "1234")
    s.upsert(copy.deepcopy(SAMPLE[0]))

    s2 = V.Session(vault_path)
    assert len(s2.unlock_recovery(recovery)) == 1
    s2.change_credentials("new-password", "5678")

    with pytest.raises(V.WrongCredentials):
        V.Session(vault_path).unlock("forgotten", "1234")

    got = V.Session(vault_path).unlock("new-password", "5678")
    assert got and got[0]["title"] == "Example FTP"


def test_wrong_recovery_key(vault_path):
    V.Session(vault_path).create("pw", "1234", n_exp=NEXP)
    with pytest.raises(V.WrongCredentials):
        V.Session(vault_path).unlock_recovery("AAAA-BBBB-CCCC-DDDD-EEEE")


def test_change_password_keeps_data(vault_path):
    s = V.Session(vault_path)
    s.create("old", "1111", n_exp=NEXP)
    s.unlock("old", "1111")
    s.upsert(copy.deepcopy(SAMPLE[0]))
    s.upsert(copy.deepcopy(SAMPLE[1]))
    s.change_credentials("new", "2222")
    assert len(V.Session(vault_path).unlock("new", "2222")) == 2


def test_lock_wipes_key(vault_path):
    s = V.Session(vault_path)
    s.create("pw", "1234", n_exp=NEXP)
    s.unlock("pw", "1234")
    assert s.is_open()
    s.lock()
    assert not s.is_open()
    assert s._dek is None  # regression: the DEK is dropped on lock/close


def test_base32_roundtrip():
    for _ in range(50):
        b = os.urandom(V.KEYLEN)
        assert V.b32_parse(V.b32_display(b)) == b


def test_password_generator():
    pw = V.generate_password(24, symbols=False)
    assert len(pw) == 24
    assert all(c not in V._SYMBOL for c in pw)
    assert V.generate_password(30) != V.generate_password(30)


def test_kdf_input_length_prefix():
    assert V.kdf_input("ab", "123") != V.kdf_input("ab1", "23")


def test_concurrent_no_clobber(vault_path):
    # Two sessions on the same vault: a stale one must not wipe the other's entries.
    def note(idstr):
        return {"id": idstr, "type": "note", "title": idstr, "group": "", "fields": []}

    a = V.Session(vault_path)
    a.create("pw", "1234", n_exp=NEXP)
    a.unlock("pw", "1234")
    for i in range(3):
        a.upsert(note(f"a{i}"))  # disk now holds 3 entries

    b = V.Session(vault_path)
    b.unlock("pw", "1234")  # b loads the 3-entry view

    for i in range(3, 12):
        a.upsert(note(f"a{i}"))  # a grows the file to 12

    b.upsert(note("b1"))  # b saves; the fix must reload first, not clobber a's 9

    final = V.Session(vault_path).unlock("pw", "1234")
    ids = {e["id"] for e in final}
    assert len(final) == 13
    assert "b1" in ids
    assert all((f"a{i}") in ids for i in range(12))


@pytest.mark.parametrize(
    "tamper",
    [
        {"r": 100000},  # a single parameter out of range
        {"n": 1 << 21, "r": 64},  # each in range, but the n*r product is far too large
    ],
)
def test_absurd_scrypt_params_rejected(vault_path, tamper):
    # A tampered Scrypt cost must be rejected up front (Corrupt), before any Scrypt work.
    V.Session(vault_path).create("pw", "1234", n_exp=NEXP)
    env = V.load_file(vault_path)
    env["kdf"].update(tamper)
    V.save_file(vault_path, env)
    with pytest.raises((V.Corrupt, V.WrongCredentials)):
        V.Session(vault_path).unlock("pw", "1234")


# ---------------------------------------------------------------- Focus area + backups
FOCUS = {
    "name": "Alex",
    "dailyDay": 20321,
    "notes": "Ideen: einfach anfangen.",
    "lists": [{"id": "l1", "title": "Heute", "items": [{"id": "i1", "text": "Posten", "done": True}]}],
}


def test_focus_roundtrip(vault_path):
    s = V.Session(vault_path)
    s.create("pw", "1234", n_exp=NEXP)
    s.unlock("pw", "1234")
    assert s.focus == {}  # a fresh vault starts with empty focus
    s.set_focus(copy.deepcopy(FOCUS))

    reopened = V.Session(vault_path)
    reopened.unlock("pw", "1234")
    assert reopened.focus == FOCUS
    assert reopened.entries == []  # focus lives alongside entries, not instead of them


def test_focus_and_entries_coexist(vault_path):
    s = V.Session(vault_path)
    s.create("pw", "1234", n_exp=NEXP)
    s.unlock("pw", "1234")
    s.upsert(copy.deepcopy(SAMPLE[0]))
    s.set_focus(copy.deepcopy(FOCUS))
    s.upsert(copy.deepcopy(SAMPLE[1]))  # saving an entry must not drop focus

    got = V.Session(vault_path)
    got.unlock("pw", "1234")
    assert len(got.entries) == 2
    assert got.focus["name"] == "Alex"


def test_old_vault_without_focus_still_opens(vault_path):
    # Simulate a vault written before the Focus feature: its data payload has only "entries".
    s = V.Session(vault_path)
    s.create("pw", "1234", n_exp=NEXP)
    s.unlock("pw", "1234")
    hdr = V._hdr_of(s.env)
    old_payload = json.dumps({"entries": [copy.deepcopy(SAMPLE[0])]}).encode("utf-8")
    s.env["data"] = V._encrypt(bytes(s._dek), old_payload, V._aad("data", hdr))
    s.env["checksum"] = V._checksum(s.env)
    V.save_file(vault_path, s.env)

    got = V.Session(vault_path)
    entries = got.unlock("pw", "1234")
    assert len(entries) == 1  # entries load unchanged
    assert got.focus == {}  # missing focus defaults to empty, no crash


def test_focus_recovery_unlock(vault_path):
    s = V.Session(vault_path)
    recovery = s.create("pw", "1234", n_exp=NEXP)
    s.unlock("pw", "1234")
    s.set_focus(copy.deepcopy(FOCUS))

    got = V.Session(vault_path)
    got.unlock_recovery(recovery)
    assert got.focus == FOCUS


def test_autobackups_created_and_capped(vault_path):
    s = V.Session(vault_path)
    s.create("pw", "1234", n_exp=NEXP)
    s.unlock("pw", "1234")
    folder = os.path.join(os.path.dirname(vault_path), "backups")
    assert os.path.isdir(folder)  # create() already made the first backup
    for i in range(V.BACKUP_KEEP + 5):
        s.upsert({"id": f"e{i}", "type": "note", "title": str(i), "group": "", "fields": []})
    backups = [f for f in os.listdir(folder) if f.startswith("vault-")]
    assert 1 <= len(backups) <= V.BACKUP_KEEP  # kept, and never grows without bound
