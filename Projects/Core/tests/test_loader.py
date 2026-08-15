import unittest
from unittest.mock import patch

from app.modules import loader
from app.modules.ai.assistant import AIAssistant
from app.modules.base import ModuleBase
from app.modules.tradingbot.trading_bot import TradingBot


class AIAssistantLifecycleTests(unittest.TestCase):
    def test_is_a_module_base(self):
        self.assertIsInstance(AIAssistant(), ModuleBase)

    def test_start_matches_status(self):
        assistant = AIAssistant()

        self.assertEqual(assistant.start(), assistant.status())


class LoadModulesLifecycleTests(unittest.TestCase):
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

    def test_start_is_invoked_for_each_module(self):
        with patch.object(AIAssistant, "start") as ai_start, \
                patch.object(TradingBot, "start") as bot_start:
            loader.load_modules()

        ai_start.assert_called_once_with()
        bot_start.assert_called_once_with()

    def test_populates_loaded_modules_with_unchanged_shape(self):
        loader.load_modules()

        self.assertIn("AI Assistant", loader.loaded_modules)
        self.assertIn("Trading Bot", loader.loaded_modules)
        for entry in loader.loaded_modules.values():
            self.assertEqual(set(entry.keys()), {"name", "version", "status"})

    def test_populates_module_instances_with_started_instances(self):
        loader.load_modules()

        self.assertIsInstance(loader.module_instances["AI Assistant"], AIAssistant)
        self.assertIsInstance(loader.module_instances["Trading Bot"], TradingBot)

    def test_start_failure_propagates_and_leaves_loaded_modules_untouched(self):
        with patch.object(AIAssistant, "start", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                loader.load_modules()

        self.assertEqual(loader.loaded_modules, {})

    def test_start_failure_propagates_and_leaves_module_instances_untouched(self):
        with patch.object(AIAssistant, "start", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                loader.load_modules()

        self.assertEqual(loader.module_instances, {})

    def test_start_failure_on_second_module_still_leaves_both_dicts_untouched(self):
        with patch.object(TradingBot, "start", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                loader.load_modules()

        self.assertEqual(loader.loaded_modules, {})
        self.assertEqual(loader.module_instances, {})

    def test_failed_load_is_retried_deterministically_on_next_call(self):
        with patch.object(AIAssistant, "start", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                loader.load_modules()

        loader.load_modules()

        self.assertIn("AI Assistant", loader.loaded_modules)
        self.assertIn("AI Assistant", loader.module_instances)

    def test_get_module_instance_returns_same_object_across_calls(self):
        first = loader.get_module_instance("AI Assistant")
        second = loader.get_module_instance("AI Assistant")

        self.assertIsInstance(first, AIAssistant)
        self.assertIs(first, second)

    def test_get_module_instance_triggers_lazy_load(self):
        instance = loader.get_module_instance("Trading Bot")

        self.assertIsInstance(instance, TradingBot)

    def test_get_module_instance_unknown_name_returns_none(self):
        self.assertIsNone(loader.get_module_instance("Nonexistent Module"))


if __name__ == "__main__":
    unittest.main()
