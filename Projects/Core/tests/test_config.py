import unittest

from pydantic import ValidationError

from app.core.config import Settings


class SettingsTests(unittest.TestCase):
    def test_default_history_limit_is_bounded_even_value(self):
        settings = Settings(_env_file=None)

        self.assertEqual(settings.ai_history_message_limit, 40)

    def test_history_limit_accepts_even_value_in_range(self):
        settings = Settings(_env_file=None, ai_history_message_limit=20)

        self.assertEqual(settings.ai_history_message_limit, 20)

    def test_history_limit_rejects_odd_or_out_of_range_values(self):
        for value in (1, 3, 202):
            with self.assertRaises(ValidationError):
                Settings(_env_file=None, ai_history_message_limit=value)

    def test_ai_request_limit_is_bounded(self):
        self.assertEqual(Settings(_env_file=None).ai_requests_per_minute, 10)
        self.assertEqual(
            Settings(_env_file=None, ai_requests_per_minute=60).ai_requests_per_minute,
            60,
        )
        for value in (0, 121):
            with self.assertRaises(ValidationError):
                Settings(_env_file=None, ai_requests_per_minute=value)


if __name__ == "__main__":
    unittest.main()
