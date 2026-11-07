import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock

from app.core.approvals.models import ApprovalStatus
from app.core.approvals.repository import (
    MAX_PENDING_APPROVALS,
    SqliteApprovalRepository,
)
from app.core.capabilities.models import Capability, CapabilityAccess
from app.core.capabilities.registry import CapabilityRegistry
from app.modules.ai.assistant import AIAssistant
from app.modules.ai.orchestration import ToolOrchestrationError, generate_with_tools


def tool_request(name, arguments=None):
    return "MARVIS_TOOL_REQUEST: " + json.dumps(
        {"capability": name, "arguments": arguments or {}}
    )


class ActionProposalTests(unittest.TestCase):
    def setUp(self):
        self._temp_dir = TemporaryDirectory()
        self.approvals = SqliteApprovalRepository(
            Path(self._temp_dir.name) / "approvals.db",
            clock=lambda: datetime(2026, 10, 23, 10, 0, tzinfo=timezone.utc),
        )
        self.action = Mock()
        self.read = Mock(return_value={"balance": "10000.00"})
        self.registry = CapabilityRegistry()
        self.registry.register(Capability(
            "example.read", "Read balance", CapabilityAccess.READ,
            lambda: self.read(),
        ))
        self.registry.register(Capability(
            "example.transfer", "Move paper cash", CapabilityAccess.ACTION,
            lambda amount: self.action(amount),
            summarize=lambda amount: f"Move {amount} paper cash",
        ))
        self.provider = Mock()

    def tearDown(self):
        self._temp_dir.cleanup()

    def _run(self, prompt="Move 5", **overrides):
        values = {"approvals": self.approvals, "principal_id": "p-1"}
        values.update(overrides)
        return generate_with_tools(self.provider, self.registry, prompt, **values)

    def test_action_request_creates_pending_approval_and_fixed_reply(self):
        self.provider.generate.side_effect = [
            tool_request("example.transfer", {"amount": "5"}),
        ]

        reply = self._run()

        pending = self.approvals.list_pending("p-1")
        self.assertEqual(len(pending), 1)
        approval = pending[0]
        self.assertEqual(approval.capability, "example.transfer")
        self.assertEqual(approval.arguments, {"amount": "5"})
        self.assertEqual(approval.summary, "Move 5 paper cash")
        self.assertEqual(approval.status, ApprovalStatus.PENDING)
        self.assertEqual(
            reply,
            "Approval needed: Move 5 paper cash\n"
            f"Request: {approval.request_id}\n"
            f"Expires: {approval.expires_at}\n"
            "Nothing has been done yet. Approve or reject this request in MARVIS.",
        )
        self.action.assert_not_called()
        self.assertEqual(self.provider.generate.call_count, 1)

    def test_catalog_lists_actions_as_proposals_only_when_approvals_enabled(self):
        self.provider.generate.return_value = "Hello"

        self._run()
        enabled = self.provider.generate.call_args.kwargs["history"][0][1]
        generate_with_tools(self.provider, self.registry, "Hi")
        disabled = self.provider.generate.call_args.kwargs["history"][0][1]

        self.assertIn("example.transfer", enabled)
        self.assertIn("human approval", enabled)
        self.assertNotIn("example.transfer", disabled)

    def test_action_without_approvals_or_principal_is_denied(self):
        for overrides in ({"approvals": None}, {"principal_id": None}):
            with self.subTest(overrides=overrides):
                self.provider.generate.side_effect = [
                    tool_request("example.transfer", {"amount": "5"}),
                ]
                with self.assertRaises(ToolOrchestrationError):
                    self._run(**overrides)

        self.assertEqual(self.approvals.list_pending("p-1"), ())
        self.action.assert_not_called()

    def test_invalid_arguments_create_nothing(self):
        for arguments in ({}, {"amount": "5", "extra": 1}, {"wrong": "5"}):
            with self.subTest(arguments=arguments):
                self.provider.generate.side_effect = [
                    tool_request("example.transfer", arguments),
                ]
                with self.assertRaises(ToolOrchestrationError):
                    self._run()

        self.assertEqual(self.approvals.list_pending("p-1"), ())

    def test_failing_or_blank_summary_creates_nothing(self):
        for summarize in (Mock(side_effect=ValueError("bad")), lambda amount: "  "):
            with self.subTest(summarize=summarize):
                registry = CapabilityRegistry()
                registry.register(Capability(
                    "example.transfer", "Move", CapabilityAccess.ACTION,
                    lambda amount: None, summarize=summarize,
                ))
                self.provider.generate.side_effect = [
                    tool_request("example.transfer", {"amount": "5"}),
                ]
                with self.assertRaises(ToolOrchestrationError):
                    generate_with_tools(
                        self.provider, registry, "Move",
                        approvals=self.approvals, principal_id="p-1",
                    )

        self.assertEqual(self.approvals.list_pending("p-1"), ())

    def test_sixth_pending_request_gets_fixed_limit_reply(self):
        for _ in range(MAX_PENDING_APPROVALS):
            self.provider.generate.side_effect = [
                tool_request("example.transfer", {"amount": "5"}),
            ]
            self._run()

        self.provider.generate.side_effect = [
            tool_request("example.transfer", {"amount": "5"}),
        ]
        reply = self._run()

        self.assertEqual(
            reply,
            "Approval not created: you already have 5 pending approval requests. "
            "Approve or reject those first. Nothing has been done.",
        )
        self.assertEqual(len(self.approvals.list_pending("p-1")), MAX_PENDING_APPROVALS)

    def test_read_tools_still_round_trip_with_approvals_enabled(self):
        self.provider.generate.side_effect = [
            tool_request("example.read"), "Balance is 10000.00",
        ]

        self.assertEqual(self._run("Balance?"), "Balance is 10000.00")
        self.read.assert_called_once_with()
        self.assertEqual(self.approvals.list_pending("p-1"), ())

    def test_assistant_passes_principal_and_approvals_through(self):
        assistant = AIAssistant(self.provider, registry=self.registry)
        self.provider.generate.side_effect = [
            tool_request("example.transfer", {"amount": "7"}),
        ]

        reply = assistant.respond(
            "Move 7", principal_id="p-1", approvals=self.approvals
        )

        self.assertTrue(reply.startswith("Approval needed: Move 7 paper cash"))
        self.assertEqual(len(self.approvals.list_pending("p-1")), 1)


if __name__ == "__main__":
    unittest.main()
