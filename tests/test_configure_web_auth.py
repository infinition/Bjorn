import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import configure_web_auth
from web_auth import CredentialStore


class ConfigureWebAuthTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.credential_file = Path(self.temp_dir.name) / "web_auth.json"
        self.file_patch = patch.object(
            configure_web_auth,
            "CREDENTIAL_FILE",
            self.credential_file,
        )
        self.file_patch.start()

    def tearDown(self):
        self.file_patch.stop()
        self.temp_dir.cleanup()

    def run_command(self, arguments, standard_input=""):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            patch("sys.stdin", io.StringIO(standard_input)),
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            result = configure_web_auth.main(arguments)
        return result, stdout.getvalue(), stderr.getvalue()

    def test_password_stdin_sets_hashed_credentials(self):
        result, stdout, stderr = self.run_command(
            ["set", "validation-user", "--password-stdin"],
            "temporary validation password\n",
        )

        self.assertEqual(result, 0)
        self.assertEqual(stderr, "")
        self.assertIn("validation-user", stdout)
        store = CredentialStore(self.credential_file)
        self.assertTrue(
            store.verify(
                "validation-user",
                "temporary validation password",
            )
        )
        self.assertNotIn(
            "temporary validation password",
            self.credential_file.read_text(encoding="utf-8"),
        )

    def test_empty_password_stdin_is_rejected(self):
        result, _, stderr = self.run_command(
            ["set", "validation-user", "--password-stdin"],
        )

        self.assertEqual(result, 1)
        self.assertIn("No password was provided", stderr)
        self.assertFalse(self.credential_file.exists())

    def test_status_disable_and_enable_commands(self):
        self.run_command(
            ["set", "validation-user", "--password-stdin"],
            "temporary validation password\n",
        )

        result, stdout, _ = self.run_command(["status"])
        self.assertEqual(result, 0)
        self.assertIn("Credentials configured: yes", stdout)
        self.assertIn("Authentication enabled: yes", stdout)

        result, _, _ = self.run_command(["disable"])
        self.assertEqual(result, 0)
        self.assertFalse(CredentialStore(self.credential_file).auth_required())

        result, _, _ = self.run_command(["enable"])
        self.assertEqual(result, 0)
        self.assertTrue(CredentialStore(self.credential_file).auth_required())


if __name__ == "__main__":
    unittest.main()
