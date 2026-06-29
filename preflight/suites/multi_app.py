"""MultiAppSuite — run the core pipeline (boot→generate→automate→run) against
multiple AUT targets and aggregate results.

Each target is a dict::

    {
        "name": "saucedemo",          # short identifier used in report labels
        "aut_url": "https://...",     # base URL the phoenix CLI receives
        "story_file": "fixtures/saucedemo_story.md"
    }

The suite does NOT start a server for each target — the intelligence server is
assumed to be already running (started by the gate that owns this suite).

Usage::

    python -m preflight.suites.multi_app --targets preflight/fixtures/targets.yaml
"""
from __future__ import annotations

import logging
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List

from preflight.assertions.result import AssertionResult

logger = logging.getLogger(__name__)

_HERE = Path(__file__).parent.parent   # preflight/


# ---------------------------------------------------------------------------
# Single-target pipeline
# ---------------------------------------------------------------------------

def _run_target(
    target: Dict[str, Any],
    adapter,
    spec: dict,
    base_sandbox: Path,
    python_exe: str,
    config: dict,
    run_metadata: dict,
) -> List[AssertionResult]:
    """Run boot→init→generate→automate→run for one target and return results."""
    from preflight.stages.automate import AutomateStage
    from preflight.stages.generate import GenerateStage
    from preflight.stages.init import InitStage
    from preflight.stages.run import RunStage

    target_name = target.get("name", "unnamed")
    aut_url = target["aut_url"]
    story_file = Path(target["story_file"])

    # Each target gets its own sandbox sub-directory
    sandbox = base_sandbox / target_name
    if sandbox.exists():
        shutil.rmtree(sandbox)
    sandbox.mkdir(parents=True, exist_ok=True)

    context = {
        "adapter": adapter,
        "sandbox": sandbox,
        "spec": spec,
        "python_exe": python_exe,
        "config": dict(config, aut_url=aut_url),
        "run_metadata": run_metadata,
        "aut_port": _port_from_url(aut_url),
    }

    results: List[AssertionResult] = []

    # Prefix every result name with the target name for disambiguation
    def _tagged(r: AssertionResult) -> AssertionResult:
        return AssertionResult(
            tier=r.tier,
            name=f"[{target_name}] {r.name}",
            passed=r.passed,
            detail=r.detail,
            data=r.data,
        )

    for Stage in (InitStage, GenerateStage, AutomateStage, RunStage):
        stage = Stage()
        # Override story_file in context for GenerateStage
        if isinstance(stage, GenerateStage) and story_file.exists():
            context["_override_story_file"] = str(story_file)
        try:
            stage_results = stage.run(context)
            results.extend(_tagged(r) for r in stage_results)
            # Stop this target's pipeline on a T1 failure
            if any(not r.passed and r.tier == "T1" for r in stage_results):
                logger.warning(
                    "T1 failure in stage %s for target %s — stopping target pipeline",
                    type(stage).__name__,
                    target_name,
                )
                break
        except Exception as exc:
            import traceback
            fail = AssertionResult(
                tier="T1",
                name=f"[{target_name}] {type(stage).__name__}_exception",
                passed=False,
                detail=f"Stage raised: {exc}\n{traceback.format_exc()}",
            )
            results.append(fail)
            break

    return results


def _port_from_url(url: str) -> int:
    """Extract port from a URL string; default to 80."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.port or 80
    except Exception:
        return 80


# ---------------------------------------------------------------------------
# Suite class
# ---------------------------------------------------------------------------

class MultiAppSuite:
    """Run the core pipeline across multiple AUT targets.

    Parameters
    ----------
    targets:
        List of target dicts (see module docstring).
    adapter:
        A running TargetAdapter (server already started).
    spec:
        Loaded expected_structure.yaml dict.
    sandbox_root:
        Parent directory under which per-target sandboxes are created.
    python_exe:
        Path to the Python executable to use for CLI invocations.
    config:
        Harness config dict.
    run_metadata:
        Metadata dict from EnvironmentManager.prepare().
    """

    def __init__(
        self,
        targets: List[Dict[str, Any]],
        adapter,
        spec: dict,
        sandbox_root: Path,
        python_exe: str,
        config: dict,
        run_metadata: dict,
    ) -> None:
        self._targets = targets
        self._adapter = adapter
        self._spec = spec
        self._sandbox_root = sandbox_root
        self._python_exe = python_exe
        self._config = config
        self._run_metadata = run_metadata

    def run(self) -> Dict[str, List[AssertionResult]]:
        """Run all targets; return {target_name: results}."""
        all_target_results: Dict[str, List[AssertionResult]] = {}

        for target in self._targets:
            name = target.get("name", "unnamed")
            logger.info("MultiAppSuite: running target %r", name)
            results = _run_target(
                target=target,
                adapter=self._adapter,
                spec=self._spec,
                base_sandbox=self._sandbox_root,
                python_exe=self._python_exe,
                config=self._config,
                run_metadata=self._run_metadata,
            )
            all_target_results[name] = results
            total = len(results)
            passed = sum(1 for r in results if r.passed)
            logger.info("  Target %r: %d/%d passed", name, passed, total)

        return all_target_results

    def flat_results(self, target_results: Dict[str, List[AssertionResult]]) -> List[AssertionResult]:
        """Flatten target_results into a single list for the Gate."""
        return [r for rs in target_results.values() for r in rs]


# ---------------------------------------------------------------------------
# Target file loader
# ---------------------------------------------------------------------------

def load_targets(targets_yaml: Path) -> List[Dict[str, Any]]:
    """Load a list of targets from a YAML file."""
    import yaml
    raw = yaml.safe_load(targets_yaml.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict) and "targets" in raw:
        return raw["targets"]
    raise ValueError(f"targets YAML must be a list or have a 'targets' key: {targets_yaml}")


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

    parser = argparse.ArgumentParser(description="Multi-AUT suite runner")
    parser.add_argument(
        "--targets",
        required=True,
        help="YAML file listing targets (see module docstring)",
    )
    parser.add_argument(
        "--config",
        default=str(_HERE / "config.yaml"),
        help="Path to config.yaml",
    )
    args = parser.parse_args(argv)

    targets_path = Path(args.targets)
    if not targets_path.exists():
        print(f"Targets file not found: {targets_path}", file=sys.stderr)
        return 2

    targets = load_targets(targets_path)
    print(f"Loaded {len(targets)} target(s) from {targets_path}")
    for t in targets:
        print(f"  - {t.get('name', '?')} @ {t.get('aut_url', '?')}")

    print("\nTo run the full multi-app suite, instantiate MultiAppSuite with a live")
    print("adapter and call suite.run(). See preflight/gates/preflight_gate.py for")
    print("an example of wiring up an adapter.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
