"""LocatorRegistry — loads, saves, and queries LocatorBundle JSON files.

Layout on disk::

    locators/
    ├── login.json
    ├── dashboard.json
    └── employee_management.json

Each file is a JSON array of LocatorBundle objects (as produced by
``LocatorBundle.to_dict()``).

Example usage::

    registry = LocatorRegistry.load_all("locators/")
    bundle = registry.get("username_field")
    for loc in bundle.ordered():
        try:
            page.locator(loc.value).fill("admin")
            break
        except Exception:
            continue

    # Persist a newly discovered bundle
    registry.upsert(new_bundle)
    registry.save("locators/login.json")
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

logger = logging.getLogger(__name__)

try:
    from phoenix_shared.models.locator import LocatorBundle
except ImportError:
    from shared.phoenix_shared.models.locator import LocatorBundle  # type: ignore[no-redef]


def _normalise_raw_bundle(item: Dict[str, Any]) -> Dict[str, Any]:
    """Normalise raw LLM / legacy JSON into the LocatorBundle field names.

    The LLM prompts emit ``element_id``, ``selector``, and ``interaction_type``
    whereas the Pydantic model uses ``element_name``, ``value``, and (ignores
    interaction_type).  ``verified_in_snapshot`` is passed through directly.
    
    Also preserves SmartLocatorAI metadata fields.
    """
    item = dict(item)

    # Top-level element_id → element_name
    if "element_name" not in item and "element_id" in item:
        item["element_name"] = item.pop("element_id")

    # Get the element_name for propagation to sub-dicts
    element_name = item.get("element_name")

    if "primary" in item and item["primary"] is None:
        metadata = dict(item.get("metadata") or {})
        metadata.setdefault("unresolved_reason", "primary_missing")
        metadata["locator_source"] = "unresolved"
        item["metadata"] = metadata
        item["primary"] = {
            "element_name": element_name or "unresolved",
            "strategy": "css",
            "value": "",
            "confidence": 0.0,
            "fallback": False,
            "verified_in_snapshot": False,
            "metadata": {"unresolved_reason": "primary_missing", "locator_source": "unresolved"},
        }

    # ``primary`` locator sub-dict normalisation
    if "primary" in item and isinstance(item["primary"], dict):
        p = dict(item["primary"])
        if "element_name" not in p and "element_id" in p:
            p["element_name"] = p.pop("element_id")
        # Ensure element_name is present (required by Pydantic Locator model)
        if "element_name" not in p and element_name:
            p["element_name"] = element_name
        # LLM emits "selector" for the raw CSS/XPath/attribute string
        if "value" not in p and "selector" in p:
            p["value"] = p.pop("selector")
        if not isinstance(p.get("value"), str):
            p["value"] = ""
        # Pass through verified_in_snapshot (prompt may omit it)
        if "verified_in_snapshot" in item and "verified_in_snapshot" not in p:
            p["verified_in_snapshot"] = item["verified_in_snapshot"]
        # Preserve metadata field
        if "metadata" in item and "metadata" not in p:
            p["metadata"] = item["metadata"]
        # interaction_type is not a model field — remove to avoid validation noise
        p.pop("interaction_type", None)
        p.pop("label", None)
        item["primary"] = p

    # ``alternates`` list — same normalisation per entry
    if "alternates" in item and isinstance(item["alternates"], list):
        normed = []
        for alt in item["alternates"]:
            if isinstance(alt, dict):
                alt = dict(alt)
                if "element_name" not in alt and "element_id" in alt:
                    alt["element_name"] = alt.pop("element_id")
                # Ensure element_name is present (required by Pydantic Locator model)
                if "element_name" not in alt and element_name:
                    alt["element_name"] = element_name
                if "value" not in alt and "selector" in alt:
                    alt["value"] = alt.pop("selector")
                # Preserve metadata field
                if "metadata" in alt:
                    # Keep metadata as-is
                    pass
                alt.pop("interaction_type", None)
                alt.pop("label", None)
            normed.append(alt)
        item["alternates"] = normed

    return item


class LocatorRegistry:
    """In-memory registry of LocatorBundles, backed by per-page JSON files."""

    def __init__(self) -> None:
        self._bundles: Dict[tuple[str, str], LocatorBundle] = {}  # keyed by (page, element_name)

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    @classmethod
    def load_all(cls, locators_dir: str | Path) -> "LocatorRegistry":
        """Load all *.json files from *locators_dir* into a single registry."""
        registry = cls()
        loc_dir = Path(locators_dir)
        if not loc_dir.exists():
            return registry
        for json_file in sorted(loc_dir.glob("*.json")):
            registry._load_file(json_file)
        return registry

    @classmethod
    def load_page(cls, json_path: str | Path) -> "LocatorRegistry":
        """Load a single page JSON file."""
        registry = cls()
        registry._load_file(Path(json_path))
        return registry

    def _load_file(self, path: Path) -> None:
        try:
            raw: List[Dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(raw, list):
                raw = [raw]
            for item in raw:
                try:
                    item = _normalise_raw_bundle(item)
                    bundle = LocatorBundle.from_dict(item)
                    self._bundles[(bundle.page, bundle.element_name)] = bundle
                except Exception as e:
                    logger.warning(f"Failed to load locator bundle from {path}: {e}")
                    logger.debug(f"Failed item data: {item}")
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to read or parse locator file {path}: {e}")

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    def get(self, element_name: str, page: Optional[str] = None) -> Optional[LocatorBundle]:
        """Find a page-scoped bundle, or an unambiguous legacy name.

        Without a page, duplicate names return None rather than selecting
        a locator from an unrelated page.
        """
        if page is not None:
            return self._bundles.get((page, element_name))
        matches = [b for b in self._bundles.values() if b.element_name == element_name]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            logger.warning("Ambiguous locator name %r; specify page (candidates: %s)",
                           element_name, sorted(b.page for b in matches))
        return None

    def require(self, element_name: str, page: Optional[str] = None) -> LocatorBundle:
        """Require a bundle; ambiguous legacy names must specify a page."""
        bundle = self.get(element_name, page=page)
        if bundle is None:
            available = sorted(self._bundles.keys())
            raise KeyError(
                f"element_id={element_name!r}, page={page!r} not found or ambiguous "
                f"in locators registry. Specify page for duplicate names. "
                f"Available (page, element_id): {available}"
            )
        return bundle

    def page_bundles(self, page: str) -> List[LocatorBundle]:
        """Return all bundles belonging to a logical page."""
        return [b for b in self._bundles.values() if b.page == page]

    def __iter__(self) -> Iterator[LocatorBundle]:
        return iter(self._bundles.values())

    def __len__(self) -> int:
        return len(self._bundles)

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def upsert(self, bundle: LocatorBundle) -> None:
        """Add or replace a bundle by (page, element_name)."""
        self._bundles[(bundle.page, bundle.element_name)] = bundle

    def remove(self, element_name: str, page: Optional[str] = None) -> bool:
        """Remove one scoped bundle; ambiguous names leave all pages intact."""
        bundle = self.get(element_name, page=page)
        if bundle is None:
            return False
        return self._bundles.pop((bundle.page, bundle.element_name), None) is not None

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, json_path: str | Path, page: Optional[str] = None) -> None:
        """Write bundles to a JSON file.

        Args:
            json_path: Destination file.
            page:      If given, only write bundles whose .page == page.
                       If None, write all bundles.
        """
        bundles = [b for b in self._bundles.values() if page is None or b.page == page]
        data = [b.to_dict() for b in bundles]
        path = Path(json_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def save_all(self, locators_dir: str | Path) -> None:
        """Save each page's bundles to its own <page>.json file."""
        loc_dir = Path(locators_dir)
        pages = {b.page for b in self._bundles.values()}
        for page in pages:
            self.save(loc_dir / f"{page}.json", page=page)

    def summary(self) -> List[Dict[str, Any]]:
        """Return a summary list suitable for CLI display."""
        rows = []
        for bundle in self._bundles.values():
            rows.append(
                {
                    "element": bundle.element_name,
                    "page": bundle.page,
                    "primary_strategy": bundle.primary.strategy.value,
                    "primary_value": bundle.primary.value[:60],
                    "confidence": bundle.primary.confidence,
                    "alternates": len(bundle.alternates),
                }
            )
        return sorted(rows, key=lambda r: (r["page"], r["element"]))
