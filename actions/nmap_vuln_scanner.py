# nmap_vuln_scanner.py
# This script performs vulnerability scanning using Nmap on specified IP addresses.
# It scans for vulnerabilities on various ports and saves the results and progress.

import os
import pandas as pd
import subprocess
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from rich.console import Console
from rich.progress import Progress, BarColumn, TextColumn
from shared import SharedData
from logger import Logger

logger = Logger(name="nmap_vuln_scanner.py", level=logging.INFO)

b_class = "NmapVulnScanner"
b_module = "nmap_vuln_scanner"
b_status = "vuln_scan"
b_port = None
b_parent = None

class NmapVulnScanner:
    """
    This class handles the Nmap vulnerability scanning process.
    """
    def __init__(self, shared_data):
        self.shared_data = shared_data
        self.scan_results = []
        self.summary_file = self.shared_data.vuln_summary_file
        self.create_summary_file()
        logger.debug("NmapVulnScanner initialized.")

    def create_summary_file(self):
        """
        Creates a summary file for vulnerabilities if it does not exist.
        """
        if not os.path.exists(self.summary_file):
            os.makedirs(self.shared_data.vulnerabilities_dir, exist_ok=True)
            df = pd.DataFrame(columns=["IP", "Hostname", "MAC Address", "Port", "Vulnerabilities"])
            df.to_csv(self.summary_file, index=False)

    def update_summary_file(self, ip, hostname, mac, port, vulnerabilities):
        """
        Updates the summary file with the scan results.
        """
        try:
            # Read existing data
            df = pd.read_csv(self.summary_file)
            
            # Create new data entry
            new_data = pd.DataFrame([{"IP": ip, "Hostname": hostname, "MAC Address": mac, "Port": port, "Vulnerabilities": vulnerabilities}])
            
            # Append new data
            df = pd.concat([df, new_data], ignore_index=True)
            
            # Remove duplicates based on IP and MAC Address, keeping the last occurrence
            df.drop_duplicates(subset=["IP", "MAC Address"], keep='last', inplace=True)
            
            # Save the updated data back to the summary file
            df.to_csv(self.summary_file, index=False)
        except Exception as e:
            logger.error(f"Error updating summary file: {e}")


    def scan_vulnerabilities(self, ip, hostname, mac, ports):
        combined_result = ""
        success = True  # Initialize to True, will become False if an error occurs
        try:
            self.shared_data.bjornstatustext2 = ip

            # Proceed with scanning if ports are not already scanned
            logger.info(f"Scanning {ip} on ports {','.join(ports)} for vulnerabilities with aggressivity {self.shared_data.nmap_scan_aggressivity}")
            result = subprocess.run(
                ["nmap", self.shared_data.nmap_scan_aggressivity, "-sV", "--script", "vulners.nse", "-p", ",".join(ports), ip],
                capture_output=True, text=True
            )
            combined_result += result.stdout

            vulnerabilities = self.parse_vulnerabilities(result.stdout)
            self.update_summary_file(ip, hostname, mac, ",".join(ports), vulnerabilities)
        except Exception as e:
            logger.error(f"Error scanning {ip}: {e}")
            success = False  # Mark as failed if an error occurs

        return combined_result if success else None

    def execute(self, ip, row, status_key):
        """
        Executes the vulnerability scan for a given IP and row data.
        """
        self.shared_data.bjornorch_status = "NmapVulnScanner"
        ports = row["Ports"].split(";")
        scan_result = self.scan_vulnerabilities(ip, row["Hostnames"], row["MAC Address"], ports)

        if scan_result is not None:
            self.scan_results.append((ip, row["Hostnames"], row["MAC Address"]))
            self.save_results(row["MAC Address"], ip, scan_result)
            return 'success'
        else:
            return 'success' # considering failed as success as we just need to scan vulnerabilities once
            # return 'failed'

    def parse_vulnerabilities(self, scan_result):
        """
        Parses the Nmap scan result to extract vulnerabilities.
        """
        vulnerabilities = set()
        capture = False
        for line in scan_result.splitlines():
            if "VULNERABLE" in line or "CVE-" in line or "*EXPLOIT*" in line:
                capture = True
            if capture:
                if line.strip() and not line.startswith('|_'):
                    vulnerabilities.add(line.strip())
                else:
                    capture = False
        return "; ".join(vulnerabilities)

    def save_results(self, mac_address, ip, scan_result):
        """
        Saves the detailed scan results to a file.
        """
        try:
            sanitized_mac_address = mac_address.replace(":", "")
            result_dir = self.shared_data.vulnerabilities_dir
            os.makedirs(result_dir, exist_ok=True)
            result_file = os.path.join(result_dir, f"{sanitized_mac_address}_{ip}_vuln_scan.txt")
            
            # Open the file in write mode to clear its contents if it exists, then close it
            if os.path.exists(result_file):
                open(result_file, 'w').close()
            
            # Write the new scan result to the file
            with open(result_file, 'w') as file:
                file.write(scan_result)
            
            logger.info(f"Results saved to {result_file}")
        except Exception as e:
            logger.error(f"Error saving scan results for {ip}: {e}")


    def save_summary(self):
        """
        Saves a summary of all scanned vulnerabilities to a final summary file.
        """
        try:
            final_summary_file = os.path.join(self.shared_data.vulnerabilities_dir, "final_vulnerability_summary.csv")
            df = pd.read_csv(self.summary_file)
            summary_data = df.groupby(["IP", "Hostname", "MAC Address"])["Vulnerabilities"].apply(lambda x: "; ".join(set("; ".join(x).split("; ")))).reset_index()
            summary_data.to_csv(final_summary_file, index=False)
            logger.info(f"Summary saved to {final_summary_file}")
        except Exception as e:
            logger.error(f"Error saving summary: {e}")

if __name__ == "__main__":
    shared_data = SharedData()
    try:
        nmap_vuln_scanner = NmapVulnScanner(shared_data)
        logger.info("Starting vulnerability scans...")

        # Load the netkbfile and get the IPs to scan
        ips_to_scan = shared_data.read_data()  # Use your existing method to read the data

        # Execute the scan on each IP with concurrency
        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            "[progress.percentage]{task.percentage:>3.1f}%",
            console=Console()
        ) as progress:
            task = progress.add_task("Scanning vulnerabilities...", total=len(ips_to_scan))
            futures = []
            with ThreadPoolExecutor(max_workers=2) as executor:  # Adjust the number of workers for RPi Zero
                for row in ips_to_scan:
                    if row["Alive"] == '1':  # Check if the host is alive
                        ip = row["IPs"]
                        futures.append(executor.submit(nmap_vuln_scanner.execute, ip, row, b_status))

                for future in as_completed(futures):
                    progress.update(task, advance=1)

        nmap_vuln_scanner.save_summary()
        logger.info(f"Total scans performed: {len(nmap_vuln_scanner.scan_results)}")
        exit(len(nmap_vuln_scanner.scan_results))
    except Exception as e:
        logger.error(f"Error: {e}")
