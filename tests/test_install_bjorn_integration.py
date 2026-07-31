"""Regression tests for fresh-install integration and its safe plan view."""

import re
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
INSTALLER_PATH = PROJECT_DIR / "install_bjorn.sh"


class FreshInstallerIntegrationTests(unittest.TestCase):
    """Keep optional authentication visible and safe during fresh installs."""

    @classmethod
    def setUpClass(cls):
        cls.installer = INSTALLER_PATH.read_text(encoding="utf-8")

    def function_body(self, name):
        match = re.search(
            rf"^{re.escape(name)}\(\) \{{\n(?P<body>.*?)^\}}\n",
            self.installer,
            flags=re.MULTILINE | re.DOTALL,
        )
        self.assertIsNotNone(match, f"missing shell function: {name}")
        return match.group("body")

    def test_full_install_has_nine_ordered_steps(self):
        expected_steps = (
            "Checking system compatibility",
            "Installing system dependencies",
            "Configuring system limits",
            "Configuring interfaces",
            "Setting up BJORN",
            "Installing optional web-authentication tools",
            "Configuring USB Gadget",
            "Setting up services",
            "Verifying installation",
        )
        positions = [self.installer.index(f'"{step}"') for step in expected_steps]
        self.assertEqual(positions, sorted(positions))
        self.assertIn('TOTAL_STEPS="${#FULL_INSTALL_STEPS[@]}"', self.installer)

    def test_authentication_password_is_prompted_by_python_not_shell(self):
        body = self.function_body("configure_web_auth")
        self.assertRegex(
            body,
            r'configure_web_auth\.py"\s*\\\s*set "\$web_username"',
        )
        self.assertNotIn("read -s", body)
        self.assertIn('chmod 600 "$BJORN_PATH/config/web_auth.json"', body)

    def test_fresh_install_makes_management_command_optional(self):
        setup_body = self.function_body("setup_bjorn")
        auth_body = self.function_body("configure_web_auth")
        self.assertNotIn("/usr/local/sbin/http_auth", setup_body)
        self.assertIn("Install the http_auth management command?", auth_body)
        self.assertIn("HTTP_AUTH_COMMAND_PATH", auth_body)
        self.assertIn(
            'chmod 755 "$BJORN_PATH/configure_web_auth.py"',
            auth_body,
        )
        self.assertIn("sudo http_auth set <username>", auth_body)

    def test_show_plan_exits_before_log_or_system_changes(self):
        show_plan_position = self.installer.index("--show-plan)")
        log_directory_position = self.installer.index(
            'LOG_DIR="${LOG_DIR:-/var/log/bjorn_install}"'
        )
        self.assertLess(show_plan_position, log_directory_position)

    def test_installer_can_be_sourced_for_isolated_integration_testing(self):
        self.assertIn(
            'if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then\n    main "$@"',
            self.installer,
        )
        self.assertIn(
            'HTTP_AUTH_COMMAND_PATH="${HTTP_AUTH_COMMAND_PATH:-'
            '/usr/local/sbin/http_auth}"',
            self.installer,
        )

    def test_credential_failure_has_a_real_retry_loop(self):
        body = self.function_body("configure_web_auth")
        self.assertIn("while true; do", body)
        self.assertIn("Retry credential setup? (Y/n):", body)
        self.assertLess(
            body.index('if python3 "$BJORN_PATH/configure_web_auth.py"'),
            body.index('chown "$BJORN_USER:$BJORN_USER"'),
        )

    def test_generic_required_failure_aborts_instead_of_fake_retry(self):
        body = self.function_body("handle_error")
        self.assertNotIn("Retry this step", body)
        self.assertIn('clean_exit "$error_code"', body)

    def test_fresh_install_starts_and_strictly_verifies_service(self):
        services_body = self.function_body("setup_services")
        verify_body = self.function_body("verify_installation")
        self.assertIn("systemctl restart bjorn.service", services_body)
        self.assertIn('http_status" == "200"', verify_body)
        self.assertIn('http_status" == "401"', verify_body)
        self.assertIn('log "ERROR" "BJORN service is not running"', verify_body)
        self.assertIn('return "$verification_failed"', verify_body)


if __name__ == "__main__":
    unittest.main()
