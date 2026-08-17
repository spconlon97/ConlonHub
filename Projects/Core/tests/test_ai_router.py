import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from app.core.auth.principal import Principal
from app.modules import loader
from app.modules.ai import router as ai_router_module
from app.modules.ai.providers import AIProviderUnavailable
from app.modules.ai.repository import ConversationNotFound


class AIRouterRegistrationTests(unittest.TestCase):
    def test_status_route_is_registered_as_get(self):
        matching_routes = [
            route
            for route in ai_router_module.router.routes
            if route.path == "/ai/status"
        ]

        self.assertEqual(len(matching_routes), 1)
        self.assertIn("GET", matching_routes[0].methods)

    def test_response_route_is_registered_as_post(self):
        matching_routes = [
            route
            for route in ai_router_module.router.routes
            if route.path == "/ai/respond"
        ]

        self.assertEqual(len(matching_routes), 1)
        self.assertIn("POST", matching_routes[0].methods)

    def test_conversation_route_supports_get_and_delete(self):
        matching_routes = [
            route
            for route in ai_router_module.router.routes
            if route.path == "/ai/conversations/{conversation_id}"
        ]

        self.assertEqual(len(matching_routes), 2)
        methods = {method for route in matching_routes for method in route.methods}
        self.assertIn("GET", methods)
        self.assertIn("DELETE", methods)

    def test_conversation_index_is_registered_as_get(self):
        matching_routes = [
            route
            for route in ai_router_module.router.routes
            if route.path == "/ai/conversations"
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
            def status_details(self):
                return {
                    "name": "AI Assistant",
                    "version": "9.9.9",
                    "status": "fake-status",
                    "provider": "fake",
                    "model": "fake-model",
                }

        fake = FakeAssistant()

        with patch.object(
            ai_router_module, "get_module_instance", return_value=fake
        ) as get_instance:
            result = ai_router_module.get_ai_status()

        get_instance.assert_called_once_with("AI Assistant")
        self.assertEqual(
            result,
            {
                "name": "AI Assistant",
                "version": "9.9.9",
                "status": "fake-status",
                "provider": "fake",
                "model": "fake-model",
            },
        )

    def test_response_shape_and_values_match_loader_managed_instance(self):
        result = ai_router_module.get_ai_status()
        assistant = loader.get_module_instance("AI Assistant")

        self.assertEqual(
            set(result.keys()),
            {"name", "version", "status", "provider", "model"},
        )
        self.assertEqual(result["name"], assistant.name)
        self.assertEqual(result["version"], assistant.version)
        self.assertEqual(result["status"], assistant.status())
        self.assertEqual(result["provider"], "unconfigured")
        self.assertIsNone(result["model"])

    def test_handler_reuses_same_instance_as_loader(self):
        ai_router_module.get_ai_status()
        instance_a = loader.get_module_instance("AI Assistant")
        instance_b = loader.get_module_instance("AI Assistant")

        self.assertIs(instance_a, instance_b)


class AIRouterDoesNotConstructOwnInstanceTests(unittest.TestCase):
    def test_router_source_does_not_instantiate_ai_assistant(self):
        source = Path(ai_router_module.__file__).read_text()

        self.assertNotIn("AIAssistant(", source)


class AIResponseHandlerTests(unittest.TestCase):
    principal = Principal(principal_id="p-1", name="Test User")

    class FakeRepository:
        def __init__(self):
            self.exchanges = []
            self.created = []

        def create_conversation(self, principal_id):
            self.created.append(principal_id)
            return "conversation-1"

        def claim_request_quota(self, principal_id, *, maximum):
            self.claimed_quota = (principal_id, maximum)
            return True

        def list_messages(self, conversation_id, principal_id, *, limit=None):
            self.history_limit = limit
            return (("user", "earlier"), ("assistant", "previous"))

        def append_exchange(
            self, conversation_id, principal_id, prompt, response
        ):
            self.exchanges.append(
                (conversation_id, principal_id, prompt, response)
            )

        def delete_conversation(self, conversation_id, principal_id):
            self.deleted = (conversation_id, principal_id)

    def test_delegates_to_loader_managed_assistant(self):
        class FakeAssistant:
            def respond(self, prompt, history=()):
                return f"answer: {prompt}"

        repository = self.FakeRepository()
        with patch.object(
            ai_router_module, "get_module_instance", return_value=FakeAssistant()
        ):
            result = ai_router_module.create_ai_response(
                ai_router_module.AIResponseRequest(prompt="question"),
                self.principal,
                repository,
            )

        self.assertEqual(result.response, "answer: question")
        self.assertEqual(result.conversation_id, "conversation-1")
        self.assertEqual(
            repository.exchanges,
            [("conversation-1", "p-1", "question", "answer: question")],
        )
        self.assertEqual(repository.created, ["p-1"])
        self.assertEqual(
            repository.claimed_quota,
            ("p-1", ai_router_module.settings.ai_requests_per_minute),
        )
        self.assertFalse(hasattr(repository, "history_limit"))

    def test_unavailable_provider_maps_to_503(self):
        class FakeAssistant:
            def respond(self, prompt, history=()):
                raise AIProviderUnavailable("offline")

        repository = self.FakeRepository()
        with patch.object(
            ai_router_module, "get_module_instance", return_value=FakeAssistant()
        ):
            with self.assertRaises(HTTPException) as raised:
                ai_router_module.create_ai_response(
                    ai_router_module.AIResponseRequest(prompt="question"),
                    self.principal,
                    repository,
                )

        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(raised.exception.detail, "AI provider is unavailable.")
        self.assertEqual(repository.created, [])
        self.assertEqual(repository.exchanges, [])

    def test_invalid_provider_response_maps_to_502(self):
        class FakeAssistant:
            def respond(self, prompt, history=()):
                raise ValueError("bad response")

        with patch.object(
            ai_router_module, "get_module_instance", return_value=FakeAssistant()
        ):
            with self.assertRaises(HTTPException) as raised:
                ai_router_module.create_ai_response(
                    ai_router_module.AIResponseRequest(prompt="question"),
                    self.principal,
                    self.FakeRepository(),
                )

        self.assertEqual(raised.exception.status_code, 502)
        self.assertEqual(
            raised.exception.detail,
            "AI provider returned an invalid response.",
        )

    def test_other_principals_conversation_maps_to_404(self):
        class MissingRepository(self.FakeRepository):
            def list_messages(self, conversation_id, principal_id, *, limit=None):
                raise ConversationNotFound("hidden")

        class FakeAssistant:
            def respond(self, prompt, history=()):
                raise AssertionError("provider should not be called")

        with patch.object(
            ai_router_module, "get_module_instance", return_value=FakeAssistant()
        ):
            with self.assertRaises(HTTPException) as raised:
                ai_router_module.create_ai_response(
                    ai_router_module.AIResponseRequest(
                        prompt="question", conversation_id="someone-elses"
                    ),
                    self.principal,
                    MissingRepository(),
                )

        self.assertEqual(raised.exception.status_code, 404)
        self.assertEqual(raised.exception.detail, "Conversation was not found.")

    def test_resumed_conversation_is_validated_and_uses_bounded_history(self):
        class FakeAssistant:
            def __init__(self):
                self.history = None

            def respond(self, prompt, history=()):
                self.history = history
                return "answer"

        assistant = FakeAssistant()
        repository = self.FakeRepository()
        with patch.object(
            ai_router_module, "get_module_instance", return_value=assistant
        ):
            result = ai_router_module.create_ai_response(
                ai_router_module.AIResponseRequest(
                    prompt="question", conversation_id="existing"
                ),
                self.principal,
                repository,
            )

        self.assertEqual(result.conversation_id, "existing")
        self.assertEqual(
            repository.history_limit,
            ai_router_module.settings.ai_history_message_limit,
        )
        self.assertEqual(
            assistant.history,
            (("user", "earlier"), ("assistant", "previous")),
        )
        self.assertEqual(repository.created, [])

    def test_rate_limit_prevents_provider_call(self):
        class LimitedRepository(self.FakeRepository):
            def claim_request_quota(self, principal_id, *, maximum):
                return False

        class FakeAssistant:
            def respond(self, prompt, history=()):
                raise AssertionError("provider should not be called")

        with patch.object(
            ai_router_module, "get_module_instance", return_value=FakeAssistant()
        ):
            with self.assertRaises(HTTPException) as raised:
                ai_router_module.create_ai_response(
                    ai_router_module.AIResponseRequest(prompt="question"),
                    self.principal,
                    LimitedRepository(),
                )

        self.assertEqual(raised.exception.status_code, 429)
        self.assertEqual(raised.exception.headers, {"Retry-After": "60"})


class AIConversationControlTests(unittest.TestCase):
    principal = Principal(principal_id="p-1", name="Test User")

    class FakeRepository:
        def list_conversations(self, principal_id, *, limit, offset):
            return (
                {
                    "conversation_id": "conversation-1",
                    "created_at": "2026-08-17T12:00:00+00:00",
                    "message_count": 2,
                },
            )

        def list_messages(self, conversation_id, principal_id):
            return (("user", "hello"), ("assistant", "hello back"))

        def delete_conversation(self, conversation_id, principal_id):
            self.deleted = (conversation_id, principal_id)

    def test_returns_stored_conversation(self):
        result = ai_router_module.get_ai_conversation(
            "conversation-1", self.principal, self.FakeRepository()
        )

        self.assertEqual(result.conversation_id, "conversation-1")
        self.assertEqual(
            [(message.role, message.content) for message in result.messages],
            [("user", "hello"), ("assistant", "hello back")],
        )

    def test_lists_principals_conversations(self):
        result = ai_router_module.list_ai_conversations(
            10, 5, self.principal, self.FakeRepository()
        )

        self.assertEqual(result.limit, 10)
        self.assertEqual(result.offset, 5)
        self.assertEqual(len(result.conversations), 1)
        self.assertEqual(
            result.conversations[0].conversation_id, "conversation-1"
        )
        self.assertEqual(result.conversations[0].message_count, 2)

    def test_deletes_owned_conversation(self):
        repository = self.FakeRepository()

        result = ai_router_module.delete_ai_conversation(
            "conversation-1", self.principal, repository
        )

        self.assertEqual(result.status_code, 204)
        self.assertEqual(repository.deleted, ("conversation-1", "p-1"))

    def test_missing_conversation_is_hidden_as_404(self):
        class MissingRepository(self.FakeRepository):
            def list_messages(self, conversation_id, principal_id):
                raise ConversationNotFound("hidden")

            def delete_conversation(self, conversation_id, principal_id):
                raise ConversationNotFound("hidden")

        for operation in (
            ai_router_module.get_ai_conversation,
            ai_router_module.delete_ai_conversation,
        ):
            with self.assertRaises(HTTPException) as raised:
                operation(
                    "conversation-1", self.principal, MissingRepository()
                )

            self.assertEqual(raised.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
