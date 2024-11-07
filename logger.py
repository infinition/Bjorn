#logger.py
# Description:
# This file, logger.py, is responsible for setting up a robust logging system for the Bjorn project. It defines custom logging levels and formats,
# integrates with the Rich library for enhanced console output, and ensures logs are written to rotating files for persistence.
#
# Key functionalities include:
# - Defining a custom log level "SUCCESS" to log successful operations distinctively.
# - Creating a vertical filter to exclude specific log messages based on their content.
# - Setting up a logger class (`Logger`) that initializes logging handlers for both console and file output.
# - Utilizing Rich for console logging with custom themes for different log levels, providing a more readable and visually appealing log output.
# - Ensuring log files are written to a specified directory, with file rotation to manage log file sizes and backups.
# - Providing methods to log messages at various levels (debug, info, warning, error, critical, success).
# - Allowing dynamic adjustment of log levels and the ability to disable logging entirely.



import logging
from logging.handlers import RotatingFileHandler
import os
from rich.console import Console
from rich.logging import RichHandler
from rich.theme import Theme

# Define custom log level "SUCCESS"
SUCCESS_LEVEL_NUM = 25
logging.addLevelName(SUCCESS_LEVEL_NUM, "SUCCESS")

def success(self, message, *args, **kwargs):
    if self.isEnabledFor(SUCCESS_LEVEL_NUM):
        self._log(SUCCESS_LEVEL_NUM, message, args, **kwargs)

logging.Logger.success = success

class VerticalFilter(logging.Filter):
    def filter(self, record):
        return 'Vertical' not in record.getMessage()

class Logger:
    LOGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'logs')

    def __init__(self, name, level=logging.DEBUG, enable_file_logging=True):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        self.enable_file_logging = enable_file_logging

        # Define custom log level styles
        custom_theme = Theme({
            "debug": "yellow",
            "info": "blue",
            "warning": "yellow",
            "error": "bold red",
            "critical": "bold magenta",
            "success": "bold green"
        })

        console = Console(theme=custom_theme)
        
        # Create console handler with rich and set level
        console_handler = RichHandler(console=console, show_time=False, show_level=False, show_path=False, log_time_format="%Y-%m-%d %H:%M:%S")
        console_handler.setLevel(level)
        console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        console_handler.setFormatter(console_formatter)

        # Add filter to console handler
        vertical_filter = VerticalFilter()
        console_handler.addFilter(vertical_filter)

        # Add console handler to the logger
        self.logger.addHandler(console_handler)

        if self.enable_file_logging:
            # Ensure the log folder exists
            os.makedirs(self.LOGS_DIR, exist_ok=True)
            log_file_path = os.path.join(self.LOGS_DIR, f"{name}.log")

            # Create file handler and set level
            file_handler = RotatingFileHandler(log_file_path, maxBytes=5*1024*1024, backupCount=2)
            file_handler.setLevel(level)
            file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
            file_handler.setFormatter(file_formatter)

            # Add filter to file handler
            file_handler.addFilter(vertical_filter)

            # Add file handler to the logger
            self.logger.addHandler(file_handler)
    
    def set_level(self, level):
        self.logger.setLevel(level)
        for handler in self.logger.handlers:
            handler.setLevel(level)
    
    def debug(self, message):
        self.logger.debug(message)
    
    def info(self, message):
        self.logger.info(message)
    
    def warning(self, message):
        self.logger.warning(message)
    
    def error(self, message):
        self.logger.error(message)
    
    def critical(self, message):
        self.logger.critical(message)
    
    def success(self, message):
        self.logger.success('\n' + message) # Add newline for better readability
    
    def disable_logging(self):
        logging.disable(logging.CRITICAL)


# Example usage
if __name__ == "__main__":
    # Change enable_file_logging to False to disable file logging
    log = Logger(name="MyLogger", level=logging.DEBUG, enable_file_logging=False)
    
    log.debug("This is a debug message")
    log.info("This is an info message")
    log.warning("This is a warning message")
    log.error("This is an error message")
    log.critical("This is a critical message")
    log.success("This is a success message")
    
    # Change log level
    log.set_level(logging.WARNING)
    
    log.debug("This debug message should not appear")
    log.info("This info message should not appear")
    log.warning("This warning message should appear")
    
    # Disable logging
    log.disable_logging()
    log.error("This error message should not appear")
