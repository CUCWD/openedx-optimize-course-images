"""
Handlers to work with tar files specifically.
"""

import logging
import os
import tarfile

from utils import file_handlers as utils_file

def create_tar_gz(source_dir, destination_dir, archive_name):
    """
    Creates a .tar.gz archive of the source directory and saves it 
    in the destination directory.

    Args:
        source_dir (str): Path to the directory to be archived.
        destination_dir (str): Path to the directory where the archive will be saved.
        archive_name (str): Name of the archive file (without the .tar.gz extension).
    """
    archive_path = os.path.join(destination_dir, archive_name + ".tar.gz")
    with tarfile.open(archive_path, "w:gz") as tar:
        tar.add(source_dir, arcname=os.path.basename(source_dir))
        logging.info(f"Created TGZ course at {archive_path}")

def extract_tar_gz(source_path, destination_path, ignore_clear=False):
    """
    Extracts the given .tar file to the specified destination path.

    Args:
        source_path (str): Path to the .tar file to be extracted.
        destination_path (str): Path to the directory where the contents will be extracted.
        ignore_clear (bool): If True, the destination directory will not be cleared before extraction.
    """
    try:
        if not os.path.exists(source_path):
            raise FileNotFoundError(f"Source file {source_path} not found.")

        if not ignore_clear:
            utils_file.clear_destination(destination_path)

        with tarfile.open(source_path, "r") as tar:
            tar.extractall(path=destination_path)
            logging.info(f"Extracted contents to {destination_path}")
    except (FileNotFoundError, tarfile.TarError, OSError) as error:
        logging.error(f"Error: {error}")
