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
from init_shared import shared_data
from display import Display, handle_exit_display
from comment import Commentaireia
from webapp import web_thread, handle_exit_web
from orchestrator import Orchestrator
from logger import Logger
from wifi_setup import WifiSetupManager

logger = Logger(name="Bjorn.py", level=logging.DEBUG)

class Bjorn:
    """Main class for Bjorn. Manages the primary operations of the application."""
    def __init__(self, shared_data):
        self.shared_data = shared_data
        self.commentaire_ia = Commentaireia()
        self.orchestrator_thread = None
        self.orchestrator = None
        self.wifi_setup = WifiSetupManager(self.shared_data, logger)
        self.shared_data.wifi_setup_manager = self.wifi_setup
        self.wifi_reconnect_grace = 60
        self.wifi_disconnected_since = None
        self.has_connected_wifi = False

    def run(self):
        """Main loop for Bjorn. Waits for Wi-Fi connection and starts Orchestrator."""
        # Wait for startup delay if configured in shared data
        if hasattr(self.shared_data, 'startup_delay') and self.shared_data.startup_delay > 0:
            logger.info(f"Waiting for startup delay: {self.shared_data.startup_delay} seconds")
            time.sleep(self.shared_data.startup_delay)

        # Main loop to keep Bjorn running
        while not self.shared_data.should_exit:
            self.check_and_start_orchestrator()
            time.sleep(10)  # Main loop idle waiting

    def check_and_start_orchestrator(self):
        """Check Wi-Fi and start the orchestrator if connected."""
        if self.is_wifi_connected():
            self.wifi_connected = True
            self.shared_data.wifi_connected = True
            self.has_connected_wifi = True
            self.wifi_disconnected_since = None
            if (not self.shared_data.manual_mode and
                    (self.orchestrator_thread is None or not self.orchestrator_thread.is_alive())):
                self.start_orchestrator()
        else:
            self.wifi_connected = False
            self.shared_data.wifi_connected = False

            if self.wifi_setup.access_point_active:
                self.ensure_web_server()
                return

            if not self.has_connected_wifi:
                logger.info("No saved Wi-Fi connection; enabling the setup access point.")
                if self.wifi_setup.start_access_point():
                    self.ensure_web_server()
                return

            if self.wifi_disconnected_since is None:
                self.wifi_disconnected_since = time.monotonic()
                logger.warning(
                    f"Wi-Fi connection lost; waiting {self.wifi_reconnect_grace} seconds "
                    "before enabling setup mode."
                )
                return

            disconnected_for = time.monotonic() - self.wifi_disconnected_since
            if disconnected_for >= self.wifi_reconnect_grace:
                logger.warning(
                    f"Wi-Fi has been unavailable for {self.wifi_reconnect_grace} seconds; "
                    "enabling setup mode."
                )
                if self.wifi_setup.start_access_point():
                    self.ensure_web_server()

    @staticmethod
    def ensure_web_server():
        """Start the web server if setup mode needs it and it is not running."""
        if web_thread.ident is None:
            logger.info("Starting the web server for Wi-Fi setup...")
            web_thread.start()

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
        """Return whether wlan0 is connected to an infrastructure network."""
        self.wifi_connected = self.wifi_setup.is_station_connected()
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

        bjorn = Bjorn(shared_data)
        shared_data.bjorn_instance = bjorn

        if shared_data.config["websrv"]:
            logger.info("Starting the web server...")
            web_thread.start()

        logger.info("Starting Bjorn thread...")
        bjorn_thread = threading.Thread(target=bjorn.run)
        bjorn_thread.start()

        signal.signal(signal.SIGINT, lambda sig, frame: handle_exit(sig, frame, display_thread, bjorn_thread, web_thread))
        signal.signal(signal.SIGTERM, lambda sig, frame: handle_exit(sig, frame, display_thread, bjorn_thread, web_thread))

    except Exception as e:
        logger.error(f"An exception occurred during thread start: {e}")
        handle_exit_display(signal.SIGINT, None)
        exit(1)
