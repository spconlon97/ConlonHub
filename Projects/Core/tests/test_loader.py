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
        loader.loaded_modules.clear()

    def tearDown(self):
        loader.loaded_modules.clear()
        loader.loaded_modules.update(self._original_loaded_modules)

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

    def test_start_failure_propagates_and_leaves_loaded_modules_untouched(self):
        with patch.object(AIAssistant, "start", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                loader.load_modules()

        self.assertEqual(loader.loaded_modules, {})


if __name__ == "__main__":
    unittest.main()
