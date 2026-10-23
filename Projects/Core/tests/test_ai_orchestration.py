import unittest

from app.core.capabilities.models import Capability, CapabilityAccess
from app.core.capabilities.registry import (
    CapabilityNotFound,
    CapabilityRegistry,
)
from app.modules.ai.orchestration import (
    TOOL_REQUEST_PREFIX,
    ToolExecutionDenied,
    ToolRequest,
    execute_read_tool,
    parse_tool_request,
)


class ToolRequestTests(unittest.TestCase):
    def test_normal_response_is_not_a_tool_request(self):
        self.assertIsNone(parse_tool_request("Hello from MARVIS."))

    def test_parses_valid_tool_request(self):
        result = parse_tool_request(
            'MARVIS_TOOL_REQUEST: '
            '{"capability":"trading.paper_account","arguments":{}}'
        )

        self.assertEqual(
            result,
            ToolRequest(
                capability="trading.paper_account",
                arguments={},
            ),
        )

    def test_parses_tool_request_arguments(self):
        result = parse_tool_request(
            'MARVIS_TOOL_REQUEST: '
            '{"capability":"example.lookup","arguments":{"symbol":"XAUUSD"}}'
        )

        self.assertEqual(result.capability, "example.lookup")
        self.assertEqual(result.arguments, {"symbol": "XAUUSD"})

    def test_rejects_invalid_json(self):
        with self.assertRaisesRegex(ValueError, "invalid JSON"):
            parse_tool_request("MARVIS_TOOL_REQUEST: not-json")

    def test_rejects_non_object_payload(self):
        with self.assertRaisesRegex(ValueError, "payload must be an object"):
            parse_tool_request(
                'MARVIS_TOOL_REQUEST: ["trading.paper_account"]'
            )

    def test_rejects_missing_capability(self):
        with self.assertRaisesRegex(ValueError, "non-empty"):
            parse_tool_request(
                'MARVIS_TOOL_REQUEST: {"arguments":{}}'
            )

    def test_rejects_blank_capability(self):
        with self.assertRaisesRegex(ValueError, "non-empty"):
            parse_tool_request(
                'MARVIS_TOOL_REQUEST: {"capability":"   ","arguments":{}}'
            )

    def test_rejects_non_object_arguments(self):
        with self.assertRaisesRegex(ValueError, "arguments must be an object"):
            parse_tool_request(
                'MARVIS_TOOL_REQUEST: '
                '{"capability":"system.modules","arguments":[]}'
            )

    def test_prefix_constant_is_stable(self):
        self.assertEqual(
            TOOL_REQUEST_PREFIX,
            "MARVIS_TOOL_REQUEST:",
        )


class ToolExecutionTests(unittest.TestCase):
    def test_executes_registered_read_capability(self):
        registry = CapabilityRegistry()

        registry.register(
            Capability(
                name="system.status",
                description="Return system status.",
                access=CapabilityAccess.READ,
                handler=lambda: {"status": "online"},
            )
        )

        result = execute_read_tool(
            registry,
            ToolRequest(
                capability="system.status",
                arguments={},
            ),
        )

        self.assertEqual(result, {"status": "online"})

    def test_passes_validated_arguments_to_read_capability(self):
        registry = CapabilityRegistry()

        registry.register(
            Capability(
                name="example.lookup",
                description="Look up a value.",
                access=CapabilityAccess.READ,
                handler=lambda symbol: {"symbol": symbol},
            )
        )

        result = execute_read_tool(
            registry,
            ToolRequest(
                capability="example.lookup",
                arguments={"symbol": "XAUUSD"},
            ),
        )

        self.assertEqual(result, {"symbol": "XAUUSD"})

    def test_rejects_action_capability(self):
        registry = CapabilityRegistry()

        registry.register(
            Capability(
                name="trading.place_paper_order",
                description="Place a paper order.",
                access=CapabilityAccess.ACTION,
                handler=lambda: "should never execute",
                summarize=lambda: "Place a paper order",
            )
        )

        with self.assertRaisesRegex(
            ToolExecutionDenied,
            "requires approval",
        ):
            execute_read_tool(
                registry,
                ToolRequest(
                    capability="trading.place_paper_order",
                    arguments={},
                ),
            )

    def test_rejects_unknown_capability(self):
        registry = CapabilityRegistry()

        with self.assertRaises(CapabilityNotFound):
            execute_read_tool(
                registry,
                ToolRequest(
                    capability="system.does_not_exist",
                    arguments={},
                ),
            )


if __name__ == "__main__":
    unittest.main()
