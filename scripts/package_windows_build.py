"""Verify the frozen Windows executable and prepare its checksum and notices."""

import argparse
import hashlib
import json
import marshal
import sys
import tempfile
from importlib.metadata import distribution
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

import pefile
from check_release import check
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from PyInstaller.archive.readers import CArchiveReader

ROOT = Path(__file__).resolve().parents[1]
EXTRA_NOTICES = ROOT / "packaging" / "notices"
PROJECT_FILES = (
    "LICENSE",
    "LICENSES.md",
    "LICENSE-HALVETH-PIRL-2.0.md",
    "HALVETH-RIGHTS.md",
    "HALVETH-RIGHTS.json",
    "THIRD-PARTY-LICENSES.md",
)


def runtime_packages():
    pending = ["tresor"]
    resolved = {}
    while pending:
        name = pending.pop()
        if name in resolved:
            continue
        package = distribution(name)
        resolved[name] = package
        for spec in package.requires or ():
            req = Requirement(spec)
            if req.marker is None or req.marker.evaluate({"extra": ""}):
                pending.append(canonicalize_name(req.name))
    return resolved


def windows_sdk_version(webview):
    assembly = webview.locate_file("webview/lib/Microsoft.Web.WebView2.Core.dll")
    with pefile.PE(str(assembly)) as pe:
        info = pe.VS_FIXEDFILEINFO[0]
        high, low = info.FileVersionMS, info.FileVersionLS
    return ".".join(map(str, (high >> 16, high & 0xFFFF, low >> 16, low & 0xFFFF)))


def package_notices(output):
    packages = runtime_packages()
    sdk = windows_sdk_version(packages["pywebview"])
    files = {name: ROOT / name for name in PROJECT_FILES}
    files["CPython/LICENSE.txt"] = Path(sys.base_prefix) / "LICENSE.txt"
    for name in ("LICENSE.txt", "NOTICE.txt"):
        files[f"WebView2-SDK-{sdk}/{name}"] = EXTRA_NOTICES / f"webview2-sdk-{sdk}-{name}"

    # The bootloader is distributed in the frozen executable.
    packages["pyinstaller"] = distribution("pyinstaller")
    for name, package in packages.items():
        if name == "tresor":
            continue
        prefix = f"packages/{name}-{package.version}/"
        notices = {}
        for entry in package.files or ():
            parts = entry.as_posix().partition(".dist-info/licenses/")
            if parts[1]:
                notices[prefix + parts[2]] = package.locate_file(entry)
        if not notices and name == "proxy-tools" and package.version == "0.1.0":
            notices[prefix + "LICENSE.txt"] = EXTRA_NOTICES / "proxy-tools-0.1.0-LICENSE.txt"
        if not notices:
            raise ValueError(f"Missing distribution notices for {name} {package.version}")
        files.update(notices)

    versions = {name: pkg.version for name, pkg in sorted(packages.items())}
    versions.update({"CPython": sys.version.split()[0], "WebView2-SDK": sdk})
    entries = {name: source.read_bytes() for name, source in files.items()}
    entries["versions.json"] = (json.dumps(versions, indent=2) + "\n").encode()
    with ZipFile(output, "w") as archive:
        for name, data in sorted(entries.items()):
            archive.writestr(ZipInfo(name), data, compress_type=ZIP_DEFLATED)


def finish_build(executable):
    version = check()
    with pefile.PE(str(executable)) as pe:
        versions = {
            (table.entries.get(b"FileVersion"), table.entries.get(b"ProductVersion"))
            for group in pe.FileInfo
            for block in group
            if block.Key == b"StringFileInfo"
            for table in block.StringTable
        }
    if versions != {(version.encode(), version.encode())}:
        raise ValueError("Executable version mismatch")
    archive = CArchiveReader(str(executable))
    ui = next(name for name in archive.toc if name.replace("\\", "/") == "ui/index.html")
    source = ROOT / "src" / "tresor"
    if archive.extract(ui) != (source / "ui/index.html").read_bytes():
        raise ValueError("Executable UI differs from source")
    modules = archive.open_embedded_archive("PYZ.pyz")
    for path in sorted(source.glob("*.py")):
        if path.stem == "__main__":
            code = marshal.loads(archive.extract("__main__"))
        else:
            module = "tresor" if path.stem == "__init__" else "tresor." + path.stem
            code = modules.extract(module)
        expected = compile(
            path.read_bytes(), code.co_filename, "exec", dont_inherit=True, optimize=0
        )
        if code != expected:
            raise ValueError(f"Executable module differs from source: {path.name}")
    with executable.open("rb") as binary:
        checksum = hashlib.file_digest(binary, "sha256").hexdigest().upper()
    with tempfile.TemporaryDirectory(dir=executable.parent) as tmp:
        notices = Path(tmp) / "Tresor-notices.zip"
        package_notices(notices)
        sidecar = Path(tmp) / (executable.name + ".sha256")
        sidecar.write_text(checksum + "\n", encoding="ascii")
        notices.replace(executable.parent / notices.name)
        sidecar.replace(executable.parent / sidecar.name)
    print(f"{executable.name} {version}  SHA-256 {checksum}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    finish_build(parser.parse_args().executable)
