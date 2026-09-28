"""Offline local release installs, independent of pytest's source-path injection.

Requires pip, setuptools and wheel in the test environment. Third-party runtime
dependencies are reused without processing the host environment's .pth files.
"""

import json
from pathlib import Path
import shutil
import subprocess
import sys
import sysconfig

import pytest


def run(*args, cwd):
    result = subprocess.run(
        [sys.executable, *args], cwd=cwd, capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result


@pytest.fixture(scope="module")
def local_release(tmp_path_factory):
    root = Path(__file__).resolve().parents[2]
    staging = tmp_path_factory.mktemp("phase1-release")
    wheels = staging / "wheels"
    wheels.mkdir()
    # Build from copies so setuptools never writes build/egg-info into the repo.
    for package, modules in (
        ("shared", ["phoenix_shared"]),
        ("phoenix-core", ["phoenix"]),
        ("phoenix-intelligence", ["api", "services"]),
    ):
        source = staging / package
        source.mkdir()
        for filename in ("pyproject.toml", "README.md"):
            if (root / package / filename).exists():
                shutil.copy2(root / package / filename, source / filename)
        for module in modules:
            shutil.copytree(
                root / package / module, source / module,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )
        run(
            "-m", "pip", "wheel", "--no-deps", "--no-build-isolation", "--no-index",
            "--wheel-dir", str(wheels), str(source), cwd=staging,
        )
    return staging


@pytest.mark.parametrize("package", ["phoenix-core", "phoenix-intelligence"])
@pytest.mark.parametrize("editable", [False, True])
def test_local_package_install_supplies_shared(local_release, tmp_path, package, editable):
    target = tmp_path / "site-packages"
    if editable:
        inputs = ["-e", str(local_release / "shared"), "-e", str(local_release / package)]
    else:
        wheels = local_release / "wheels"
        inputs = [str(next(wheels.glob(f"{name}-*.whl"))) for name in (
            "phoenix_shared", package.replace("-", "_"),
        )]
    # --no-deps avoids downloading third-party libraries. Below we independently
    # assert the built metadata requires the exact Shared version we installed.
    run(
        "-m", "pip", "install", "--no-index", "--no-deps", "--no-build-isolation",
        "--target", str(target), *inputs, cwd=tmp_path,
    )
    expected_shared = local_release / "shared" if editable else target
    expected_package = local_release / package if editable else target
    probe = r'''
import importlib
from importlib.metadata import distribution
import json
from pathlib import Path
import site
import sys

target, dependencies, package, expected_shared, expected_package = json.loads(sys.argv[1])
# -I -S excludes PYTHONPATH, user site, repository paths and host editable hooks.
# Only the freshly installed target's .pth files may be processed.
sys.path.extend(dependencies)
sys.path.insert(0, target)
site.addsitedir(target)
from packaging.requirements import Requirement
from phoenix_shared.contracts.project_context import ProjectContext
import phoenix_shared.contracts.project_context as shared_module
module = importlib.import_module(
    "phoenix.sdk.intelligence_client" if package == "phoenix-core" else "api.models"
)
assert module.ProjectContext is ProjectContext
assert Path(shared_module.__file__).is_relative_to(Path(expected_shared))
assert Path(module.__file__).is_relative_to(Path(expected_package))
requirements = [Requirement(item) for item in distribution(package).requires or []]
shared_requirement, = [item for item in requirements if item.name == "phoenix-shared"]
assert shared_requirement.url is None  # No absolute paths or invented registry URL.
assert str(shared_requirement.specifier) == "==" + distribution("phoenix-shared").version
print("isolated local install/import passed")
'''
    dependency_paths = list(dict.fromkeys(
        sysconfig.get_paths()[key] for key in ("purelib", "platlib")
    ))
    result = run(
        "-I", "-S", "-B", "-c", probe,
        json.dumps([str(target), dependency_paths, package, str(expected_shared), str(expected_package)]),
        cwd=tmp_path,
    )
    assert "isolated local install/import passed" in result.stdout
