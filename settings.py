# Description: This file contains the settings for the application. 
# The settings are divided into sections, each with a specific purpose.

import os
from datetime import datetime

from utils import logger_handlers as utils_logger

# AWS S3 Settings
# ----------------
# These settings are used to configure the connection to an AWS S3 bucket.

# The AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY are required to authenticate
# with the AWS S3 service. The S3_BUCKET_NAME is the name of the bucket where
# the files will be uploaded. The S3_REGION_NAME is the region where the bucket
# is located.

AWS_ACCESS_KEY_ID = 'SET_ME_PLEASE'
AWS_SECRET_ACCESS_KEY = 'SET_ME_PLEASE'
AWS_S3_USE_SSL = True
S3_BUCKET_NAME = 'SET_ME_PLEASE'
S3_REGION_NAME = 'SET_ME_PLEASE'

# Application Settings
# --------------------
# These settings are used to configure the application behavior.
OPTIMIZED_DIRECTORY = "./courses-optimized"
SOURCE_DIRECTORY = "./courses-sourced"
TMP_DESTINATION = "./tmp/"
LOG_PATH = "./logs/"
NUM_COURSE_OPTIMIZATION_CHUNKS = 2  # Specify the number of courses to optimize at a time
NUM_WORKER_PROCESSES = 2  # Specify the number of worker processes
CHUNK_SIZE = min(NUM_COURSE_OPTIMIZATION_CHUNKS, NUM_WORKER_PROCESSES) # Define chunk size as a constant

# Define current date and time as constants
APPLICATION_DATE = datetime.now().strftime("%Y%m%d")
APPLICATION_TIME = datetime.now().strftime("%H%M%S")

# Setup application logger
os.makedirs(LOG_PATH, exist_ok=True)
app_logger = utils_logger.setup_logger(
    os.path.join(LOG_PATH, f"application.log"), enable_stdout=True
)
