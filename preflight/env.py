"""EnvironmentManager — provision the sandbox and collect run metadata."""
from __future__ import annotations

import datetime
import shutil
import subprocess
from pathlib import Path

from preflight.adapters.base import TargetAdapter


class EnvironmentManager:
    def __init__(self, config: dict, adapter: TargetAdapter, repo_root: Path) -> None:
        self._config = config
        self._adapter = adapter
        self._repo_root = repo_root
        self._preflight_dir = repo_root / "preflight"
        self._sandbox = self._preflight_dir / "_sandbox"

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def prepare(self) -> dict:
        """Call adapter.setup(); return run_metadata dict."""
        # Recreate a fresh sandbox
        if self._sandbox.exists():
            shutil.rmtree(self._sandbox)
        self._sandbox.mkdir(parents=True, exist_ok=True)

        # Set up the adapter (creates venv, installs packages)
        self._adapter.setup()

        git_branch = self._git("rev-parse", "--abbrev-ref", "HEAD")
        git_commit = self._git("rev-parse", "--short=7", "HEAD")

        return {
            "git_branch": git_branch,
            "git_commit": git_commit,
            "model_id": self._config.get("model_id", "unknown"),
            "temperature": self._config.get("temperature", 0.0),
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "sandbox_path": str(self._sandbox),
        }

    def sandbox_path(self) -> Path:
        """Return preflight/_sandbox/ — recreated fresh on every run."""
        return self._sandbox

    def teardown(self) -> None:
        """Tear down the adapter.  Sandbox is preserved for post-mortem inspection."""
        self._adapter.teardown()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _git(self, *args: str) -> str:
        """Run a git command and return stripped stdout, or '' on error."""
        try:
            result = subprocess.run(
                ["git"] + list(args),
                cwd=str(self._repo_root),
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.stdout.strip()
        except Exception:
            return ""
