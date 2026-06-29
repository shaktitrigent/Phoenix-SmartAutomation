"""PackagingCheckSuite — verify dist/ artifacts are present and self-consistent.

Checks performed
----------------
T1  wheel_present_shared        phoenix_shared-*.whl exists in dist/
T1  wheel_present_core          phoenix_core-*.whl exists in dist/
T1  wheel_version_match         wheel metadata version == pyproject.toml version
T2  wheel_importable_shared     `python -c "import phoenix_shared"` succeeds (dry install)
T2  wheel_importable_core       `python -c "import phoenix"` succeeds (dry install)
T1  exe_present                 phoenix-intelligence*.exe exists (optional, skipped if absent)

Usage::

    python -m preflight.suites.packaging
    python preflight/suites/packaging.py --dist-dir dist/
"""
from __future__ import annotations

import logging
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path
from typing import List

from preflight.assertions.result import AssertionResult

logger = logging.getLogger(__name__)

_HERE = Path(__file__).parent.parent   # preflight/
_REPO = _HERE.parent                   # repo root


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def check_wheel_present(dist_dir: Path, pattern: str, name: str) -> AssertionResult:
    """Assert that at least one wheel matching *pattern* exists in *dist_dir*."""
    matches = sorted(dist_dir.glob(pattern))
    if matches:
        return AssertionResult(
            tier="T1",
            name=f"T1:wheel_present_{name}",
            passed=True,
            detail=str(matches[-1]),
        )
    return AssertionResult(
        tier="T1",
        name=f"T1:wheel_present_{name}",
        passed=False,
        detail=f"No file matching {dist_dir / pattern} found",
    )


def check_version_match(dist_dir: Path, pkg_dir: Path, pkg_name: str) -> AssertionResult:
    """Assert the newest wheel's version == the version declared in pyproject.toml."""
    wheel_pattern = f"{pkg_name.replace('-', '_')}-*.whl"
    wheels = sorted(dist_dir.glob(wheel_pattern))
    if not wheels:
        return AssertionResult(
            tier="T1",
            name=f"T1:wheel_version_match_{pkg_name}",
            passed=False,
            detail=f"No wheel found matching {wheel_pattern}",
        )

    # Extract version from wheel filename: <dist>-<version>-*.whl
    wheel_path = wheels[-1]
    parts = wheel_path.stem.split("-")
    wheel_version = parts[1] if len(parts) >= 2 else "unknown"

    # Read version from pyproject.toml
    toml_path = pkg_dir / "pyproject.toml"
    if not toml_path.exists():
        return AssertionResult(
            tier="T1",
            name=f"T1:wheel_version_match_{pkg_name}",
            passed=False,
            detail=f"pyproject.toml not found at {toml_path}",
        )

    try:
        with open(toml_path, "rb") as fh:
            toml_data = tomllib.load(fh)
        toml_version = toml_data.get("project", {}).get("version", "unknown")
    except Exception as exc:
        return AssertionResult(
            tier="T1",
            name=f"T1:wheel_version_match_{pkg_name}",
            passed=False,
            detail=f"Failed to parse pyproject.toml: {exc}",
        )

    passed = wheel_version == toml_version
    return AssertionResult(
        tier="T1",
        name=f"T1:wheel_version_match_{pkg_name}",
        passed=passed,
        detail=(
            f"wheel={wheel_version}, pyproject={toml_version}"
            + (" — MISMATCH" if not passed else "")
        ),
    )


def check_wheel_importable(dist_dir: Path, wheel_pattern: str, import_stmt: str, name: str) -> AssertionResult:
    """Dry-install the wheel into a temp venv and verify the import succeeds."""
    wheels = sorted(dist_dir.glob(wheel_pattern))
    if not wheels:
        return AssertionResult(
            tier="T2",
            name=f"T2:wheel_importable_{name}",
            passed=False,
            detail=f"No wheel matching {wheel_pattern} to install",
        )

    wheel_path = wheels[-1]
    with tempfile.TemporaryDirectory(prefix="phoenix_pkg_check_") as tmp:
        venv_dir = Path(tmp) / "venv"
        try:
            subprocess.run(
                [sys.executable, "-m", "venv", str(venv_dir)],
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as exc:
            return AssertionResult(
                tier="T2",
                name=f"T2:wheel_importable_{name}",
                passed=False,
                detail=f"venv creation failed: {exc.stderr}",
            )

        if sys.platform == "win32":
            python_exe = venv_dir / "Scripts" / "python.exe"
        else:
            python_exe = venv_dir / "bin" / "python"

        # Install the wheel (no --no-deps so transitive deps resolve)
        install = subprocess.run(
            [str(python_exe), "-m", "pip", "install", str(wheel_path)],
            capture_output=True,
            text=True,
        )
        if install.returncode != 0:
            return AssertionResult(
                tier="T2",
                name=f"T2:wheel_importable_{name}",
                passed=False,
                detail=f"pip install failed:\n{install.stderr[:2000]}",
            )

        # Try import
        result = subprocess.run(
            [str(python_exe), "-c", import_stmt],
            capture_output=True,
            text=True,
        )
        passed = result.returncode == 0
        return AssertionResult(
            tier="T2",
            name=f"T2:wheel_importable_{name}",
            passed=passed,
            detail=(
                f"{import_stmt!r} succeeded"
                if passed
                else f"{import_stmt!r} failed:\n{result.stderr[:1000]}"
            ),
        )


def check_exe_present(dist_dir: Path) -> AssertionResult:
    """Check for the intelligence server executable (optional — skip if absent)."""
    matches = list(dist_dir.glob("phoenix-intelligence*.exe"))
    if not matches:
        # Non-fatal: exe is built separately and may not be present on every OS
        return AssertionResult(
            tier="T1",
            name="T1:exe_present",
            passed=True,
            detail="No phoenix-intelligence*.exe found — skipped (non-fatal on non-Windows builds)",
            data={"warned": True},
        )
    return AssertionResult(
        tier="T1",
        name="T1:exe_present",
        passed=True,
        detail=str(matches[-1]),
    )


# ---------------------------------------------------------------------------
# Suite runner
# ---------------------------------------------------------------------------

def run_packaging_checks(dist_dir: Path, repo_root: Path) -> List[AssertionResult]:
    """Run all packaging checks and return the result list."""
    results: List[AssertionResult] = []

    results.append(check_wheel_present(dist_dir, "phoenix_shared-*.whl", "shared"))
    results.append(check_wheel_present(dist_dir, "phoenix_core-*.whl", "core"))

    results.append(check_version_match(dist_dir, repo_root / "shared", "phoenix_shared"))
    results.append(check_version_match(dist_dir, repo_root / "phoenix-core", "phoenix_core"))

    results.append(check_wheel_importable(
        dist_dir,
        "phoenix_shared-*.whl",
        "import phoenix_shared",
        "shared",
    ))
    results.append(check_wheel_importable(
        dist_dir,
        "phoenix_core-*.whl",
        "import phoenix.cli.main",
        "core",
    ))

    results.append(check_exe_present(dist_dir))

    return results


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(description="Packaging artifact checks")
    parser.add_argument(
        "--dist-dir",
        default=str(_REPO / "dist"),
        help="Directory containing built artifacts (default: dist/)",
    )
    args = parser.parse_args(argv)

    dist_dir = Path(args.dist_dir)
    print(f"Checking artifacts in: {dist_dir}")

    results = run_packaging_checks(dist_dir, _REPO)

    passed = [r for r in results if r.passed]
    failed = [r for r in results if not r.passed]
    warned = [r for r in results if r.data.get("warned")]

    print(f"\n  {len(passed)}/{len(results)} checks passed, {len(failed)} failed\n")
    for r in results:
        icon = "✓" if r.passed else "✗"
        suffix = " [WARN]" if r.data.get("warned") else ""
        print(f"  {icon} [{r.tier}] {r.name}{suffix}")
        if not r.passed or r.data.get("warned"):
            print(f"      {r.detail}")

    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
