"""Runtime orchestration for the optional SmartLocatorAI pre-pass.

SmartLocatorAI owns DOM discovery and candidate validation.  This module keeps
that external schema out of the CLI and returns Phoenix ``LocatorBundle``
objects through the existing adapter.
"""

from __future__ import annotations

import logging
import json
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, List

from phoenix.locators.smartlocator_adaptor import convert_file

logger = logging.getLogger(__name__)


class SmartLocatorUnavailableError(RuntimeError):
    """Raised when the optional SmartLocatorAI package is not installed."""


def _normalized_name(value: object) -> str:
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", str(value or ""))
    return " ".join(re.findall(r"[a-z0-9]+", text.casefold()))


def _name_variants(value: object) -> set[str]:
    normalized = _normalized_name(value)
    if not normalized:
        return set()
    variants = {normalized}
    words = normalized.split()
    if words[-1] in {"input", "field", "element", "control"}:
        variants.add(" ".join(words[:-1]))
    return {item for item in variants if item}


def _contains_name(text: str, name: object) -> bool:
    padded = f" {_normalized_name(text)} "
    return any(f" {variant} " in padded for variant in _name_variants(name))


def _bundle_names(bundle: object) -> set[str]:
    metadata = bundle.metadata or {}
    values = [bundle.element_name]
    for key in ("source_names", "custom_name", "bundle_element_name", "element_name"):
        value = metadata.get(key)
        values.extend(value if isinstance(value, list) else [value])
    for source in [bundle.primary, *bundle.alternates]:
        values.append(source.element_name)
        source_metadata = source.metadata or {}
        values.extend(source_metadata.get(key) for key in ("custom_name", "element_name"))
        for details in (metadata.get("element_data"), source_metadata.get("element_data")):
            if isinstance(details, dict):
                values.extend(details.get(key) for key in (
                    "aria-label", "accessible_name", "placeholder", "name", "id", "text"
                ))
    return {
        variant
        for value in values
        for variant in _name_variants(value)
    }


def _locator_is_usable(locator: object, bundle_metadata: dict) -> bool:
    if locator.verified_in_snapshot is not True or not str(locator.value or "").strip():
        return False
    if bundle_metadata.get("broken") is True or bundle_metadata.get("unresolved") is True:
        return False
    metadata = locator.metadata or {}
    if metadata.get("broken") is True or metadata.get("unresolved") is True:
        return False
    status = str(metadata.get("status", bundle_metadata.get("status", ""))).casefold()
    if status in {"broken", "unresolved", "invalid"}:
        return False
    try:
        from phoenix.locators.smartlocator_fallback import has_positional_selector

        if has_positional_selector(str(locator.value)):
            return False
        import ast

        ast.parse(locator.to_playwright(), mode="eval")
    except (SyntaxError, ValueError, TypeError):
        return False
    return True


def validated_locator_bundles(
    locators_dir: str | Path,
    page: str,
    manual_tests: list[dict] | None = None,
) -> List[object]:
    """Discover project-local validated bundles relevant to the automation request."""
    from phoenix.locators.registry import LocatorRegistry

    locators_path = Path(locators_dir).resolve()
    if not locators_path.is_dir():
        return []

    context_text = " ".join(
        str(value)
        for test in (manual_tests or [])
        for value in (
            test.get("name", ""),
            test.get("description", ""),
            test.get("preconditions", ""),
            *[
                step.get("action", "")
                for step in test.get("steps", [])
                if isinstance(step, dict)
            ],
        )
    )
    exact_path = (locators_path / f"{page}.json").resolve()
    paths = [
        candidate.resolve()
        for candidate in locators_path.glob("*.json")
        if candidate.is_file()
        and candidate.resolve().parent == locators_path
    ]
    paths.sort(key=lambda candidate: (candidate != exact_path, candidate.name.casefold()))
    if not context_text and exact_path not in paths and len(paths) == 1:
        relevant_paths = paths
    else:
        relevant_paths = []
        for candidate in paths:
            exact_match = candidate == exact_path
            page_match = _contains_name(context_text, candidate.stem)
            registry = LocatorRegistry.load_page(candidate)
            bundles = list(registry)
            matching_bundles = [
                bundle for bundle in bundles
                if _normalized_name(bundle.page) == _normalized_name(page)
                or any(
                    f" {name} " in f" {_normalized_name(context_text)} "
                    for name in _bundle_names(bundle)
                )
            ]
            if exact_match or page_match or matching_bundles:
                relevant_paths.append((candidate, bundles if exact_match or page_match else matching_bundles))
        paths = []

    if paths:
        relevant_paths = [(candidate, list(LocatorRegistry.load_page(candidate))) for candidate in paths]

    result = []
    for path, bundles in relevant_paths:
        for bundle in bundles:
            metadata = dict(bundle.metadata or {})
            usable = [
                locator
                for locator in [bundle.primary, *bundle.alternates]
                if _locator_is_usable(locator, metadata)
            ]
            if not usable:
                continue
            primary_source = (
                "stored_primary"
                if _locator_is_usable(bundle.primary, metadata)
                else "stored_alternate"
            )
            primary_metadata = dict(usable[0].metadata or {})
            primary_metadata["locator_source"] = primary_source
            primary = usable[0].model_copy(update={"fallback": False, "metadata": primary_metadata})
            alternates = []
            for locator in usable[1:]:
                alternate_metadata = dict(locator.metadata or {})
                alternate_metadata["locator_source"] = "stored_alternate"
                alternates.append(locator.model_copy(update={"fallback": True, "metadata": alternate_metadata}))
            metadata["locator_source"] = primary_source
            result.append(bundle.model_copy(update={
                "primary": primary,
                "alternates": alternates,
                "metadata": metadata,
            }))
    # Scenario output can repeat a stored page bundle. Keep its page identity,
    # but do not send identical evidence twice to matching or to the prompt.
    deduplicated = []
    seen_evidence = set()
    for bundle in result:
        key = (bundle.page, bundle.element_name, bundle.primary.strategy.value,
               bundle.primary.value, json.dumps(bundle.metadata or {}, sort_keys=True, default=str))
        if key not in seen_evidence:
            seen_evidence.add(key)
            deduplicated.append(bundle)
    result = deduplicated
    logger.info("Discovered %d validated stored locator bundle(s) for automation", len(result))
    return result


def locator_bundle_evidence(bundles: list[object]) -> List[Dict[str, Any]]:
    """Serialize selector evidence with explicit source provenance."""
    from phoenix.locators.persist import locator_bundle_to_dict

    evidence = []
    for bundle in bundles:
        item = locator_bundle_to_dict(bundle)
        primary = item.get("primary") or {}
        source = (item.get("metadata") or {}).get("locator_source", "stored_primary")
        primary.setdefault("metadata", {})
        primary["metadata"]["locator_source"] = source
        for alternate in item.get("alternates", []):
            alternate.setdefault("metadata", {})
            alternate["metadata"]["locator_source"] = (
                "stored_alternate" if source == "stored_primary" else source
            )
        item.setdefault("metadata", {})
        item["metadata"]["locator_source"] = source
        evidence.append(item)
    return evidence


def generate_smartlocator_bundles(
    application_url: str,
    *,
    page: str = "global",
    validate: bool = True,
    output_dir: str | Path | None = None,
    element_names: list[str] | None = None,
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
        if element_names:
            from phoenix_smartlocatorai.core import _validate_locators_with_playwright
            from phoenix_smartlocatorai.dom_scanner import (
                _guess_custom_name,
                generate_locators_from_elements,
                scan_dom,
            )
            from phoenix.locators.reconciliation import bundle_matches_element

            elements = scan_dom(application_url, js_render=True)
            targets = [
                element
                for element in elements
                if any(
                    bundle_matches_element(
                        name,
                        {
                            "element_name": _guess_custom_name(element),
                            "metadata": {"element_data": element},
                        },
                    )
                    for name in element_names
                )
            ]
            raw_locators = generate_locators_from_elements(targets)
            if validate:
                raw_locators = _validate_locators_with_playwright(
                    application_url, raw_locators, {}
                )
            json_path = Path(target_dir) / "locators.json"
            json_path.write_text(
                json.dumps({"locators": raw_locators}, ensure_ascii=False),
                encoding="utf-8",
            )
        else:
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


def reconcile_automation_tests_with_bundles(
    automation_tests: list[dict],
    bundles: list[dict] | list[object],
) -> tuple[list[str], list[dict]]:
    """Enforce validated selectors in returned code before output is written."""
    from phoenix.locators.reconciliation import reconcile_generated_code

    evidence = (
        bundles
        if not bundles or isinstance(bundles[0], dict)
        else locator_bundle_evidence(bundles)
    )
    unresolved: list[str] = []
    used: list[dict] = []
    for test in automation_tests:
        test_used: list[dict] = []
        code_targets = []
        if isinstance(test.get("script_code"), str) and test["script_code"].strip():
            code_targets.append((test, "script_code"))
        for bundle_key in ("pom_bundle", "bdd_bundle"):
            generated_bundle = test.get(bundle_key)
            if not isinstance(generated_bundle, dict):
                continue
            code_targets.extend(
                (node, "code")
                for section in ("page_objects", "steps", "tests")
                for node in generated_bundle.get(section, [])
                if isinstance(node, dict) and isinstance(node.get("code"), str)
            )
        for target, key in code_targets:
            try:
                final_code, selected, missing = reconcile_generated_code(target[key], evidence)
            except (SyntaxError, ValueError, TypeError) as exc:
                raise ValueError("generated source could not be reconciled safely") from exc
            target[key] = final_code
            test_used.extend(selected)
            unresolved.extend(missing)

        seen: set[tuple[str, str, str]] = set()
        selected_for_test = []
        for bundle in test_used:
            selector = str((bundle.get("primary") or {}).get("value", ""))
            key = (str(bundle.get("page", "")), str(bundle.get("element_name", "")), selector)
            if key not in seen:
                seen.add(key)
                selected_for_test.append(bundle)
                used.append(bundle)
        if selected_for_test:
            existing = test.get("locators")
            existing = existing if isinstance(existing, list) else []
            combined = selected_for_test + existing
            deduplicated = []
            seen_locators: set[tuple[str, str, str]] = set()
            for bundle in combined:
                if not isinstance(bundle, dict):
                    continue
                selector = (bundle.get("primary") or {}).get("value")
                identity = str(bundle.get("element_name") or bundle.get("element_id") or "")
                key = (str(bundle.get("page", "")), identity, str(selector or ""))
                if key not in seen_locators:
                    seen_locators.add(key)
                    deduplicated.append(bundle)
            test["locators"] = deduplicated
            test["locator_provenance"] = [
                {
                    "page": bundle.get("page"),
                    "matched_pages": (bundle.get("metadata") or {}).get("matched_pages", [bundle.get("page")]),
                    "element_name": bundle.get("element_name"),
                    "selector": (bundle.get("primary") or {}).get("value"),
                    "source": (bundle.get("metadata") or {}).get("locator_source", "unresolved"),
                }
                for bundle in selected_for_test
            ]
    return list(dict.fromkeys(unresolved)), used


def fresh_bundles_for_elements(bundles: list[object], labels: list[str]) -> list[object]:
    """Keep fresh-scan candidates relevant to unresolved generated labels only."""
    from phoenix.locators.persist import locator_bundle_to_dict
    from phoenix.locators.reconciliation import bundle_matches_element

    selected = []
    for bundle in bundles:
        evidence = locator_bundle_to_dict(bundle)
        if not any(bundle_matches_element(label, evidence) for label in labels):
            continue
        metadata = dict(bundle.metadata or {})
        metadata["locator_source"] = "fresh_smartlocator_scan"
        selected.append(bundle.model_copy(update={"metadata": metadata}))
    return selected


def locator_expert_targets(
    labels: list[str],
    fresh_bundles: list[object],
    *,
    page: str,
) -> list[object]:
    """Build only unresolved per-element candidates for LocatorExpert."""
    from phoenix.locators.persist import locator_bundle_to_dict
    from phoenix.locators.reconciliation import bundle_matches_element, match_locator_bundle
    from phoenix_shared.models.locator import Locator, LocatorBundle, LocatorStrategy

    targets = []
    used_identities: set[str] = set()
    for label in labels:
        matching = [
            bundle for bundle in fresh_bundles
            if bundle_matches_element(label, locator_bundle_to_dict(bundle))
        ]
        if len(matching) == 1 and match_locator_bundle(
            label, [locator_bundle_to_dict(matching[0])]
        ) is None:
            bundle = matching[0]
        elif not matching:
            bundle = LocatorBundle(
                element_name=label,
                page=page,
                primary=Locator(
                    element_name=label,
                    strategy=LocatorStrategy.CSS,
                    value="__unresolved__",
                    verified_in_snapshot=False,
                ),
                metadata={"unresolved": True, "smartlocator_raw_records": []},
            )
        else:
            continue
        identity = str((bundle.metadata or {}).get("element_identity") or f"name:{bundle.element_name}")
        if identity not in used_identities:
            used_identities.add(identity)
            targets.append(bundle)
    return targets


def resolve_automation_locator_evidence(
    automation_tests: list[dict],
    stored_bundles: list[object],
    *,
    application_url: str,
    page: str,
    scan,
    discover,
    validate,
) -> dict[str, Any]:
    """Apply stored, fresh-scan, then LocatorExpert precedence per element."""
    from phoenix.locators.smartlocator_fallback import resolve_with_locator_expert

    stored_evidence = locator_bundle_evidence(stored_bundles)
    unresolved, used = reconcile_automation_tests_with_bundles(
        automation_tests, stored_evidence
    )
    fresh_bundles: list[object] = []
    scanned_count = 0
    if unresolved and scan is not None:
        try:
            scanned = scan(
                application_url,
                page=page,
                validate=True,
                element_names=unresolved,
            )
        except Exception as exc:
            logger.warning(
                "SmartLocator scan unavailable for unresolved elements (%s)",
                type(exc).__name__,
            )
            scanned = []
        scanned_count = len(scanned)
        fresh_bundles = fresh_bundles_for_elements(scanned, unresolved)
        fresh_evidence = locator_bundle_evidence(fresh_bundles)
        unresolved, used = reconcile_automation_tests_with_bundles(
            automation_tests, stored_evidence + fresh_evidence
        )
    else:
        fresh_evidence = []

    expert_evidence: list[dict[str, Any]] = []
    fallback_result = {
        "llm_calls": 0,
        "unresolved_elements": [],
    }
    if unresolved:
        targets = locator_expert_targets(unresolved, fresh_bundles, page=page)
        if targets:
            fallback_result = resolve_with_locator_expert(
                targets,
                page_url=application_url,
                discover=discover,
                validate=validate,
            )
            for bundle in fallback_result.get("resolved_bundles", []):
                metadata = dict(bundle.metadata or {})
                if metadata.get("locator_expert_fallback", {}).get("resolved"):
                    metadata["locator_source"] = "locator_expert"
                    primary_metadata = dict(bundle.primary.metadata or {})
                    primary_metadata["locator_source"] = "locator_expert"
                    bundle = bundle.model_copy(update={
                        "metadata": metadata,
                        "primary": bundle.primary.model_copy(update={"metadata": primary_metadata}),
                    })
                expert_evidence.extend(locator_bundle_evidence([bundle]))
            all_evidence = stored_evidence + fresh_evidence + expert_evidence
            unresolved, used = reconcile_automation_tests_with_bundles(
                automation_tests, all_evidence
            )
    return {
        "unresolved": unresolved,
        "used_bundles": used,
        "stored_count": len(stored_bundles),
        "scanned_count": scanned_count,
        "fresh_count": len(fresh_bundles),
        "locator_expert_calls": fallback_result.get("llm_calls", 0),
        "locator_expert_unresolved": fallback_result.get("unresolved_elements", []),
    }


def live_locator_validator(application_url: str):
    """Create a LocatorExpert validator requiring one match and identity fit."""
    import re

    from phoenix.locators.smartlocator_fallback import has_positional_selector
    from phoenix_shared.models.locator import LocatorStrategy

    def validate(candidate, payload):
        if has_positional_selector(candidate.value) or candidate.strategy == LocatorStrategy.CONTEXT:
            return {"match_count": 0, "identity_matches": False}
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.goto(payload.get("page_url") or application_url, wait_until="domcontentloaded")
                value = candidate.value
                strategy = candidate.strategy
                if strategy == LocatorStrategy.ROLE:
                    match = re.match(r"^(\w[\w-]*)(?:\[name=(.+)\])?$", value)
                    if match and match.group(2):
                        locator = page.get_by_role(match.group(1), name=match.group(2).strip("\"'"))
                    else:
                        locator = page.get_by_role(value)
                elif strategy == LocatorStrategy.LABEL:
                    locator = page.get_by_label(value)
                elif strategy == LocatorStrategy.PLACEHOLDER:
                    locator = page.get_by_placeholder(value)
                elif strategy == LocatorStrategy.TEST_ID:
                    locator = page.get_by_test_id(value)
                elif strategy == LocatorStrategy.TEXT:
                    locator = page.get_by_text(value)
                elif strategy == LocatorStrategy.XPATH:
                    locator = page.locator(value if value.startswith("xpath=") else f"xpath={value}")
                elif strategy == LocatorStrategy.ALT_TEXT:
                    locator = page.get_by_alt_text(value)
                elif strategy == LocatorStrategy.TITLE:
                    locator = page.get_by_title(value)
                else:
                    locator = page.locator(value)
                count = locator.count()
                if count != 1:
                    return {"match_count": count, "identity_matches": False}
                actual = locator.evaluate("""element => ({
                    tag: element.tagName.toLowerCase(),
                    id: element.id || '',
                    name: element.getAttribute('name') || '',
                    placeholder: element.getAttribute('placeholder') || '',
                    aria: element.getAttribute('aria-label') || '',
                    testid: element.getAttribute('data-testid') || element.getAttribute('data-test') || '',
                    role: element.getAttribute('role') || '',
                    text: (element.innerText || element.textContent || '').trim()
                })""")
            finally:
                browser.close()

        element_data = payload.get("element_data") or {}
        expected_stable = {
            "id": element_data.get("id"),
            "name": element_data.get("name"),
            "placeholder": element_data.get("placeholder"),
            "aria": element_data.get("aria-label") or element_data.get("aria_label"),
        }
        expected_stable = {key: value for key, value in expected_stable.items() if value}
        if expected_stable:
            identity_matches = all(str(actual.get(key, "")) == str(value) for key, value in expected_stable.items())
        else:
            label = str(payload.get("element_name") or payload.get("custom_name") or "")
            label_words = set(re.findall(r"[a-z0-9]+", normalize_element_name(label)))
            label_words -= {"input", "field", "element", "control", "button", "link", "checkbox", "textbox"}
            actual_words = set(re.findall(r"[a-z0-9]+", normalize_element_name(" ".join(str(actual.get(key, "")) for key in (
                "id", "name", "placeholder", "aria", "testid", "text", "role"
            )))))
            identity_matches = bool(label_words) and label_words.issubset(actual_words)
        return {"match_count": 1, "identity_matches": identity_matches}

    return validate


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
