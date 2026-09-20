import json
import unittest
from unittest.mock import Mock, patch

from app.core.capabilities.models import Capability, CapabilityAccess
from app.core.capabilities.registry import CapabilityRegistry
from app.modules.ai.assistant import AIAssistant
from app.modules.ai.orchestration import ToolOrchestrationError
from app.modules.ai.providers import AIProviderUnavailable


def request(name="example.read", arguments=None):
    return "MARVIS_TOOL_REQUEST: " + json.dumps({
        "capability": name, "arguments": arguments or {},
    })


class ToolFlowTests(unittest.TestCase):
    def setUp(self):
        self.handler = Mock(return_value={"balance": "10000.00"})
        self.action = Mock()
        self.registry = CapabilityRegistry()
        self.registry.register(Capability(
            "example.read", "Read balance", CapabilityAccess.READ,
            lambda: self.handler(),
        ))
        self.registry.register(Capability(
            "example.action", "Change balance", CapabilityAccess.ACTION,
            self.action,
        ))
        self.provider = Mock()
        self.assistant = AIAssistant(self.provider, registry=self.registry)

    def test_read_round_trip_preserves_history_and_returns_answer(self):
        self.provider.generate.side_effect = [request(), "Balance is 10000.00"]
        history = [("user", "Earlier"), ("assistant", "Hello")]
        self.assertEqual(self.assistant.respond(" Balance? ", history),
                         "Balance is 10000.00")
        self.handler.assert_called_once_with()
        first, second = self.provider.generate.call_args_list
        self.assertEqual(first.args, ("Balance?",))
        self.assertEqual(first.kwargs["history"][1:], tuple(history))
        self.assertNotIn("example.action", first.kwargs["history"][0][1])
        self.assertIn('"balance": "10000.00"', second.args[0])
        self.assertEqual(second.kwargs["history"][-2:],
                         (("user", "Balance?"), ("assistant", request())))
        self.assertEqual(len(history), 2)

    def test_denied_unknown_malformed_and_invalid_arguments_never_execute(self):
        for response in [request("example.action"), request("unknown"),
                         "MARVIS_TOOL_REQUEST: broken",
                         request(arguments={"unexpected": 1})]:
            with self.subTest(response=response):
                self.provider.generate.return_value = response
                with self.assertRaises(ToolOrchestrationError):
                    self.assistant.respond("Balance?")
        self.handler.assert_not_called()
        self.action.assert_not_called()

    def test_repeated_requests_are_bounded(self):
        self.provider.generate.return_value = request()
        with self.assertRaisesRegex(ToolOrchestrationError, "limit"):
            self.assistant.respond("Balance?")
        self.assertEqual(self.handler.call_count, 3)
        self.assertEqual(self.provider.generate.call_count, 4)

    def test_handler_failure_is_sanitized_and_stops_flow(self):
        self.handler.side_effect = RuntimeError("sensitive detail")
        self.provider.generate.return_value = request()
        with self.assertRaises(ToolOrchestrationError) as caught:
            self.assistant.respond("Balance?")
        self.assertNotIn("sensitive", str(caught.exception))
        self.assertEqual(self.provider.generate.call_count, 1)

    def test_unserializable_result_stops_flow(self):
        self.handler.return_value = object()
        self.provider.generate.return_value = request()
        with self.assertRaises(ToolOrchestrationError):
            self.assistant.respond("Balance?")
        self.assertEqual(self.provider.generate.call_count, 1)

    def test_empty_final_response_is_rejected(self):
        self.provider.generate.side_effect = [request(), " "]
        with self.assertRaisesRegex(ValueError, "empty response"):
            self.assistant.respond("Balance?")

    def test_provider_failure_after_read_propagates(self):
        self.provider.generate.side_effect = [request(), AIProviderUnavailable()]
        with self.assertRaises(AIProviderUnavailable):
            self.assistant.respond("Balance?")
        self.handler.assert_called_once()

    def test_tool_state_does_not_leak_between_requests(self):
        self.provider.generate.side_effect = [request(), "First", "Second"]
        self.assistant.respond("Balance?")
        self.assistant.respond("Hello")
        self.assertEqual(len(self.provider.generate.call_args.kwargs["history"]), 1)

    def test_builtin_account_uses_loaded_module_data(self):
        from decimal import Decimal
        bot = Mock()
        bot.account.starting_cash = Decimal("10000")
        bot.account.cash_balance = Decimal("9000")
        bot.account.positions = {"TEST": Decimal("2")}
        self.provider.generate.side_effect = [request("trading.paper_account"), "9000"]
        with patch("app.core.capabilities.builtin.get_module_instance", return_value=bot):
            self.assertEqual(AIAssistant(self.provider).respond("Balance?"), "9000")
        self.assertIn('"cash_balance": "9000"', self.provider.generate.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
