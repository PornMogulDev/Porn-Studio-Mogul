import logging
import logging.handlers
import os
import sys

from utils.paths import LOG_DIR, LOG_FILE

def setup_logging():
    """
    Configures the root logger for the application.

    This setup includes two handlers:
    1. A StreamHandler to show INFO level messages and higher on the console.
    2. A RotatingFileHandler to write DEBUG level messages and higher to a
       log file (`logs/app.log`) that rotates when it reaches 1 MB.
    """
    # Create the log directory if it doesn't exist
    os.makedirs(LOG_DIR, exist_ok=True)
    log_file_path = os.path.join(LOG_DIR, LOG_FILE)

    # Define the format for the log messages
    log_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # --- Setup File Handler ---
    # Writes logs to a file, rotating it when it gets too large.
    file_handler = logging.handlers.RotatingFileHandler(
        log_file_path, maxBytes=1024*1024, backupCount=5, encoding='utf-8'
    )
    file_handler.setFormatter(log_formatter)
    file_handler.setLevel(logging.DEBUG) # Log everything to the file

    # --- Setup Console Handler ---
    # Prints logs to the console.
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_formatter)
    console_handler.setLevel(logging.INFO) # Only show info/warnings/errors on console

    # --- Configure Root Logger ---
    # The root logger's level must be the lowest of all its handlers.
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    # Add handlers to the root logger
    # Avoid adding handlers if they already exist (e.g., in an interactive session)
    if not root_logger.handlers:
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)

    logging.info("Logging configured successfully.")