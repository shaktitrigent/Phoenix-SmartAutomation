#!/usr/bin/env python3
"""Post-pack gate — validate Phoenix from built artifacts before publishing.

Run this gate after `python build.py` (or CI build step) to confirm the
packaged wheels and exe work identically to the source.  This is the gate
that must pass before tagging a release.

Usage::

    python -m preflight.gates.acceptance_gate
    python preflight/gates/acceptance_gate.py
    # From VS Code: Tasks > Preflight: Run Acceptance Gate
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

_HERE = Path(__file__).parent.parent          # preflight/
_REPO = _HERE.parent                          # repo root

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("preflight.gates.acceptance_gate")


def _load_config(cfg_path: Path) -> dict:
    import yaml
    if not cfg_path.exists():
        raise FileNotFoundError(f"config.yaml not found at {cfg_path}")
    return yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}


def _check_artifacts(dist_dir: Path) -> list[str]:
    """Return a list of missing-artifact error messages (empty = all present)."""
    import glob as _glob
    errors = []
    for pattern in ("phoenix_shared-*.whl", "phoenix_core-*.whl"):
        matches = list(dist_dir.glob(pattern))
        if not matches:
            errors.append(f"Missing artifact in {dist_dir}: {pattern}")
    return errors


def _build_pipeline(config: dict, dist_dir: Path):
    """Instantiate all pipeline components for the package-mode gate."""
    from preflight.adapters.package_adapter import PackageAdapter
    from preflight.env import EnvironmentManager
    from preflight.gate import Gate
    from preflight.orchestrator import Orchestrator
    from preflight.report import Reporter
    from preflight.stages.automate import AutomateStage
    from preflight.stages.boot import BootStage
    from preflight.stages.doctor import DoctorStage
    from preflight.stages.fix import FixStage
    from preflight.stages.generate import GenerateStage
    from preflight.stages.init import InitStage
    from preflight.stages.run import RunStage

    adapter = PackageAdapter(config=config, repo_root=_REPO, wheel_dir=dist_dir)
    env_manager = EnvironmentManager(config=config, adapter=adapter, repo_root=_REPO)
    gate = Gate()
    reporter = Reporter(output_dir=_HERE / "reports")

    stages = [
        BootStage(),
        DoctorStage(),
        InitStage(),
        GenerateStage(),
        AutomateStage(),
        RunStage(),
        FixStage(),
    ]

    return Orchestrator(
        adapter=adapter,
        stages=stages,
        gate=gate,
        reporter=reporter,
        env_manager=env_manager,
    )


def main(argv: list[str] | None = None) -> int:
    """Entry point for the post-pack acceptance gate.

    Returns
    -------
    0   → GO
    1   → NO-GO or GO-WITH-WARNINGS
    2   → Configuration / startup error (missing artifacts, bad config)
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Phoenix Post-Pack Acceptance Gate (package mode)",
    )
    parser.add_argument(
        "--config",
        default=str(_HERE / "config.yaml"),
        help="Path to config.yaml (default: preflight/config.yaml)",
    )
    parser.add_argument(
        "--dist-dir",
        default=str(_REPO / "dist"),
        help="Directory containing built wheels and exe (default: dist/)",
    )
    parser.add_argument(
        "--skip-artifact-check",
        action="store_true",
        help="Skip the upfront artifact presence check",
    )
    args = parser.parse_args(argv)

    try:
        config = _load_config(Path(args.config))
    except Exception as exc:
        logger.error("Failed to load config: %s", exc)
        return 2

    dist_dir = Path(args.dist_dir)

    logger.info("=== Phoenix Post-Pack Acceptance Gate (package mode) ===")
    logger.info("Repo root : %s", _REPO)
    logger.info("Dist dir  : %s", dist_dir)

    # ------------------------------------------------------------------
    # Upfront artifact check — fail fast before creating any venv
    # ------------------------------------------------------------------
    if not args.skip_artifact_check:
        errors = _check_artifacts(dist_dir)
        if errors:
            for err in errors:
                logger.error(err)
            logger.error(
                "Run `python build.py` (or the CI build step) first, "
                "then re-run the acceptance gate."
            )
            return 2

    try:
        orchestrator = _build_pipeline(config, dist_dir)
    except Exception as exc:
        logger.error("Failed to build pipeline: %s", exc)
        return 2

    return orchestrator.run()


if __name__ == "__main__":
    sys.exit(main())
