import importlib
import ipaddress
import os
import subprocess
import sys
import tempfile
import threading
import types
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch


class NullLogger:
    def __init__(self, *args, **kwargs):
        pass

    def error(self, message):
        pass

    def info(self, message):
        pass

    def warning(self, message):
        pass


def scanning_import_stubs():
    """Return lightweight stubs for dependencies unused by these unit tests."""
    pandas = types.ModuleType("pandas")
    netifaces = types.ModuleType("netifaces")
    netifaces.AF_INET = 2

    rich = types.ModuleType("rich")
    rich_console = types.ModuleType("rich.console")
    rich_console.Console = object
    rich_table = types.ModuleType("rich.table")
    rich_table.Table = object
    rich_text = types.ModuleType("rich.text")
    rich_text.Text = str
    rich_progress = types.ModuleType("rich.progress")
    rich_progress.Progress = object

    getmac = types.ModuleType("getmac")
    getmac.get_mac_address = lambda **kwargs: None

    shared = types.ModuleType("shared")
    shared.SharedData = object

    logger = types.ModuleType("logger")
    logger.Logger = NullLogger

    nmap = types.ModuleType("nmap")
    nmap.PortScanner = object

    return {
        "pandas": pandas,
        "netifaces": netifaces,
        "rich": rich,
        "rich.console": rich_console,
        "rich.table": rich_table,
        "rich.text": rich_text,
        "rich.progress": rich_progress,
        "getmac": getmac,
        "shared": shared,
        "logger": logger,
        "nmap": nmap,
    }


class FakeNmapScanner:
    def __init__(self, hosts):
        self.hosts = hosts

    def all_hosts(self):
        return self.hosts


class ScanningWorkerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module_patch = patch.dict(sys.modules, scanning_import_stubs())
        cls.module_patch.start()
        sys.modules.pop("actions.scanning", None)
        cls.scanning_module = importlib.import_module("actions.scanning")
        cls.network_scanner = cls.scanning_module.NetworkScanner

    @classmethod
    def tearDownClass(cls):
        sys.modules.pop("actions.scanning", None)
        cls.module_patch.stop()

    def test_port_scanner_waits_for_workers_and_deduplicates_ports(self):
        outer = SimpleNamespace(
            lock=threading.Lock(),
            logger=Mock(),
            shutdown_requested=Mock(return_value=False),
        )
        open_ports = {"192.0.2.10": []}
        scanner = self.network_scanner.PortScanner(
            outer,
            "192.0.2.10",
            open_ports,
            20,
            24,
            [22, 80],
        )

        started = threading.Event()
        release = threading.Event()
        completed = []

        def delayed_scan(port):
            started.set()
            release.wait(timeout=2)
            completed.append(port)

        scanner.scan = delayed_scan
        runner = threading.Thread(target=scanner.start)
        runner.start()

        self.assertTrue(started.wait(timeout=1))
        self.assertTrue(runner.is_alive())

        release.set()
        runner.join(timeout=2)

        self.assertFalse(runner.is_alive())
        self.assertEqual(sorted(completed), [20, 21, 22, 23, 80])

    def test_worker_limits_fit_resource_constrained_devices(self):
        self.assertLessEqual(
            self.scanning_module.MAX_PORT_SCAN_WORKERS,
            32,
        )
        self.assertLessEqual(
            self.scanning_module.MAX_HOST_SCAN_WORKERS,
            16,
        )

    def test_progress_updates_without_a_background_refresh_thread(self):
        progress_options = []
        progress_updates = []

        class FakeProgress:
            def __init__(self, **kwargs):
                progress_options.append(kwargs)

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_value, traceback):
                del exc_type, exc_value, traceback

            def add_task(self, description, total):
                del description, total
                return 1

            def update(self, task, **kwargs):
                del task
                progress_updates.append(kwargs)

        class FakePortScanner:
            def __init__(self, *args, **kwargs):
                del args, kwargs

            def start(self):
                pass

        outer = SimpleNamespace(
            GetIpFromCsv=Mock(
                return_value=SimpleNamespace(
                    ip_list=["192.0.2.10"],
                )
            ),
            PortScanner=FakePortScanner,
            shutdown_requested=Mock(return_value=False),
            wait_or_cancel=Mock(),
        )
        scan_ports = object.__new__(self.network_scanner.ScanPorts)
        scan_ports.outer_instance = outer
        scan_ports.scan_network_and_write_to_csv = Mock()
        scan_ports.csv_scan_file = "scan.csv"
        scan_ports.portstart = 1
        scan_ports.portend = 2
        scan_ports.extra_ports = []
        scan_ports.csv_result_file = "result.csv"
        scan_ports.netkbfile = "netkb.csv"

        with (
            patch.object(self.scanning_module, "Progress", FakeProgress),
            patch.object(self.scanning_module.time, "sleep"),
        ):
            scan_ports.start()

        self.assertEqual(progress_options, [{"auto_refresh": False}])
        self.assertEqual(
            progress_updates,
            [{"advance": 1, "refresh": True}],
        )

    def test_expected_shutdown_does_not_log_scan_exception_as_error(self):
        scanner = object.__new__(self.network_scanner)
        scanner.shared_data = SimpleNamespace(
            should_exit=True,
            orchestrator_should_exit=True,
        )
        scanner.logger = Mock()
        scanner.get_network = Mock(
            side_effect=RuntimeError("interrupted nmap XML")
        )

        scanner.scan()

        scanner.logger.error.assert_not_called()
        scanner.logger.info.assert_any_call(
            "Network scan stopped during application shutdown."
        )

    def test_host_discovery_parses_completed_nmap_xml(self):
        scanner = object.__new__(self.network_scanner)
        scanner.shared_data = SimpleNamespace(
            should_exit=False,
            orchestrator_should_exit=False,
        )
        scanner.discovery_process = None
        scanner.nm = SimpleNamespace(
            _nmap_path="/usr/bin/nmap",
            analyse_nmap_xml_scan=Mock(),
        )
        process = Mock()
        process.communicate.return_value = (
            b"<nmaprun></nmaprun>",
            b"",
        )
        process.poll.return_value = 0

        with patch.object(
            self.scanning_module.subprocess,
            "Popen",
            return_value=process,
        ) as popen:
            scanner.run_host_discovery(
                ipaddress.ip_network("192.0.2.0/24")
            )

        popen.assert_called_once_with(
            [
                "/usr/bin/nmap",
                "-oX",
                "-",
                "192.0.2.0/24",
                "-sn",
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        scanner.nm.analyse_nmap_xml_scan.assert_called_once_with(
            nmap_xml_output=b"<nmaprun></nmaprun>",
            nmap_err="",
        )
        self.assertIsNone(scanner.discovery_process)

    def test_host_discovery_terminates_nmap_during_shutdown(self):
        scanner = object.__new__(self.network_scanner)
        scanner.shared_data = SimpleNamespace(
            should_exit=False,
            orchestrator_should_exit=False,
        )
        scanner.discovery_process = None
        scanner.nm = SimpleNamespace(
            _nmap_path="/usr/bin/nmap",
            analyse_nmap_xml_scan=Mock(),
        )

        class BlockingProcess:
            def __init__(self):
                self.terminated = False

            def communicate(self, timeout=None):
                if not self.terminated:
                    scanner.shared_data.should_exit = True
                    raise subprocess.TimeoutExpired("nmap", timeout)
                return b"", b""

            def poll(self):
                return 0 if self.terminated else None

            def terminate(self):
                self.terminated = True

            def kill(self):
                self.terminated = True

        process = BlockingProcess()
        with (
            patch.object(
                self.scanning_module.subprocess,
                "Popen",
                return_value=process,
            ),
            self.assertRaises(
                self.scanning_module.NetworkScanCancelled
            ),
        ):
            scanner.run_host_discovery(
                ipaddress.ip_network("192.0.2.0/24")
            )

        self.assertTrue(process.terminated)
        scanner.nm.analyse_nmap_xml_scan.assert_not_called()
        self.assertIsNone(scanner.discovery_process)

    def test_host_discovery_waits_for_workers_before_sorting_results(self):
        hosts = ["192.0.2.10", "192.0.2.11"]
        workers_finished = threading.Event()
        release = threading.Event()
        completed = []

        with tempfile.TemporaryDirectory() as temp_dir:
            csv_scan_file = os.path.join(temp_dir, "scan.csv")
            outer = SimpleNamespace(
                lock=threading.Lock(),
                logger=Mock(),
                nm=FakeNmapScanner(hosts),
                run_host_discovery=Mock(),
                shutdown_requested=Mock(return_value=False),
                check_if_csv_scan_file_exists=Mock(),
                sort_and_write_csv=Mock(),
            )

            scan_ports = object.__new__(self.network_scanner.ScanPorts)
            scan_ports.outer_instance = outer
            scan_ports.network = ipaddress.ip_network("192.0.2.0/24")
            scan_ports.csv_scan_file = csv_scan_file
            scan_ports.csv_result_file = os.path.join(temp_dir, "result.csv")
            scan_ports.netkbfile = os.path.join(temp_dir, "netkb.csv")

            def delayed_host_scan(host):
                release.wait(timeout=2)
                completed.append(host)
                if len(completed) == len(hosts):
                    workers_finished.set()

            scan_ports.scan_host = delayed_host_scan
            runner = threading.Thread(
                target=scan_ports.scan_network_and_write_to_csv
            )
            runner.start()

            self.assertTrue(runner.is_alive())
            self.assertFalse(outer.sort_and_write_csv.called)

            release.set()
            self.assertTrue(workers_finished.wait(timeout=1))
            runner.join(timeout=2)

            self.assertFalse(runner.is_alive())
            self.assertCountEqual(completed, hosts)
            outer.run_host_discovery.assert_called_once_with(
                scan_ports.network
            )
            outer.sort_and_write_csv.assert_called_once_with(csv_scan_file)


if __name__ == "__main__":
    unittest.main()
