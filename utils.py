#utils.py

import json
import subprocess
import os
import csv
import zipfile
import cgi
import io
import importlib
import logging
import re
import shutil
import threading
import time
from datetime import datetime
from logger import Logger
from setup_access import SetupAccessManager
from urllib.parse import unquote
from actions.nmap_vuln_scanner import NmapVulnScanner



logger = Logger(name="utils.py", level=logging.DEBUG)


class WebUtils:
    def __init__(self, shared_data, logger):
        self.shared_data = shared_data
        self.logger = logger
        self.setup_access_manager = SetupAccessManager(self.shared_data.currentdir)
        self.actions = None  # List that contains all actions
        self.standalone_actions = None  # List that contains all standalone actions
        self.last_wifi_scan_at = 0.0
        self.cached_wifi_scan = {"networks": [], "current_ssid": "", "message": ""}
        self.auth_failure_window = 60
        self.auth_failure_limit = 5
        self.auth_failures = {}
        self.sensitive_config_keys = {"setup_ap_password", "bluetooth_pairing_pin"}

    def get_connectivity_state(self):
        try:
            with open(self.shared_data.connectivity_state_file, 'r', encoding='utf-8') as handle:
                return json.load(handle)
        except FileNotFoundError:
            return {}
        except json.JSONDecodeError as e:
            self.logger.error(f"Error decoding connectivity state: {e}")
            return {}

    def serve_connectivity_state(self, handler):
        handler.send_response(200)
        handler.send_header("Content-type", "application/json")
        handler.end_headers()
        handler.wfile.write(json.dumps(self.get_connectivity_state()).encode('utf-8'))

    def is_setup_authenticated(self, handler):
        return self.setup_access_manager.is_authenticated(handler)

    def serve_setup_auth_status(self, handler, auth_required):
        self._write_json(
            handler,
            200,
            {
                "auth_required": auth_required,
                "authenticated": self.is_setup_authenticated(handler),
                "hint": "Enter the 6-digit setup code shown on Bjorn's screen.",
            },
        )

    def login_setup_auth(self, handler):
        retry_after = self._get_auth_retry_after(handler)
        if retry_after:
            self._write_json(
                handler,
                429,
                {
                    "status": "error",
                    "message": "Too many invalid setup code attempts. Try again shortly.",
                },
                {"Retry-After": str(retry_after)},
            )
            return

        try:
            content_length = int(handler.headers['Content-Length'])
            post_data = handler.rfile.read(content_length).decode('utf-8')
            params = json.loads(post_data)
            token = params.get('token', '')
        except Exception as exc:
            self._write_json(handler, 400, {"status": "error", "message": str(exc)})
            return

        if not self.setup_access_manager.verify_token(token):
            self._record_auth_failure(handler)
            retry_after = self._get_auth_retry_after(handler)
            status_code = 429 if retry_after else 403
            headers = {"Retry-After": str(retry_after)} if retry_after else None
            self._write_json(
                handler,
                status_code,
                {"status": "error", "message": "Invalid setup code"},
                headers,
            )
            return

        self._clear_auth_failures(handler)
        handler.send_response(200)
        self.setup_access_manager.write_auth_cookie(handler)
        handler.send_header("Content-type", "application/json")
        handler.end_headers()
        handler.wfile.write(json.dumps({"status": "success", "message": "Setup access granted"}).encode('utf-8'))

    def logout_setup_auth(self, handler):
        handler.send_response(200)
        self.setup_access_manager.clear_auth_cookie(handler)
        handler.send_header("Content-type", "application/json")
        handler.end_headers()
        handler.wfile.write(json.dumps({"status": "success", "message": "Logged out"}).encode('utf-8'))

    def _write_json(self, handler, status_code, payload, extra_headers=None):
        handler.send_response(status_code)
        if extra_headers:
            for key, value in extra_headers.items():
                handler.send_header(key, value)
        handler.send_header("Content-type", "application/json")
        handler.end_headers()
        handler.wfile.write(json.dumps(payload).encode('utf-8'))

    def _client_ip(self, handler):
        try:
            return handler.client_address[0]
        except Exception:
            return "unknown"

    def _prune_auth_failures(self, now=None):
        if now is None:
            now = time.time()

        cutoff = now - self.auth_failure_window
        stale_clients = []
        for client_ip, attempts in self.auth_failures.items():
            fresh_attempts = [attempt for attempt in attempts if attempt >= cutoff]
            if fresh_attempts:
                self.auth_failures[client_ip] = fresh_attempts
            else:
                stale_clients.append(client_ip)

        for client_ip in stale_clients:
            self.auth_failures.pop(client_ip, None)

    def _get_auth_retry_after(self, handler):
        now = time.time()
        self._prune_auth_failures(now)
        attempts = self.auth_failures.get(self._client_ip(handler), [])
        if len(attempts) < self.auth_failure_limit:
            return 0
        return max(1, int(self.auth_failure_window - (now - attempts[0])))

    def _record_auth_failure(self, handler):
        now = time.time()
        self._prune_auth_failures(now)
        client_ip = self._client_ip(handler)
        attempts = self.auth_failures.setdefault(client_ip, [])
        attempts.append(now)

    def _clear_auth_failures(self, handler):
        self.auth_failures.pop(self._client_ip(handler), None)

    def _resolve_safe_path(self, base_dir, requested_path):
        candidate_path = os.path.realpath(os.path.join(base_dir, requested_path))
        base_path = os.path.realpath(base_dir)
        if candidate_path == base_path or candidate_path.startswith(f"{base_path}{os.sep}"):
            return candidate_path
        raise PermissionError("Requested path is outside the allowed directory")

    def _sanitize_config_for_response(self, config):
        sanitized = dict(config)
        for key in self.sensitive_config_keys:
            if key in sanitized:
                sanitized[key] = "********"
        return sanitized

    def _extract_safe_zip(self, backup_zip, base_dir):
        for member in backup_zip.infolist():
            target_path = self._resolve_safe_path(base_dir, member.filename)

            if member.is_dir():
                os.makedirs(target_path, exist_ok=True)
                continue

            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            with backup_zip.open(member, 'r') as source_handle:
                with open(target_path, 'wb') as target_handle:
                    shutil.copyfileobj(source_handle, target_handle)

    def split_nmcli_line(self, line, field_count):
        fields = []
        current = []
        escaped = False

        for char in line:
            if escaped:
                current.append(char)
                escaped = False
                continue

            if char == "\\":
                escaped = True
                continue

            if char == ":" and len(fields) < field_count - 1:
                fields.append("".join(current))
                current = []
                continue

            current.append(char)

        fields.append("".join(current))
        while len(fields) < field_count:
            fields.append("")
        return fields

    def load_actions(self):
        """Load all actions from the actions file"""
        if self.actions is None or self.standalone_actions is None:
            self.actions = []  # reset the actions list
            self.standalone_actions = []  # reset the standalone actions list
            self.actions_dir = self.shared_data.actions_dir
            with open(self.shared_data.actions_file, 'r') as file:
                actions_config = json.load(file)
            for action in actions_config:
                module_name = action["b_module"]
                if module_name == 'scanning':
                    self.load_scanner(module_name)
                elif module_name == 'nmap_vuln_scanner':
                    self.load_nmap_vuln_scanner(module_name)
                else:
                    self.load_action(module_name, action)

    def load_scanner(self, module_name):
        """Load the network scanner"""
        module = importlib.import_module(f'actions.{module_name}')
        b_class = getattr(module, 'b_class')
        self.network_scanner = getattr(module, b_class)(self.shared_data)

    def load_nmap_vuln_scanner(self, module_name):
        """Load the nmap vulnerability scanner"""
        self.nmap_vuln_scanner = NmapVulnScanner(self.shared_data)

    def load_action(self, module_name, action):
        """Load an action from the actions file"""
        module = importlib.import_module(f'actions.{module_name}')
        try:
            b_class = action["b_class"]
            action_instance = getattr(module, b_class)(self.shared_data)
            action_instance.action_name = b_class
            action_instance.port = action.get("b_port")
            action_instance.b_parent_action = action.get("b_parent")
            if action_instance.port == 0:
                self.standalone_actions.append(action_instance)
            else:
                self.actions.append(action_instance)
        except AttributeError as e:
            self.logger.error(f"Module {module_name} is missing required attributes: {e}")

    def serve_netkb_data_json(self, handler):
        try:
            netkb_file = self.shared_data.netkbfile
            with open(netkb_file, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                data = [row for row in reader if row['Alive'] == '1']

            actions = reader.fieldnames[5:]  # Actions are all fields after 'Ports'
            response_data = {
                'ips': [row['IPs'] for row in data],
                'ports': {row['IPs']: row['Ports'].split(';') for row in data},
                'actions': actions
            }

            handler.send_response(200)
            handler.send_header("Content-type", "application/json")
            handler.end_headers()
            handler.wfile.write(json.dumps(response_data).encode('utf-8'))
        except Exception as e:
            handler.send_response(500)
            handler.send_header("Content-type", "application/json")
            handler.end_headers()
            handler.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))

    def execute_manual_attack(self, handler):
        try:
            content_length = int(handler.headers['Content-Length'])
            post_data = handler.rfile.read(content_length).decode('utf-8')
            params = json.loads(post_data)
            ip = params['ip']
            port = params['port']
            action_class = params['action']

            self.logger.info(f"Received request to execute {action_class} on {ip}:{port}")

            # Charger les actions si ce n'est pas déjà fait
            self.load_actions()

            action_instance = next((action for action in self.actions if action.action_name == action_class), None)
            if action_instance is None:
                raise Exception(f"Action class {action_class} not found")

            # Charger les données actuelles
            current_data = self.shared_data.read_data()
            row = next((r for r in current_data if r["IPs"] == ip), None)

            if row is None:
                raise Exception(f"No data found for IP: {ip}")

            action_key = action_instance.action_name
            self.logger.info(f"Executing {action_key} on {ip}:{port}")
            result = action_instance.execute(ip, port, row, action_key)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            if result == 'success':
                row[action_key] = f'success_{timestamp}'
                self.logger.info(f"Action {action_key} executed successfully on {ip}:{port}")
            else:
                row[action_key] = f'failed_{timestamp}'
                self.logger.error(f"Action {action_key} failed on {ip}:{port}")
            self.shared_data.write_data(current_data)

            handler.send_response(200)
            handler.send_header("Content-type", "application/json")
            handler.end_headers()
            handler.wfile.write(json.dumps({"status": "success", "message": "Manual attack executed"}).encode('utf-8'))
        except Exception as e:
            self.logger.error(f"Error executing manual attack: {e}")
            handler.send_response(500)
            handler.send_header("Content-type", "application/json")
            handler.end_headers()
            handler.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))


    def serve_logs(self, handler):
        try:
            log_file_path = self.shared_data.webconsolelog
            if not os.path.exists(log_file_path):
                subprocess.Popen(f"sudo tail -f /home/bjorn/Bjorn/data/logs/* > {log_file_path}", shell=True)

            with open(log_file_path, 'r') as log_file:
                log_lines = log_file.readlines()

            max_lines = 2000
            if len(log_lines) > max_lines:
                log_lines = log_lines[-max_lines:]
                with open(log_file_path, 'w') as log_file:
                    log_file.writelines(log_lines)

            log_data = ''.join(log_lines)

            handler.send_response(200)
            handler.send_header("Content-type", "text/plain")
            handler.end_headers()
            handler.wfile.write(log_data.encode('utf-8'))
        except BrokenPipeError:
            # Ignore broken pipe errors
            pass
        except Exception as e:
            handler.send_response(500)
            handler.send_header("Content-type", "application/json")
            handler.end_headers()
            handler.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))

    def start_orchestrator(self, handler):
        try:
            bjorn_instance = self.shared_data.bjorn_instance
            bjorn_instance.start_orchestrator()
            handler.send_response(200)
            handler.send_header("Content-type", "application/json")
            handler.end_headers()
            handler.wfile.write(json.dumps({"status": "success", "message": "Orchestrator starting..."}).encode('utf-8'))
        except Exception as e:
            handler.send_response(500)
            handler.send_header("Content-type", "application/json")
            handler.end_headers()
            handler.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))

    def stop_orchestrator(self, handler):
        try:
            bjorn_instance = self.shared_data.bjorn_instance
            bjorn_instance.stop_orchestrator()
            self.shared_data.orchestrator_should_exit = True
            handler.send_response(200)
            handler.send_header("Content-type", "application/json")
            handler.end_headers()
            handler.wfile.write(json.dumps({"status": "success", "message": "Orchestrator stopping..."}).encode('utf-8'))
        except Exception as e:
            handler.send_response(500)
            handler.send_header("Content-type", "application/json")
            handler.end_headers()
            handler.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))

    def backup(self, handler):
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_filename = f"backup_{timestamp}.zip"
            backup_path = os.path.join(self.shared_data.backupdir, backup_filename)

            with zipfile.ZipFile(backup_path, 'w') as backup_zip:
                for folder in [self.shared_data.configdir, self.shared_data.datadir, self.shared_data.actions_dir, self.shared_data.resourcesdir]:
                    for root, dirs, files in os.walk(folder):
                        for file in files:
                            file_path = os.path.join(root, file)
                            backup_zip.write(file_path, os.path.relpath(file_path, self.shared_data.currentdir))

            handler.send_response(200)
            handler.send_header("Content-type", "application/json")
            handler.end_headers()
            handler.wfile.write(json.dumps({"status": "success", "url": f"/download_backup?filename={backup_filename}", "filename": backup_filename}).encode('utf-8'))
        except Exception as e:
            handler.send_response(500)
            handler.send_header("Content-type", "application/json")
            handler.end_headers()
            handler.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))

    def restore(self, handler):
        try:
            content_length = int(handler.headers['Content-Length'])
            field_data = handler.rfile.read(content_length)
            field_storage = cgi.FieldStorage(fp=io.BytesIO(field_data), headers=handler.headers, environ={'REQUEST_METHOD': 'POST'})

            file_item = field_storage['file']
            if file_item.filename:
                backup_path = os.path.join(self.shared_data.upload_dir, file_item.filename)
                with open(backup_path, 'wb') as output_file:
                    output_file.write(file_item.file.read())

                with zipfile.ZipFile(backup_path, 'r') as backup_zip:
                    self._extract_safe_zip(backup_zip, self.shared_data.currentdir)

                handler.send_response(200)
                handler.send_header("Content-type", "application/json")
                handler.end_headers()
                handler.wfile.write(json.dumps({"status": "success", "message": "Restore completed successfully"}).encode('utf-8'))
            else:
                handler.send_response(400)
                handler.send_header("Content-type", "application/json")
                handler.end_headers()
                handler.wfile.write(json.dumps({"status": "error", "message": "No selected file"}).encode('utf-8'))
        except Exception as e:
            handler.send_response(500)
            handler.send_header("Content-type", "application/json")
            handler.end_headers()
            handler.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))

    def download_backup(self, handler):
        try:
            query = unquote(handler.path.split('?filename=')[1])
            backup_path = self._resolve_safe_path(self.shared_data.backupdir, query)
            if os.path.isfile(backup_path):
                handler.send_response(200)
                handler.send_header("Content-Disposition", f'attachment; filename="{os.path.basename(backup_path)}"')
                handler.send_header("Content-type", "application/zip")
                handler.end_headers()
                with open(backup_path, 'rb') as file:
                    handler.wfile.write(file.read())
            else:
                handler.send_response(404)
                handler.end_headers()
        except PermissionError as exc:
            self._write_json(handler, 403, {"status": "error", "message": str(exc)})
        except Exception as exc:
            self._write_json(handler, 500, {"status": "error", "message": str(exc)})

    def serve_credentials_data(self, handler):
        try:
            directory = self.shared_data.crackedpwddir
            html_content = self.generate_html_for_csv_files(directory)
            handler.send_response(200)
            handler.send_header("Content-type", "text/html")
            handler.end_headers()
            handler.wfile.write(html_content.encode('utf-8'))
        except Exception as e:
            handler.send_response(500)
            handler.send_header("Content-type", "application/json")
            handler.end_headers()
            handler.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))

    def generate_html_for_csv_files(self, directory):
        html = '<div class="credentials-container">\n'
        for filename in os.listdir(directory):
            if filename.endswith('.csv'):
                filepath = os.path.join(directory, filename)
                html += f'<h2>{filename}</h2>\n'
                html += '<table class="styled-table">\n<thead>\n<tr>\n'
                with open(filepath, 'r') as file:
                    reader = csv.reader(file)
                    headers = next(reader)
                    for header in headers:
                        html += f'<th>{header}</th>\n'
                    html += '</tr>\n</thead>\n<tbody>\n'
                    for row in reader:
                        html += '<tr>\n'
                        for cell in row:
                            html += f'<td>{cell}</td>\n'
                        html += '</tr>\n'
                html += '</tbody>\n</table>\n'
        html += '</div>\n'
        return html

    def list_files(self, directory):
        files = []
        for entry in os.scandir(directory):
            if entry.is_dir():
                files.append({
                    "name": entry.name,
                    "is_directory": True,
                    "children": self.list_files(entry.path)
                })
            else:
                files.append({
                    "name": entry.name,
                    "is_directory": False,
                    "path": entry.path
                })
        return files



    def serve_file(self, handler, filename):
        try:
            with open(os.path.join(self.shared_data.webdir, filename), 'r', encoding='utf-8') as file:
                content = file.read()
                content = content.replace('{{ web_delay }}', str(self.shared_data.web_delay * 1000))
                handler.send_response(200)
                handler.send_header("Content-type", "text/html")
                handler.end_headers()
                handler.wfile.write(content.encode('utf-8'))
        except FileNotFoundError:
            handler.send_response(404)
            handler.end_headers()

    def serve_current_config(self, handler):
        handler.send_response(200)
        handler.send_header("Content-type", "application/json")
        handler.end_headers()
        with open(self.shared_data.shared_config_json, 'r') as f:
            config = json.load(f)
        handler.wfile.write(
            json.dumps(self._sanitize_config_for_response(config)).encode('utf-8')
        )

    def restore_default_config(self, handler):
        handler.send_response(200)
        handler.send_header("Content-type", "application/json")
        handler.end_headers()
        self.shared_data.config = self.shared_data.default_config.copy()
        self.shared_data.save_config()
        handler.wfile.write(
            json.dumps(self._sanitize_config_for_response(self.shared_data.config)).encode('utf-8')
        )

    def serve_image(self, handler):
        image_path = os.path.join(self.shared_data.webdir, 'screen.png')
        try:
            with open(image_path, 'rb') as file:
                handler.send_response(200)
                handler.send_header("Content-type", "image/png")
                handler.send_header("Cache-Control", "max-age=0, must-revalidate")
                handler.end_headers()
                handler.wfile.write(file.read())
        except FileNotFoundError:
            handler.send_response(404)
            handler.end_headers()
        except BrokenPipeError:
            # Ignore broken pipe errors
            pass
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")


    def serve_favicon(self, handler):
        handler.send_response(200)
        handler.send_header("Content-type", "image/x-icon")
        handler.end_headers()
        favicon_path = os.path.join(self.shared_data.webdir, 'images', 'favicon.ico')
        self.logger.info(f"Serving favicon from {favicon_path}")
        try:
            with open(favicon_path, 'rb') as file:
                handler.wfile.write(file.read())
        except FileNotFoundError:
            self.logger.error(f"Favicon not found at {favicon_path}")
            handler.send_response(404)
            handler.end_headers()

    def serve_manifest(self, handler):
        handler.send_response(200)
        handler.send_header("Content-type", "application/json")
        handler.end_headers()
        manifest_path = os.path.join(self.shared_data.webdir, 'manifest.json')
        try:
            with open(manifest_path, 'r') as file:
                handler.wfile.write(file.read().encode('utf-8'))
        except FileNotFoundError:
            handler.send_response(404)
            handler.end_headers()
    
    def serve_apple_touch_icon(self, handler):
        handler.send_response(200)
        handler.send_header("Content-type", "image/png")
        handler.end_headers()
        icon_path = os.path.join(self.shared_data.webdir, 'icons/apple-touch-icon.png')
        try:
            with open(icon_path, 'rb') as file:
                handler.wfile.write(file.read())
        except FileNotFoundError:
            handler.send_response(404)
            handler.end_headers()

    def scan_wifi(self, handler):
        try:
            if time.time() - self.last_wifi_scan_at < 10 and self.cached_wifi_scan["message"]:
                self._write_json(handler, 200, self.cached_wifi_scan)
                return

            result = subprocess.run(
                ['sudo', 'nmcli', '-t', '-f', 'IN-USE,SSID,SIGNAL,SECURITY', 'device', 'wifi', 'list', 'ifname', 'wlan0', '--rescan', 'yes'],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                connectivity_state = self.get_connectivity_state()
                message = "Wi-Fi scanning is unavailable right now. Enter the SSID manually."
                if connectivity_state.get("setup_ap_active"):
                    message = "Wi-Fi scanning is unavailable while the setup AP is active. Enter the SSID manually."

                self.cached_wifi_scan = {
                    "networks": [],
                    "current_ssid": "",
                    "message": message,
                }
                self.last_wifi_scan_at = time.time()
                self._write_json(handler, 200, self.cached_wifi_scan)
                return

            networks = []
            current_ssid = ""
            seen_ssids = set()
            for line in result.stdout.splitlines():
                parts = self.split_nmcli_line(line, 4)
                if len(parts) < 4:
                    continue
                in_use, ssid, signal_strength, security = parts[0], parts[1], parts[2], ':'.join(parts[3:])
                if not ssid:
                    continue
                if ssid in seen_ssids:
                    continue
                seen_ssids.add(ssid)
                if in_use == '*':
                    current_ssid = ssid
                networks.append({
                    "ssid": ssid,
                    "signal": signal_strength,
                    "security": security,
                    "active": in_use == '*',
                })

            self.cached_wifi_scan = {
                "networks": networks,
                "current_ssid": current_ssid,
                "message": "Select a scanned SSID or enter one manually.",
            }
            self.last_wifi_scan_at = time.time()
            self._write_json(handler, 200, self.cached_wifi_scan)
        except Exception as e:
            self.logger.error(f"Error scanning Wi-Fi networks: {e}")
            self._write_json(handler, 500, {"error": str(e)})

    def connect_wifi(self, handler):
        try:
            content_length = int(handler.headers['Content-Length'])
            post_data = handler.rfile.read(content_length).decode('utf-8')
            params = json.loads(post_data)
            ssid = params.get('ssid', '').strip()
            password = params.get('password', '')
            if not ssid:
                raise Exception("SSID is required")

            worker = threading.Thread(target=self._connect_wifi_worker, args=(ssid, password), daemon=True)
            worker.start()

            handler.send_response(200)
            handler.send_header('Content-type', 'application/json')
            handler.end_headers()
            handler.wfile.write(json.dumps({
                "status": "accepted",
                "message": f"Attempting connection to {ssid}. If you are on a temporary setup network, this page may disconnect while Bjorn joins the target Wi-Fi."
            }).encode('utf-8'))

        except Exception as e:
            handler.send_response(500)
            handler.send_header('Content-type', 'application/json')
            handler.end_headers()
            handler.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))

    def _connect_wifi_worker(self, ssid, password):
        os.makedirs(os.path.dirname(self.shared_data.wifi_connect_lock_file), exist_ok=True)
        with open(self.shared_data.wifi_connect_lock_file, 'w', encoding='utf-8') as handle:
            handle.write(str(time.time()))
        time.sleep(1)
        connection_name = self._connection_name_for_ssid(ssid)
        connectivity_state = self.get_connectivity_state()
        setup_ap_was_active = bool(connectivity_state.get("setup_ap_active"))
        try:
            self.logger.info(f"Connecting wlan0 to SSID {ssid}")
            subprocess.run(['sudo', 'nmcli', 'connection', 'down', 'bjorn-setup'], check=False, capture_output=True, text=True)
            subprocess.run(['sudo', 'nmcli', 'device', 'disconnect', 'wlan0'], check=False, capture_output=True, text=True)
            subprocess.run(['sudo', 'nmcli', 'connection', 'delete', connection_name], check=False, capture_output=True, text=True)

            command = ['sudo', 'nmcli', 'device', 'wifi', 'connect', ssid, 'ifname', 'wlan0', 'name', connection_name]
            if password:
                command.extend(['password', password])

            result = subprocess.run(command, capture_output=True, text=True, check=False)
            if result.returncode != 0:
                raise RuntimeError(result.stderr.strip() or result.stdout.strip())

            subprocess.run(
                ['sudo', 'nmcli', 'connection', 'modify', connection_name, 'connection.autoconnect', 'yes', 'ipv6.method', 'ignore'],
                check=False,
                capture_output=True,
                text=True,
            )
            self.shared_data.wifichanged = True
            self.logger.info(f"Connected to Wi-Fi SSID {ssid}")
        except Exception as e:
            self.logger.error(f"Error connecting to Wi-Fi {ssid}: {e}")
            if setup_ap_was_active:
                subprocess.run(
                    ['sudo', 'nmcli', 'connection', 'up', 'bjorn-setup'],
                    check=False,
                    capture_output=True,
                    text=True,
                )
        finally:
            time.sleep(10)
            try:
                os.remove(self.shared_data.wifi_connect_lock_file)
            except OSError:
                pass

    def _connection_name_for_ssid(self, ssid):
        sanitized = re.sub(r'[^A-Za-z0-9._-]+', '-', ssid).strip('-') or 'wifi'
        return f"bjorn-{sanitized}"

    def disconnect_and_clear_wifi(self, handler):
        try:
            active_wifi = subprocess.run(
                ['sudo', 'nmcli', '-t', '-f', 'NAME,DEVICE,TYPE', 'connection', 'show', '--active'],
                capture_output=True,
                text=True,
                check=False,
            )
            active_connections = []
            for line in active_wifi.stdout.splitlines():
                parts = self.split_nmcli_line(line, 3)
                if len(parts) == 3 and parts[1] == 'wlan0' and parts[2] == '802-11-wireless':
                    active_connections.append(parts[0])

            for connection_name in active_connections:
                subprocess.run(['sudo', 'nmcli', 'connection', 'down', connection_name], check=False, capture_output=True, text=True)
            self.shared_data.wifichanged = False

            handler.send_response(200)
            handler.send_header('Content-type', 'application/json')
            handler.end_headers()
            handler.wfile.write(json.dumps({"status": "success", "message": "Disconnected wlan0 from active Wi-Fi connections"}).encode('utf-8'))

        except Exception as e:
            handler.send_response(500)
            handler.send_header('Content-type', 'application/json')
            handler.end_headers()
            handler.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))

    def clear_files(self, handler):
        try:
            command = """
            sudo rm -rf config/*.json && sudo rm -rf data/*.csv && sudo rm -rf data/*.log  && sudo rm -rf backup/backups/* && sudo rm -rf backup/uploads/* && sudo rm -rf data/output/data_stolen/* && sudo rm -rf data/output/crackedpwd/* && sudo rm -rf config/* && sudo rm -rf data/output/scan_results/* && sudo rm -rf __pycache__ && sudo rm -rf config/__pycache__ && sudo rm -rf data/__pycache__  && sudo rm -rf actions/__pycache__  && sudo rm -rf resources/__pycache__ && sudo rm -rf web/__pycache__ && sudo rm -rf *.log && sudo rm -rf resources/waveshare_epd/__pycache__ && sudo rm -rf data/logs/*  && sudo rm -rf data/output/vulnerabilities/* && sudo rm -rf data/logs/*
            """
            result = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            stdout, stderr = result.communicate()

            if result.returncode == 0:
                handler.send_response(200)
                handler.send_header("Content-type", "application/json")
                handler.end_headers()
                handler.wfile.write(json.dumps({"status": "success", "message": "Files cleared successfully"}).encode('utf-8'))
            else:
                handler.send_response(500)
                handler.send_header("Content-type", "application/json")
                handler.end_headers()
                handler.wfile.write(json.dumps({"status": "error", "message": stderr}).encode('utf-8'))
        except Exception as e:
            handler.send_response(500)
            handler.send_header("Content-type", "application/json")
            handler.end_headers()
            handler.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))

    def clear_files_light(self, handler):
        try:
            command = """
            sudo rm -rf data/*.log && sudo rm -rf data/output/data_stolen/* && sudo rm -rf data/output/crackedpwd/*  && sudo rm -rf data/output/scan_results/* && sudo rm -rf __pycache__ && sudo rm -rf config/__pycache__ && sudo rm -rf data/__pycache__  && sudo rm -rf actions/__pycache__  && sudo rm -rf resources/__pycache__ && sudo rm -rf web/__pycache__ && sudo rm -rf *.log && sudo rm -rf resources/waveshare_epd/__pycache__ && sudo rm -rf data/logs/*  && sudo rm -rf data/output/vulnerabilities/* && sudo rm -rf data/logs/*
            """
            result = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            stdout, stderr = result.communicate()

            if result.returncode == 0:
                handler.send_response(200)
                handler.send_header("Content-type", "application/json")
                handler.end_headers()
                handler.wfile.write(json.dumps({"status": "success", "message": "Files cleared successfully"}).encode('utf-8'))
            else:
                handler.send_response(500)
                handler.send_header("Content-type", "application/json")
                handler.end_headers()
                handler.wfile.write(json.dumps({"status": "error", "message": stderr}).encode('utf-8'))
        except Exception as e:
            handler.send_response(500)
            handler.send_header("Content-type", "application/json")
            handler.end_headers()
            handler.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))

    def initialize_csv(self, handler):
        try:
            self.shared_data.generate_actions_json()
            self.shared_data.initialize_csv()
            self.shared_data.create_livestatusfile()
            handler.send_response(200)
            handler.send_header("Content-type", "application/json")
            handler.end_headers()
            handler.wfile.write(json.dumps({"status": "success", "message": "CSV files initialized successfully"}).encode('utf-8'))
        except Exception as e:
            handler.send_response(500)
            handler.send_header("Content-type", "application/json")
            handler.end_headers()
            handler.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))

    def reboot_system(self, handler):
        try:
            command = "sudo reboot"
            subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            handler.send_response(200)
            handler.send_header("Content-type", "application/json")
            handler.end_headers()
            handler.wfile.write(json.dumps({"status": "success", "message": "System is rebooting"}).encode('utf-8'))
        except subprocess.CalledProcessError as e:
            handler.send_response(500)
            handler.send_header("Content-type", "application/json")
            handler.end_headers()
            handler.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))

    def shutdown_system(self, handler):
        try:
            command = "sudo shutdown now"
            subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            handler.send_response(200)
            handler.send_header("Content-type", "application/json")
            handler.end_headers()
            handler.wfile.write(json.dumps({"status": "success", "message": "System is shutting down"}).encode('utf-8'))
        except subprocess.CalledProcessError as e:
            handler.send_response(500)
            handler.send_header("Content-type", "application/json")
            handler.end_headers()
            handler.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))

    def restart_bjorn_service(self, handler):
        try:
            command = "sudo systemctl restart bjorn.service"
            subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            handler.send_response(200)
            handler.send_header("Content-type", "application/json")
            handler.end_headers()
            handler.wfile.write(json.dumps({"status": "success", "message": "Bjorn service restarted successfully"}).encode('utf-8'))
        except subprocess.CalledProcessError as e:
            handler.send_response(500)
            handler.send_header("Content-type", "application/json")
            handler.end_headers()
            handler.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))

    def serve_network_data(self, handler):
        try:
            latest_file = max(
                [os.path.join(self.shared_data.scan_results_dir, f) for f in os.listdir(self.shared_data.scan_results_dir) if f.startswith('result_')],
                key=os.path.getctime
            )
            table_html = self.generate_html_table(latest_file)
            handler.send_response(200)
            handler.send_header("Content-type", "text/html")
            handler.end_headers()
            handler.wfile.write(table_html.encode('utf-8'))
        except Exception as e:
            handler.send_response(500)
            handler.send_header("Content-type", "application/json")
            handler.end_headers()
            handler.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))

    def generate_html_table(self, file_path):
        table_html = '<table class="styled-table"><thead><tr>'
        with open(file_path, 'r') as file:
            reader = csv.reader(file)
            headers = next(reader)
            for header in headers:
                table_html += f'<th>{header}</th>'
            table_html += '</tr></thead><tbody>'
            for row in reader:
                table_html += '<tr>'
                for cell in row:
                    cell_class = "green" if cell.strip() else "red"
                    table_html += f'<td class="{cell_class}">{cell}</td>'
                table_html += '</tr>'
            table_html += '</tbody></table>'
        return table_html

    def generate_html_table_netkb(self, file_path):
        table_html = '<table class="styled-table"><thead><tr>'
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                reader = csv.reader(file)
                headers = next(reader)
                for header in headers:
                    table_html += f'<th>{header}</th>'
                table_html += '</tr></thead><tbody>'
                for row in reader:
                    row_class = "blue-row" if '0' in row[3] else ""
                    table_html += f'<tr class="{row_class}">'
                    for cell in row:
                        cell_class = ""
                        if "success" in cell:
                            cell_class = "green bold"
                        elif "failed" in cell:
                            cell_class = "red bold"
                        elif cell.strip() == "":
                            cell_class = "grey"
                        table_html += f'<td class="{cell_class}">{cell}</td>'
                    table_html += '</tr>'
                table_html += '</tbody></table>'
        except Exception as e:
            self.logger.error(f"Error in generate_html_table_netkb: {e}")
        return table_html


    def serve_netkb_data(self, handler):
        try:
            latest_file = self.shared_data.netkbfile
            table_html = self.generate_html_table_netkb(latest_file)
            handler.send_response(200)
            handler.send_header("Content-type", "text/html")
            handler.end_headers()
            handler.wfile.write(table_html.encode('utf-8'))
        except Exception as e:
            handler.send_response(500)
            handler.send_header("Content-type", "application/json")
            handler.end_headers()
            handler.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))

    def save_configuration(self, handler):
        try:
            content_length = int(handler.headers['Content-Length'])
            post_data = handler.rfile.read(content_length).decode('utf-8')
            params = json.loads(post_data)
            fichier = self.shared_data.shared_config_json
            self.logger.info(f"Received params: {params}")

            with open(fichier, 'r') as f:
                current_config = json.load(f)

            for key, value in params.items():
                if key in self.sensitive_config_keys and str(value).strip() in {"", "********"}:
                    continue
                if isinstance(value, bool):
                    current_config[key] = value
                elif isinstance(value, str) and value.lower() in ['true', 'false']:
                    current_config[key] = value.lower() == 'true'
                elif isinstance(value, (int, float)):
                    current_config[key] = value
                elif isinstance(value, list):
                    # Lets boot any values in a list that are just empty strings
                    for val in value[:]:
                        if val == "" :
                            value.remove(val)
                    current_config[key] = value
                elif isinstance(value, str):
                    if value.replace('.', '', 1).isdigit():
                        current_config[key] = float(value) if '.' in value else int(value)
                    else:
                        current_config[key] = value
                else:
                    current_config[key] = value

            with open(fichier, 'w') as f:
                json.dump(current_config, f, indent=4)
            self.logger.info("Configuration saved to file")

            handler.send_response(200)
            handler.send_header('Content-type', 'application/json')
            handler.end_headers()
            handler.wfile.write(json.dumps({"status": "success", "message": "Configuration saved"}).encode('utf-8'))
            self.logger.info("Configuration saved (web)")

            self.shared_data.load_config()
            self.logger.info("Configuration reloaded (web)")

        except Exception as e:
            handler.send_response(500)
            handler.send_header('Content-type', 'application/json')
            handler.end_headers()
            error_message = {"status": "error", "message": str(e)}
            handler.wfile.write(json.dumps(error_message).encode('utf-8'))
            self.logger.error(f"Error saving configuration: {e}")

    def list_files(self, directory):
        files = []
        for entry in os.scandir(directory):
            if entry.is_dir():
                files.append({
                    "name": entry.name,
                    "is_directory": True,
                    "children": self.list_files(entry.path)
                })
            else:
                files.append({
                    "name": entry.name,
                    "is_directory": False,
                    "path": entry.path
                })
        return files

    def list_files_endpoint(self, handler):
        try:
            files = self.list_files(self.shared_data.datastolendir)
            handler.send_response(200)
            handler.send_header("Content-type", "application/json")
            handler.end_headers()
            handler.wfile.write(json.dumps(files).encode('utf-8'))
        except Exception as e:
            handler.send_response(500)
            handler.send_header("Content-type", "application/json")
            handler.end_headers()
            handler.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))

    def download_file(self, handler):
        try:
            query = unquote(handler.path.split('?path=')[1])
            file_path = self._resolve_safe_path(self.shared_data.datastolendir, query)
            if os.path.isfile(file_path):
                handler.send_response(200)
                handler.send_header("Content-Disposition", f'attachment; filename="{os.path.basename(file_path)}"')
                handler.end_headers()
                with open(file_path, 'rb') as file:
                    handler.wfile.write(file.read())
            else:
                handler.send_response(404)
                handler.end_headers()
        except PermissionError as e:
            self._write_json(handler, 403, {"status": "error", "message": str(e)})
        except Exception as e:
            self._write_json(handler, 500, {"status": "error", "message": str(e)})
