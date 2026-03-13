#webapp.py 
import json
import threading
import http.server
import socketserver
import logging
import sys
import signal
import os
import gzip
import io
from logger import Logger
from init_shared import shared_data
from utils import WebUtils

# Initialize the logger
logger = Logger(name="webapp.py", level=logging.DEBUG)

# Set the path to the favicon
favicon_path = os.path.join(shared_data.webdir, 'images', 'favicon.ico')
shared_web_utils = WebUtils(shared_data, logger)
PROTECTED_GET_PATHS = {
    "/restore_default_config",
    "/get_logs",
    "/list_credentials",
}
PROTECTED_GET_PREFIXES = {
    "/list_files",
    "/download_file",
    "/download_backup",
}
PROTECTED_POST_PATHS = {
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
}


class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True

class CustomHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        self.shared_data = shared_data
        self.web_utils = shared_web_utils
        super().__init__(*args, **kwargs)

    def get_connectivity_state(self):
        return self.web_utils.get_connectivity_state()

    def is_setup_auth_required(self, connectivity_state=None):
        if connectivity_state is None:
            connectivity_state = self.get_connectivity_state()

        try:
            local_address = self.connection.getsockname()[0]
        except OSError:
            local_address = ""

        protected_addresses = {
            connectivity_state.get("setup_ap_ip"),
            connectivity_state.get("bluetooth_pan_ip"),
        }
        return bool(local_address and local_address in protected_addresses)

    def maybe_require_setup_auth(self, connectivity_state=None):
        if not self.is_setup_auth_required(connectivity_state):
            return True
        if self.web_utils.is_setup_authenticated(self):
            return True

        self.send_response(403)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(
            json.dumps(
                {
                    "status": "error",
                    "message": "Setup authentication is required. Enter the 6-digit code shown on Bjorn's screen.",
                }
            ).encode("utf-8")
        )
        return False

    def log_message(self, format, *args):
        # Override to suppress logging of GET requests.
        if 'GET' not in format % args:
            logger.info("%s - - [%s] %s\n" %
                        (self.client_address[0],
                         self.log_date_time_string(),
                         format % args))

    def gzip_encode(self, content):
        """Gzip compress the given content."""
        out = io.BytesIO()
        with gzip.GzipFile(fileobj=out, mode="w") as f:
            f.write(content)
        return out.getvalue()

    def send_gzipped_response(self, content, content_type):
        """Send a gzipped HTTP response."""
        gzipped_content = self.gzip_encode(content)
        self.send_response(200)
        self.send_header("Content-type", content_type)
        self.send_header("Content-Encoding", "gzip")
        self.send_header("Content-Length", str(len(gzipped_content)))
        self.end_headers()
        self.wfile.write(gzipped_content)

    def serve_file_gzipped(self, file_path, content_type):
        """Serve a file with gzip compression."""
        with open(file_path, 'rb') as file:
            content = file.read()
        self.send_gzipped_response(content, content_type)

    def do_GET(self):
        # Handle GET requests. Serve the HTML interface and the EPD image.
        connectivity_state = self.get_connectivity_state()
        setup_mode_active = connectivity_state.get("provisioning_mode_active")

        if self.path == '/' and setup_mode_active:
            self.serve_file_gzipped(os.path.join(self.shared_data.webdir, 'setup.html'), 'text/html')
        elif self.path == '/index.html' or self.path == '/':
            self.serve_file_gzipped(os.path.join(self.shared_data.webdir, 'index.html'), 'text/html')
        elif self.path == '/setup.html':
            self.serve_file_gzipped(os.path.join(self.shared_data.webdir, 'setup.html'), 'text/html')
        elif self.path == '/config.html':
            self.serve_file_gzipped(os.path.join(self.shared_data.webdir, 'config.html'), 'text/html')
        elif self.path == '/actions.html':
            self.serve_file_gzipped(os.path.join(self.shared_data.webdir, 'actions.html'), 'text/html')
        elif self.path == '/network.html':
            self.serve_file_gzipped(os.path.join(self.shared_data.webdir, 'network.html'), 'text/html')
        elif self.path == '/netkb.html':
            self.serve_file_gzipped(os.path.join(self.shared_data.webdir, 'netkb.html'), 'text/html')
        elif self.path == '/bjorn.html':
            self.serve_file_gzipped(os.path.join(self.shared_data.webdir, 'bjorn.html'), 'text/html')
        elif self.path == '/loot.html':
            self.serve_file_gzipped(os.path.join(self.shared_data.webdir, 'loot.html'), 'text/html')
        elif self.path == '/credentials.html':
            self.serve_file_gzipped(os.path.join(self.shared_data.webdir, 'credentials.html'), 'text/html')
        elif self.path == '/manual.html':
            self.serve_file_gzipped(os.path.join(self.shared_data.webdir, 'manual.html'), 'text/html')
        elif self.path == '/load_config':
            if not self.maybe_require_setup_auth(connectivity_state):
                return
            self.web_utils.serve_current_config(self)
        elif self.path == '/restore_default_config':
            if not self.maybe_require_setup_auth(connectivity_state):
                return
            self.web_utils.restore_default_config(self)
        elif self.path == '/get_web_delay':
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            response = json.dumps({"web_delay": self.shared_data.web_delay})
            self.wfile.write(response.encode('utf-8'))
        elif self.path == '/scan_wifi':
            self.web_utils.scan_wifi(self)
        elif self.path == '/auth/status':
            self.web_utils.serve_setup_auth_status(self, self.is_setup_auth_required(connectivity_state))
        elif self.path == '/connectivity_state':
            self.web_utils.serve_connectivity_state(self)
        elif self.path == '/network_data':
            self.web_utils.serve_network_data(self)
        elif self.path == '/netkb_data':
            self.web_utils.serve_netkb_data(self)
        elif self.path == '/netkb_data_json':
            self.web_utils.serve_netkb_data_json(self)
        elif self.path.startswith('/screen.png'):
            self.web_utils.serve_image(self)
        elif self.path == '/favicon.ico':
            self.web_utils.serve_favicon(self)
        elif self.path == '/manifest.json':
            self.web_utils.serve_manifest(self)
        elif self.path == '/apple-touch-icon':
            self.web_utils.serve_apple_touch_icon(self)
        elif self.path == '/get_logs':
            if not self.maybe_require_setup_auth(connectivity_state):
                return
            self.web_utils.serve_logs(self)
        elif self.path == '/list_credentials':
            if not self.maybe_require_setup_auth(connectivity_state):
                return
            self.web_utils.serve_credentials_data(self)
        elif self.path.startswith('/list_files'):
            if not self.maybe_require_setup_auth(connectivity_state):
                return
            self.web_utils.list_files_endpoint(self)
        elif self.path.startswith('/download_file'):
            if not self.maybe_require_setup_auth(connectivity_state):
                return
            self.web_utils.download_file(self)
        elif self.path.startswith('/download_backup'):
            if not self.maybe_require_setup_auth(connectivity_state):
                return
            self.web_utils.download_backup(self)
        elif self.path in PROTECTED_GET_PATHS or any(
            self.path.startswith(prefix) for prefix in PROTECTED_GET_PREFIXES
        ):
            if not self.maybe_require_setup_auth(connectivity_state):
                return
        else:
            super().do_GET()

    def do_POST(self):
        # Handle POST requests for saving configuration, connecting to Wi-Fi, clearing files, rebooting, and shutting down.
        connectivity_state = self.get_connectivity_state()
        if self.path == '/auth/login':
            self.web_utils.login_setup_auth(self)
            return
        if self.path == '/auth/logout':
            self.web_utils.logout_setup_auth(self)
            return
        if self.path in PROTECTED_POST_PATHS and not self.maybe_require_setup_auth(connectivity_state):
            return

        if self.path == '/save_config':
            self.web_utils.save_configuration(self)
        elif self.path == '/connect_wifi':
            self.web_utils.connect_wifi(self)
        elif self.path == '/disconnect_wifi':  # New route to disconnect Wi-Fi
            self.web_utils.disconnect_and_clear_wifi(self)
        elif self.path == '/clear_files':
            self.web_utils.clear_files(self)
        elif self.path == '/clear_files_light':
            self.web_utils.clear_files_light(self)
        elif self.path == '/initialize_csv':
            self.web_utils.initialize_csv(self)
        elif self.path == '/reboot':
            self.web_utils.reboot_system(self)
        elif self.path == '/shutdown':
            self.web_utils.shutdown_system(self)
        elif self.path == '/restart_bjorn_service':
            self.web_utils.restart_bjorn_service(self)
        elif self.path == '/backup':
            self.web_utils.backup(self)
        elif self.path == '/restore':
            self.web_utils.restore(self)
        elif self.path == '/stop_orchestrator':  # New route to stop the orchestrator
            self.web_utils.stop_orchestrator(self)
        elif self.path == '/start_orchestrator':  # New route to start the orchestrator
            self.web_utils.start_orchestrator(self)
        elif self.path == '/execute_manual_attack':  # New route to execute a manual attack
            self.web_utils.execute_manual_attack(self)
        else:
            self.send_response(404)
            self.end_headers()

class WebThread(threading.Thread):
    """
    Thread to run the web server serving the EPD display interface.
    """
    def __init__(self, handler_class=CustomHandler, port=8000):
        super().__init__()
        self.shared_data = shared_data
        self.port = port
        self.handler_class = handler_class
        self.httpd = None

    def run(self):
        """
        Run the web server in a separate thread.
        """
        while not self.shared_data.webapp_should_exit:
            try:
                with ReusableTCPServer(("", self.port), self.handler_class) as httpd:
                    self.httpd = httpd
                    logger.info(f"Serving at port {self.port}")
                    while not self.shared_data.webapp_should_exit:
                        httpd.handle_request()
            except OSError as e:
                if e.errno == 98:  # Address already in use error
                    logger.warning(f"Port {self.port} is in use, trying the next port...")
                    self.port += 1
                else:
                    logger.error(f"Error in web server: {e}")
                    break
            finally:
                if self.httpd:
                    self.httpd.server_close()
                    logger.info("Web server closed.")

    def shutdown(self):
        """
        Shutdown the web server gracefully.
        """
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            logger.info("Web server shutdown initiated.")


class RedirectHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        if 'GET' not in format % args:
            logger.info("%s - - [%s] %s\n" %
                        (self.client_address[0],
                         self.log_date_time_string(),
                         format % args))

    def build_redirect_url(self):
        connectivity_state = shared_web_utils.get_connectivity_state()
        setup_mode_active = connectivity_state.get("provisioning_mode_active")
        target_path = "/setup.html" if setup_mode_active else "/"
        try:
            local_address = self.connection.getsockname()[0]
        except OSError:
            local_address = ""

        if local_address in {"", "0.0.0.0", "::"}:
            local_address = (
                connectivity_state.get("setup_ap_ip")
                or connectivity_state.get("bluetooth_pan_ip")
                or "127.0.0.1"
            )

        if ":" in local_address and not local_address.startswith("["):
            local_address = f"[{local_address}]"

        return f"http://{local_address}:8000{target_path}"

    def do_GET(self):
        self.send_response(302)
        self.send_header("Location", self.build_redirect_url())
        self.end_headers()

    def do_HEAD(self):
        self.send_response(302)
        self.send_header("Location", self.build_redirect_url())
        self.end_headers()


class RedirectThread(threading.Thread):
    def __init__(self, handler_class=RedirectHandler, port=80):
        super().__init__()
        self.shared_data = shared_data
        self.port = port
        self.handler_class = handler_class
        self.httpd = None

    def run(self):
        while not self.shared_data.webapp_should_exit:
            try:
                with ReusableTCPServer(("", self.port), self.handler_class) as httpd:
                    self.httpd = httpd
                    logger.info(f"Redirect server listening on port {self.port}")
                    while not self.shared_data.webapp_should_exit:
                        httpd.handle_request()
            except OSError as e:
                logger.warning(f"Redirect server unavailable on port {self.port}: {e}")
                break
            finally:
                if self.httpd:
                    self.httpd.server_close()
                    logger.info("Redirect server closed.")

    def shutdown(self):
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            logger.info("Redirect server shutdown initiated.")

def handle_exit_web(signum, frame):
    """
    Handle exit signals to shutdown the web server cleanly.
    """
    shared_data.webapp_should_exit = True
    if web_thread.is_alive():
        web_thread.shutdown()
        web_thread.join()  # Wait until the web_thread is finished
    if redirect_thread.is_alive():
        redirect_thread.shutdown()
        redirect_thread.join()
    logger.info("Server shutting down...")
    sys.exit(0)

# Initialize the web thread
web_thread = WebThread(port=8000)
redirect_thread = RedirectThread(port=80)

# Set up signal handling for graceful shutdown
signal.signal(signal.SIGINT, handle_exit_web)
signal.signal(signal.SIGTERM, handle_exit_web)

if __name__ == "__main__":
    try:
        # Start the web server thread
        web_thread.start()
        redirect_thread.start()
        logger.info("Web server thread started.")
    except Exception as e:
        logger.error(f"An exception occurred during web server start: {e}")
        handle_exit_web(signal.SIGINT, None)
        sys.exit(1)
