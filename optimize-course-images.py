#!/usr/bin/env python3.10

"""
Script to extract all Open edX exported course tar.gz files from the source directory, clear the 
destination directory before extraction, and optimize all extracted images (JPEG, PNG) by 
converting them to JPEG format.

This script will also find and remove unused images from the course content. Multipl courses can be
run after another if the tar.gz files exist in the sources-courses directory.
"""

import os
import glob
import logging
import shutil
from wand.image import Image

from utils import file_handlers as ufh
from utils import img_handlers as uih
from utils import json_handlers as ujh
from utils import tar_handlers as uth

def setup_logger(log_file):
    """Setup logging to output messages to both stdout and a log file."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),  # Output to stdout
            logging.FileHandler(log_file)  # Output to log file
        ]
    )

def traverse_image_files(directory_path):
    """Traverses through all image files and optimizes them."""
    supported_extensions = ['.png', '.jpeg', '.jpg']
    for root, _, files in os.walk(os.path.join(directory_path, "static")):
        for file in files:
            # Skip hidden files that begin with '.' - macOS
            if file.lower().startswith('.'):
                continue

            if any(file.lower().endswith(ext) for ext in supported_extensions):
                image_path = os.path.join(root, file)
                logging.info("--------------------------------------------------------------")
                logging.info(f"Found image file ({uih.get_image_stats(image_path)}): {image_path}")

                try:
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
                            logging.warning(f"Updated references of {file} to {new_file_name} in course files.")
                    else:
                        # Remove the unused image from course
                        # Todo: Also need to remove the file configuration in assets.json
                        os.remove(image_path)
                        logging.warning(f"Removed unused image file: {image_path}")

                        # Update the course assets.json file by removing the unused image.
                        ujh.delete_key_from_json(
                            os.path.join(directory_path, "policies", "assets.json"),
                            file
                        )

                except Exception as error:  # pylint: disable=broad-except
                    logging.error(f"Error optimizing image {image_path}: {error}")

def main():
    """
    Main function to process all .tar.gz files from source-courses directory.
    """
    optimized_directory = "./optimized-courses"
    source_directory = "./source-courses"
    tmp_destination = "./tmp/"
    log_path = "./logs/"

    try:
        # Create supporting directories for application logs, optimized course tar.gz output, and
        # temporary modification to existing courses.
        os.makedirs(log_path, exist_ok=True)
        os.makedirs(optimized_directory, exist_ok=True)
        os.makedirs(tmp_destination, exist_ok=True)

        # Check to see if any source Open edX tar.gz courses exists and process image optimization.
        tar_files = glob.glob(os.path.join(source_directory, "*.tar.gz"))
        if not tar_files:
            print("No .tar.gz files found in source directory.")

        for tar_file in tar_files:
            # Get the base name of the tar file without the .tar.gz extension
            tar_file_name = os.path.splitext(os.path.splitext(os.path.basename(tar_file))[0])[0]
            # Create a tmp destination folder using the tar file name
            tar_destination = os.path.join(tmp_destination, tar_file_name)
            os.makedirs(tar_destination, exist_ok=True)

            # Set up logging for the specific tar file
            log_file = os.path.join(log_path, f"{tar_file_name}.log")
            setup_logger(log_file)

            # Create a copy of the tar file with the .gz extension removed
            tar_file_copy = os.path.join(tmp_destination, tar_file_name + ".tar")
            shutil.copy(tar_file, tar_file_copy)

            # Extract the copied tar file into the newly created directory
            uth.extract_tar_gz(tar_file_copy, tar_destination)

            # Remove the copied tar file after extraction
            os.remove(tar_file_copy)

            # After extraction, traverse image files in the static folder
            course_path = os.path.join(tar_destination, "course")
            # traverse_image_files(course_path)

            # Replace contentType 'image/png' within the assets.json file to 'image/jpeg'.
            # Replace thumbnail_location 'file-png.jpg' with 'file.jpg' within the assets.json file.
            # Replace '.png' with '.jpg' within the assets.json file.
            logging.info("--------------------------------------------------------------")
            assets_path = os.path.join(course_path, "policies", "assets.json")
            ujh.find_and_replace_in_json(assets_path, 'image\/png', 'image/jpeg')
            ujh.find_and_replace_in_json(assets_path, "-png\.jpg", ".jpg")
            ujh.find_and_replace_in_json(assets_path, "\.png", ".jpg")
            ujh.replace_json_keys(assets_path, ".png", ".jpg")

            # Replace course image .png with .jpg version in policy.json
            policy_path = ujh.find_json_file(os.path.join(course_path, "policies"), "policy.json")
            ujh.find_and_replace_in_json(policy_path, "\.png", ".jpg")

            # Archive and gzip the modified course for use with importing into the platform.
            optimized_file = f"{tar_file_name}-optimized"
            optimized_file_path = optimized_directory
            uth.create_tar_gz(tar_destination, optimized_file_path, optimized_file)  

            # Delete all from tmp destination
            ufh.delete_directory(tar_destination)

    except OSError as error:
        logging.error(f"Failed to execute main function: {error}")

    print("All courses have been optimized")

if __name__ == "__main__":
    main()
