"""SourceAdapter — runs phoenix from the checked-out source tree."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import List

from preflight.adapters.base import CliResult, TargetAdapter


def _venv_python(venv_dir: Path) -> Path:
    """Return the Python executable path inside a venv (cross-platform)."""
    if sys.platform == "win32":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


class SourceAdapter(TargetAdapter):
    """Install from source into an isolated venv; launch uvicorn from source."""

    def __init__(self, config: dict, repo_root: Path) -> None:
        self._config = config
        self._repo_root = repo_root
        self._port: int = int(config.get("intelligence_server_port", 8001))
        # preflight/ lives one level below repo_root
        self._preflight_dir: Path = repo_root / "preflight"

        # Allow config to point to an existing venv (avoids heavy reinstalls)
        _venv_path_override: str = config.get("venv_path", "").strip()
        if _venv_path_override:
            self._venv_dir = (repo_root / _venv_path_override).resolve()
            self._external_venv = True  # don't create/destroy it
        else:
            self._venv_dir = self._preflight_dir / "_venvs" / "source"
            self._external_venv = False

        self._python: Path = _venv_python(self._venv_dir)
        self._proc: subprocess.Popen | None = None

    # ------------------------------------------------------------------
    # TargetAdapter implementation
    # ------------------------------------------------------------------

    def setup(self) -> None:
        """Prepare the Python environment for the gate run.

        Modes
        -----
        external venv (``venv_path`` set in config):
            Reuse an existing venv as-is.  Re-run editable installs so the
            latest source is always linked, but skip venv creation and browser
            install (they're already present).  Useful on machines where fresh
            large-wheel installs fail (e.g. MemoryError on Windows + Py 3.13).

        isolated venv (default):
            Create a fresh venv, install all packages from source, and install
            Playwright chromium.  Fully isolated but slower.

        ``--skip-setup`` flag:
            Skip *all* installation steps and reuse the venv exactly as found.
        """
        if self._config.get("_skip_setup") and self._python.exists():
            return  # fast-path: reuse venv unchanged

        pip = self._python.parent / ("pip.exe" if sys.platform == "win32" else "pip")

        if self._external_venv:
            # External venv: just re-link editable packages so we test the
            # checked-out source, not whatever was installed previously.
            if not self._python.exists():
                raise RuntimeError(
                    f"venv_path points to {self._venv_dir!s} but Python "
                    "executable not found there — check config.yaml venv_path."
                )
            for pkg_key in ("shared_pkg", "core_pkg", "intelligence_src"):
                pkg_path = self._repo_root / self._config["paths"][pkg_key]
                subprocess.run(
                    [
                        str(pip), "install",
                        "--no-build-isolation",  # reuse venv setuptools, avoids Windows AV crash
                        "--no-compile",
                        "-e", str(pkg_path),
                    ],
                    check=True,
                )
            return

        # ------------------------------------------------------------------
        # Isolated venv mode
        # ------------------------------------------------------------------
        # Remove stale venv if present
        if self._venv_dir.exists():
            shutil.rmtree(self._venv_dir)

        self._venv_dir.mkdir(parents=True, exist_ok=True)

        # Create venv — do NOT upgrade pip to avoid pip 26 MemoryError on win
        subprocess.run(
            [sys.executable, "-m", "venv", str(self._venv_dir)],
            check=True,
        )

        # Install editable packages: shared → core → intelligence
        for pkg_key in ("shared_pkg", "core_pkg", "intelligence_src"):
            pkg_path = self._repo_root / self._config["paths"][pkg_key]
            subprocess.run(
                [str(pip), "install", "--no-compile", "-e", str(pkg_path)],
                check=True,
            )

        # Extra runtime / test dependencies — installed one-at-a-time to keep
        # peak memory low (large wheels like playwright can cause MemoryError
        # on constrained machines when installed in a single batch)
        for extra in ["uvicorn[standard]", "anthropic", "playwright", "pytest-playwright", "pytest"]:
            subprocess.run(
                [str(pip), "install", "--no-compile", extra],
                check=True,
            )

        # Install Playwright browsers
        subprocess.run(
            [str(self._python), "-m", "playwright", "install", "--with-deps", "chromium"],
            check=True,
        )

    def start_server(self) -> None:
        """Launch the intelligence server via uvicorn in the source tree."""
        # Kill any stale process occupying the port so the new server binds correctly.
        # Without this, a lingering server from a prior gate run answers health checks
        # while serving OLD code — the new server silently fails to start.
        self._kill_port(self._port)

        server_cwd = self._repo_root / self._config["paths"]["intelligence_src"]
        cmd = [
            str(self._python),
            "-m", "uvicorn",
            "api.server:app",
            "--host", "0.0.0.0",
            "--port", str(self._port),
            "--no-access-log",
        ]
        # Disable MCP browser automation in the gate — npx @playwright/mcp hangs
        # on fresh starts (npm network fetch) and would block the automate endpoint.
        # Strip the API key so the intelligence server uses the fast heuristic fallback
        # path (_build_fallback_script_from_manual_test) instead of making a live LLM
        # call that exceeds the 300s client timeout.
        server_env = {**os.environ, "PHOENIX_MCP_ENABLED": "false"}
        server_env.pop("ANTHROPIC_API_KEY", None)
        self._proc = subprocess.Popen(
            cmd,
            cwd=str(server_cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=server_env,
        )

    def stop_server(self) -> None:
        """Terminate the server process, waiting up to 5 s before killing."""
        if self._proc is None:
            return
        self._proc.terminate()
        try:
            self._proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self._proc.kill()
            self._proc.wait()
        self._proc = None

    def _kill_port(self, port: int) -> None:
        """Kill any process listening on *port* so a new server can bind to it."""
        try:
            if sys.platform == "win32":
                # netstat -ano gives PID; taskkill kills it
                result = subprocess.run(
                    ["netstat", "-ano"],
                    capture_output=True, text=True, timeout=10,
                )
                for line in result.stdout.splitlines():
                    if f":{port}" in line and "LISTENING" in line:
                        parts = line.split()
                        pid = int(parts[-1])
                        subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                                       capture_output=True, timeout=5)
            else:
                subprocess.run(["fuser", "-k", f"{port}/tcp"],
                               capture_output=True, timeout=5)
        except Exception:
            pass  # best-effort; if it fails the server start will handle it

    def health_url(self) -> str:
        return f"http://localhost:{self._port}/health"

    def api_base_url(self) -> str:
        return f"http://localhost:{self._port}/api/v1"

    def run_cli(self, args: List[str], cwd: str) -> CliResult:
        """Run phoenix CLI via the venv's python -m phoenix.cli.main."""
        cmd = [str(self._python), "-m", "phoenix.cli.main"] + args
        t0 = time.perf_counter()
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
        )
        duration = time.perf_counter() - t0
        return CliResult(
            exit_code=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            duration_s=duration,
        )

    def teardown(self) -> None:
        """Stop server; remove the venv only if we created it ourselves."""
        self.stop_server()
        if not self._external_venv and self._venv_dir.exists():
            shutil.rmtree(self._venv_dir, ignore_errors=True)

    # ------------------------------------------------------------------
    # Helpers accessible from stages
    # ------------------------------------------------------------------

    @property
    def python_exe(self) -> str:
        return str(self._python)
