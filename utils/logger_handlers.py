"""
This module contains functions to setup logging handlers for logging messages to both a log file and stdout.
"""

import logging
import os


def setup_logger(log_file, enable_stdout=True):
    """Setup logging to output messages to both stdout and a log file."""
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Remove existing FileHandlers and StreamHandlers
    for handler in logger.handlers[:]:
        if isinstance(handler, (logging.FileHandler, logging.StreamHandler)):
            logger.removeHandler(handler)
    
    # Create handlers
    handlers = [logging.FileHandler(log_file)]
    if enable_stdout:
        handlers.append(logging.StreamHandler())
    
    # Create formatters and add them to handlers
    class CustomFormatter(logging.Formatter):
        def format(self, record):
            max_length = 32
            filename_lineno = f"{record.filename}:{record.lineno}"
            if len(filename_lineno) > max_length:
                filename_lineno = filename_lineno[:max_length]
            record.filename_lineno = filename_lineno.ljust(max_length)
            return super().format(record)

    formatter = CustomFormatter('%(asctime)-25s %(levelname)-8s %(filename_lineno)-32s %(message)-50s')
    for handler in handlers:
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    return logger

def setup_course_logger(log_path, course_id):
    """Setup a logger for course-specific logs."""
    # Create the logs directory if it does not exist
    os.makedirs(log_path, exist_ok=True)
    course_id_filename = course_id.replace('course-v1:', '')
    course_logger = setup_logger(
        os.path.join(log_path, f"{course_id_filename}.log"), enable_stdout=True
    )
    return course_logger
