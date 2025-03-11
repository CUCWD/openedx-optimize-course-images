'''
This module contains functions to export and import courses from the Open edX platform.
'''
import os
import subprocess

from utils import file_handlers as utils_file
from utils import logger_handlers as utils_logger
from utils import tar_handlers as utils_tar
from settings import (LOG_PATH, OPTIMIZED_DIRECTORY, SOURCE_DIRECTORY, app_logger)


def export_course_from_platform(course_id):
    """Export course from the Open edX platform using a subprocess call and tutor command."""

    # Use a separate logger for course-specific logs
    course_logger = utils_logger.setup_course_logger(LOG_PATH, course_id)

    # Exit early if course_id is empty
    if not course_id:
        course_logger.error("Course ID is empty")
        return
    
    CONTAINER_TMP_SOURCE_COURSES = "/tmp/openedx-optimize-course-image/courses-sourced"
    
    try:
        course_logger.info(f">>> Exporting course {course_id} from the platform.")

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
        course_logger.info(f"Executing: {' '.join(subprocess_cmd)}")
        subprocess.run(
            ' '.join(subprocess_cmd), shell=True, check=True, capture_output=True, text=True
        )
        # Tar GZ the exported course
        utils_tar.create_tar_gz(course_dest_source, SOURCE_DIRECTORY, 'course.' + course_id_filename)

        course_logger.info(f"Exported course: {course_id}")
    except subprocess.CalledProcessError as error:
        course_logger.error(f"Error exporting course {course_id}: {error.returncode} {error.stderr}")
    except Exception as error:
        course_logger.error(f"Error exporting courses: {error}")

    # Remove the temporary course directory
    utils_file.delete_directory(os.path.join(SOURCE_DIRECTORY, 'course.' + course_id_filename))

def import_course_to_platform(course_id):
    """Import course to the Open edX platform using a subprocess call and tutor command."""

    # Use a separate logger for course-specific logs
    course_logger = utils_logger.setup_course_logger(LOG_PATH, course_id)

    # Exit early if course_id is empty
    if not course_id:
        course_logger.error("Course ID is empty")
        return
    
    CONTAINER_TMP_OPTIMIZED_COURSES = "/tmp/openedx-optimize-course-image/courses-optimized"

    try:
        course_logger.info(f">>> Importing course {course_id} to the platform.")

        # Extract the tar.gz file to a temporary directory before importing the course.
        course_id_filename = course_id.replace('course-v1:', '')
        optimized_tar_gz_path = os.path.join(OPTIMIZED_DIRECTORY, 'course.' + course_id_filename + '-optimized.tar.gz')
        try:
            utils_tar.extract_tar_gz(optimized_tar_gz_path, OPTIMIZED_DIRECTORY, ignore_clear=True)
        except FileNotFoundError:
            # Exit early if the tar.gz file is not found
            return

        # Import the course using the tutor command
        subprocess_cmd = [
            '/home/ubuntu/venv/bin/tutor', 'local', 'run',
            '-v ' + os.path.abspath(OPTIMIZED_DIRECTORY) + ':' + CONTAINER_TMP_OPTIMIZED_COURSES,
            'cms', './manage.py cms import', '/openedx/data',
            os.path.join(CONTAINER_TMP_OPTIMIZED_COURSES, f'course.{course_id_filename}', 'course'),
            '--settings', 'tutor.production'
        ]
        course_logger.info(f"Executing: {' '.join(subprocess_cmd)}")
        subprocess.run(
            ' '.join(subprocess_cmd), shell=True, check=True, capture_output=True, text=True
        )
        course_logger.info(f"Imported course: {course_id}")
    except subprocess.CalledProcessError as error:
        course_logger.error(f"Error importing course {course_id}: {error.returncode} {error.stderr}")
    except Exception as error:
        course_logger.error(f"Error importing courses: {error}")

    # Remove the temporary course directory and tar.gz file
    utils_file.delete_directory(os.path.join(OPTIMIZED_DIRECTORY, 'course.' + course_id_filename))

    # Remove OPTIMIZED_DIRECTORY tar.gz course file after optimization files have been uploaded.
    try:
        os.remove(optimized_tar_gz_path)
        course_logger.info(f"Removed optimized course file: {optimized_tar_gz_path}")
    except FileNotFoundError: # pylint: disable=broad-except
        course_logger.warning(f"Optimized course file not found: {optimized_tar_gz_path}")


def delete_course_assets_in_contentstore(course_id, asset_key_strings):
    """Delete course assets in the Open edX platform using a subprocess call and tutor command."""

    # Use a separate logger for course-specific logs
    course_logger = utils_logger.setup_course_logger(LOG_PATH, course_id)

    # Exit early if course_id is empty
    if not course_id:
        course_logger.error("Course ID is empty")
        return

    # Exit early if asset_key_strings is empty
    if not asset_key_strings:
        course_logger.error("Asset key strings list is empty")
        return
    
    CONTAINER_TMP_DJANGO_MGT_COMMAND = "/tmp/openedx-optimize-course-images"
    DELETE_COURSE_ASSETS_COMMAND = "import json; import os; from openedx_optimize_course_images.management.commands.delete_course_assets import Command; Command().handle(course_id=os.getenv(\"OPTIMIZE_COURSE_ID\"), asset_key_strings=json.loads(os.getenv(\"OPTIMIZE_ASSET_KEY_STRINGS\")))"
    
    try:
        subprocess_cmd = [
            '/home/ubuntu/venv/bin/tutor', 'local', 'run',
            '-v ' + os.path.abspath('.') + ':' + CONTAINER_TMP_DJANGO_MGT_COMMAND,
            '-e PYTHONPATH="/tmp/openedx-optimize-course-images:\$PYTHONPATH"',
            '-e OPTIMIZE_COURSE_ID="' + course_id + '"',
            '-e OPTIMIZE_ASSET_KEY_STRINGS=\'[' + ','.join(f'"{asset_key}"' for asset_key in asset_key_strings) + ']\'',
            'cms', './manage.py cms shell -c', f"'{DELETE_COURSE_ASSETS_COMMAND}'",
            '--settings', 'tutor.production'
        ]
        course_logger.info(f"Executing: {' '.join(subprocess_cmd)}")
        subprocess.run(
            ' '.join(subprocess_cmd), shell=True, check=True, capture_output=True, text=True
        )
        course_logger.info(f"Deleted unused course assets from course: {course_id} in Open edX MongoDB contentstore.")
        for asset_key in asset_key_strings:
            course_logger.info(f"Deleted asset: {asset_key}")
    
    except subprocess.CalledProcessError as error:
        course_logger.error(f"Error deleting unused course assets for course {course_id}: {error.returncode} {error.stderr}")
    except Exception as error:
        course_logger.error(f"Error deleting unused course assets for course {course_id}: {error}")
