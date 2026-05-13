#!/usr/bin/env python3

import json
import logging
import os
import queue
import random
import re
import shutil
import signal
import socket
import subprocess
import threading
import time
from datetime import datetime, timezone

from logger import Logger


logger = Logger(name="bluetooth_manager.py", level=logging.DEBUG)

ANSI_ESCAPE_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0B-\x1F\x7F]")
DEVICE_LINE_RE = re.compile(r"Device ([0-9A-F:]{17}) (.+)")
PIN_RE = re.compile(r"(\d{4,6})")


class BluetoothManager:
    def __init__(self):
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.config_path = os.path.join(self.base_dir, "config", "shared_config.json")
        self.state_path = os.path.join(self.base_dir, "config", "bluetooth_state.json")
        self.output_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.proc = None
        self.reader_thread = None
        self.settings = self.load_settings()
        self.last_applied_settings = {}
        self.current_device = {"mac": None, "name": None}
        self.current_pin = None
        self.pin_updated_at = 0.0
        self.last_pairing_success_at = 0.0
        self.last_error = ""
        self.last_error_at = 0.0
        self.last_event = ""
        self.adapter_state = {
            "powered": False,
            "pairable": False,
            "discoverable": False,
            "alias": self.settings["bluetooth_alias"],
        }
        self.paired_devices = []
        self.connected_devices = []

    def run(self):
        try:
            while not self.stop_event.is_set():
                self.settings = self.load_settings()
                self.ensure_session()
                self.apply_adapter_settings()
                self.consume_output(timeout=1.0)
                self.refresh_state()
                self.write_state()
                time.sleep(1)
        finally:
            self.cleanup()

    def load_settings(self):
        hostname = socket.gethostname().split(".")[0]
        defaults = {
            "bluetooth_pairing_enabled": False,
            "bluetooth_discoverable_timeout": 0,
            "bluetooth_agent_capability": "DisplayYesNo",
            "bluetooth_ssh_user": "bjorn",
            "bluetooth_pairing_pin": "",
            "bluetooth_alias": hostname,
        }

        try:
            with open(self.config_path, "r", encoding="utf-8") as handle:
                config = json.load(handle)
        except FileNotFoundError:
            return defaults
        except json.JSONDecodeError as exc:
            logger.error(f"Unable to read Bluetooth settings from {self.config_path}: {exc}")
            return defaults

        for key in defaults:
            if key in config:
                defaults[key] = config[key]

        defaults["bluetooth_discoverable_timeout"] = self.safe_int(
            defaults["bluetooth_discoverable_timeout"],
            0,
        )
        defaults["bluetooth_alias"] = str(defaults["bluetooth_alias"]).strip() or hostname
        defaults["bluetooth_ssh_user"] = str(defaults["bluetooth_ssh_user"]).strip() or "bjorn"
        defaults["bluetooth_pairing_pin"] = str(defaults["bluetooth_pairing_pin"]).strip()
        defaults["bluetooth_agent_capability"] = (
            str(defaults["bluetooth_agent_capability"]).strip() or "DisplayYesNo"
        )
        defaults["bluetooth_pairing_enabled"] = bool(defaults["bluetooth_pairing_enabled"])
        return defaults

    def safe_int(self, value, fallback):
        try:
            return int(value)
        except (TypeError, ValueError):
            return fallback

    def ensure_session(self):
        capability = self.settings["bluetooth_agent_capability"]

        if self.proc and self.proc.poll() is None:
            return

        logger.info("Starting bluetoothctl agent session")
        self.proc = subprocess.Popen(
            ["bluetoothctl", "--agent", capability],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        self.reader_thread = threading.Thread(target=self.enqueue_output, daemon=True)
        self.reader_thread.start()
        self.last_applied_settings = {}
        time.sleep(1)

        self.send_command("power on")
        self.send_command(f"agent {capability}")
        self.send_command("default-agent")
        self.send_command(f"system-alias {self.settings['bluetooth_alias']}")

    def enqueue_output(self):
        if not self.proc or not self.proc.stdout:
            return

        for line in self.proc.stdout:
            self.output_queue.put(self.clean_line(line))

        self.output_queue.put(None)

    def clean_line(self, line):
        line = ANSI_ESCAPE_RE.sub("", line)
        return CONTROL_CHARS_RE.sub("", line).strip()

    def send_command(self, command):
        if not self.proc or self.proc.poll() is not None or not self.proc.stdin:
            return

        logger.debug(f"bluetoothctl <= {command}")
        self.proc.stdin.write(f"{command}\n")
        self.proc.stdin.flush()

    def consume_output(self, timeout):
        while not self.stop_event.is_set():
            try:
                line = self.output_queue.get(timeout=timeout)
            except queue.Empty:
                break

            if line is None:
                raise RuntimeError("bluetoothctl session ended unexpectedly")

            if line:
                self.handle_output_line(line)

            timeout = 0

    def handle_output_line(self, line):
        lower_line = line.lower()
        logger.debug(f"bluetoothctl => {line}")
        self.last_event = line

        device_match = DEVICE_LINE_RE.search(line)
        if device_match:
            self.current_device["mac"] = device_match.group(1)
            self.current_device["name"] = device_match.group(2).strip()

        if "confirm passkey" in lower_line or "request confirmation" in lower_line:
            self.current_pin = self.extract_pin(line)
            self.pin_updated_at = time.time()
            self.last_error = ""
            self.send_command("yes")
            return

        if "enter pin code" in lower_line or "enter passkey" in lower_line:
            pin = self.settings["bluetooth_pairing_pin"] or self.generate_pin()
            self.current_pin = pin
            self.pin_updated_at = time.time()
            self.last_error = ""
            self.send_command(pin)
            return

        if (
            "authorize service" in lower_line
            or "request authorization" in lower_line
            or "accept pairing" in lower_line
        ):
            self.send_command("yes")
            return

        if "pairing successful" in lower_line:
            self.current_pin = None
            self.last_pairing_success_at = time.time()
            self.last_error = ""
            if self.current_device["mac"]:
                self.trust_device(self.current_device["mac"])
            return

        if "failed to pair" in lower_line or "authenticationfailed" in lower_line:
            self.current_pin = None
            self.last_error = line
            self.last_error_at = time.time()
            return

    def extract_pin(self, line):
        pin_match = PIN_RE.search(line)
        if pin_match:
            return pin_match.group(1)
        return None

    def generate_pin(self):
        return f"{random.randint(0, 999999):06d}"

    def apply_adapter_settings(self):
        if not self.last_applied_settings.get("power_on"):
            self.send_command("power on")
            self.last_applied_settings["power_on"] = True

        alias = self.settings["bluetooth_alias"]
        if self.last_applied_settings.get("alias") != alias:
            self.send_command(f"system-alias {alias}")
            self.last_applied_settings["alias"] = alias

        timeout = self.settings["bluetooth_discoverable_timeout"]
        if self.last_applied_settings.get("discoverable_timeout") != timeout:
            self.send_command(f"discoverable-timeout {timeout}")
            self.last_applied_settings["discoverable_timeout"] = timeout

        enabled = self.settings["bluetooth_pairing_enabled"]
        if self.last_applied_settings.get("pairing_enabled") == enabled:
            return

        if enabled:
            self.send_command("pairable on")
            self.send_command("discoverable on")
        else:
            self.send_command("discoverable off")
            self.send_command("pairable off")

        self.last_applied_settings["pairing_enabled"] = enabled

    def refresh_state(self):
        self.refresh_adapter_state()
        self.refresh_devices()
        self.prune_temporary_state()

    def refresh_adapter_state(self):
        output = self.run_command(["bluetoothctl", "show"])
        self.adapter_state["powered"] = "Powered: yes" in output
        self.adapter_state["pairable"] = "Pairable: yes" in output
        self.adapter_state["discoverable"] = "Discoverable: yes" in output

        alias = self.parse_info_field(output, "Alias")
        if alias:
            self.adapter_state["alias"] = alias

    def refresh_devices(self):
        output = self.run_command(["bluetoothctl", "devices", "Paired"])
        paired_devices = []

        for raw_line in output.splitlines():
            line = raw_line.strip()
            match = DEVICE_LINE_RE.match(line)
            if not match:
                continue

            mac_address = match.group(1)
            device_name = match.group(2).strip()
            info_output = self.run_command(["bluetoothctl", "info", mac_address])
            trusted = "Trusted: yes" in info_output
            connected = "Connected: yes" in info_output
            info_name = self.parse_info_field(info_output, "Name") or device_name
            entry = {
                "mac": mac_address,
                "name": info_name,
                "trusted": trusted,
                "connected": connected,
            }
            paired_devices.append(entry)

            if not trusted:
                self.trust_device(mac_address)

        self.paired_devices = paired_devices
        self.connected_devices = [device for device in paired_devices if device["connected"]]

    def trust_device(self, mac_address):
        if not mac_address:
            return

        output = self.run_command(["bluetoothctl", "trust", mac_address])
        if "trust succeeded" in output.lower():
            logger.info(f"Trusted Bluetooth device {mac_address}")

    def prune_temporary_state(self):
        now = time.time()

        if self.current_pin and now - self.pin_updated_at > 90:
            self.current_pin = None

        if self.last_error and now - self.last_error_at > 30:
            self.last_error = ""

    def parse_info_field(self, output, key):
        prefix = f"{key}:"
        for line in output.splitlines():
            stripped = line.strip()
            if stripped.startswith(prefix):
                return stripped.split(":", 1)[1].strip()
        return ""

    def run_command(self, command):
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError:
            return ""

        return (result.stdout or "") + (result.stderr or "")

    def build_ssh_targets(self):
        targets = []
        seen_values = set()

        tailscale_dns = self.get_tailscale_dns_name()
        tailscale_ip = self.get_tailscale_ip()
        ipv4_addresses = self.get_ipv4_addresses()

        candidate_targets = []
        if tailscale_ip:
            candidate_targets.append(("Tailscale", tailscale_ip))
        if tailscale_dns:
            candidate_targets.append(("Tailnet", tailscale_dns))

        preferred_interfaces = ("wlan0", "eth0", "usb0")
        for interface_name in preferred_interfaces:
            if interface_name in ipv4_addresses:
                candidate_targets.append((interface_name, ipv4_addresses[interface_name]))

        for interface_name, address in ipv4_addresses.items():
            if interface_name not in preferred_interfaces and interface_name != "tailscale0":
                candidate_targets.append((interface_name, address))

        for label, value in candidate_targets:
            if not value or value in seen_values:
                continue

            seen_values.add(value)
            targets.append({"label": label, "value": value})

        return targets

    def get_ipv4_addresses(self):
        output = self.run_command(["ip", "-o", "-4", "addr", "show", "up", "scope", "global"])
        addresses = {}

        for line in output.splitlines():
            parts = line.split()
            if len(parts) < 4:
                continue

            interface_name = parts[1]
            if interface_name == "lo":
                continue

            address = parts[3].split("/", 1)[0]
            addresses[interface_name] = address

        return addresses

    def get_tailscale_dns_name(self):
        if not shutil.which("tailscale"):
            return ""

        output = self.run_command(["tailscale", "status", "--json"])
        try:
            data = json.loads(output)
        except json.JSONDecodeError:
            return ""

        dns_name = str(data.get("Self", {}).get("DNSName", "")).strip()
        return dns_name.rstrip(".")

    def get_tailscale_ip(self):
        if not shutil.which("tailscale"):
            return ""

        output = self.run_command(["tailscale", "ip", "-4"])
        for line in output.splitlines():
            candidate = line.strip()
            if candidate:
                return candidate
        return ""

    def build_state(self):
        ssh_targets = self.build_ssh_targets()
        ssh_user = self.settings["bluetooth_ssh_user"]
        primary_host = ssh_targets[0]["value"] if ssh_targets else ""
        display_host = self.select_display_host(ssh_targets)
        overlay_lines = self.build_display_lines(display_host, ssh_user)

        return {
            "enabled": self.settings["bluetooth_pairing_enabled"],
            "powered": self.adapter_state["powered"],
            "pairable": self.adapter_state["pairable"],
            "discoverable": self.adapter_state["discoverable"],
            "status": self.get_status(),
            "alias": self.adapter_state["alias"],
            "device_name": self.current_device["name"],
            "device_mac": self.current_device["mac"],
            "pin": self.current_pin,
            "last_error": self.last_error,
            "last_event": self.last_event,
            "paired_devices": self.paired_devices,
            "connected_devices": self.connected_devices,
            "ssh_user": ssh_user,
            "ssh_host": primary_host,
            "ssh_command": f"ssh {ssh_user}@{primary_host}" if primary_host else "",
            "ssh_targets": ssh_targets,
            "display_overlay": self.should_show_overlay(),
            "display_lines": overlay_lines,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    def select_display_host(self, ssh_targets):
        if not ssh_targets:
            return "unavailable"

        for target in ssh_targets:
            if re.match(r"^\d+\.\d+\.\d+\.\d+$", target["value"]):
                return target["value"]

        return self.truncate_text(ssh_targets[0]["value"], 18)

    def truncate_text(self, text, limit):
        if len(text) <= limit:
            return text
        return f"{text[: limit - 3]}..."

    def get_status(self):
        if not self.settings["bluetooth_pairing_enabled"]:
            return "inactive"
        if self.last_error:
            return "error"
        if self.current_pin:
            return "confirm"
        if self.connected_devices:
            return "connected"
        if self.last_pairing_success_at and time.time() - self.last_pairing_success_at < 180:
            return "paired"
        if self.adapter_state["powered"]:
            return "ready"
        return "starting"

    def should_show_overlay(self):
        status = self.get_status()
        if status in {"confirm", "paired", "connected", "error"}:
            return True
        if status == "ready" and not self.paired_devices:
            return True
        return False

    def build_display_lines(self, display_host, ssh_user):
        status = self.get_status()
        device_name = self.current_device["name"]
        if not device_name and self.connected_devices:
            device_name = self.connected_devices[0]["name"]
        if not device_name and self.paired_devices:
            device_name = self.paired_devices[0]["name"]

        if status == "confirm":
            lines = ["PAIR CODE", self.current_pin or "CHECK PHONE"]
        elif status == "paired":
            lines = ["BT PAIRED", self.truncate_text(device_name or "Ready", 18)]
        elif status == "connected":
            lines = ["BT CONNECTED", self.truncate_text(device_name or "Phone linked", 18)]
        elif status == "error":
            lines = ["BT ERROR", self.truncate_text(self.last_error, 18)]
        elif status == "ready":
            lines = ["BT READY", "PAIR FROM PHONE"]
        else:
            lines = ["BT STARTING"]

        lines.append(f"USER {self.truncate_text(ssh_user, 13)}")
        lines.append(f"SSH {self.truncate_text(display_host, 14)}")
        return lines

    def write_state(self):
        state = self.build_state()
        os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
        temp_path = f"{self.state_path}.tmp"

        with open(temp_path, "w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=2)

        os.replace(temp_path, self.state_path)

    def cleanup(self):
        try:
            if self.proc and self.proc.poll() is None:
                self.send_command("discoverable off")
                self.send_command("pairable off")
                self.send_command("quit")
                self.proc.terminate()
                self.proc.wait(timeout=5)
        except Exception as exc:
            logger.error(f"Bluetooth cleanup failed: {exc}")


def main():
    manager = BluetoothManager()

    def stop_handler(signum, frame):
        del signum, frame
        manager.stop_event.set()

    signal.signal(signal.SIGINT, stop_handler)
    signal.signal(signal.SIGTERM, stop_handler)

    try:
        manager.run()
    except Exception as exc:
        logger.error(f"Bluetooth manager crashed: {exc}")
        manager.last_error = str(exc)
        manager.last_error_at = time.time()
        try:
            manager.write_state()
        except Exception:
            pass
        raise


if __name__ == "__main__":
    main()
