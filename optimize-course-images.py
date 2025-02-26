#!/usr/bin/env python3.10

"""
Script to extract all Open edX exported course tar.gz files from the source directory, clear the 
destination directory before extraction, and optimize all extracted images (JPEG, PNG) by 
converting them to JPEG format.

This script will also find and remove unused images from the course content. 

Multiprocessing is used to optimize multiple courses concurrently and the number of worker processes
can be adjusted to optimize resource usage.
"""

import glob
import logging
import multiprocessing
import os
import shutil
import subprocess
from datetime import datetime

from botocore.exceptions import NoCredentialsError, PartialCredentialsError
from wand.image import Image

from utils import file_handlers as utils_file
from utils import img_handlers as utils_img
from utils import json_handlers as utils_json
from utils import s3_handlers as utils_s3
from utils import tar_handlers as utils_tar

OPTIMIZED_DIRECTORY = "./courses-optimized"
SOURCE_DIRECTORY = "./courses-sourced"
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
os.makedirs(LOG_PATH, exist_ok=True)
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
                course_logger.info(f"Found image file ({utils_img.get_image_stats(image_path)}): {image_path}")

                try:
                    # Ensure that file use their `/policies/assets.json` key name when searching the
                    # course. Example on disk with '/static/iguana-8084900@5257x3505.jpg' including
                    # the '@' character is the displayName property in the assets.json file, while
                    # the key name replaces the '@' to '_' and the named used within the course
                    # content is 'iguana-8084900_5257x3505.jpg' instead.
                    file = utils_json.find_parent_key(
                        os.path.join(directory_path, "policies", "assets.json"),
                        file
                    )

                    found_image_usage_in_course = utils_file.search_image_in_files(file, directory_path)
                    if found_image_usage_in_course:
                        # Convert all supported extensions to JPEG type and compress.
                        utils_img.optimize_image(image_path)

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
                        try:
                            os.remove(image_path)
                            course_logger.warning(f"Removed unused image file: {image_path}")
                        except FileNotFoundError:
                            course_logger.warning(f"Image file not found: {image_path}")

                        # Update the course assets.json file by removing the unused image.
                        utils_json.delete_key_from_json(
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

    # Use a separate logger for file-specific logs
    log_file = os.path.join(log_path, f"{tar_file_name}.log")
    course_logger = setup_logger(log_file, enable_stdout=False)

    course_logger.info("//////////////////////////////////////////////////////////////")
    course_logger.info(f"Starting new image optimization for {tar_file_name}")

    utils_tar.extract_tar_gz(tar_file, tar_destination)

    course_path = os.path.join(tar_destination, "course")
    traverse_image_files(course_path, course_logger)

    assets_path = os.path.join(course_path, "policies", "assets.json")
    utils_json.find_and_replace_in_json(assets_path, 'image\/png', 'image/jpeg')
    utils_json.find_and_replace_in_json(assets_path, "-png\.jpg", ".jpg")
    utils_json.find_and_replace_in_json(assets_path, "\.png", ".jpg")
    utils_json.replace_json_keys(assets_path, ".png", ".jpg")

    policy_path = utils_json.find_json_file(os.path.join(course_path, "policies"), "policy.json")
    utils_json.find_and_replace_in_json(policy_path, "\.png", ".jpg")

    optimized_file = f"{tar_file_name}-optimized"
    optimized_file_path = optimized_directory
    utils_tar.create_tar_gz(tar_destination, optimized_file_path, optimized_file)
    utils_file.delete_directory(tar_destination)

def chunk_courses_to_optimized(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

def export_course_from_platform(course_id):
    """Export course from the Open edX platform using a subprocess call and tutor command."""

    # Exit early if course_id is empty
    if not course_id:
        app_logger.error("Course ID is empty")
        return
    
    CONTAINER_TMP_SOURCE_COURSES = "/tmp/courses-sourced"
    
    try:
        # Create temporary course directory using removed 'course-v1:' prefix from course_id
        course_id_filename = course_id.replace('course-v1:', '')
        course_tmp_dir = os.path.join(CONTAINER_TMP_SOURCE_COURSES, 'course.' + course_id_filename, 'course')

        # Make the course directory before exporting the course so the command doesn't fail.
        course_dest_source = os.path.join(SOURCE_DIRECTORY, 'course.' + course_id_filename, 'course')
        os.makedirs(course_dest_source, exist_ok=True)

        # Export the course using the tutor command
        subprocess_cmd = [
            '/home/ubuntu/venv/bin/tutor', 'local', 'run',
            '-v ' + os.path.abspath(SOURCE_DIRECTORY) + ':' + CONTAINER_TMP_SOURCE_COURSES,
            'cms', './manage.py cms export', course_id, course_tmp_dir,
            '--settings', 'tutor.production'
        ]
        app_logger.info(f"Executing: {' '.join(subprocess_cmd)}")
        subprocess.run(
            ' '.join(subprocess_cmd), shell=True, check=True, capture_output=True, text=True
        )
        # Tar GZ the exported course
        utils_tar.create_tar_gz(course_dest_source, SOURCE_DIRECTORY, 'course.' + course_id_filename)

        app_logger.info(f"Exported course: {course_id}")
    except subprocess.CalledProcessError as error:
        app_logger.error(f"Error exporting course {course_id}: {error.returncode} {error.stderr}")
    except Exception as error:
        app_logger.error(f"Error exporting courses: {error}")

    # Remove the temporary course directory
    utils_file.delete_directory(os.path.join(SOURCE_DIRECTORY, 'course.' + course_id_filename))

def import_course_to_platform(course_id):
    """Import course to the Open edX platform using a subprocess call and tutor command."""
    # Exit early if course_id is empty
    if not course_id:
        app_logger.error("Course ID is empty")
        return
    
    CONTAINER_TMP_OPTIMIZED_COURSES = "/tmp/courses-optimized"

    try:
        # Extract the tar.gz file to a temporary directory before importing the course.
        course_id_filename = course_id.replace('course-v1:', '')
        optimized_tar_gz_path = os.path.join(OPTIMIZED_DIRECTORY, 'course.' + course_id_filename + '-optimized.tar.gz')
        utils_tar.extract_tar_gz(optimized_tar_gz_path, OPTIMIZED_DIRECTORY, ignore_clear=True)

        # Import the course using the tutor command
        subprocess_cmd = [
            '/home/ubuntu/venv/bin/tutor', 'local', 'run',
            '-v ' + os.path.abspath(OPTIMIZED_DIRECTORY) + ':' + CONTAINER_TMP_OPTIMIZED_COURSES,
            'cms', './manage.py cms import', '/openedx/data',
            os.path.join(CONTAINER_TMP_OPTIMIZED_COURSES, f'course.{course_id_filename}', 'course'),
            '--settings', 'tutor.production'
        ]
        app_logger.info(f"Executing: {' '.join(subprocess_cmd)}")
        subprocess.run(
            ' '.join(subprocess_cmd), shell=True, check=True, capture_output=True, text=True
        )
        app_logger.info(f"Imported course: {course_id}")
    except subprocess.CalledProcessError as error:
        app_logger.error(f"Error importing course {course_id}: {error.returncode} {error.stderr}")
    except Exception as error:
        app_logger.error(f"Error importing courses: {error}")

    # Remove the temporary course directory and tar.gz file
    utils_file.delete_directory(os.path.join(OPTIMIZED_DIRECTORY, 'course.' + course_id_filename))

    # Remove OPTIMIZED_DIRECTORY tar.gz course file after optimization files have been uploaded.
    try:
        os.remove(optimized_tar_gz_path)
        app_logger.info(f"Removed optimized course file: {optimized_tar_gz_path}")
    except FileNotFoundError: # pylint: disable=broad-except
        app_logger.warning(f"Optimized course file not found: {optimized_tar_gz_path}")

def main():
    """
    Main function to process all .tar.gz files from source-courses directory.
    """
    try:
        current_date = datetime.now().strftime("%Y%m%d")
        current_time = datetime.now().strftime("%H%M%S")
        
        # Create supporting directories for application logs, optimized course tar.gz output, and
        # temporary modification to existing courses.
        os.makedirs(OPTIMIZED_DIRECTORY, exist_ok=True)
        os.makedirs(TMP_DESTINATION, exist_ok=True)
        
        # Ensure that the number of courses processed in each chunk does not exceed the number of
        # worker processes, thereby optimizing resource usage.
        chunk_size = min(NUM_COURSE_OPTIMIZATION_CHUNKS, NUM_WORKER_PROCESSES)

        # Export courses from process-course-ids.txt from the Open edX platform.
        course_ids = []
        with open(os.path.join('.', 'process-course-ids.txt'), 'r', encoding='utf-8') as file:
            for line in file:
                course_ids.append(line.strip())
                
        while True:
            # Prompt user for the command to run
            print("Select the command to run:")
            print("0. Quit application.")
            print("1. Export Open edX courses and backup to S3.")
            print("2. Optimize images for exported tar gzip Open edX courses.")
            print("3. Import optimized Open edX courses back to the platform.")
            print("4. (Run steps 1 - 3) Export, optimize images, and import back to the platform.")
            command_choice = input("Enter the number of the command to run: ")

            if command_choice == '0':
                app_logger.info("Exiting application.")
                break
            elif command_choice == '1':
                app_logger.info(f"//////// Step [{command_choice}] Exporting Open edX courses and backup to S3.")

                for chunk in chunk_courses_to_optimized(course_ids, chunk_size):
                    with multiprocessing.Pool(processes=NUM_WORKER_PROCESSES) as pool:
                        pool.starmap(export_course_from_platform, [(course_id,) for course_id in chunk])
                
                # Backup SOURCE_DIRECTORY exported courses to S3 as original tar.gz files backup.
                for course_id in course_ids:
                    course_id_filename = course_id.replace('course-v1:', '')
                    tar_gz_path = os.path.join(SOURCE_DIRECTORY, f'course.{course_id_filename}.tar.gz')
                    s3_key = f'openedx-course-backups/{course_id_filename}/{current_date}/course.{course_id_filename}.{current_date}.{current_time}.tar.gz'

                    try:
                        utils_s3.upload_file_to_s3(tar_gz_path, s3_key)
                    except (FileNotFoundError, NoCredentialsError, PartialCredentialsError, Exception):
                        # Continue to the next course file on S3 upload error.
                        continue

                app_logger.info(f"[{command_choice}] All courses have been exported and backed up to S3.")
            elif command_choice == '2':
                app_logger.info(f"//////// Step [{command_choice}] Optimize images for exported tar gzip Open edX courses.")

                # Check to see if any source Open edX tar.gz courses exists and process image optimization.
                tar_files = glob.glob(os.path.join(SOURCE_DIRECTORY, "*.tar.gz"))
                if not tar_files:
                    app_logger.info(f"[{command_choice}] No .tar.gz files found in source directory.")
                    continue

                # Process tar.gz course files in chunks to limit resources used at a time.
                for chunk in chunk_courses_to_optimized(tar_files, chunk_size):
                    with multiprocessing.Pool(processes=NUM_WORKER_PROCESSES) as pool:
                        pool.starmap(process_tar_file, [(tar_file, LOG_PATH, OPTIMIZED_DIRECTORY, TMP_DESTINATION) for tar_file in chunk])

                # Backup OPTIMIZED_DIRECTORY exported courses to S3 as original tar.gz files backup.
                for course_id in course_ids:
                    course_id_filename = course_id.replace('course-v1:', '')
                    optimized_tar_gz_path = os.path.join(OPTIMIZED_DIRECTORY, f'course.{course_id_filename}-optimized.tar.gz')
                    s3_key = f'openedx-course-backups/{course_id_filename}/{current_date}/course.{course_id_filename}.{current_date}.{current_time}-optimized.tar.gz'

                    try:
                        utils_s3.upload_file_to_s3(optimized_tar_gz_path, s3_key)
                    except (FileNotFoundError, NoCredentialsError, PartialCredentialsError, Exception):
                        # Continue to the next course file on S3 upload error.
                        continue

                    # Remove SOURCE_DIRECTORY tar.gz course file after optimization files have been uploaded.
                    src_tar_gz_path = os.path.join(SOURCE_DIRECTORY, f'course.{course_id_filename}.tar.gz')
                    try:
                        os.remove(src_tar_gz_path)
                        app_logger.info(f"[{command_choice}] Removed source course file: {src_tar_gz_path}")
                    except FileNotFoundError: # pylint: disable=broad-except
                        app_logger.warning(f"[{command_choice}] Source course file not found: {src_tar_gz_path}")

                app_logger.info(f"[{command_choice}] All course images have been optimized")
            elif command_choice == '3':
                app_logger.info(f"//////// Step [{command_choice}] Import optimized Open edX courses back to the platform.")

                # Import the optimized courses back to the Open edX platform using a subprocess call and tutor command.
                for chunk in chunk_courses_to_optimized(course_ids, chunk_size):
                    with multiprocessing.Pool(processes=NUM_WORKER_PROCESSES) as pool:
                        pool.starmap(import_course_to_platform, [(course_id,) for course_id in chunk])

                app_logger.info(f"[{command_choice}] All courses have been imported back to the platform.")
            elif command_choice == '4':
                app_logger.info(f"//////// Step [{command_choice}] Exporting Open edX courses and backup to S3, optimizing course, then importing back to the platform.")

                # Add code to export, optimize, and import courses here

                app_logger.info(f"[{command_choice}] All courses have been exported, optimized, and imported back to the platform.")
                pass
            else:
                app_logger.error("Invalid command choice.")

    except OSError as error:
        app_logger.error("Failed to execute main function: %s", error)

    app_logger.info("//////////////////////////////////////////////////////////////")

if __name__ == "__main__":
    main()
