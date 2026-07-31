import base64
import json
import tempfile
import unittest
from pathlib import Path

from web_auth import (
    BasicAuthGate,
    CredentialError,
    CredentialStore,
    is_credential_file_request,
)


class WebAuthTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.credential_file = Path(self.temp_dir.name) / "web_auth.json"
        self.store = CredentialStore(self.credential_file)

    def tearDown(self):
        self.temp_dir.cleanup()

    @staticmethod
    def authorization_header(username, password):
        payload = base64.b64encode(
            f"{username}:{password}".encode("utf-8")
        ).decode("ascii")
        return f"Basic {payload}"

    def test_missing_credentials_leave_authentication_disabled(self):
        self.assertFalse(self.store.auth_required())
        self.assertFalse(self.store.is_configured())

    def test_credentials_are_hashed_and_valid_login_is_accepted(self):
        self.store.save("bjornadmin", "correct horse battery staple")
        gate = BasicAuthGate(self.store)

        stored_record = json.loads(self.credential_file.read_text("utf-8"))
        self.assertNotIn("correct horse battery staple", str(stored_record))
        self.assertEqual(stored_record["algorithm"], "scrypt")
        self.assertTrue(self.store.auth_required())
        self.assertTrue(
            gate.is_authorized(
                self.authorization_header(
                    "bjornadmin",
                    "correct horse battery staple",
                )
            )
        )

    def test_invalid_headers_and_credentials_are_rejected(self):
        self.store.save("bjornadmin", "correct horse battery staple")
        gate = BasicAuthGate(self.store)

        self.assertFalse(gate.is_authorized(None))
        self.assertFalse(gate.is_authorized("Bearer token"))
        self.assertFalse(gate.is_authorized("Basic not-base64"))
        self.assertFalse(
            gate.is_authorized(
                self.authorization_header("bjornadmin", "wrong password")
            )
        )
        self.assertFalse(
            gate.is_authorized(
                self.authorization_header(
                    "wrong-user",
                    "correct horse battery staple",
                )
            )
        )

    def test_successful_header_is_cached_until_credentials_change(self):
        self.store.save("bjornadmin", "correct horse battery staple")

        class CountingStore(CredentialStore):
            def __init__(self, path):
                super().__init__(path)
                self.verify_calls = 0

            def verify(self, username, password):
                self.verify_calls += 1
                return super().verify(username, password)

        counting_store = CountingStore(self.credential_file)
        gate = BasicAuthGate(counting_store)
        header = self.authorization_header(
            "bjornadmin",
            "correct horse battery staple",
        )

        self.assertTrue(gate.is_authorized(header))
        self.assertTrue(gate.is_authorized(header))
        self.assertEqual(counting_store.verify_calls, 1)

        counting_store.save("bjornadmin", "new correct horse password")
        self.assertFalse(gate.is_authorized(header))
        self.assertEqual(counting_store.verify_calls, 2)

    def test_authentication_can_be_disabled_without_deleting_credentials(self):
        self.store.save("bjornadmin", "correct horse battery staple")
        self.store.set_enabled(False)

        self.assertTrue(self.store.is_configured())
        self.assertFalse(self.store.auth_required())
        self.store.set_enabled(True)
        self.assertTrue(self.store.auth_required())

    def test_corrupt_existing_credential_file_fails_closed(self):
        self.credential_file.write_text("{not-json", encoding="utf-8")

        self.assertTrue(self.store.auth_required())
        self.assertFalse(self.store.is_configured())

    def test_malformed_hash_parameters_fail_closed(self):
        self.credential_file.write_text(
            json.dumps(
                {
                    "version": 1,
                    "enabled": True,
                    "username": "bjornadmin",
                    "algorithm": "scrypt",
                    "salt": "invalid",
                    "password_hash": "invalid",
                    "scrypt": {"n": "not-a-number", "r": 8, "p": 1},
                }
            ),
            encoding="utf-8",
        )

        self.assertTrue(self.store.auth_required())
        self.assertFalse(self.store.is_configured())

    def test_short_password_is_rejected(self):
        with self.assertRaises(CredentialError):
            self.store.save("bjornadmin", "too-short")

    def test_credential_file_path_cannot_be_requested_as_static_content(self):
        protected_paths = [
            "/config/web_auth.json",
            "//config/web_auth.json",
            "/config/../config/web_auth.json",
            "/config%2Fweb_auth.json?download=1",
            r"/config\web_auth.json",
        ]
        for path in protected_paths:
            with self.subTest(path=path):
                self.assertTrue(is_credential_file_request(path))

        self.assertFalse(is_credential_file_request("/config.html"))


if __name__ == "__main__":
    unittest.main()
