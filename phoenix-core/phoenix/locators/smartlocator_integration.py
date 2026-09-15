"""Runtime orchestration for the optional SmartLocatorAI pre-pass.

SmartLocatorAI owns DOM discovery and candidate validation.  This module keeps
that external schema out of the CLI and returns Phoenix ``LocatorBundle``
objects through the existing adapter.
"""

from __future__ import annotations

import logging
import json
import tempfile
from pathlib import Path
from typing import List

from phoenix.locators.smartlocator_adaptor import convert_file

logger = logging.getLogger(__name__)


class SmartLocatorUnavailableError(RuntimeError):
    """Raised when the optional SmartLocatorAI package is not installed."""


def generate_smartlocator_bundles(
    application_url: str,
    *,
    page: str = "global",
    validate: bool = True,
    output_dir: str | Path | None = None,
) -> List[object]:
    """Run SmartLocatorAI and translate its JSON output into Phoenix bundles.

    A temporary output directory is intentional: ``locators.json`` is an
    interchange artifact, while Phoenix's locator repository is the durable
    source of truth after adapter conversion and persistence.
    """
    try:
        from phoenix_smartlocatorai import generate_locators_from_dom
    except ImportError as exc:
        raise SmartLocatorUnavailableError(
            "SmartLocatorAI is not installed. Install Phoenix-SmartLocatorAI "
            "in the active environment (for local development: "
            "pip install -e ../Phoenix-SmartLocatorAI)."
        ) from exc

    def _generate(target_dir: str) -> List[object]:
        result = generate_locators_from_dom(
            application_url,
            frameworks=["Playwright"],
            output_dir=target_dir,
            class_name="SmartLocatorPage",
            use_js=True,
            validate=validate,
        )
        json_path = result.get("locators_json") if isinstance(result, dict) else None
        if not json_path or not Path(json_path).is_file():
            raise RuntimeError("SmartLocatorAI did not produce locators.json")
        return convert_file(json_path, page=page)

    if output_dir is not None:
        target = Path(output_dir)
        target.mkdir(parents=True, exist_ok=True)
        bundles = _generate(str(target))
    else:
        with tempfile.TemporaryDirectory(prefix="phoenix-smartlocator-") as tmpdir:
            bundles = _generate(tmpdir)

    logger.info(
        "SmartLocatorAI generated %d Phoenix locator bundle(s) for %s",
        len(bundles),
        application_url,
    )
    return bundles


def enrich_automation_tests_with_smartlocator(
    automation_tests: list[dict],
    bundles: list[object],
) -> list[dict]:
    """Merge SmartLocator bundles into every generated test's locator input."""
    if not bundles:
        return automation_tests

    from phoenix.locators.persist import enrich_locators_with_smartlocator

    for test in automation_tests:
        existing = test.get("locators")
        if not isinstance(existing, list):
            existing = []
        test["locators"] = enrich_locators_with_smartlocator(existing, bundles)
    return automation_tests


def smartlocator_prompt_context(bundles: list[object], *, max_items: int = 100) -> str:
    """Build bounded, serializable locator evidence for intelligence prompts."""
    if not bundles:
        return ""

    from phoenix.locators.persist import locator_bundle_to_dict

    payload = [locator_bundle_to_dict(bundle) for bundle in bundles[:max_items]]
    return (
        "## SmartLocatorAI validated locator evidence\n"
        "Prefer primary locators verified_in_snapshot=true. Use alternates only "
        "when the primary does not apply to the requested element. Do not invent "
        "or alter selector values.\n"
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    )
