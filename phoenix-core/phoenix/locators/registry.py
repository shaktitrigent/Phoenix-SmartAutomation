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
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

try:
    from phoenix_shared.models.locator import LocatorBundle
except ImportError:
    from shared.phoenix_shared.models.locator import LocatorBundle  # type: ignore[no-redef]


class LocatorRegistry:
    """In-memory registry of LocatorBundles, backed by per-page JSON files."""

    def __init__(self) -> None:
        self._bundles: Dict[str, LocatorBundle] = {}  # keyed by element_name

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
                    bundle = LocatorBundle.from_dict(item)
                    self._bundles[bundle.element_name] = bundle
                except Exception:
                    pass
        except (json.JSONDecodeError, OSError):
            pass

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    def get(self, element_name: str) -> Optional[LocatorBundle]:
        """Return the bundle for *element_name*, or None if not found."""
        return self._bundles.get(element_name)

    def require(self, element_name: str) -> LocatorBundle:
        """Return the bundle for *element_name*, raising KeyError if absent."""
        bundle = self._bundles.get(element_name)
        if bundle is None:
            raise KeyError(f"No LocatorBundle registered for '{element_name}'")
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
        """Add or replace a bundle by element_name."""
        self._bundles[bundle.element_name] = bundle

    def remove(self, element_name: str) -> bool:
        """Remove a bundle. Returns True if it existed."""
        return self._bundles.pop(element_name, None) is not None

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
