import secrets
import subprocess
import threading
import time
import uuid


class WifiSetupManager:
    """Manage the temporary Wi-Fi access point used for first-time setup."""

    interface = "wlan0"
    access_point_connection = "bjorn-setup"
    access_point_ip = "10.42.0.1"

    def __init__(self, shared_data, logger, command_runner=None):
        self.shared_data = shared_data
        self.logger = logger
        self.command_runner = command_runner or subprocess.run
        self.lock = threading.Lock()
        self.connecting = False
        self.access_point_active = False
        self.retry_after = 0
        self._initialize_shared_state()

    def _initialize_shared_state(self):
        self.shared_data.wifi_setup_active = False
        self.shared_data.wifi_setup_ssid = ""
        self.shared_data.wifi_setup_password = ""
        self.shared_data.wifi_setup_ip = self.access_point_ip
        self.shared_data.wifi_setup_status = ""
        self.shared_data.wifi_setup_networks = []

    def _run_nmcli(self, *arguments, check=True, timeout=20):
        result = self.command_runner(
            ["nmcli", *arguments],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if check and result.returncode != 0:
            message = result.stderr.strip() or result.stdout.strip()
            raise RuntimeError(message or "NetworkManager command failed")
        return result

    def is_station_connected(self):
        """Return true only for a connected infrastructure Wi-Fi profile."""
        try:
            result = self._run_nmcli(
                "--get-values", "GENERAL.CONNECTION", "device", "show", self.interface
            )
            connection = result.stdout.strip()
            if not connection or connection == "--":
                return False
            mode = self._run_nmcli(
                "--get-values",
                "802-11-wireless.mode",
                "connection",
                "show",
                "id",
                connection,
            )
            return mode.stdout.strip() in {"infrastructure", "adhoc"}
        except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
            self.logger.debug(f"Could not check Wi-Fi connection: {error}")
            return False

    def scan_networks(self):
        """Scan before enabling the AP; one Wi-Fi radio cannot reliably do both."""
        try:
            result = self._run_nmcli(
                "--terse",
                "--escape",
                "no",
                "--fields",
                "SSID",
                "device",
                "wifi",
                "list",
                "ifname",
                self.interface,
                "--rescan",
                "yes",
                timeout=30,
            )
            networks = list(dict.fromkeys(
                ssid.rstrip("\r")
                for ssid in result.stdout.splitlines()
                if ssid.strip()
            ))
            self.shared_data.wifi_setup_networks = networks
            return networks
        except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
            self.logger.warning(f"Could not scan for Wi-Fi networks: {error}")
            self.shared_data.wifi_setup_networks = []
            return []

    def start_access_point(self, force=False):
        if self.access_point_active or (self.connecting and not force):
            return self.access_point_active
        if time.monotonic() < self.retry_after:
            return False

        try:
            self._run_nmcli("radio", "wifi", "on")
            self._run_nmcli(
                "connection", "down", "id", self.access_point_connection, check=False
            )
            self.scan_networks()

            suffix = secrets.randbelow(9000) + 1000
            password = f"bjorn{secrets.randbelow(999) + 1:03d}"
            ssid = f"Bjorn-connect-{suffix}"

            self.shared_data.wifi_setup_ssid = ssid
            self.shared_data.wifi_setup_password = password
            self.shared_data.wifi_setup_status = "Starting setup Wi-Fi..."
            self._run_nmcli(
                "connection", "delete", "id", self.access_point_connection, check=False
            )
            self._run_nmcli(
                "connection",
                "add",
                "type",
                "wifi",
                "ifname",
                self.interface,
                "con-name",
                self.access_point_connection,
                "ssid",
                ssid,
            )
            self._run_nmcli(
                "connection",
                "modify",
                "id",
                self.access_point_connection,
                "connection.autoconnect",
                "no",
                "802-11-wireless.mode",
                "ap",
                "802-11-wireless.band",
                "bg",
                "wifi-sec.key-mgmt",
                "wpa-psk",
                "wifi-sec.psk",
                password,
                "ipv4.method",
                "shared",
                "ipv6.method",
                "disabled",
            )
            self._run_nmcli(
                "--wait",
                "20",
                "connection",
                "up",
                "id",
                self.access_point_connection,
                "ifname",
                self.interface,
                timeout=25,
            )
            self.access_point_active = True
            self.shared_data.wifi_setup_active = True
            self.shared_data.wifi_setup_ip = self._get_access_point_ip()
            self.shared_data.wifi_setup_status = "Connect to Bjorn's setup Wi-Fi."
            self.logger.info(f"Wi-Fi setup access point started: {ssid}")
            return True
        except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
            self.access_point_active = False
            self.shared_data.wifi_setup_active = False
            self.shared_data.wifi_setup_status = "Could not start setup Wi-Fi."
            self.retry_after = time.monotonic() + 60
            self.logger.error(f"Could not start Wi-Fi setup access point: {error}")
            return False

    def _get_access_point_ip(self):
        try:
            result = self._run_nmcli(
                "--get-values", "IP4.ADDRESS", "device", "show", self.interface
            )
            address = result.stdout.strip().splitlines()[0].split("/", 1)[0]
            return address or self.access_point_ip
        except (IndexError, OSError, RuntimeError, subprocess.TimeoutExpired):
            return self.access_point_ip

    def submit_credentials(self, ssid, password):
        if not isinstance(ssid, str) or not isinstance(password, str):
            raise ValueError("Network name and password must be text.")
        if not ssid.strip() or len(ssid.encode("utf-8")) > 32:
            raise ValueError("Choose a valid Wi-Fi network name.")
        if "\n" in ssid or "\r" in ssid or "\x00" in ssid:
            raise ValueError("The Wi-Fi network name contains unsupported characters.")
        password_length = len(password.encode("utf-8"))
        if password and (password_length < 8 or password_length > 63):
            raise ValueError("Wi-Fi passwords must be 8 to 63 characters.")
        if "\n" in password or "\r" in password or "\x00" in password:
            raise ValueError("The Wi-Fi password contains unsupported characters.")

        with self.lock:
            if self.connecting:
                raise RuntimeError("A Wi-Fi connection attempt is already running.")
            self.connecting = True
            self.shared_data.wifi_setup_status = f"Connecting to {ssid}..."

        worker = threading.Thread(
            target=self._connect_worker,
            args=(ssid, password),
            name="wifi-setup-connect",
            daemon=True,
        )
        try:
            worker.start()
        except RuntimeError:
            with self.lock:
                self.connecting = False
            self.shared_data.wifi_setup_status = "Could not start the connection attempt."
            raise

    def _connect_worker(self, ssid, password):
        connection_id = f"bjorn-wifi-{uuid.uuid4().hex[:8]}"
        try:
            self._run_nmcli(
                "connection",
                "add",
                "type",
                "wifi",
                "ifname",
                self.interface,
                "con-name",
                connection_id,
                "ssid",
                ssid,
            )
            modifications = [
                "connection.autoconnect", "yes",
                "ipv4.method", "auto",
                "ipv6.method", "auto",
            ]
            if password:
                modifications.extend(
                    ["wifi-sec.key-mgmt", "wpa-psk", "wifi-sec.psk", password]
                )
            self._run_nmcli(
                "connection", "modify", "id", connection_id, *modifications
            )

            self._run_nmcli(
                "connection", "down", "id", self.access_point_connection, check=False
            )
            self.access_point_active = False
            self.shared_data.wifi_setup_active = False
            self._run_nmcli(
                "--wait",
                "30",
                "connection",
                "up",
                "id",
                connection_id,
                "ifname",
                self.interface,
                timeout=35,
            )

            # Keep the established profile name used by Bjorn's existing Wi-Fi UI.
            try:
                self._run_nmcli(
                    "connection", "delete", "id", "preconfigured", check=False
                )
                self._run_nmcli(
                    "connection",
                    "modify",
                    "id",
                    connection_id,
                    "connection.id",
                    "preconfigured",
                )
            except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
                self.logger.warning(f"Could not rename the Wi-Fi profile: {error}")
            self.shared_data.wifi_connected = True
            self.shared_data.wifi_setup_status = f"Connected to {ssid}."
            self.shared_data.wifi_setup_password = ""
            self.logger.info(f"Connected to configured Wi-Fi network: {ssid}")
        except Exception as error:
            try:
                self._run_nmcli(
                    "connection", "delete", "id", connection_id, check=False
                )
            except Exception as cleanup_error:
                self.logger.debug(f"Could not remove temporary Wi-Fi profile: {cleanup_error}")
            self.shared_data.wifi_setup_active = True
            self.shared_data.wifi_setup_status = (
                "Could not connect. Check the password and try again."
            )
            self.logger.warning(f"Wi-Fi setup connection failed for {ssid}: {error}")
            self.start_access_point(force=True)
        finally:
            with self.lock:
                self.connecting = False
