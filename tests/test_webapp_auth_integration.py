import base64
import gzip
import http.client
import importlib.util
import signal
import socket
import sys
import tempfile
import threading
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


class NullLogger:
    info_messages = []
    warning_messages = []
    error_messages = []

    def __init__(self, *_args, **_kwargs):
        pass

    def info(self, message):
        type(self).info_messages.append(message)

    def warning(self, message):
        type(self).warning_messages.append(message)

    def error(self, message):
        type(self).error_messages.append(message)


class DummyWebUtils:
    post_calls = 0

    def __init__(self, shared_data, logger):
        self.shared_data = shared_data
        self.logger = logger

    def save_configuration(self, handler):
        type(self).post_calls += 1
        content_length = int(handler.headers.get("Content-Length", 0))
        if content_length:
            handler.rfile.read(content_length)
        handler.send_response(200)
        handler.end_headers()


class WebAppAuthIntegrationTests(unittest.TestCase):
    WEBAPP_MODULE_NAME = "_bjorn_webapp_under_test"
    GET_ROUTES = (
        "/",
        "/index.html",
        "/config.html",
        "/actions.html",
        "/network.html",
        "/netkb.html",
        "/bjorn.html",
        "/loot.html",
        "/credentials.html",
        "/manual.html",
        "/load_config",
        "/restore_default_config",
        "/get_web_delay",
        "/scan_wifi",
        "/network_data",
        "/netkb_data",
        "/netkb_data_json",
        "/screen.png",
        "/favicon.ico",
        "/manifest.json",
        "/apple-touch-icon",
        "/get_logs",
        "/list_credentials",
        "/list_files",
        "/download_file",
        "/download_backup",
        "/styles.css",
    )
    POST_ROUTES = (
        "/save_config",
        "/connect_wifi",
        "/disconnect_wifi",
        "/clear_files",
        "/clear_files_light",
        "/initialize_csv",
        "/reboot",
        "/shutdown",
        "/restart_bjorn_service",
        "/backup",
        "/restore",
        "/stop_orchestrator",
        "/start_orchestrator",
        "/execute_manual_attack",
    )

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        temp_path = Path(self.temp_dir.name)
        web_dir = temp_path / "web"
        web_dir.mkdir()
        (web_dir / "index.html").write_text(
            "<html><body>Bjorn test page</body></html>",
            encoding="utf-8",
        )

        self.shared_data = SimpleNamespace(
            webdir=str(web_dir),
            web_auth_file=str(temp_path / "web_auth.json"),
            webapp_should_exit=False,
            web_delay=1,
        )
        init_shared = types.ModuleType("init_shared")
        init_shared.shared_data = self.shared_data
        utils = types.ModuleType("utils")
        utils.WebUtils = DummyWebUtils
        logger = types.ModuleType("logger")
        logger.Logger = NullLogger

        self.module_patch = patch.dict(
            sys.modules,
            {
                "init_shared": init_shared,
                "utils": utils,
                "logger": logger,
            },
        )
        self.module_patch.start()
        sys.modules.pop(self.WEBAPP_MODULE_NAME, None)

        self.previous_sigint = signal.getsignal(signal.SIGINT)
        self.previous_sigterm = signal.getsignal(signal.SIGTERM)
        webapp_path = Path(__file__).resolve().parents[1] / "webapp.py"
        module_spec = importlib.util.spec_from_file_location(
            self.WEBAPP_MODULE_NAME,
            webapp_path,
        )
        if module_spec is None or module_spec.loader is None:
            self.fail(f"Cannot load web application from {webapp_path}")
        self.webapp = importlib.util.module_from_spec(module_spec)
        sys.modules[self.WEBAPP_MODULE_NAME] = self.webapp
        module_spec.loader.exec_module(self.webapp)

        self.server = self.webapp.ReusableTCPServer(
            ("127.0.0.1", 0),
            self.webapp.CustomHandler,
        )
        self.server.daemon_threads = True
        self.server_thread = threading.Thread(
            target=self.server.serve_forever,
            daemon=True,
        )
        self.server_thread.start()
        self.port = self.server.server_address[1]
        DummyWebUtils.post_calls = 0
        NullLogger.info_messages = []
        NullLogger.warning_messages = []
        NullLogger.error_messages = []

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.server_thread.join(timeout=3)
        signal.signal(signal.SIGINT, self.previous_sigint)
        signal.signal(signal.SIGTERM, self.previous_sigterm)
        sys.modules.pop(self.WEBAPP_MODULE_NAME, None)
        self.module_patch.stop()
        self.temp_dir.cleanup()

    @staticmethod
    def authorization_header(username, password):
        encoded = base64.b64encode(
            f"{username}:{password}".encode("utf-8")
        ).decode("ascii")
        return f"Basic {encoded}"

    def request(self, method, path, authorization=None, body=None):
        headers = {}
        if authorization is not None:
            headers["Authorization"] = authorization
        if body is not None:
            headers["Content-Type"] = "application/json"
            headers["Content-Length"] = str(len(body))

        connection = http.client.HTTPConnection(
            "127.0.0.1",
            self.port,
            timeout=5,
        )
        try:
            connection.request(
                method,
                path,
                body=body,
                headers=headers,
            )
            response = connection.getresponse()
            response_body = response.read()
            return response.status, dict(response.getheaders()), response_body
        finally:
            connection.close()

    def enable_authentication(self):
        self.webapp.credential_store.save(
            "bjornadmin",
            "correct horse battery staple",
        )
        return self.authorization_header(
            "bjornadmin",
            "correct horse battery staple",
        )

    def test_no_credentials_preserve_current_open_behavior(self):
        status, headers, body = self.request("GET", "/")

        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Encoding"], "gzip")
        self.assertIn(b"Bjorn test page", gzip.decompress(body))

    def test_real_http_challenge_rejects_wrong_and_accepts_valid_login(self):
        valid_header = self.enable_authentication()

        status, headers, _ = self.request("GET", "/")
        self.assertEqual(status, 401)
        self.assertIn("Basic realm=", headers["WWW-Authenticate"])

        wrong_header = self.authorization_header("bjornadmin", "wrong")
        status, _, _ = self.request("GET", "/", wrong_header)
        self.assertEqual(status, 401)

        status, _, body = self.request("GET", "/", valid_header)
        self.assertEqual(status, 200)
        self.assertIn(b"Bjorn test page", gzip.decompress(body))

    def test_expected_challenge_is_silent_but_invalid_header_is_warned(self):
        self.enable_authentication()

        status, _, _ = self.request(
            "GET",
            "/index.html?cache-bust=expected-challenge",
        )
        self.assertEqual(status, 401)
        self.assertEqual(NullLogger.warning_messages, [])

        status, _, _ = self.request(
            "GET",
            "/index.html?private-value=must-not-be-logged",
            authorization="Basic not-base64",
        )
        self.assertEqual(status, 401)
        self.assertEqual(len(NullLogger.warning_messages), 1)
        warning = NullLogger.warning_messages[0]
        self.assertIn(
            "Rejected invalid web credentials for GET /index.html",
            warning,
        )
        self.assertIn("from 127.0.0.1", warning)
        self.assertNotIn("private-value", warning)

    def test_read_only_access_logs_are_suppressed_but_errors_remain(self):
        status, _, _ = self.request("GET", "/")
        self.assertEqual(status, 200)

        status, _, body = self.request("HEAD", "/")
        self.assertEqual(status, 200)
        self.assertEqual(body, b"")
        self.assertEqual(NullLogger.info_messages, [])

        status, _, _ = self.request("GET", "/missing")
        self.assertEqual(status, 404)
        status, _, body = self.request("HEAD", "/missing")
        self.assertEqual(status, 404)
        self.assertEqual(body, b"")

        self.assertEqual(len(NullLogger.info_messages), 2)
        for message in NullLogger.info_messages:
            self.assertIn("code 404, message File not found", message)
            self.assertNotIn('"GET /missing', message)
            self.assertNotIn('"HEAD /missing', message)

    def test_post_path_containing_get_is_still_logged(self):
        status, _, _ = self.request("POST", "/GET")

        self.assertEqual(status, 404)
        self.assertEqual(len(NullLogger.info_messages), 1)
        self.assertIn(
            '"POST /GET HTTP/1.1" 404',
            NullLogger.info_messages[0],
        )

    def test_post_challenge_does_not_wait_for_an_unsent_request_body(self):
        self.enable_authentication()
        request_headers = (
            "POST /save_config HTTP/1.1\r\n"
            f"Host: 127.0.0.1:{self.port}\r\n"
            "Content-Type: application/json\r\n"
            "Content-Length: 1048576\r\n"
            "Connection: keep-alive\r\n"
            "\r\n"
        ).encode("ascii")

        client = socket.create_connection(
            ("127.0.0.1", self.port),
            timeout=2,
        )
        try:
            client.settimeout(2)
            client.sendall(request_headers)
            response = client.recv(4096)
        finally:
            client.close()

        self.assertIn(b" 401 ", response)
        self.assertIn(b"Connection: close\r\n", response)
        self.assertEqual(DummyWebUtils.post_calls, 0)

    def test_head_post_and_private_file_are_protected(self):
        valid_header = self.enable_authentication()

        status, _, body = self.request("HEAD", "/")
        self.assertEqual(status, 401)
        self.assertEqual(body, b"")

        status, _, _ = self.request("POST", "/save_config", body=b"{}")
        self.assertEqual(status, 401)
        self.assertEqual(DummyWebUtils.post_calls, 0)

        status, _, _ = self.request(
            "POST",
            "/save_config",
            authorization=valid_header,
            body=b"{}",
        )
        self.assertEqual(status, 200)
        self.assertEqual(DummyWebUtils.post_calls, 1)

        status, _, _ = self.request(
            "GET",
            "/config%2Fweb_auth.json",
            authorization=valid_header,
        )
        self.assertEqual(status, 404)

    def test_every_known_route_requires_authentication(self):
        self.enable_authentication()

        for route in self.GET_ROUTES:
            with self.subTest(method="GET", route=route):
                status, _, _ = self.request("GET", route)
                self.assertEqual(status, 401)

        for route in self.POST_ROUTES:
            with self.subTest(method="POST", route=route):
                status, _, _ = self.request("POST", route, body=b"{}")
                self.assertEqual(status, 401)

        status, _, body = self.request("HEAD", "/")
        self.assertEqual(status, 401)
        self.assertEqual(body, b"")

        status, _, _ = self.request("GET", "/config/web_auth.json")
        self.assertEqual(status, 404)

    def test_server_socket_allows_immediate_port_reuse(self):
        self.assertTrue(self.webapp.ReusableTCPServer.allow_reuse_address)

    def test_web_thread_has_stable_name(self):
        web_thread = self.webapp.WebThread(
            handler_class=self.webapp.CustomHandler,
            port=0,
        )

        self.assertEqual(web_thread.name, "BjornWeb")

    def test_web_thread_shutdown_matches_manual_request_loop(self):
        class FakeServer:
            def __init__(self):
                self.close_calls = 0
                self.shutdown_calls = 0

            def server_close(self):
                self.close_calls += 1

            def shutdown(self):
                self.shutdown_calls += 1

        web_thread = self.webapp.WebThread(
            handler_class=self.webapp.CustomHandler,
            port=0,
        )
        fake_server = FakeServer()
        web_thread.httpd = fake_server

        web_thread.shutdown()

        self.assertTrue(self.shared_data.webapp_should_exit)
        self.assertEqual(fake_server.close_calls, 1)
        self.assertEqual(fake_server.shutdown_calls, 0)

    def test_web_thread_exits_promptly_after_shutdown_flag(self):
        web_thread = self.webapp.WebThread(
            handler_class=self.webapp.CustomHandler,
            port=0,
        )
        web_thread.start()

        for _ in range(100):
            if web_thread.httpd is not None:
                break
            threading.Event().wait(0.01)
        self.assertIsNotNone(web_thread.httpd)

        self.shared_data.webapp_should_exit = True
        web_thread.join(timeout=1.5)

        self.assertFalse(web_thread.is_alive())
        self.assertEqual(NullLogger.error_messages, [])


if __name__ == "__main__":
    unittest.main()
