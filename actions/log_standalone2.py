#Test script to add more actions to  BJORN 

import logging
from shared import SharedData
from logger import Logger

# Configure the logger
logger = Logger(name="log_standalone2.py", level=logging.INFO)

# Define the necessary global variables
b_class = "LogStandalone2"
b_module = "log_standalone2"
b_status = "log_standalone2"
b_port = 0  # Indicate this is a standalone action

class LogStandalone2:
    """
    Class to handle the standalone log action.
    """
    def __init__(self, shared_data):
        self.shared_data = shared_data
        logger.info("LogStandalone initialized")

    def execute(self):
        """
        Execute the standalone log action.
        """
        try:
            logger.info("Executing standalone log action.")
            logger.info("This is a test log message for the standalone action.")
            return 'success'
        except Exception as e:
            logger.error(f"Error executing standalone log action: {e}")
            return 'failed'
