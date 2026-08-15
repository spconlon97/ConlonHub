import unittest

from app.core.registry import get_modules
from app.modules.loader import get_loaded_modules


class ModuleRegistryTests(unittest.TestCase):
    def test_reconciles_status_and_version_with_loaded_modules(self):
        loaded = get_loaded_modules()["modules"]
        registry = get_modules()["modules"]

        for key in ("ai", "trading"):
            loaded_entry = loaded[registry[key]["name"]]
            self.assertEqual(registry[key]["status"], loaded_entry["status"])
            self.assertEqual(registry[key]["version"], loaded_entry["version"])

    def test_no_longer_reports_loaded_modules_as_planned(self):
        registry = get_modules()["modules"]

        self.assertNotEqual(registry["ai"]["status"], "planned")
        self.assertNotEqual(registry["trading"]["status"], "planned")

    def test_keeps_static_entry_for_modules_with_no_loader_backing(self):
        registry = get_modules()["modules"]

        self.assertEqual(registry["core"]["status"], "online")
        self.assertEqual(registry["home"]["status"], "planned")

    def test_returns_updated_timestamp(self):
        response = get_modules()

        self.assertIn("updated", response)


if __name__ == "__main__":
    unittest.main()
