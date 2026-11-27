# Tresor: dated source and test review

Source: `66da64abfc58cd8cce05f935197aa51e31e232f2` (application 1.8.0).
Review date: 20 October 2026. Project-led, AI-assisted review; no independent third-party audit is claimed.

## What was checked

- Static architecture review of the native Python/pywebview entry points, encrypted envelope, JavaScript bridge, clipboard, saves, backups and explicit browser preview.
- Local synthetic tests: `python -m pytest tests/test_vault.py tests/test_app_backup.py -q` — **27 passed, no skips** on Windows / Python 3.14.6. All vaults in these tests are temporary synthetic fixtures. No real vault was opened.
- GitHub CI at this exact source revision: [CI run](https://github.com/Juri-Halveth/halveth-tresor/actions/runs/39413763519) and [CodeQL run](https://github.com/Juri-Halveth/halveth-tresor/actions/runs/39413763526) were completed successfully when inspected on this date. Their status is not a certification of the application or later commits.

## Security boundary

The native vault uses Scrypt-derived password-plus-PIN wrapping of a random data key, with AES-GCM for authenticated encryption. The separately held recovery key is an alternative full-access secret. Password and PIN are two knowledge inputs, not hardware multifactor authentication. See [the detailed model](security-model.md).

The operating system, Python runtime, bundled UI and WebView bridge are trusted. An unlocked renderer receives plaintext. A process with access to that session, clipboard or memory is outside the stolen-file protection model. The mutable session key buffer is overwritten on lock, but Python strings, renderer memory, paging and crash dumps prevent a promise of complete erasure.

The normal secret-copy UI requests **20 seconds**, then conditional clipboard clearing. Lock and close attempt immediate conditional clearing. Windows history/cloud exclusion requires cooperation from the native clipboard path and the OS. The fallback and other clipboard readers prevent an absolute secrecy guarantee.

The primary file, encrypted temporary save, automatic backups and user-selected exports are separate copies. Password changes rewrap the existing data key; they do not rotate the recovery key or invalidate historical copies. A recovery key is displayed at creation; it is not a consumable single-use credential.

The explicit browser preview is a mock and stores plaintext in origin-local browser storage. Use synthetic data there. It is separate from the native encrypted vault.

## What this review leaves open

Native GUI end-to-end behavior, released executable/source correspondence, signing, host ACLs, WebView/runtime behavior, physical clipboard cleanup, concurrent writers and crash/power-loss durability were not tested in this review. Local model tests and green CI do not establish those properties. Dependency versions used by a particular installed executable need their own inventory.

The review corrected documentation and support-version drift. It did not change the cryptographic implementation, touch a user vault, establish a remote exploit, or certify production suitability.

## Reproduce the bounded test

Use Python with the project's runtime dependencies and pytest in an isolated environment:

```sh
git clone https://github.com/Juri-Halveth/halveth-tresor.git
cd halveth-tresor
git checkout 66da64abfc58cd8cce05f935197aa51e31e232f2
python -m venv .venv
# Activate .venv using your shell, then:
python -m pip install -e ".[dev]"
python -m pytest tests/test_vault.py tests/test_app_backup.py -q
```

Confirm that both files execute without skips. This procedure checks the pinned source, not a downloaded executable.
