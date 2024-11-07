#scanning.py
# This script performs a network scan to identify live hosts, their MAC addresses, and open ports.
# The results are saved to CSV files and displayed using Rich for enhanced visualization.

import os
import threading
import csv
import pandas as pd
import socket
import netifaces
import time
import glob
import logging
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich.progress import Progress
from getmac import get_mac_address as gma
from shared import SharedData
from logger import Logger
import ipaddress
import nmap

logger = Logger(name="scanning.py", level=logging.DEBUG)

b_class = "NetworkScanner"
b_module = "scanning"
b_status = "network_scanner"
b_port = None
b_parent = None
b_priority = 1

class NetworkScanner:
    """
    This class handles the entire network scanning process.
    """
    def __init__(self, shared_data):
        self.shared_data = shared_data
        self.logger = logger
        self.displaying_csv = shared_data.displaying_csv
        self.blacklistcheck = shared_data.blacklistcheck
        self.mac_scan_blacklist = shared_data.mac_scan_blacklist
        self.ip_scan_blacklist = shared_data.ip_scan_blacklist
        self.console = Console()
        self.lock = threading.Lock()
        self.currentdir = shared_data.currentdir
        self.semaphore = threading.Semaphore(200)  # Limit the number of active threads to 20
        self.nm = nmap.PortScanner()  # Initialize nmap.PortScanner()
        self.running = False

    def check_if_csv_scan_file_exists(self, csv_scan_file, csv_result_file, netkbfile):
        """
        Checks and prepares the necessary CSV files for the scan.
        """
        with self.lock:
            try:
                if not os.path.exists(os.path.dirname(csv_scan_file)):
                    os.makedirs(os.path.dirname(csv_scan_file))
                if not os.path.exists(os.path.dirname(netkbfile)):
                    os.makedirs(os.path.dirname(netkbfile))
                if os.path.exists(csv_scan_file):
                    os.remove(csv_scan_file)
                if os.path.exists(csv_result_file):
                    os.remove(csv_result_file)
                if not os.path.exists(netkbfile):
                    with open(netkbfile, 'w', newline='') as file:
                        writer = csv.writer(file)
                        writer.writerow(['MAC Address', 'IPs', 'Hostnames', 'Alive', 'Ports'])
            except Exception as e:
                self.logger.error(f"Error in check_if_csv_scan_file_exists: {e}")

    def get_current_timestamp(self):
        """
        Returns the current timestamp in a specific format.
        """
        return datetime.now().strftime("%Y%m%d_%H%M%S")

    def ip_key(self, ip):
        """
        Converts an IP address to a tuple of integers for sorting.
        """
        if ip == "STANDALONE":
            return (0, 0, 0, 0)
        try:
            return tuple(map(int, ip.split('.')))
        except ValueError as e:
            self.logger.error(f"Error in ip_key: {e}")
            return (0, 0, 0, 0)

    def sort_and_write_csv(self, csv_scan_file):
        """
        Sorts the CSV file based on IP addresses and writes the sorted content back to the file.
        """
        with self.lock:
            try:
                with open(csv_scan_file, 'r') as file:
                    lines = file.readlines()
                sorted_lines = [lines[0]] + sorted(lines[1:], key=lambda x: self.ip_key(x.split(',')[0]))
                with open(csv_scan_file, 'w') as file:
                    file.writelines(sorted_lines)
            except Exception as e:
                self.logger.error(f"Error in sort_and_write_csv: {e}")

    class GetIpFromCsv:
        """
        Helper class to retrieve IP addresses, hostnames, and MAC addresses from a CSV file.
        """
        def __init__(self, outer_instance, csv_scan_file):
            self.outer_instance = outer_instance
            self.csv_scan_file = csv_scan_file
            self.ip_list = []
            self.hostname_list = []
            self.mac_list = []
            self.get_ip_from_csv()

        def get_ip_from_csv(self):
            """
            Reads IP addresses, hostnames, and MAC addresses from the CSV file.
            """
            with self.outer_instance.lock:
                try:
                    with open(self.csv_scan_file, 'r') as csv_scan_file:
                        csv_reader = csv.reader(csv_scan_file)
                        next(csv_reader)
                        for row in csv_reader:
                            if row[0] == "STANDALONE" or row[1] == "STANDALONE" or row[2] == "STANDALONE":
                                continue
                            if not self.outer_instance.blacklistcheck or (row[2] not in self.outer_instance.mac_scan_blacklist and row[0] not in self.outer_instance.ip_scan_blacklist):
                                self.ip_list.append(row[0])
                                self.hostname_list.append(row[1])
                                self.mac_list.append(row[2])
                except Exception as e:
                    self.outer_instance.logger.error(f"Error in get_ip_from_csv: {e}")

    def update_netkb(self, netkbfile, netkb_data, alive_macs):
        """
        Updates the net knowledge base (netkb) file with the scan results.
        """
        with self.lock:
            try:
                netkb_entries = {}
                existing_action_columns = []

                # Read existing CSV file
                if os.path.exists(netkbfile):
                    with open(netkbfile, 'r') as file:
                        reader = csv.DictReader(file)
                        existing_headers = reader.fieldnames
                        existing_action_columns = [header for header in existing_headers if header not in ["MAC Address", "IPs", "Hostnames", "Alive", "Ports"]]
                        for row in reader:
                            mac = row["MAC Address"]
                            ips = row["IPs"].split(';')
                            hostnames = row["Hostnames"].split(';')
                            alive = row["Alive"]
                            ports = row["Ports"].split(';')
                            netkb_entries[mac] = {
                                'IPs': set(ips) if ips[0] else set(),
                                'Hostnames': set(hostnames) if hostnames[0] else set(),
                                'Alive': alive,
                                'Ports': set(ports) if ports[0] else set()
                            }
                            for action in existing_action_columns:
                                netkb_entries[mac][action] = row.get(action, "")

                ip_to_mac = {}  # Dictionary to track IP to MAC associations

                for data in netkb_data:
                    mac, ip, hostname, ports = data
                    if not mac or mac == "STANDALONE" or ip == "STANDALONE" or hostname == "STANDALONE":
                        continue
                    
                    # Check if MAC address is "00:00:00:00:00:00"
                    if mac == "00:00:00:00:00:00":
                        continue

                    if self.blacklistcheck and (mac in self.mac_scan_blacklist or ip in self.ip_scan_blacklist):
                        continue

                    # Check if IP is already associated with a different MAC
                    if ip in ip_to_mac and ip_to_mac[ip] != mac:
                        # Mark the old MAC as not alive
                        old_mac = ip_to_mac[ip]
                        if old_mac in netkb_entries:
                            netkb_entries[old_mac]['Alive'] = '0'

                    # Update or create entry for the new MAC
                    ip_to_mac[ip] = mac
                    if mac in netkb_entries:
                        netkb_entries[mac]['IPs'].add(ip)
                        netkb_entries[mac]['Hostnames'].add(hostname)
                        netkb_entries[mac]['Alive'] = '1'
                        netkb_entries[mac]['Ports'].update(map(str, ports))
                    else:
                        netkb_entries[mac] = {
                            'IPs': {ip},
                            'Hostnames': {hostname},
                            'Alive': '1',
                            'Ports': set(map(str, ports))
                        }
                        for action in existing_action_columns:
                            netkb_entries[mac][action] = ""

                # Update all existing entries to mark missing hosts as not alive
                for mac in netkb_entries:
                    if mac not in alive_macs:
                        netkb_entries[mac]['Alive'] = '0'

                # Remove entries with multiple IP addresses for a single MAC address
                netkb_entries = {mac: data for mac, data in netkb_entries.items() if len(data['IPs']) == 1}

                sorted_netkb_entries = sorted(netkb_entries.items(), key=lambda x: self.ip_key(sorted(x[1]['IPs'])[0]))

                with open(netkbfile, 'w', newline='') as file:
                    writer = csv.writer(file)
                    writer.writerow(existing_headers)  # Use existing headers
                    for mac, data in sorted_netkb_entries:
                        row = [
                            mac,
                            ';'.join(sorted(data['IPs'], key=self.ip_key)),
                            ';'.join(sorted(data['Hostnames'])),
                            data['Alive'],
                            ';'.join(sorted(data['Ports'], key=int))
                        ]
                        row.extend(data.get(action, "") for action in existing_action_columns)
                        writer.writerow(row)
            except Exception as e:
                self.logger.error(f"Error in update_netkb: {e}")

    def display_csv(self, file_path):
        """
        Displays the contents of the specified CSV file using Rich for enhanced visualization.
        """
        with self.lock:
            try:
                table = Table(title=f"Contents of {file_path}", show_lines=True)
                with open(file_path, 'r') as file:
                    reader = csv.reader(file)
                    headers = next(reader)
                    for header in headers:
                        table.add_column(header, style="cyan", no_wrap=True)
                    for row in reader:
                        formatted_row = [Text(cell, style="green bold") if cell else Text("", style="on red") for cell in row]
                        table.add_row(*formatted_row)
                self.console.print(table)
            except Exception as e:
                self.logger.error(f"Error in display_csv: {e}")

    def get_network(self):
        """
        Retrieves the network information including the default gateway and subnet.
        """
        try:
            gws = netifaces.gateways()
            default_gateway = gws['default'][netifaces.AF_INET][1]
            iface = netifaces.ifaddresses(default_gateway)[netifaces.AF_INET][0]
            ip_address = iface['addr']
            netmask = iface['netmask']
            cidr = sum([bin(int(x)).count('1') for x in netmask.split('.')])
            network = ipaddress.IPv4Network(f"{ip_address}/{cidr}", strict=False)
            self.logger.info(f"Network: {network}")
            return network
        except Exception as e:
            self.logger.error(f"Error in get_network: {e}")

    def get_mac_address(self, ip, hostname):
        """
        Retrieves the MAC address for the given IP address and hostname.
        """
        try:
            mac = None
            retries = 5
            while not mac and retries > 0:
                mac = gma(ip=ip)
                if not mac:
                    time.sleep(2)  # Attendre 2 secondes avant de réessayer
                    retries -= 1
            if not mac:
                mac = f"{ip}_{hostname}" if hostname else f"{ip}_NoHostname"
            return mac
        except Exception as e:
            self.logger.error(f"Error in get_mac_address: {e}")
            return None

    class PortScanner:
        """
        Helper class to perform port scanning on a target IP.
        """
        def __init__(self, outer_instance, target, open_ports, portstart, portend, extra_ports):
            self.outer_instance = outer_instance
            self.logger = logger
            self.target = target
            self.open_ports = open_ports
            self.portstart = portstart
            self.portend = portend
            self.extra_ports = extra_ports

        def scan(self, port):
            """
            Scans a specific port on the target IP.
            """
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2)
            try:
                con = s.connect((self.target, port))
                self.open_ports[self.target].append(port)
                con.close()
            except:
                pass
            finally:
                s.close()  # Ensure the socket is closed

        def start(self):
            """
            Starts the port scanning process for the specified range and extra ports.
            """
            try:
                for port in range(self.portstart, self.portend):
                    t = threading.Thread(target=self.scan_with_semaphore, args=(port,))
                    t.start()
                for port in self.extra_ports:
                    t = threading.Thread(target=self.scan_with_semaphore, args=(port,))
                    t.start()
            except Exception as e:
                self.logger.info(f"Maximum threads defined in the semaphore reached: {e}")

        def scan_with_semaphore(self, port):
            """
            Scans a port using a semaphore to limit concurrent threads.
            """
            with self.outer_instance.semaphore:
                self.scan(port)

    class ScanPorts:
        """
        Helper class to manage the overall port scanning process for a network.
        """
        def __init__(self, outer_instance, network, portstart, portend, extra_ports):
            self.outer_instance = outer_instance
            self.logger = logger
            self.progress = 0
            self.network = network
            self.portstart = portstart
            self.portend = portend
            self.extra_ports = extra_ports
            self.currentdir = outer_instance.currentdir
            self.scan_results_dir = outer_instance.shared_data.scan_results_dir
            self.timestamp = outer_instance.get_current_timestamp()
            self.csv_scan_file = os.path.join(self.scan_results_dir, f'scan_{network.network_address}_{self.timestamp}.csv')
            self.csv_result_file = os.path.join(self.scan_results_dir, f'result_{network.network_address}_{self.timestamp}.csv')
            self.netkbfile = outer_instance.shared_data.netkbfile
            self.ip_data = None
            self.open_ports = {}
            self.all_ports = []
            self.ip_hostname_list = []

        def scan_network_and_write_to_csv(self):
            """
            Scans the network and writes the results to a CSV file.
            """
            self.outer_instance.check_if_csv_scan_file_exists(self.csv_scan_file, self.csv_result_file, self.netkbfile)
            with self.outer_instance.lock:
                try:
                    with open(self.csv_scan_file, 'a', newline='') as file:
                        writer = csv.writer(file)
                        writer.writerow(['IP', 'Hostname', 'MAC Address'])
                except Exception as e:
                    self.outer_instance.logger.error(f"Error in scan_network_and_write_to_csv (initial write): {e}")

            # Use nmap to scan for live hosts
            self.outer_instance.nm.scan(hosts=str(self.network), arguments='-sn')
            for host in self.outer_instance.nm.all_hosts():
                t = threading.Thread(target=self.scan_host, args=(host,))
                t.start()

            time.sleep(5)
            self.outer_instance.sort_and_write_csv(self.csv_scan_file)

        def scan_host(self, ip):
            """
            Scans a specific host to check if it is alive and retrieves its hostname and MAC address.
            """
            if self.outer_instance.blacklistcheck and ip in self.outer_instance.ip_scan_blacklist:
                return
            try:
                hostname = self.outer_instance.nm[ip].hostname() if self.outer_instance.nm[ip].hostname() else ''
                mac = self.outer_instance.get_mac_address(ip, hostname)
                if not self.outer_instance.blacklistcheck or mac not in self.outer_instance.mac_scan_blacklist:
                    with self.outer_instance.lock:
                        with open(self.csv_scan_file, 'a', newline='') as file:
                            writer = csv.writer(file)
                            writer.writerow([ip, hostname, mac])
                            self.ip_hostname_list.append((ip, hostname, mac))
            except Exception as e:
                self.outer_instance.logger.error(f"Error getting MAC address or writing to file for IP {ip}: {e}")
            self.progress += 1
            time.sleep(0.1)  # Adding a small delay to avoid overwhelming the network

        def get_progress(self):
            """
            Returns the progress of the scanning process.
            """
            return (self.progress / self.total_ips) * 100

        def start(self):
            """
            Starts the network and port scanning process.
            """
            self.scan_network_and_write_to_csv()
            time.sleep(7)
            self.ip_data = self.outer_instance.GetIpFromCsv(self.outer_instance, self.csv_scan_file)
            self.open_ports = {ip: [] for ip in self.ip_data.ip_list}
            with Progress() as progress:
                task = progress.add_task("[cyan]Scanning IPs...", total=len(self.ip_data.ip_list))
                for ip in self.ip_data.ip_list:
                    progress.update(task, advance=1)
                    port_scanner = self.outer_instance.PortScanner(self.outer_instance, ip, self.open_ports, self.portstart, self.portend, self.extra_ports)
                    port_scanner.start()

            self.all_ports = sorted(list(set(port for ports in self.open_ports.values() for port in ports)))
            alive_ips = set(self.ip_data.ip_list)
            return self.ip_data, self.open_ports, self.all_ports, self.csv_result_file, self.netkbfile, alive_ips

    class LiveStatusUpdater:
        """
        Helper class to update the live status of hosts and clean up scan results.
        """
        def __init__(self, source_csv_path, output_csv_path):
            self.logger = logger
            self.source_csv_path = source_csv_path
            self.output_csv_path = output_csv_path

        def read_csv(self):
            """
            Reads the source CSV file into a DataFrame.
            """
            try:
                self.df = pd.read_csv(self.source_csv_path)
            except Exception as e:
                self.logger.error(f"Error in read_csv: {e}")

        def calculate_open_ports(self):
            """
            Calculates the total number of open ports for alive hosts.
            """
            try:
                alive_df = self.df[self.df['Alive'] == 1].copy()
                alive_df.loc[:, 'Ports'] = alive_df['Ports'].fillna('')
                alive_df.loc[:, 'Port Count'] = alive_df['Ports'].apply(lambda x: len(x.split(';')) if x else 0)
                self.total_open_ports = alive_df['Port Count'].sum()
            except Exception as e:
                self.logger.error(f"Error in calculate_open_ports: {e}")

        def calculate_hosts_counts(self):
            """
            Calculates the total and alive host counts.
            """
            try:
                # self.all_known_hosts_count = self.df.shape[0] 
                self.all_known_hosts_count = self.df[self.df['MAC Address'] != 'STANDALONE'].shape[0] 
                self.alive_hosts_count = self.df[self.df['Alive'] == 1].shape[0]
            except Exception as e:
                self.logger.error(f"Error in calculate_hosts_counts: {e}")

        def save_results(self):
            """
            Saves the calculated results to the output CSV file.
            """
            try:
                if os.path.exists(self.output_csv_path):
                    results_df = pd.read_csv(self.output_csv_path)
                    results_df.loc[0, 'Total Open Ports'] = self.total_open_ports
                    results_df.loc[0, 'Alive Hosts Count'] = self.alive_hosts_count
                    results_df.loc[0, 'All Known Hosts Count'] = self.all_known_hosts_count
                    results_df.to_csv(self.output_csv_path, index=False)
                else:
                    self.logger.error(f"File {self.output_csv_path} does not exist.")
            except Exception as e:
                self.logger.error(f"Error in save_results: {e}")

        def update_livestatus(self):
            """
            Updates the live status of hosts and saves the results.
            """
            try:
                self.read_csv()
                self.calculate_open_ports()
                self.calculate_hosts_counts()
                self.save_results()
                self.logger.info("Livestatus updated")
                self.logger.info(f"Results saved to {self.output_csv_path}")
            except Exception as e:
                self.logger.error(f"Error in update_livestatus: {e}")
        
        def clean_scan_results(self, scan_results_dir):
            """
            Cleans up old scan result files, keeping only the most recent ones.
            """
            try:
                files = glob.glob(scan_results_dir + '/*')
                files.sort(key=os.path.getmtime)
                for file in files[:-20]:
                    os.remove(file)
                self.logger.info("Scan results cleaned up")
            except Exception as e:
                self.logger.error(f"Error in clean_scan_results: {e}")

    def scan(self):
        """
        Initiates the network scan, updates the netkb file, and displays the results.
        """
        try:
            self.shared_data.bjornorch_status = "NetworkScanner"
            self.logger.info(f"Starting Network Scanner")
            network = self.get_network()
            self.shared_data.bjornstatustext2 = str(network)
            portstart = self.shared_data.portstart
            portend = self.shared_data.portend
            extra_ports = self.shared_data.portlist
            scanner = self.ScanPorts(self, network, portstart, portend, extra_ports)
            ip_data, open_ports, all_ports, csv_result_file, netkbfile, alive_ips = scanner.start()

            alive_macs = set(ip_data.mac_list)

            table = Table(title="Scan Results", show_lines=True)
            table.add_column("IP", style="cyan", no_wrap=True)
            table.add_column("Hostname", style="cyan", no_wrap=True)
            table.add_column("Alive", style="cyan", no_wrap=True)
            table.add_column("MAC Address", style="cyan", no_wrap=True)
            for port in all_ports:
                table.add_column(f"{port}", style="green")

            netkb_data = []
            for ip, ports, hostname, mac in zip(ip_data.ip_list, open_ports.values(), ip_data.hostname_list, ip_data.mac_list):
                if self.blacklistcheck and (mac in self.mac_scan_blacklist or ip in self.ip_scan_blacklist):
                    continue
                alive = '1' if mac in alive_macs else '0'
                row = [ip, hostname, alive, mac] + [Text(str(port), style="green bold") if port in ports else Text("", style="on red") for port in all_ports]
                table.add_row(*row)
                netkb_data.append([mac, ip, hostname, ports])

            with self.lock:
                with open(csv_result_file, 'w', newline='') as file:
                    writer = csv.writer(file)
                    writer.writerow(["IP", "Hostname", "Alive", "MAC Address"] + [str(port) for port in all_ports])
                    for ip, ports, hostname, mac in zip(ip_data.ip_list, open_ports.values(), ip_data.hostname_list, ip_data.mac_list):
                        if self.blacklistcheck and (mac in self.mac_scan_blacklist or ip in self.ip_scan_blacklist):
                            continue
                        alive = '1' if mac in alive_macs else '0'
                        writer.writerow([ip, hostname, alive, mac] + [str(port) if port in ports else '' for port in all_ports])

            self.update_netkb(netkbfile, netkb_data, alive_macs)

            if self.displaying_csv:
                self.display_csv(csv_result_file)

            source_csv_path = self.shared_data.netkbfile
            output_csv_path = self.shared_data.livestatusfile

            updater = self.LiveStatusUpdater(source_csv_path, output_csv_path)
            updater.update_livestatus()
            updater.clean_scan_results(self.shared_data.scan_results_dir)
        except Exception as e:
            self.logger.error(f"Error in scan: {e}")

    def start(self):
        """
        Starts the scanner in a separate thread.
        """
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self.scan)
            self.thread.start()
            logger.info("NetworkScanner started.")

    def stop(self):
        """
        Stops the scanner.
        """
        if self.running:
            self.running = False
            if self.thread.is_alive():
                self.thread.join()
            logger.info("NetworkScanner stopped.")

if __name__ == "__main__":
    shared_data = SharedData()
    scanner = NetworkScanner(shared_data)
    scanner.scan()
