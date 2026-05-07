#!/usr/bin/env python3

import json
import logging
import os
import signal
import subprocess
import time
from datetime import datetime, timezone

from logger import Logger
from setup_access import get_effective_setup_ap_password


logger = Logger(name="connectivity_manager.py", level=logging.DEBUG)


class ConnectivityManager:
    def __init__(self):
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.config_path = os.path.join(self.base_dir, "config", "shared_config.json")
        self.state_path = os.path.join(self.base_dir, "config", "connectivity_state.json")
        self.wifi_connect_lock_path = os.path.join(self.base_dir, "run", "wifi_connect.lock")
        self.stop_requested = False
        self.started_at = time.time()
        self.last_state_payload = None
        self.bt_pan_process = None
        self.bt_pan_started_at = 0.0
        self.setup_ap_started_at = 0.0
        self.last_bt_pan_error = ""
        self.last_setup_ap_settings = None
        self.last_bt_pan_settings = None
        self.setup_ap_profile_exists = None
        self.bt_pan_profile_exists = None
        self.loop_interval = 5

    def run(self):
        while not self.stop_requested:
            settings = self.load_settings()
            wifi_state = self.get_wifi_state()
            active_connections = self.get_active_connections()
            self.ensure_bluetooth_pan(settings, wifi_state)
            self.manage_setup_ap(settings, wifi_state, active_connections)
            state = self.build_state(settings, wifi_state, active_connections)
            self.write_state_if_changed(state)
            time.sleep(self.loop_interval)

        self.cleanup()

    def load_settings(self):
        defaults = {
            "bluetooth_pan_enabled": True,
            "bluetooth_pan_address": "172.22.0.1/24",
            "setup_ap_enabled": True,
            "setup_ap_ssid": "bjorn-setup",
            "setup_ap_password": "bjornsetup",
            "setup_ap_address": "192.168.4.1/24",
            "setup_ap_boot_timeout": 30,
            "setup_ap_idle_timeout": 0,
        }

        try:
            with open(self.config_path, "r", encoding="utf-8") as handle:
                config = json.load(handle)
        except FileNotFoundError:
            return defaults
        except json.JSONDecodeError as exc:
            logger.error(f"Failed to parse {self.config_path}: {exc}")
            return defaults

        for key in defaults:
            if key in config:
                defaults[key] = config[key]

        defaults["bluetooth_pan_enabled"] = bool(defaults["bluetooth_pan_enabled"])
        defaults["setup_ap_enabled"] = bool(defaults["setup_ap_enabled"])
        defaults["setup_ap_boot_timeout"] = self.safe_int(defaults["setup_ap_boot_timeout"], 30)
        defaults["setup_ap_idle_timeout"] = self.safe_int(defaults["setup_ap_idle_timeout"], 0)
        defaults["setup_ap_ssid"] = str(defaults["setup_ap_ssid"]).strip() or "bjorn-setup"
        defaults["setup_ap_password"] = get_effective_setup_ap_password(defaults["setup_ap_password"])
        defaults["setup_ap_address"] = str(defaults["setup_ap_address"]).strip() or "192.168.4.1/24"
        defaults["bluetooth_pan_address"] = (
            str(defaults["bluetooth_pan_address"]).strip() or "172.22.0.1/24"
        )
        return defaults

    def safe_int(self, value, fallback):
        try:
            return int(value)
        except (TypeError, ValueError):
            return fallback

    def run_command(self, command, check=False):
        logger.debug(f"exec => {' '.join(command)}")
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if check and result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip())
        return result

    def is_wifi_transition_locked(self, max_age=45):
        try:
            mtime = os.path.getmtime(self.wifi_connect_lock_path)
        except FileNotFoundError:
            return False
        except OSError:
            return False

        if time.time() - mtime <= max_age:
            return True

        try:
            os.remove(self.wifi_connect_lock_path)
        except OSError:
            pass
        return False

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

    def truncate_text(self, text, limit):
        if len(text) <= limit:
            return text
        return f"{text[: limit - 3]}..."

    def connection_exists(self, profile_name):
        result = self.run_command(["nmcli", "-t", "-f", "NAME", "connection", "show"])
        if result.returncode != 0:
            return False

        for line in (result.stdout or "").splitlines():
            if self.split_nmcli_line(line, 1)[0] == profile_name:
                return True
        return False

    def get_active_connections(self):
        result = self.run_command(
            ["nmcli", "-t", "-f", "NAME,TYPE,DEVICE", "connection", "show", "--active"]
        )
        active_connections = []
        for line in (result.stdout or "").splitlines():
            parts = self.split_nmcli_line(line, 3)
            if len(parts) == 3:
                active_connections.append(
                    {
                        "name": parts[0],
                        "type": parts[1],
                        "device": parts[2],
                    }
                )
        return active_connections

    def get_device_state(self, wifi_state, device_name):
        return wifi_state.get("device_states", {}).get(device_name, "")

    def get_wifi_state(self):
        device_status = self.run_command(
            ["nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device", "status"]
        )
        general_status = self.run_command(
            ["nmcli", "-t", "-f", "STATE,CONNECTIVITY", "general", "status"]
        )

        wifi_connection = ""
        wifi_state = "disconnected"
        device_states = {}
        for line in (device_status.stdout or "").splitlines():
            parts = self.split_nmcli_line(line, 4)
            if len(parts) != 4:
                continue
            device_name, device_type, state, connection_name = parts
            device_states[device_name] = state
            if device_name == "wlan0" and device_type == "wifi":
                wifi_state = state
                wifi_connection = connection_name if connection_name != "--" else ""

        general_state = ""
        connectivity = ""
        if general_status.stdout:
            fields = self.split_nmcli_line(general_status.stdout.strip(), 2)
            if fields:
                general_state = fields[0]
            if len(fields) > 1:
                connectivity = fields[1]

        setup_ap_connection = wifi_connection == "bjorn-setup"
        infrastructure_connected = wifi_state == "connected" and not setup_ap_connection
        infrastructure_connecting = (
            wifi_state in {"connecting", "config", "ip-config", "ip-check"} and not setup_ap_connection
        )

        return {
            "wlan_state": wifi_state,
            "wifi_connection": wifi_connection,
            "connected": infrastructure_connected,
            "connecting": infrastructure_connecting,
            "setup_ap_connection": setup_ap_connection,
            "general_state": general_state,
            "connectivity": connectivity,
            "device_states": device_states,
        }

    def ensure_setup_ap_profile(self, settings):
        profile_name = "bjorn-setup"
        settings_key = (
            settings["setup_ap_ssid"],
            settings["setup_ap_password"],
            settings["setup_ap_address"],
        )
        if self.setup_ap_profile_exists is None:
            self.setup_ap_profile_exists = self.connection_exists(profile_name)

        if not self.setup_ap_profile_exists:
            self.run_command(
                [
                    "nmcli",
                    "connection",
                    "add",
                    "type",
                    "wifi",
                    "ifname",
                    "wlan0",
                    "con-name",
                    profile_name,
                    "ssid",
                    settings["setup_ap_ssid"],
                    "802-11-wireless.mode",
                    "ap",
                    "autoconnect",
                    "no",
                    "ipv4.method",
                    "shared",
                    "ipv4.addresses",
                    settings["setup_ap_address"],
                    "ipv6.method",
                    "disabled",
                    "wifi-sec.key-mgmt",
                    "wpa-psk",
                    "wifi-sec.psk",
                    settings["setup_ap_password"],
                ],
                check=True,
            )
            self.setup_ap_profile_exists = True
            self.last_setup_ap_settings = settings_key
            return

        if self.last_setup_ap_settings == settings_key:
            return

        self.run_command(
            [
                "nmcli",
                "connection",
                "modify",
                profile_name,
                "802-11-wireless.ssid",
                settings["setup_ap_ssid"],
                "802-11-wireless.mode",
                "ap",
                "autoconnect",
                "no",
                "ipv4.method",
                "shared",
                "ipv4.addresses",
                settings["setup_ap_address"],
                "ipv6.method",
                "disabled",
                "wifi-sec.key-mgmt",
                "wpa-psk",
                "wifi-sec.psk",
                settings["setup_ap_password"],
            ]
        )
        self.last_setup_ap_settings = settings_key

    def is_setup_ap_active(self, active_connections):
        for connection in active_connections:
            if connection["name"] == "bjorn-setup" and connection["device"] == "wlan0":
                return True
        return False

    def start_setup_ap(self, settings, active_connections):
        if self.is_setup_ap_active(active_connections):
            return

        self.ensure_setup_ap_profile(settings)
        logger.info("Starting setup AP")
        self.run_command(["nmcli", "connection", "up", "bjorn-setup"], check=True)
        self.setup_ap_started_at = time.time()

    def stop_setup_ap(self, active_connections=None):
        if active_connections is None:
            active_connections = self.get_active_connections()
        if not self.is_setup_ap_active(active_connections):
            return

        logger.info("Stopping setup AP")
        self.run_command(["nmcli", "connection", "down", "bjorn-setup"])

    def manage_setup_ap(self, settings, wifi_state, active_connections):
        if not settings["setup_ap_enabled"]:
            self.stop_setup_ap(active_connections)
            return

        if self.is_wifi_transition_locked():
            logger.debug("Wi-Fi transition lock is active; leaving setup AP state unchanged")
            return

        if wifi_state["connected"] or wifi_state["connecting"]:
            logger.debug(
                "Skipping setup AP because wlan0 is using client Wi-Fi "
                f"state={wifi_state['wlan_state']} connection={wifi_state['wifi_connection'] or '<none>'}"
            )
            self.stop_setup_ap(active_connections)
            return

        if wifi_state["setup_ap_connection"]:
            logger.debug("Keeping setup AP active because wlan0 is already serving bjorn-setup")
            return

        if time.time() - self.started_at < settings["setup_ap_boot_timeout"]:
            return

        if not self.is_setup_ap_active(active_connections):
            try:
                self.start_setup_ap(settings, active_connections)
            except Exception as exc:
                logger.error(f"Failed to start setup AP: {exc}")
                return

        idle_timeout = settings["setup_ap_idle_timeout"]
        if idle_timeout > 0 and self.setup_ap_started_at and time.time() - self.setup_ap_started_at > idle_timeout:
            self.stop_setup_ap(active_connections)

    def ensure_bt_pan_profile(self, settings, wifi_state):
        profile_name = "bjorn-bt-pan"
        settings_key = settings["bluetooth_pan_address"]
        if self.bt_pan_profile_exists is None:
            self.bt_pan_profile_exists = self.connection_exists(profile_name)

        if not self.bt_pan_profile_exists:
            self.run_command(
                [
                    "nmcli",
                    "connection",
                    "add",
                    "type",
                    "bridge",
                    "ifname",
                    "bt-pan",
                    "con-name",
                    profile_name,
                    "autoconnect",
                    "yes",
                    "ipv4.method",
                    "shared",
                    "ipv4.addresses",
                    settings["bluetooth_pan_address"],
                    "ipv6.method",
                    "disabled",
                    "bridge.stp",
                    "no",
                ],
                check=True,
            )
            self.bt_pan_profile_exists = True

        if self.last_bt_pan_settings == settings_key:
            bt_pan_state = self.get_device_state(wifi_state, "bt-pan")
            if bt_pan_state not in {"connected", "connecting", "config", "ip-config", "ip-check"}:
                self.run_command(["nmcli", "connection", "up", profile_name])
            return

        self.run_command(
            [
                "nmcli",
                "connection",
                "modify",
                profile_name,
                "autoconnect",
                "yes",
                "ipv4.method",
                "shared",
                "ipv4.addresses",
                settings["bluetooth_pan_address"],
                "ipv6.method",
                "disabled",
                "bridge.stp",
                "no",
            ]
        )
        self.last_bt_pan_settings = settings_key

        bt_pan_state = self.get_device_state(wifi_state, "bt-pan")
        if bt_pan_state not in {"connected", "connecting", "config", "ip-config", "ip-check"}:
            self.run_command(["nmcli", "connection", "up", profile_name])

    def ensure_bluetooth_pan(self, settings, wifi_state):
        if not settings["bluetooth_pan_enabled"]:
            self.last_bt_pan_error = ""
            self.stop_bt_pan_server()
            return

        try:
            self.ensure_bt_pan_profile(settings, wifi_state)
        except Exception as exc:
            self.last_bt_pan_error = str(exc)
            logger.error(f"Failed to prepare Bluetooth PAN bridge: {exc}")
            return

        if self.bt_pan_process and self.bt_pan_process.poll() is None:
            self.last_bt_pan_error = ""
            return

        logger.info("Starting Bluetooth PAN NAP server")
        try:
            self.bt_pan_process = subprocess.Popen(
                ["bt-network", "-s", "nap", "bt-pan"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
        except FileNotFoundError:
            self.last_bt_pan_error = "bt-network is not installed"
            logger.error(self.last_bt_pan_error)
            self.bt_pan_process = None
            return

        self.last_bt_pan_error = ""
        self.bt_pan_started_at = time.time()

    def stop_bt_pan_server(self):
        if not self.bt_pan_process or self.bt_pan_process.poll() is not None:
            return

        logger.info("Stopping Bluetooth PAN NAP server")
        self.bt_pan_process.terminate()
        try:
            self.bt_pan_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.bt_pan_process.kill()

    def get_bt_pan_clients(self):
        result = self.run_command(["ip", "-o", "link", "show", "master", "bt-pan"])
        clients = []
        for line in (result.stdout or "").splitlines():
            parts = line.split(": ", 1)
            if len(parts) != 2:
                continue
            interface_name = parts[1].split(":", 1)[0].strip()
            clients.append(interface_name)
        return clients

    def get_ipv4_for_interface(self, interface_name):
        result = self.run_command(
            ["ip", "-o", "-4", "addr", "show", "dev", interface_name]
        )
        for line in (result.stdout or "").splitlines():
            parts = line.split()
            if len(parts) >= 4:
                return parts[3].split("/", 1)[0]
        return ""

    def build_state(self, settings, wifi_state, active_connections):
        setup_ap_active = self.is_setup_ap_active(active_connections)
        bt_pan_clients = self.get_bt_pan_clients()
        bt_pan_active = bool(self.bt_pan_process and self.bt_pan_process.poll() is None)
        setup_ap_ip = self.get_ipv4_for_interface("wlan0") if setup_ap_active else settings["setup_ap_address"].split("/", 1)[0]
        bt_pan_ip = self.get_ipv4_for_interface("bt-pan") or settings["bluetooth_pan_address"].split("/", 1)[0]
        wifi_transition_locked = self.is_wifi_transition_locked()

        portal_detected = wifi_state["connectivity"] in {"portal", "limited"}
        provisioning_mode_active = False
        preferred_transport = ""
        preferred_ui_url = ""
        setup_lines = []
        if setup_ap_active:
            provisioning_mode_active = True
            preferred_transport = "setup_ap"
            preferred_ui_url = f"http://{setup_ap_ip}:8000"
            setup_lines = [
                "SETUP AP",
                self.truncate_text(settings["setup_ap_ssid"], 18),
                f"WEB {setup_ap_ip}:8000",
            ]
        elif portal_detected and bt_pan_active:
            provisioning_mode_active = True
            preferred_transport = "bluetooth_pan"
            preferred_ui_url = f"http://{bt_pan_ip}:8000"
            setup_lines = [
                "CAPTIVE LOGIN",
                "OFF WIFI/DATA",
                f"BT {bt_pan_ip}:8000",
            ]
        elif bt_pan_clients:
            preferred_transport = "bluetooth_pan"
            preferred_ui_url = f"http://{bt_pan_ip}:8000"
            provisioning_mode_active = not wifi_state["connected"]
            setup_lines = [
                "BT SECONDARY",
                "OFF WIFI/DATA",
                f"WEB {bt_pan_ip}:8000",
            ]

        return {
            "setup_ap_enabled": settings["setup_ap_enabled"],
            "setup_ap_active": setup_ap_active,
            "setup_ap_ssid": settings["setup_ap_ssid"],
            "setup_ap_url": f"http://{setup_ap_ip}:8000",
            "setup_ap_ip": setup_ap_ip,
            "bluetooth_pan_enabled": settings["bluetooth_pan_enabled"],
            "bluetooth_pan_active": bt_pan_active,
            "bluetooth_pan_url": f"http://{bt_pan_ip}:8000",
            "bluetooth_pan_ip": bt_pan_ip,
            "bluetooth_pan_error": self.last_bt_pan_error,
            "bluetooth_pan_clients": bt_pan_clients,
            "bluetooth_pan_client_count": len(bt_pan_clients),
            "wifi_state": wifi_state["wlan_state"],
            "wifi_connection": wifi_state["wifi_connection"],
            "wifi_connected": wifi_state["connected"],
            "wifi_transition_locked": wifi_transition_locked,
            "wifi_connectivity": wifi_state["connectivity"],
            "portal_detected": portal_detected,
            "preferred_transport": preferred_transport,
            "preferred_ui_url": preferred_ui_url,
            "provisioning_mode_active": provisioning_mode_active,
            "display_overlay": bool(setup_lines),
            "display_lines": setup_lines,
        }

    def write_state_if_changed(self, state):
        payload = json.dumps(state, sort_keys=True)
        if payload == self.last_state_payload:
            return

        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
        temp_path = f"{self.state_path}.tmp"
        with open(temp_path, "w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=2)
        os.replace(temp_path, self.state_path)
        self.last_state_payload = payload

    def cleanup(self):
        self.stop_setup_ap()
        self.stop_bt_pan_server()


def main():
    manager = ConnectivityManager()

    def stop_handler(signum, frame):
        del signum, frame
        manager.stop_requested = True

    signal.signal(signal.SIGINT, stop_handler)
    signal.signal(signal.SIGTERM, stop_handler)
    manager.run()


if __name__ == "__main__":
    main()
