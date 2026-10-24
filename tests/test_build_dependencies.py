"""Keep the optional icon tool off the retired Pillow compatibility line."""

from pathlib import Path

import pytest
from packaging.requirements import Requirement
from packaging.version import Version

tomllib = pytest.importorskip("tomllib")
ROOT = Path(__file__).resolve().parents[1]


def test_icon_dependency_uses_fixed_line_without_changing_vault_runtime():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert all(Requirement(item).name.lower() != "pillow" for item in project["dependencies"])
    icon = next(
        Requirement(item)
        for item in project["optional-dependencies"]["dev"]
        if Requirement(item).name.lower() == "pillow"
    )
    assert not icon.specifier.contains("12.3.0")
    assert icon.specifier.contains("13.0.0")
    assert icon.marker is not None
    assert not icon.marker.evaluate({"python_version": "3.10"})
    assert icon.marker.evaluate({"python_version": "3.11"})
    locked = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    versions = [Version(item["version"]) for item in locked["package"] if item["name"] == "pillow"]
    assert versions and all(version >= Version("13.0.0") for version in versions)
    plain = (ROOT / "requirements-dev.txt").read_text(encoding="utf-8").splitlines()
    assert str(icon) in [str(Requirement(line)) for line in plain if line.startswith("pillow")]
