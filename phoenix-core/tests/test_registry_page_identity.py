"""Regression tests for locator names shared across arbitrary pages."""
import json
import tempfile
import unittest
from pathlib import Path
from phoenix.locators.registry import LocatorRegistry
from phoenix_shared.models.locator import LocatorBundle


def bundle(page, name="SharedLink", value="#target"):
    return LocatorBundle.from_dict({"page": page, "element_name": name,
        "primary": {"element_name": name, "strategy": "css", "value": value},
        "alternates": []})


class PageIdentityTests(unittest.TestCase):
    def test_load_and_roundtrip_preserve_cross_page_names(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for page in ("alpha", "beta", "gamma"):
                (root / f"{page}.json").write_text(
                    json.dumps([bundle(page).to_dict()]), encoding="utf-8")
            registry = LocatorRegistry.load_all(root)
            self.assertEqual(len(registry), 3)
            self.assertEqual(len(registry.summary()), 3)
            for page in ("alpha", "beta", "gamma"):
                self.assertEqual(registry.require("SharedLink", page=page).page, page)
                self.assertEqual(len(registry.page_bundles(page)), 1)
            registry.save_all(root / "roundtrip")
            self.assertEqual(len(LocatorRegistry.load_all(root / "roundtrip")), 3)

    def test_legacy_unique_lookup_and_remove(self):
        registry = LocatorRegistry()
        registry.upsert(bundle("alpha"))
        self.assertEqual(registry.require("SharedLink").page, "alpha")
        self.assertTrue(registry.remove("SharedLink"))
        self.assertIsNone(registry.get("missing"))
        self.assertFalse(registry.remove("missing"))

    def test_ambiguous_lookup_and_remove_do_not_choose_another_page(self):
        registry = LocatorRegistry()
        registry.upsert(bundle("alpha"))
        registry.upsert(bundle("beta"))
        self.assertIsNone(registry.get("SharedLink"))
        with self.assertRaises(KeyError):
            registry.require("SharedLink")
        self.assertFalse(registry.remove("SharedLink"))
        self.assertEqual(len(registry), 2)
        self.assertIsNone(registry.get("SharedLink", page="missing"))
        self.assertTrue(registry.remove("SharedLink", page="alpha"))
        self.assertEqual(registry.require("SharedLink").page, "beta")

    def test_upsert_replaces_only_same_page(self):
        registry = LocatorRegistry()
        registry.upsert(bundle("alpha"))
        registry.upsert(bundle("beta"))
        registry.upsert(bundle("alpha", value="#updated"))
        self.assertEqual(len(registry), 2)
        self.assertEqual(registry.require("SharedLink", page="alpha").primary.value, "#updated")
        self.assertEqual(registry.require("SharedLink", page="beta").primary.value, "#target")
