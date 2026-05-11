#webapp.py 
import json
import threading
import http.server
import socketserver
import logging
import sys
import signal
import base64
import os
import gzip
import io
from logger import Logger
from init_shared import shared_data
from utils import WebUtils

# Initialize the logger
logger = Logger(name="webapp.py", level=logging.DEBUG)

# Set the path to the favicon
favicon_path = os.path.join(shared_data.webdir, '/images/favicon.ico')

class CustomHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        self.shared_data = shared_data
        self.web_utils = WebUtils(shared_data, logger)
        # Web auth config
        self.web_auth_enabled = bool(self.shared_data.config.get('web_auth', False))
        self.web_auth_user = self.shared_data.config.get('web_user', '')
        self.web_auth_password = self.shared_data.config.get('web_password', '')
        super().__init__(*args, **kwargs)

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
        # Enforce Basic Auth if enabled
        if self.web_auth_enabled:
            if not self.check_auth():
                self.request_auth()
                return
        # Handle GET requests. Serve the HTML interface and the EPD image.
        if self.path == '/index.html' or self.path == '/':
            self.serve_file_gzipped(os.path.join(self.shared_data.webdir, 'index.html'), 'text/html')
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
            self.web_utils.serve_current_config(self)
        elif self.path == '/restore_default_config':
            self.web_utils.restore_default_config(self)
        elif self.path == '/get_web_delay':
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            response = json.dumps({"web_delay": self.shared_data.web_delay})
            self.wfile.write(response.encode('utf-8'))
        elif self.path == '/scan_wifi':
            self.web_utils.scan_wifi(self)
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
            self.web_utils.serve_logs(self)
        elif self.path == '/list_credentials':
            self.web_utils.serve_credentials_data(self)
        elif self.path.startswith('/list_files'):
            self.web_utils.list_files_endpoint(self)
        elif self.path.startswith('/download_file'):
            self.web_utils.download_file(self)
        elif self.path.startswith('/download_backup'):
            self.web_utils.download_backup(self)
        else:
            super().do_GET()

    def do_POST(self):
        # Enforce Basic Auth for POST requests
        if self.web_auth_enabled:
            if not self.check_auth():
                self.request_auth()
                return
        # Handle POST requests for saving configuration, connecting to Wi-Fi, clearing files, rebooting, and shutting down.
        if self.path == '/save_config':
            self.web_utils.save_configuration(self)
        elif self.path == '/connect_wifi':
            self.web_utils.connect_wifi(self)
            self.shared_data.wifichanged = True  # Set the flag when Wi-Fi is connected
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

    def check_auth(self):
        """Validate HTTP Basic Authorization header against configured credentials."""
        auth_header = self.headers.get('Authorization')
        if not auth_header:
            return False
        try:
            scheme, encoded = auth_header.split(' ', 1)
            if scheme.lower() != 'basic':
                return False
            decoded = base64.b64decode(encoded.strip()).decode('utf-8')
            user, pwd = decoded.split(':', 1)
            return user == self.web_auth_user and pwd == self.web_auth_password
        except Exception:
            return False

    def request_auth(self):
        """Send a 401 response that enables Basic auth in the client."""
        self.send_response(401)
        self.send_header('WWW-Authenticate', 'Basic realm="Bjorn Web UI"')
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b'Authentication required')

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
                    with socketserver.TCPServer(("127.0.0.1", self.port), self.handler_class) as httpd:
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

def handle_exit_web(signum, frame):
    """
    Handle exit signals to shutdown the web server cleanly.
    """
    shared_data.webapp_should_exit = True
    if web_thread.is_alive():
        web_thread.shutdown()
        web_thread.join()  # Wait until the web_thread is finished
    logger.info("Server shutting down...")
    sys.exit(0)

# Initialize the web thread
web_thread = WebThread(port=8000)

# Set up signal handling for graceful shutdown
signal.signal(signal.SIGINT, handle_exit_web)
signal.signal(signal.SIGTERM, handle_exit_web)

if __name__ == "__main__":
    try:
        # Start the web server thread
        web_thread.start()
        logger.info("Web server thread started.")
    except Exception as e:
        logger.error(f"An exception occurred during web server start: {e}")
        handle_exit_web(signal.SIGINT, None)
        sys.exit(1)
