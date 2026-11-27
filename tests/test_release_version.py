"""Release label drift must stop before an incorrectly labelled build ships."""

import importlib.util
import shutil
from pathlib import Path

import pytest

from tresor import __version__

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("release_check", ROOT / "scripts/check_release.py")
release_check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release_check)


def fixture_root(tmp_path):
    for name in (
        "src/tresor/__init__.py",
        "pyproject.toml",
        "README.md",
        "README.en.md",
        "packaging/version_info.txt",
    ):
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    return tmp_path


def test_current_release_and_matching_tag():
    assert release_check.check(tag="v" + __version__) == __version__


def test_changed_tag_is_rejected():
    with pytest.raises(ValueError, match="Tag must equal"):
        release_check.check(tag="v999.0.0")


def test_stale_readme_and_windows_resource_are_rejected(tmp_path):
    root = fixture_root(tmp_path)
    readme = root / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8").replace(f"Version {__version__}", "Version 0.0.0"),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Version label drift"):
        release_check.check(root)
    release_check.check(root, write=True)
    resource = root / "packaging/version_info.txt"
    resource.write_text("SYNTHETIC_STALE_RESOURCE", encoding="utf-8")
    with pytest.raises(ValueError, match="Windows resource version drift"):
        release_check.check(root)


def test_duplicate_canonical_version_is_rejected(tmp_path):
    root = fixture_root(tmp_path)
    source = root / "src/tresor/__init__.py"
    with source.open("a", encoding="utf-8") as output:
        output.write('\n__version__ = "0.0.0"\n')
    with pytest.raises(ValueError, match="Exactly one"):
        release_check.check(root)
