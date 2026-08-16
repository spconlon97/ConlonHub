import hashlib
import hmac
import unittest

from app.core.auth import (
    ApiKeyVerifier,
    IssuedApiKey,
    ParsedApiKey,
    Principal,
    generate_api_key,
    hash_api_key,
    parse_api_key,
    verify_api_key,
)


class PrincipalTests(unittest.TestCase):
    def test_creates_principal_with_id_and_name(self):
        principal = Principal(principal_id="p-1", name="Test Principal")

        self.assertEqual(principal.principal_id, "p-1")
        self.assertEqual(principal.name, "Test Principal")

    def test_rejects_empty_principal_id(self):
        with self.assertRaisesRegex(ValueError, "principal_id must be"):
            Principal(principal_id="", name="Test Principal")

    def test_rejects_blank_principal_id(self):
        with self.assertRaisesRegex(ValueError, "principal_id must be"):
            Principal(principal_id="   ", name="Test Principal")

    def test_rejects_non_string_principal_id(self):
        with self.assertRaisesRegex(ValueError, "principal_id must be"):
            Principal(principal_id=123, name="Test Principal")

    def test_rejects_empty_name(self):
        with self.assertRaisesRegex(ValueError, "name must be"):
            Principal(principal_id="p-1", name="")

    def test_rejects_non_string_name(self):
        with self.assertRaisesRegex(ValueError, "name must be"):
            Principal(principal_id="p-1", name=None)

    def test_is_immutable(self):
        principal = Principal(principal_id="p-1", name="Test Principal")

        with self.assertRaises(AttributeError):
            principal.name = "Changed"


class GenerateApiKeyTests(unittest.TestCase):
    def test_returns_key_id_secret_and_composed_token(self):
        issued = generate_api_key()

        self.assertIsInstance(issued, IssuedApiKey)
        self.assertEqual(issued.token, f"{issued.key_id}.{issued.secret}")

    def test_key_id_meets_minimum_entropy_derived_length(self):
        issued = generate_api_key()

        self.assertGreaterEqual(len(issued.key_id), 16)

    def test_secret_meets_minimum_entropy_derived_length(self):
        issued = generate_api_key()

        self.assertGreaterEqual(len(issued.secret), 43)

    def test_generated_token_is_parseable(self):
        issued = generate_api_key()

        parsed = parse_api_key(issued.token)

        self.assertEqual(parsed.key_id, issued.key_id)
        self.assertEqual(parsed.secret, issued.secret)

    def test_rejects_too_few_key_id_bytes(self):
        with self.assertRaisesRegex(ValueError, "key_id_bytes"):
            generate_api_key(key_id_bytes=3)

    def test_rejects_too_few_secret_bytes(self):
        with self.assertRaisesRegex(ValueError, "at least 16"):
            generate_api_key(secret_bytes=8)

    def test_repr_redacts_secret_and_token(self):
        issued = generate_api_key()

        self.assertNotIn(issued.secret, repr(issued))
        self.assertNotIn(issued.token, repr(issued))
        self.assertIn(issued.key_id, repr(issued))

    def test_is_immutable(self):
        issued = generate_api_key()

        with self.assertRaises(AttributeError):
            issued.secret = "changed"


class IssuedApiKeyValidationTests(unittest.TestCase):
    def test_rejects_empty_key_id(self):
        with self.assertRaisesRegex(ValueError, "key_id"):
            IssuedApiKey(key_id="", secret="valid-secret", token=".valid-secret")

    def test_rejects_blank_key_id(self):
        with self.assertRaisesRegex(ValueError, "key_id"):
            IssuedApiKey(
                key_id="   ", secret="valid-secret", token="   .valid-secret"
            )

    def test_rejects_key_id_with_invalid_characters(self):
        with self.assertRaisesRegex(ValueError, "key_id"):
            IssuedApiKey(
                key_id="bad id!",
                secret="valid-secret",
                token="bad id!.valid-secret",
            )

    def test_rejects_empty_secret(self):
        with self.assertRaisesRegex(ValueError, "secret"):
            IssuedApiKey(key_id="valid-key-id", secret="", token="valid-key-id.")

    def test_rejects_secret_with_invalid_characters(self):
        with self.assertRaisesRegex(ValueError, "secret"):
            IssuedApiKey(
                key_id="valid-key-id",
                secret="bad secret!",
                token="valid-key-id.bad secret!",
            )

    def test_rejects_token_inconsistent_with_key_id_and_secret(self):
        with self.assertRaisesRegex(ValueError, "inconsistent"):
            IssuedApiKey(
                key_id="valid-key-id",
                secret="valid-secret",
                token="valid-key-id.a-different-secret",
            )


class ParsedApiKeyValidationTests(unittest.TestCase):
    def test_rejects_empty_key_id(self):
        with self.assertRaisesRegex(ValueError, "key_id"):
            ParsedApiKey(key_id="", secret="valid-secret")

    def test_rejects_key_id_with_invalid_characters(self):
        with self.assertRaisesRegex(ValueError, "key_id"):
            ParsedApiKey(key_id="bad id!", secret="valid-secret")

    def test_rejects_empty_secret(self):
        with self.assertRaisesRegex(ValueError, "secret"):
            ParsedApiKey(key_id="valid-key-id", secret="")

    def test_rejects_secret_with_invalid_characters(self):
        with self.assertRaisesRegex(ValueError, "secret"):
            ParsedApiKey(key_id="valid-key-id", secret="bad secret!")


class ParseApiKeyTests(unittest.TestCase):
    def test_round_trips_a_generated_credential(self):
        issued = generate_api_key()

        parsed = parse_api_key(issued.token)

        self.assertEqual(parsed.key_id, issued.key_id)
        self.assertEqual(parsed.secret, issued.secret)

    def test_rejects_empty_token(self):
        with self.assertRaisesRegex(ValueError, "non-empty string"):
            parse_api_key("")

    def test_rejects_blank_token(self):
        with self.assertRaisesRegex(ValueError, "non-empty string"):
            parse_api_key("   ")

    def test_rejects_non_string_token(self):
        with self.assertRaisesRegex(ValueError, "non-empty string"):
            parse_api_key(None)

    def test_rejects_token_without_separator(self):
        with self.assertRaisesRegex(ValueError, "exactly one"):
            parse_api_key("no-separator-here")

    def test_rejects_token_with_multiple_separators(self):
        with self.assertRaisesRegex(ValueError, "exactly one"):
            parse_api_key("abc.def.ghi")

    def test_rejects_token_with_empty_key_id(self):
        with self.assertRaisesRegex(ValueError, "key_id"):
            parse_api_key(".secret-only")

    def test_rejects_token_with_empty_secret(self):
        with self.assertRaisesRegex(ValueError, "secret"):
            parse_api_key("key-id-only.")

    def test_rejects_token_with_blank_key_id(self):
        with self.assertRaisesRegex(ValueError, "key_id"):
            parse_api_key("   .secret-value")

    def test_rejects_key_id_with_invalid_characters(self):
        with self.assertRaisesRegex(ValueError, "key_id"):
            parse_api_key("bad id!.secret-value")

    def test_rejects_secret_with_invalid_characters(self):
        with self.assertRaisesRegex(ValueError, "secret"):
            parse_api_key("key-id.bad secret!")

    def test_repr_redacts_secret(self):
        parsed = parse_api_key("abc.super-secret-value")

        self.assertNotIn("super-secret-value", repr(parsed))
        self.assertIn("abc", repr(parsed))


class HashAndVerifyApiKeyTests(unittest.TestCase):
    def test_accepts_the_correct_secret(self):
        verifier = hash_api_key("correct-horse-battery-staple", salt=b"\x00" * 16)

        self.assertTrue(verify_api_key("correct-horse-battery-staple", verifier))

    def test_rejects_an_incorrect_secret(self):
        verifier = hash_api_key("correct-horse-battery-staple", salt=b"\x00" * 16)

        self.assertFalse(verify_api_key("wrong-secret", verifier))

    def test_rejects_empty_secret_during_verification(self):
        verifier = hash_api_key("correct-horse-battery-staple", salt=b"\x00" * 16)

        self.assertFalse(verify_api_key("", verifier))

    def test_rejects_empty_secret_during_hashing(self):
        with self.assertRaisesRegex(ValueError, "non-empty string"):
            hash_api_key("")

    def test_rejects_blank_secret_during_hashing(self):
        with self.assertRaisesRegex(ValueError, "non-empty string"):
            hash_api_key("   ")

    def test_rejects_bytearray_salt_argument(self):
        with self.assertRaisesRegex(ValueError, "salt must be bytes"):
            hash_api_key("some-secret", salt=bytearray(16))

    def test_hashing_is_deterministic_given_the_same_salt(self):
        first = hash_api_key("same-secret", salt=b"\x01" * 16)
        second = hash_api_key("same-secret", salt=b"\x01" * 16)

        self.assertEqual(first.digest, second.digest)
        self.assertEqual(first.salt, second.salt)

    def test_matches_an_independently_computed_hmac(self):
        salt = b"\x00" * 16
        secret = "correct-horse-battery-staple"

        verifier = hash_api_key(secret, salt=salt)

        expected_digest = hmac.new(
            salt, secret.encode("utf-8"), hashlib.sha256
        ).digest()
        self.assertEqual(verifier.digest, expected_digest)
        self.assertEqual(verifier.scheme, "hmac-sha256-v1")

    def test_secret_from_one_credential_does_not_verify_against_another(self):
        verifier_for_first = hash_api_key("first-secret-value", salt=b"\x00" * 16)

        self.assertFalse(verify_api_key("second-secret-value", verifier_for_first))

    def test_never_stores_the_plaintext_secret(self):
        verifier = hash_api_key("super-secret-value", salt=b"\x02" * 16)

        self.assertFalse(hasattr(verifier, "secret"))
        self.assertFalse(hasattr(verifier, "api_key"))
        self.assertNotIn("super-secret-value", repr(verifier))

    def test_repr_redacts_salt_and_digest(self):
        verifier = hash_api_key("another-secret", salt=b"\x03" * 16)

        self.assertNotIn(repr(verifier.salt), repr(verifier))
        self.assertIn("redacted", repr(verifier))

    def test_is_immutable(self):
        verifier = hash_api_key("another-secret", salt=b"\x03" * 16)

        with self.assertRaises(AttributeError):
            verifier.digest = b"\x00" * 32


class ApiKeyVerifierValidationTests(unittest.TestCase):
    def test_rejects_unsupported_scheme(self):
        with self.assertRaisesRegex(ValueError, "Unsupported or missing"):
            ApiKeyVerifier(
                scheme="md5-v0",
                salt=b"\x00" * 16,
                digest=b"\x00" * 32,
            )

    def test_rejects_salt_shorter_than_minimum(self):
        with self.assertRaisesRegex(ValueError, "at least 16 bytes"):
            ApiKeyVerifier(
                scheme="hmac-sha256-v1",
                salt=b"\x00" * 8,
                digest=b"\x00" * 32,
            )

    def test_rejects_digest_of_wrong_length(self):
        with self.assertRaisesRegex(ValueError, "exactly 32 bytes"):
            ApiKeyVerifier(
                scheme="hmac-sha256-v1",
                salt=b"\x00" * 16,
                digest=b"\x00" * 16,
            )

    def test_rejects_non_bytes_salt(self):
        with self.assertRaisesRegex(ValueError, "salt must be bytes"):
            ApiKeyVerifier(
                scheme="hmac-sha256-v1",
                salt="not-bytes",
                digest=b"\x00" * 32,
            )

    def test_rejects_bytearray_salt(self):
        with self.assertRaisesRegex(ValueError, "salt must be bytes"):
            ApiKeyVerifier(
                scheme="hmac-sha256-v1",
                salt=bytearray(16),
                digest=b"\x00" * 32,
            )

    def test_rejects_non_bytes_digest(self):
        with self.assertRaisesRegex(ValueError, "digest must be bytes"):
            ApiKeyVerifier(
                scheme="hmac-sha256-v1",
                salt=b"\x00" * 16,
                digest="not-bytes",
            )

    def test_rejects_bytearray_digest(self):
        with self.assertRaisesRegex(ValueError, "digest must be bytes"):
            ApiKeyVerifier(
                scheme="hmac-sha256-v1",
                salt=b"\x00" * 16,
                digest=bytearray(32),
            )

    def test_verify_rejects_unsupported_scheme_without_raising(self):
        # Bypass normal construction validation only to prove verify_api_key
        # itself explicitly gates on scheme rather than trusting the caller.
        verifier = ApiKeyVerifier(
            scheme="hmac-sha256-v1",
            salt=b"\x00" * 16,
            digest=b"\x00" * 32,
        )
        object.__setattr__(verifier, "scheme", "unknown-future-scheme")

        self.assertFalse(verify_api_key("anything", verifier))


if __name__ == "__main__":
    unittest.main()
