import unittest

from app.core.capabilities.models import Capability, CapabilityAccess
from app.core.capabilities.registry import (
    CapabilityAlreadyRegistered,
    CapabilityNotFound,
    CapabilityRegistry,
)


class CapabilityTests(unittest.TestCase):
    def test_capability_requires_name(self):
        with self.assertRaises(ValueError):
            Capability(
                name="",
                description="Test capability",
                access=CapabilityAccess.READ,
                handler=lambda: None,
            )

    def test_capability_requires_description(self):
        with self.assertRaises(ValueError):
            Capability(
                name="system.test",
                description="",
                access=CapabilityAccess.READ,
                handler=lambda: None,
            )

    def test_capability_requires_callable_handler(self):
        with self.assertRaises(ValueError):
            Capability(
                name="system.test",
                description="Test capability",
                access=CapabilityAccess.READ,
                handler=None,
            )

    def test_registry_registers_and_gets_capability(self):
        registry = CapabilityRegistry()

        capability = Capability(
            name="system.status",
            description="Return system status.",
            access=CapabilityAccess.READ,
            handler=lambda: {"status": "online"},
        )

        registry.register(capability)

        self.assertIs(registry.get("system.status"), capability)

    def test_registry_rejects_duplicate_capability(self):
        registry = CapabilityRegistry()

        capability = Capability(
            name="system.status",
            description="Return system status.",
            access=CapabilityAccess.READ,
            handler=lambda: {"status": "online"},
        )

        registry.register(capability)

        with self.assertRaises(CapabilityAlreadyRegistered):
            registry.register(capability)

    def test_registry_raises_for_unknown_capability(self):
        registry = CapabilityRegistry()

        with self.assertRaises(CapabilityNotFound):
            registry.get("missing.capability")

    def test_registry_lists_capabilities_in_name_order(self):
        registry = CapabilityRegistry()

        registry.register(
            Capability(
                name="trading.status",
                description="Trading status.",
                access=CapabilityAccess.READ,
                handler=lambda: None,
            )
        )
        registry.register(
            Capability(
                name="system.status",
                description="System status.",
                access=CapabilityAccess.READ,
                handler=lambda: None,
            )
        )

        self.assertEqual(
            [item.name for item in registry.list()],
            ["system.status", "trading.status"],
        )

    def test_registry_executes_handler(self):
        registry = CapabilityRegistry()

        registry.register(
            Capability(
                name="math.add",
                description="Add two values.",
                access=CapabilityAccess.READ,
                handler=lambda left, right: left + right,
            )
        )

        self.assertEqual(
            registry.execute("math.add", left=2, right=3),
            5,
        )


if __name__ == "__main__":
    unittest.main()
