#!/usr/bin/env python3.10

"""
Script to extract all Open edX exported course tar.gz files from the source directory, clear the 
destination directory before extraction, and optimize all extracted images (JPEG, PNG) by 
converting them to JPEG format.

This script will also find and remove unused images from the course content. 

Multiprocessing is used to optimize multiple courses concurrently and the number of worker processes
can be adjusted to optimize resource usage.
"""

import os
import glob
import logging
import shutil
import multiprocessing
from wand.image import Image

from utils import file_handlers as ufh
from utils import img_handlers as uih
from utils import json_handlers as ujh
from utils import tar_handlers as uth

OPTIMIZED_DIRECTORY = "./optimized-courses"
SOURCE_DIRECTORY = "./source-courses"
TMP_DESTINATION = "./tmp/"
LOG_PATH = "./logs/"
NUM_COURSE_OPTIMIZATION_CHUNKS = 2  # Specify the number of courses to optimize at a time
NUM_WORKER_PROCESSES = 2  # Specify the number of worker processes

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
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    for handler in handlers:
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    return logger

# Setup application logger
app_logger = setup_logger(os.path.join(LOG_PATH, "application.log"), enable_stdout=True)

def traverse_image_files(directory_path, course_logger):
    """Traverses through all image files and optimizes them."""
    supported_extensions = ['.png', '.jpeg', '.jpg']
    for root, _, files in os.walk(os.path.join(directory_path, "static")):
        for file in files:
            # Skip hidden files that begin with '.' - macOS
            if file.lower().startswith('.'):
                continue

            if any(file.lower().endswith(ext) for ext in supported_extensions):
                image_path = os.path.join(root, file)
                course_logger.info("--------------------------------------------------------------")
                course_logger.info(f"Found image file ({uih.get_image_stats(image_path)}): {image_path}")

                try:
                    # Ensure that file use their `/policies/assets.json` key name when searching the
                    # course. Example on disk with '/static/iguana-8084900@5257x3505.jpg' including
                    # the '@' character is the displayName property in the assets.json file, while
                    # the key name replaces the '@' to '_' and the named used within the course
                    # content is 'iguana-8084900_5257x3505.jpg' instead.
                    file = ujh.find_parent_key(
                        os.path.join(directory_path, "policies", "assets.json"),
                        file
                    )

                    found_image_usage_in_course = ufh.search_image_in_files(file, directory_path)
                    if found_image_usage_in_course:
                        # Convert all supported extensions to JPEG type and compress.
                        uih.optimize_image(image_path)

                        # Find/replace old .png file names with .jpg extension throughout course.
                        if file.lower().endswith('.png'):
                            new_file_name = os.path.splitext(file)[0] + ".jpg"
                            for usage_file in found_image_usage_in_course:
                                with open(usage_file, 'r', encoding='utf-8') as f:
                                    content = f.read()
                                content = content.replace(file, new_file_name)
                                with open(usage_file, 'w', encoding='utf-8') as f:
                                    f.write(content)
                            course_logger.warning(f"Updated references of {file} to {new_file_name} in course files.")
                    else:
                        # Remove the unused image from course
                        # Todo: Also need to remove the file configuration in assets.json
                        os.remove(image_path)
                        course_logger.warning(f"Removed unused image file: {image_path}")

                        # Update the course assets.json file by removing the unused image.
                        ujh.delete_key_from_json(
                            os.path.join(directory_path, "policies", "assets.json"),
                            file
                        )

                except Exception as error:  # pylint: disable=broad-except
                    course_logger.error(f"Error optimizing image {image_path}: {error}")

def process_tar_file(tar_file, log_path, optimized_directory, tmp_destination):
    """Process a single tar.gz file."""
    app_logger.info(f"Processing tar file: {tar_file}")

    tar_file_name = os.path.splitext(os.path.splitext(os.path.basename(tar_file))[0])[0]
    tar_destination = os.path.join(tmp_destination, tar_file_name)
    os.makedirs(tar_destination, exist_ok=True)

    log_file = os.path.join(log_path, f"{tar_file_name}.log")
    # Use a separate logger for file-specific logs
    course_logger = setup_logger(log_file, enable_stdout=False)

    course_logger.info("//////////////////////////////////////////////////////////////")
    course_logger.info(f"Starting new image optimization for {tar_file_name}")

    tar_file_copy = os.path.join(tmp_destination, tar_file_name + ".tar")
    shutil.copy(tar_file, tar_file_copy)
    uth.extract_tar_gz(tar_file_copy, tar_destination)
    os.remove(tar_file_copy)

    course_path = os.path.join(tar_destination, "course")
    traverse_image_files(course_path, course_logger)

    assets_path = os.path.join(course_path, "policies", "assets.json")
    ujh.find_and_replace_in_json(assets_path, 'image\/png', 'image/jpeg')
    ujh.find_and_replace_in_json(assets_path, "-png\.jpg", ".jpg")
    ujh.find_and_replace_in_json(assets_path, "\.png", ".jpg")
    ujh.replace_json_keys(assets_path, ".png", ".jpg")

    policy_path = ujh.find_json_file(os.path.join(course_path, "policies"), "policy.json")
    ujh.find_and_replace_in_json(policy_path, "\.png", ".jpg")

    optimized_file = f"{tar_file_name}-optimized"
    optimized_file_path = optimized_directory
    uth.create_tar_gz(tar_destination, optimized_file_path, optimized_file)
    ufh.delete_directory(tar_destination)

def chunk_courses_to_optimized(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

def main():
    """
    Main function to process all .tar.gz files from source-courses directory.
    """
    try:
        # Create supporting directories for application logs, optimized course tar.gz output, and
        # temporary modification to existing courses.
        os.makedirs(LOG_PATH, exist_ok=True)
        os.makedirs(OPTIMIZED_DIRECTORY, exist_ok=True)
        os.makedirs(TMP_DESTINATION, exist_ok=True)

        # Check to see if any source Open edX tar.gz courses exists and process image optimization.
        tar_files = glob.glob(os.path.join(SOURCE_DIRECTORY, "*.tar.gz"))
        if not tar_files:
            app_logger.info("No .tar.gz files found in source directory.")
            return

        # Ensure that the number of courses processed in each chunk does not exceed the number of
        # worker processes, thereby optimizing resource usage.
        chunk_size = min(NUM_COURSE_OPTIMIZATION_CHUNKS, NUM_WORKER_PROCESSES)

        # Process tar.gz course files in chunks to limit resources used at a time.
        for chunk in chunk_courses_to_optimized(tar_files, chunk_size):
            with multiprocessing.Pool(processes=NUM_WORKER_PROCESSES) as pool:
                pool.starmap(process_tar_file, [(tar_file, LOG_PATH, OPTIMIZED_DIRECTORY, TMP_DESTINATION) for tar_file in chunk])

    except OSError as error:
        app_logger.error("Failed to execute main function: %s", error)

    app_logger.info("All courses have been optimized")
    app_logger.info("//////////////////////////////////////////////////////////////")

if __name__ == "__main__":
    main()
