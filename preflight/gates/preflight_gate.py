#!/usr/bin/env python3
"""Pre-pack gate — validate Phoenix from source before cutting a release.

Run this gate on every PR and before `python build.py` to confirm the full
pipeline works end-to-end from the checked-out source tree.

Usage::

    python -m preflight.gates.preflight_gate
    python preflight/gates/preflight_gate.py
    # From VS Code: Tasks > Preflight: Run Source Gate
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

# Allow running directly from repo root or preflight/
_HERE = Path(__file__).parent.parent          # preflight/
_REPO = _HERE.parent                          # repo root

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("preflight.gates.preflight_gate")


def _load_config() -> dict:
    import yaml
    cfg_path = _HERE / "config.yaml"
    if not cfg_path.exists():
        raise FileNotFoundError(f"config.yaml not found at {cfg_path}")
    return yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}


def _build_pipeline(config: dict):
    """Instantiate all pipeline components for the source-mode gate."""
    from preflight.adapters.source_adapter import SourceAdapter
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

    adapter = SourceAdapter(config=config, repo_root=_REPO)
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
    """Entry point for the pre-pack gate.

    Returns
    -------
    0   → GO
    1   → NO-GO or GO-WITH-WARNINGS
    2   → Configuration / startup error
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Phoenix Pre-Pack Gate (source mode)",
    )
    parser.add_argument(
        "--config",
        default=str(_HERE / "config.yaml"),
        help="Path to config.yaml (default: preflight/config.yaml)",
    )
    parser.add_argument(
        "--skip-setup",
        action="store_true",
        help="Skip venv creation (assumes _venvs/source/ already exists)",
    )
    args = parser.parse_args(argv)

    try:
        import yaml
        cfg_path = Path(args.config)
        config = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        logger.error("Failed to load config: %s", exc)
        return 2

    if args.skip_setup:
        config["_skip_setup"] = True

    logger.info("=== Phoenix Pre-Pack Gate (source mode) ===")
    logger.info("Repo root : %s", _REPO)
    logger.info("Config    : %s", args.config)

    try:
        orchestrator = _build_pipeline(config)
    except Exception as exc:
        logger.error("Failed to build pipeline: %s", exc)
        return 2

    return orchestrator.run()


if __name__ == "__main__":
    sys.exit(main())
