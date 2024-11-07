#bjorn.py
# This script defines the main execution flow for the Bjorn application. It initializes and starts
# various components such as network scanning, display, and web server functionalities. The Bjorn 
# class manages the primary operations, including initiating network scans and orchestrating tasks.
# The script handles startup delays, checks for Wi-Fi connectivity, and coordinates the execution of
# scanning and orchestrator tasks using semaphores to limit concurrent threads. It also sets up 
# signal handlers to ensure a clean exit when the application is terminated.

# Functions:
# - handle_exit:  handles the termination of the main and display threads.
# - handle_exit_webserver:  handles the termination of the web server thread.
# - is_wifi_connected: Checks for Wi-Fi connectivity using the nmcli command.

# The script starts by loading shared data configurations, then initializes and sta
# bjorn.py


import threading
import signal
import logging
import time
import sys
import subprocess
from init_shared import shared_data
from display import Display, handle_exit_display
from comment import Commentaireia
from webapp import web_thread, handle_exit_web
from orchestrator import Orchestrator
from logger import Logger

logger = Logger(name="Bjorn.py", level=logging.DEBUG)

class Bjorn:
    """Main class for Bjorn. Manages the primary operations of the application."""
    def __init__(self, shared_data):
        self.shared_data = shared_data
        self.commentaire_ia = Commentaireia()
        self.orchestrator_thread = None
        self.orchestrator = None

    def run(self):
        """Main loop for Bjorn. Waits for Wi-Fi connection and starts Orchestrator."""
        # Wait for startup delay if configured in shared data
        if hasattr(self.shared_data, 'startup_delay') and self.shared_data.startup_delay > 0:
            logger.info(f"Waiting for startup delay: {self.shared_data.startup_delay} seconds")
            time.sleep(self.shared_data.startup_delay)

        # Main loop to keep Bjorn running
        while not self.shared_data.should_exit:
            if not self.shared_data.manual_mode:
                self.check_and_start_orchestrator()
            time.sleep(10)  # Main loop idle waiting



    def check_and_start_orchestrator(self):
        """Check Wi-Fi and start the orchestrator if connected."""
        if self.is_wifi_connected():
            self.wifi_connected = True
            if self.orchestrator_thread is None or not self.orchestrator_thread.is_alive():
                self.start_orchestrator()
        else:
            self.wifi_connected = False
            logger.info("Waiting for Wi-Fi connection to start Orchestrator...")

    def start_orchestrator(self):
        """Start the orchestrator thread."""
        self.is_wifi_connected() # reCheck if Wi-Fi is connected before starting the orchestrator
        if self.wifi_connected:  # Check if Wi-Fi is connected before starting the orchestrator
            if self.orchestrator_thread is None or not self.orchestrator_thread.is_alive():
                logger.info("Starting Orchestrator thread...")
                self.shared_data.orchestrator_should_exit = False
                self.shared_data.manual_mode = False
                self.orchestrator = Orchestrator()
                self.orchestrator_thread = threading.Thread(target=self.orchestrator.run)
                self.orchestrator_thread.start()
                logger.info("Orchestrator thread started, automatic mode activated.")
            else:
                logger.info("Orchestrator thread is already running.")
        else:
            logger.warning("Cannot start Orchestrator: Wi-Fi is not connected.")

    def stop_orchestrator(self):
        """Stop the orchestrator thread."""
        self.shared_data.manual_mode = True
        logger.info("Stop button pressed. Manual mode activated & Stopping Orchestrator...")
        if self.orchestrator_thread is not None and self.orchestrator_thread.is_alive():
            logger.info("Stopping Orchestrator thread...")
            self.shared_data.orchestrator_should_exit = True
            self.orchestrator_thread.join()
            logger.info("Orchestrator thread stopped.")
            self.shared_data.bjornorch_status = "IDLE"
            self.shared_data.bjornstatustext2 = ""
            self.shared_data.manual_mode = True
        else:
            logger.info("Orchestrator thread is not running.")

    def is_wifi_connected(self):
        """Checks for Wi-Fi connectivity using the nmcli command."""
        result = subprocess.Popen(['nmcli', '-t', '-f', 'active', 'dev', 'wifi'], stdout=subprocess.PIPE, text=True).communicate()[0]
        self.wifi_connected = 'yes' in result
        return self.wifi_connected

    
    @staticmethod
    def start_display():
        """Start the display thread"""
        display = Display(shared_data)
        display_thread = threading.Thread(target=display.run)
        display_thread.start()
        return display_thread

def handle_exit(sig, frame, display_thread, bjorn_thread, web_thread):
    """Handles the termination of the main, display, and web threads."""
    shared_data.should_exit = True
    shared_data.orchestrator_should_exit = True  # Ensure orchestrator stops
    shared_data.display_should_exit = True  # Ensure display stops
    shared_data.webapp_should_exit = True  # Ensure web server stops
    handle_exit_display(sig, frame, display_thread)
    if display_thread.is_alive():
        display_thread.join()
    if bjorn_thread.is_alive():
        bjorn_thread.join()
    if web_thread.is_alive():
        web_thread.join()
    logger.info("Main loop finished. Clean exit.")
    sys.exit(0)  # Used sys.exit(0) instead of exit(0)



if __name__ == "__main__":
    logger.info("Starting threads")

    try:
        logger.info("Loading shared data config...")
        shared_data.load_config()

        logger.info("Starting display thread...")
        shared_data.display_should_exit = False  # Initialize display should_exit
        display_thread = Bjorn.start_display()

        logger.info("Starting Bjorn thread...")
        bjorn = Bjorn(shared_data)
        shared_data.bjorn_instance = bjorn  # Assigner l'instance de Bjorn à shared_data
        bjorn_thread = threading.Thread(target=bjorn.run)
        bjorn_thread.start()

        if shared_data.config["websrv"]:
            logger.info("Starting the web server...")
            web_thread.start()

        signal.signal(signal.SIGINT, lambda sig, frame: handle_exit(sig, frame, display_thread, bjorn_thread, web_thread))
        signal.signal(signal.SIGTERM, lambda sig, frame: handle_exit(sig, frame, display_thread, bjorn_thread, web_thread))

    except Exception as e:
        logger.error(f"An exception occurred during thread start: {e}")
        handle_exit_display(signal.SIGINT, None)
        exit(1)
