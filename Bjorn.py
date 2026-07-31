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
from display import Display
from comment import Commentaireia
from webapp import web_thread
from orchestrator import Orchestrator
from logger import Logger

logger = Logger(name="Bjorn.py", level=logging.DEBUG)
SHUTDOWN_TIMEOUT_SECONDS = 75
RESIDUAL_THREAD_GRACE_SECONDS = 5

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
                self.orchestrator_thread = threading.Thread(
                    target=self.orchestrator.run,
                    name="BjornOrchestrator",
                )
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
        display_thread = threading.Thread(
            target=display.run,
            name="BjornDisplay",
        )
        display_thread.start()
        return display, display_thread


def request_shutdown(display):
    """Set every component's exit flag and wake sleeping display workers."""
    shared_data.should_exit = True
    shared_data.orchestrator_should_exit = True
    shared_data.display_should_exit = True
    shared_data.webapp_should_exit = True
    display.request_stop()


def wait_for_shutdown_threads(threads, timeout=SHUTDOWN_TIMEOUT_SECONDS):
    """Wait for application threads and return names that missed the deadline."""
    deadline = time.monotonic() + timeout
    unique_threads = []
    seen_threads = set()
    current_thread = threading.current_thread()

    for thread in threads:
        if thread is None or thread is current_thread:
            continue
        thread_identity = id(thread)
        if thread_identity in seen_threads:
            continue
        seen_threads.add(thread_identity)
        unique_threads.append(thread)

    while True:
        alive_threads = [
            thread for thread in unique_threads if thread.is_alive()
        ]
        if not alive_threads:
            return []

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return [
                getattr(thread, "name", repr(thread))
                for thread in alive_threads
            ]

        for index, thread in enumerate(alive_threads):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            threads_remaining = len(alive_threads) - index
            join_slice = min(0.25, remaining / threads_remaining)
            try:
                thread.join(timeout=join_slice)
            except Exception as error:
                thread_name = getattr(thread, "name", repr(thread))
                logger.error(
                    f"Unable to join thread {thread_name}: "
                    f"{type(error).__name__}: {error}"
                )
                return [thread_name]


def describe_thread(thread):
    """Return bounded diagnostics for a Python thread left during shutdown."""
    target = getattr(thread, "_target", None)
    if target is None:
        target_name = "none"
    else:
        target_module = getattr(target, "__module__", type(target).__module__)
        target_qualname = getattr(
            target,
            "__qualname__",
            type(target).__qualname__,
        )
        target_name = f"{target_module}.{target_qualname}"

    thread_class = (
        f"{type(thread).__module__}.{type(thread).__qualname__}"
    )
    return (
        f"name={getattr(thread, 'name', 'unknown')} "
        f"class={thread_class} "
        f"target={target_name} "
        f"daemon={getattr(thread, 'daemon', 'unknown')}"
    )


def remaining_python_threads():
    """Return live Python threads other than the signal-handling thread."""
    current_thread = threading.current_thread()
    return [
        thread
        for thread in threading.enumerate()
        if thread is not current_thread and thread.is_alive()
    ]


def handle_exit(
    sig,
    frame,
    display,
    display_thread,
    bjorn,
    bjorn_thread,
    web_thread,
):
    """Request shutdown and wait for all application-owned threads."""
    del sig, frame
    request_shutdown(display)
    shutdown_threads = [
        display_thread,
        *display.background_threads(),
        bjorn_thread,
        bjorn.orchestrator_thread,
        web_thread,
    ]
    alive_thread_names = wait_for_shutdown_threads(shutdown_threads)
    if alive_thread_names:
        logger.error(
            "Shutdown deadline exceeded; threads still running: "
            + ", ".join(alive_thread_names)
        )
        raise SystemExit(1)

    display.close_hardware()

    residual_threads = remaining_python_threads()
    if residual_threads:
        logger.warning(
            "Waiting for residual Python threads: "
            + "; ".join(
                describe_thread(thread)
                for thread in residual_threads
            )
        )
        residual_thread_names = wait_for_shutdown_threads(
            residual_threads,
            timeout=RESIDUAL_THREAD_GRACE_SECONDS,
        )
        if residual_thread_names:
            logger.error(
                "Residual Python thread deadline exceeded: "
                + ", ".join(residual_thread_names)
            )
            raise SystemExit(1)

    logger.info("Main loop finished. Clean exit.")
    raise SystemExit(0)


def wait_for_primary_thread(primary_thread):
    """Keep the interpreter active while Bjorn's primary thread is running."""
    while primary_thread.is_alive():
        primary_thread.join(timeout=1)



if __name__ == "__main__":
    logger.info("Starting threads")

    try:
        logger.info("Loading shared data config...")
        shared_data.load_config()

        logger.info("Starting display thread...")
        shared_data.display_should_exit = False  # Initialize display should_exit
        display, display_thread = Bjorn.start_display()

        logger.info("Starting Bjorn thread...")
        bjorn = Bjorn(shared_data)
        shared_data.bjorn_instance = bjorn  # Assigner l'instance de Bjorn à shared_data
        bjorn_thread = threading.Thread(
            target=bjorn.run,
            name="BjornMain",
        )
        bjorn_thread.start()

        if shared_data.config["websrv"]:
            logger.info("Starting the web server...")
            web_thread.start()

        signal.signal(
            signal.SIGINT,
            lambda sig, frame: handle_exit(
                sig,
                frame,
                display,
                display_thread,
                bjorn,
                bjorn_thread,
                web_thread,
            ),
        )
        signal.signal(
            signal.SIGTERM,
            lambda sig, frame: handle_exit(
                sig,
                frame,
                display,
                display_thread,
                bjorn,
                bjorn_thread,
                web_thread,
            ),
        )
        wait_for_primary_thread(bjorn_thread)

    except Exception as e:
        logger.error(f"An exception occurred during thread start: {e}")
        shared_data.should_exit = True
        shared_data.orchestrator_should_exit = True
        shared_data.display_should_exit = True
        shared_data.webapp_should_exit = True
        raise SystemExit(1) from e
