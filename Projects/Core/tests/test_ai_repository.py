import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from app.modules.ai.repository import (
    ConversationNotFound,
    SqliteAIConversationRepository,
)


class AIConversationRepositoryTests(unittest.TestCase):
    def test_persists_and_reloads_exchange_in_order(self):
        with TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "ai.db"
            repository = SqliteAIConversationRepository(database_path)
            conversation_id = repository.create_conversation("p-1")

            repository.append_exchange(
                conversation_id, "p-1", "hello", "hello back"
            )
            reopened = SqliteAIConversationRepository(database_path)

            self.assertEqual(
                reopened.list_messages(conversation_id, "p-1"),
                (("user", "hello"), ("assistant", "hello back")),
            )

    def test_conversation_is_isolated_by_principal(self):
        with TemporaryDirectory() as temp_dir:
            repository = SqliteAIConversationRepository(
                Path(temp_dir) / "ai.db"
            )
            conversation_id = repository.create_conversation("owner")

            with self.assertRaises(ConversationNotFound):
                repository.list_messages(conversation_id, "other-principal")

            with self.assertRaises(ConversationNotFound):
                repository.append_exchange(
                    conversation_id,
                    "other-principal",
                    "attempt",
                    "response",
                )

    def test_unknown_conversation_is_not_found(self):
        with TemporaryDirectory() as temp_dir:
            repository = SqliteAIConversationRepository(
                Path(temp_dir) / "ai.db"
            )

            with self.assertRaises(ConversationNotFound):
                repository.list_messages("missing", "p-1")

    def test_deletes_conversation_and_its_messages(self):
        with TemporaryDirectory() as temp_dir:
            repository = SqliteAIConversationRepository(
                Path(temp_dir) / "ai.db"
            )
            conversation_id = repository.create_conversation("p-1")
            repository.append_exchange(
                conversation_id, "p-1", "hello", "hello back"
            )

            repository.delete_conversation(conversation_id, "p-1")

            with self.assertRaises(ConversationNotFound):
                repository.list_messages(conversation_id, "p-1")

    def test_other_principal_cannot_delete_conversation(self):
        with TemporaryDirectory() as temp_dir:
            repository = SqliteAIConversationRepository(
                Path(temp_dir) / "ai.db"
            )
            conversation_id = repository.create_conversation("owner")

            with self.assertRaises(ConversationNotFound):
                repository.delete_conversation(conversation_id, "other")

            self.assertEqual(
                repository.list_messages(conversation_id, "owner"), ()
            )

    def test_lists_only_principals_conversations_with_message_counts(self):
        with TemporaryDirectory() as temp_dir:
            repository = SqliteAIConversationRepository(
                Path(temp_dir) / "ai.db"
            )
            first = repository.create_conversation("p-1")
            second = repository.create_conversation("p-1")
            repository.create_conversation("other")
            repository.append_exchange(first, "p-1", "hello", "answer")

            conversations = repository.list_conversations("p-1")

            self.assertEqual(
                {item["conversation_id"] for item in conversations},
                {first, second},
            )
            counts = {
                item["conversation_id"]: item["message_count"]
                for item in conversations
            }
            self.assertEqual(counts, {first: 2, second: 0})
            self.assertTrue(all(item["created_at"] for item in conversations))

    def test_conversation_listing_is_paginated(self):
        with TemporaryDirectory() as temp_dir:
            repository = SqliteAIConversationRepository(
                Path(temp_dir) / "ai.db"
            )
            for _ in range(3):
                repository.create_conversation("p-1")

            first_page = repository.list_conversations("p-1", limit=2)
            second_page = repository.list_conversations(
                "p-1", limit=2, offset=2
            )

            self.assertEqual(len(first_page), 2)
            self.assertEqual(len(second_page), 1)
            self.assertTrue(
                {item["conversation_id"] for item in first_page}.isdisjoint(
                    item["conversation_id"] for item in second_page
                )
            )

    def test_conversation_listing_rejects_invalid_pagination(self):
        with TemporaryDirectory() as temp_dir:
            repository = SqliteAIConversationRepository(
                Path(temp_dir) / "ai.db"
            )

            for limit in (0, 101, True):
                with self.assertRaises(ValueError):
                    repository.list_conversations("p-1", limit=limit)
            for offset in (-1, True):
                with self.assertRaises(ValueError):
                    repository.list_conversations("p-1", offset=offset)

    def test_limited_messages_returns_most_recent_in_original_order(self):
        with TemporaryDirectory() as temp_dir:
            repository = SqliteAIConversationRepository(
                Path(temp_dir) / "ai.db"
            )
            conversation_id = repository.create_conversation("p-1")
            repository.append_exchange(
                conversation_id, "p-1", "first", "first answer"
            )
            repository.append_exchange(
                conversation_id, "p-1", "second", "second answer"
            )

            messages = repository.list_messages(
                conversation_id, "p-1", limit=2
            )

            self.assertEqual(
                messages,
                (("user", "second"), ("assistant", "second answer")),
            )
            self.assertEqual(
                len(repository.list_messages(conversation_id, "p-1")), 4
            )

    def test_message_limit_is_bounded(self):
        with TemporaryDirectory() as temp_dir:
            repository = SqliteAIConversationRepository(
                Path(temp_dir) / "ai.db"
            )
            conversation_id = repository.create_conversation("p-1")

            for limit in (0, 201, True):
                with self.assertRaises(ValueError):
                    repository.list_messages(
                        conversation_id, "p-1", limit=limit
                    )

    def test_request_quota_is_isolated_by_principal_and_window(self):
        with TemporaryDirectory() as temp_dir:
            repository = SqliteAIConversationRepository(
                Path(temp_dir) / "ai.db"
            )
            now = datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc)

            self.assertTrue(
                repository.claim_request_quota(
                    "p-1", maximum=2, now=now
                )
            )
            self.assertTrue(
                repository.claim_request_quota(
                    "p-1", maximum=2, now=now
                )
            )
            self.assertFalse(
                repository.claim_request_quota(
                    "p-1", maximum=2, now=now
                )
            )
            self.assertTrue(
                repository.claim_request_quota(
                    "p-2", maximum=2, now=now
                )
            )
            self.assertTrue(
                repository.claim_request_quota(
                    "p-1", maximum=2, now=now + timedelta(seconds=61)
                )
            )


if __name__ == "__main__":
    unittest.main()
