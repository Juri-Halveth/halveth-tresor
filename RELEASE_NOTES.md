# Tresor v1.8.1

Locking the vault now finishes pending Focus writes. Existing vaults retain their file format. When opening or recovering a vault, Tresor checks file structure and key-derivation costs before invoking the password derivation. These checks also run under optimized Python.

Concurrent saves use separate temporary files. Brief Windows file-replacement failures are retried. If the replacement fails permanently, Tresor reports the error and preserves the previous destination.

The Windows build provides `Tresor.exe`, its SHA-256 in `Tresor.exe.sha256` and the accompanying `Tresor-notices.zip`. You can check the executable in PowerShell with `Get-FileHash .\Tresor.exe -Algorithm SHA256`. Compare the result with the hash for the same build. The executable is unsigned.

See the [security model](docs/security-model.md), [versioned license map](LICENSES.md) and [component notices](THIRD-PARTY-LICENSES.md).
