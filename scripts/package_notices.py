"""Collect notices from the actual Windows build environment alongside the EXE."""

import argparse
import json
import sys
from importlib.metadata import distribution
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

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
    import pefile  # Windows build dependency of PyInstaller

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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    package_notices(parser.parse_args().output)
