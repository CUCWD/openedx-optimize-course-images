"""
This module contains utility functions to interact with AWS S3.
"""

import logging

import boto3
from botocore.exceptions import NoCredentialsError, PartialCredentialsError

from settings import (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, S3_BUCKET_NAME,
                      S3_REGION_NAME, AWS_S3_USE_SSL)


def upload_file_to_s3(file_path, s3_key):
    """
    Upload a file to an S3 bucket.

    :param file_path: Path to the file to upload.
    :param s3_key: S3 key (path) where the file will be stored.
    """
    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=S3_REGION_NAME,
            use_ssl=AWS_S3_USE_SSL  # Use the setting for SSL
        )

        s3_client.upload_file(file_path, S3_BUCKET_NAME, s3_key)
        logging.info(f"Successfully uploaded {file_path} to s3://{S3_BUCKET_NAME}/{s3_key}")

    except FileNotFoundError as e:
        logging.error(f"The file {file_path} was not found.")
        raise e
    except NoCredentialsError as e:
        logging.error("Credentials not available.")
        raise e
    except PartialCredentialsError as e:
        logging.error("Incomplete credentials provided.")
        raise e
    except Exception as e:
        logging.error(f"Failed to upload {file_path} to S3: {e}")
        raise e
