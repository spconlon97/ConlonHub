import unittest
from pathlib import Path
from unittest.mock import patch

from app.modules import loader
from app.modules.ai import router as ai_router_module


class AIRouterRegistrationTests(unittest.TestCase):
    def test_status_route_is_registered_as_get(self):
        matching_routes = [
            route
            for route in ai_router_module.router.routes
            if route.path == "/ai/status"
        ]

        self.assertEqual(len(matching_routes), 1)
        self.assertIn("GET", matching_routes[0].methods)

    def test_router_has_ai_prefix(self):
        self.assertEqual(ai_router_module.router.prefix, "/ai")


class AIStatusHandlerTests(unittest.TestCase):
    def setUp(self):
        self._original_loaded_modules = dict(loader.loaded_modules)
        self._original_module_instances = dict(loader.module_instances)
        loader.loaded_modules.clear()
        loader.module_instances.clear()

    def tearDown(self):
        loader.loaded_modules.clear()
        loader.loaded_modules.update(self._original_loaded_modules)
        loader.module_instances.clear()
        loader.module_instances.update(self._original_module_instances)

    def test_handler_resolves_loader_managed_instance(self):
        class FakeAssistant:
            name = "AI Assistant"
            version = "9.9.9"

            def status(self):
                return "fake-status"

        fake = FakeAssistant()

        with patch.object(
            ai_router_module, "get_module_instance", return_value=fake
        ) as get_instance:
            result = ai_router_module.get_ai_status()

        get_instance.assert_called_once_with("AI Assistant")
        self.assertEqual(
            result,
            {"name": "AI Assistant", "version": "9.9.9", "status": "fake-status"},
        )

    def test_response_shape_and_values_match_loader_managed_instance(self):
        result = ai_router_module.get_ai_status()
        assistant = loader.get_module_instance("AI Assistant")

        self.assertEqual(set(result.keys()), {"name", "version", "status"})
        self.assertEqual(result["name"], assistant.name)
        self.assertEqual(result["version"], assistant.version)
        self.assertEqual(result["status"], assistant.status())

    def test_handler_reuses_same_instance_as_loader(self):
        ai_router_module.get_ai_status()
        instance_a = loader.get_module_instance("AI Assistant")
        instance_b = loader.get_module_instance("AI Assistant")

        self.assertIs(instance_a, instance_b)


class AIRouterDoesNotConstructOwnInstanceTests(unittest.TestCase):
    def test_router_source_does_not_instantiate_ai_assistant(self):
        source = Path(ai_router_module.__file__).read_text()

        self.assertNotIn("AIAssistant(", source)


if __name__ == "__main__":
    unittest.main()
