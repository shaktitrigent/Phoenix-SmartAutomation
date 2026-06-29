"""Orchestrator — drives the full validation pipeline end-to-end."""
from __future__ import annotations

import logging
import time
import traceback
from typing import Any, Dict, List

from preflight.assertions.result import AssertionResult

logger = logging.getLogger(__name__)


class Orchestrator:
    """Coordinate stages, gate, reporter, and environment lifecycle.

    Parameters
    ----------
    adapter:
        A TargetAdapter (SourceAdapter or PackageAdapter).
    stages:
        Ordered list of stage instances, each having a ``run(context) -> List[AssertionResult]``.
    gate:
        A Gate instance with a ``verdict(results, ...) -> str`` method.
    reporter:
        A Reporter instance with a ``write(...) -> Path`` method.
    env_manager:
        An EnvironmentManager instance.
    """

    def __init__(self, adapter, stages, gate, reporter, env_manager) -> None:
        self._adapter = adapter
        self._stages = stages
        self._gate = gate
        self._reporter = reporter
        self._env_manager = env_manager

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def run(self) -> int:
        """Run all stages; collect results; write report; return exit code.

        Returns
        -------
        0   → GO
        1   → NO-GO or GO-WITH-WARNINGS
        """
        t_start = time.perf_counter()
        stage_results: Dict[str, List[AssertionResult]] = {}
        all_results: List[AssertionResult] = []
        run_metadata: dict = {}
        t3_data: dict = {}

        # ----------------------------------------------------------
        # Phase 1 — Prepare environment
        # ----------------------------------------------------------
        try:
            run_metadata = self._env_manager.prepare()
        except Exception as exc:
            logger.error("EnvironmentManager.prepare() failed: %s", exc)
            fail = AssertionResult(
                tier="T1",
                name="T1:env_prepare",
                passed=False,
                detail=f"Environment preparation raised: {exc}\n{traceback.format_exc()}",
            )
            all_results.append(fail)
            stage_results["_env_prepare"] = [fail]
            # Cannot proceed without the environment
            self._finalize(
                run_metadata, stage_results, all_results, t3_data, t_start
            )
            return 1

        # ----------------------------------------------------------
        # Phase 2 — Build context passed to every stage
        # ----------------------------------------------------------
        from pathlib import Path
        import yaml

        sandbox = self._env_manager.sandbox_path()

        # Load expected_structure.yaml
        spec: dict = {}
        spec_path = Path(__file__).parent / "expected_structure.yaml"
        if spec_path.exists():
            try:
                spec = yaml.safe_load(spec_path.read_text(encoding="utf-8")) or {}
            except Exception as exc:
                logger.warning("Could not load expected_structure.yaml: %s", exc)

        # python_exe from adapter if it exposes one, else fall back
        python_exe: str = getattr(self._adapter, "python_exe", "python")

        context: Dict[str, Any] = {
            "adapter": self._adapter,
            "sandbox": sandbox,
            "spec": spec,
            "python_exe": python_exe,
            "config": getattr(self._env_manager, "_config", {}),
            "run_metadata": run_metadata,
        }

        # ----------------------------------------------------------
        # Phase 3 — Run stages
        # ----------------------------------------------------------
        try:
            for stage in self._stages:
                stage_name = type(stage).__name__
                logger.info("Running stage: %s", stage_name)
                try:
                    results = stage.run(context)
                    stage_results[stage_name] = results
                    all_results.extend(results)

                    # Collect T3 numeric data from results
                    for r in results:
                        if r.tier == "T3" and r.data:
                            t3_data.setdefault(stage_name, []).append(r.data)

                except Exception as exc:
                    logger.exception("Stage %s raised an exception", stage_name)
                    fail = AssertionResult(
                        tier="T1",
                        name=f"T1:{stage_name}_exception",
                        passed=False,
                        detail=(
                            f"Stage {stage_name!r} raised unexpectedly: {exc}\n"
                            + traceback.format_exc()
                        ),
                    )
                    stage_results[stage_name] = [fail]
                    all_results.append(fail)
                    # Continue with remaining stages
        finally:
            # Always tear down server and environment
            try:
                self._env_manager.teardown()
            except Exception as exc:
                logger.warning("env_manager.teardown() raised: %s", exc)

            # Teardown any AUT process stored in context
            aut_proc = context.get("aut_proc")
            if aut_proc is not None:
                try:
                    aut_proc.terminate()
                    aut_proc.wait(timeout=5)
                except Exception:
                    try:
                        aut_proc.kill()
                    except Exception:
                        pass

        # ----------------------------------------------------------
        # Phase 4 — Gate + Report
        # ----------------------------------------------------------
        return self._finalize(run_metadata, stage_results, all_results, t3_data, t_start)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _finalize(
        self,
        run_metadata: dict,
        stage_results: dict,
        all_results: List[AssertionResult],
        t3_data: dict,
        t_start: float,
    ) -> int:
        config = getattr(self._env_manager, "_config", {})
        t3_first = float(config.get("t3_first_run_green_min", 0.70))
        t3_heal = float(config.get("t3_post_heal_green_min", 0.88))

        verdict = self._gate.verdict(all_results, t3_first, t3_heal)
        duration_s = time.perf_counter() - t_start

        try:
            report_path = self._reporter.write(
                run_metadata=run_metadata,
                stage_results=stage_results,
                t3_data=t3_data,
                verdict=verdict,
                duration_s=duration_s,
            )
            logger.info("Report written to: %s", report_path)
        except Exception as exc:
            logger.error("Reporter.write() failed: %s", exc)

        return 0 if verdict == "GO" else 1
