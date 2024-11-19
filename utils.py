#utils.py

import json
import subprocess
import os
import json
import csv
import zipfile
import uuid
import cgi
import io
import importlib
import logging
from datetime import datetime
from logger import Logger
from urllib.parse import unquote
from actions.nmap_vuln_scanner import NmapVulnScanner



logger = Logger(name="utils.py", level=logging.DEBUG)


class WebUtils:
    def __init__(self, shared_data, logger):
        self.shared_data = shared_data
        self.logger = logger
        self.actions = None  # List that contains all actions
        self.standalone_actions = None  # List that contains all standalone actions

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
                    backup_zip.extractall(self.shared_data.currentdir)

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
        query = unquote(handler.path.split('?filename=')[1])
        backup_path = os.path.join(self.shared_data.backupdir, query)
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
        handler.wfile.write(json.dumps(config).encode('utf-8'))

    def restore_default_config(self, handler):
        handler.send_response(200)
        handler.send_header("Content-type", "application/json")
        handler.end_headers()
        self.shared_data.config = self.shared_data.default_config.copy()
        self.shared_data.save_config()
        handler.wfile.write(json.dumps(self.shared_data.config).encode('utf-8'))

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
        favicon_path = os.path.join(self.shared_data.webdir, '/images/favicon.ico')
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
            result = subprocess.Popen(['sudo', 'iwlist', 'wlan0', 'scan'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            stdout, stderr = result.communicate()
            if result.returncode != 0:
                raise Exception(stderr)
            networks = self.parse_scan_result(stdout)
            self.logger.info(f"Found {len(networks)} networks")
            current_ssid = subprocess.Popen(['iwgetid', '-r'], stdout=subprocess.PIPE, text=True)
            ssid_out, ssid_err = current_ssid.communicate()
            if current_ssid.returncode != 0:
                raise Exception(ssid_err)
            current_ssid = ssid_out.strip()
            self.logger.info(f"Current SSID: {current_ssid}")
            handler.send_response(200)
            handler.send_header("Content-type", "application/json")
            handler.end_headers()
            handler.wfile.write(json.dumps({"networks": networks, "current_ssid": current_ssid}).encode('utf-8'))
        except Exception as e:
            handler.send_response(500)
            handler.send_header("Content-type", "application/json")
            handler.end_headers()
            self.logger.error(f"Error scanning Wi-Fi networks: {e}")
            handler.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))

    def parse_scan_result(self, scan_output):
        networks = []
        for line in scan_output.split('\n'):
            if 'ESSID' in line:
                ssid = line.split(':')[1].strip('"')
                if ssid not in networks:
                    networks.append(ssid)
        return networks

    def connect_wifi(self, handler):
        try:
            content_length = int(handler.headers['Content-Length'])
            post_data = handler.rfile.read(content_length).decode('utf-8')
            params = json.loads(post_data)
            ssid = params['ssid']
            password = params['password']

            self.update_nmconnection(ssid, password)
            command = f'sudo nmcli connection up "preconfigured"'
            connect_result = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            stdout, stderr = connect_result.communicate()
            if connect_result.returncode != 0:
                raise Exception(stderr)

            self.shared_data.wifichanged = True

            handler.send_response(200)
            handler.send_header('Content-type', 'application/json')
            handler.end_headers()
            handler.wfile.write(json.dumps({"status": "success", "message": "Connected to " + ssid}).encode('utf-8'))

        except Exception as e:
            handler.send_response(500)
            handler.send_header('Content-type', 'application/json')
            handler.end_headers()
            handler.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))

    def disconnect_and_clear_wifi(self, handler):
        try:
            command_disconnect = 'sudo nmcli connection down "preconfigured"'
            disconnect_result = subprocess.Popen(command_disconnect, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            stdout, stderr = disconnect_result.communicate()
            if disconnect_result.returncode != 0:
                raise Exception(stderr)

            config_path = '/etc/NetworkManager/system-connections/preconfigured.nmconnection'
            with open(config_path, 'w') as f:
                f.write("")
            subprocess.Popen(['sudo', 'chmod', '600', config_path]).communicate()
            subprocess.Popen(['sudo', 'nmcli', 'connection', 'reload']).communicate()

            self.shared_data.wifichanged = False

            handler.send_response(200)
            handler.send_header('Content-type', 'application/json')
            handler.end_headers()
            handler.wfile.write(json.dumps({"status": "success", "message": "Disconnected from Wi-Fi and cleared preconfigured settings"}).encode('utf-8'))

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

    def update_nmconnection(self, ssid, password):
        config_path = '/etc/NetworkManager/system-connections/preconfigured.nmconnection'
        with open(config_path, 'w') as f:
            f.write(f"""
[connection]
id=preconfigured
uuid={uuid.uuid4()}
type=wifi
autoconnect=true

[wifi]
ssid={ssid}
mode=infrastructure

[wifi-security]
key-mgmt=wpa-psk
psk={password}

[ipv4]
method=auto

[ipv6]
method=auto
""")
        subprocess.Popen(['sudo', 'chmod', '600', config_path]).communicate()
        subprocess.Popen(['sudo', 'nmcli', 'connection', 'reload']).communicate()

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
            file_path = os.path.join(self.shared_data.datastolendir, query)
            if os.path.isfile(file_path):
                handler.send_response(200)
                handler.send_header("Content-Disposition", f'attachment; filename="{os.path.basename(file_path)}"')
                handler.end_headers()
                with open(file_path, 'rb') as file:
                    handler.wfile.write(file.read())
            else:
                handler.send_response(404)
                handler.end_headers()
        except Exception as e:
            handler.send_response(500)
            handler.send_header("Content-type", "application/json")
            handler.end_headers()
            handler.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))



