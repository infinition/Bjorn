"""Regression tests for the combined transactional installer."""

import re
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
INSTALLER_PATH = PROJECT_DIR / "install_stability_web_auth.sh"


class CombinedInstallerTests(unittest.TestCase):
    """Keep deployment and recovery ordering explicit and reviewable."""

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

    def test_port_readiness_is_verified_with_a_real_bind_probe(self):
        body = self.function_body("wait_for_web_port_release")
        self.assertIn("probe.bind((\"\", port))", body)
        self.assertIn("socket.SO_REUSEADDR", body)
        self.assertNotIn("return 0\n    fi", body)

    def test_failed_deployment_stops_before_overwriting_recovery_files(self):
        body = self.function_body("on_exit")
        stop_position = body.index("stop_before_restore")
        restore_position = body.index("restore_snapshot")
        start_position = body.index("start_and_verify")
        self.assertLess(stop_position, restore_position)
        self.assertLess(restore_position, start_position)

    def test_recovery_requires_process_exit_before_file_restore(self):
        body = self.function_body("stop_before_restore")
        self.assertIn("systemctl is-active --quiet", body)
        self.assertIn("pgrep -f", body)
        self.assertIn("refusing to restore files", body)

    def test_startup_verification_checks_service_and_expected_http(self):
        body = self.function_body("start_and_verify")
        self.assertIn("must be inactive before startup", body)
        self.assertIn("systemctl is-active --quiet", body)
        self.assertIn('HTTP_STATUS" != "200"', body)
        self.assertIn('HTTP_STATUS" != "401"', body)

    def test_human_output_keeps_statuses_and_machine_markers(self):
        self.assertIn('${NO_COLOR:-}', self.installer)
        for function_name in (
            "banner",
            "step",
            "info",
            "success",
            "warning",
            "error",
            "summary_row",
            "complete",
        ):
            self.function_body(function_name)
        self.assertIn("Machine marker: INSTALL_OK", self.installer)
        self.assertIn("Machine marker: RESTORE_OK", self.installer)
        self.assertIn("Machine marker: RECOVERY_OK", self.installer)


if __name__ == "__main__":
    unittest.main()
