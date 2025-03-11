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
import multiprocessing
import os
import sys

from botocore.exceptions import NoCredentialsError, PartialCredentialsError
from wand.image import Image
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.styles.colors import Color

from utils import file_handlers as utils_file
from utils import img_handlers as utils_img
from utils import json_handlers as utils_json
from utils import logger_handlers as utils_logger
from utils import openedx_handlers as utils_openedx
from utils import s3_handlers as utils_s3
from utils import tar_handlers as utils_tar

from settings import (APPLICATION_DATE, APPLICATION_TIME, CHUNK_SIZE, LOG_PATH,
                      NUM_WORKER_PROCESSES, OPTIMIZED_DIRECTORY, SOURCE_DIRECTORY, TMP_DESTINATION,
                      app_logger)

def combine_and_save_image_optimization_excel_summary(log_path):
    """Combine multiple Excel files into a single Excel file and create a pivot table summary."""

    COMBINED_WORKBOOK_NAME = f"image_optimization_stats.{APPLICATION_DATE}.{APPLICATION_TIME}.xlsx"

    # ---------------------------------------
    # Image Optimization Details
    # ---------------------------------------
    combined_workbook = Workbook()
    combined_sheet = combined_workbook.active
    combined_sheet.title = "Image Optimization Details"

    headers = [
        "Course ID", "Deleted From Course", "Reduced Size",
        "Before File Name", "Before Format", "Before Size",
        "Before Resolution", "Before DPI", "After File Name",
        "After Format", "After Size", "After Resolution",
        "After DPI"
    ]
    combined_sheet.append(headers)

    # Style headers
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="669933", end_color="669933", fill_type="solid")
    for cell in combined_sheet[1]:
        cell.font = header_font
        cell.fill = header_fill

    for excel_file in glob.glob(os.path.join(log_path, f"image_optimization_stats.{APPLICATION_DATE}-*.xlsx")):
        workbook = load_workbook(excel_file)
        sheet = workbook.active

        for row in sheet.iter_rows(min_row=2, values_only=True):
            combined_sheet.append(row)

    # Apply alternating row colors
    for idx, row in enumerate(combined_sheet.iter_rows(min_row=2), start=2):
        if idx % 2 == 0:
            for cell in row:
                cell.fill = PatternFill(start_color="D3D3D3", end_color="D3D3D3", fill_type="solid")

    combined_sheet.auto_filter.ref = combined_sheet.dimensions

    # Expand all columns to fit the content
    for column in combined_sheet.columns:
        max_length = 0
        column = list(column)
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(cell.value)
            except:
                pass
        adjusted_width = (max_length + 2)
        combined_sheet.column_dimensions[column[0].column_letter].width = adjusted_width

    combined_workbook.save(
        os.path.join(
            log_path,
            COMBINED_WORKBOOK_NAME
        )
    )

    # ---------------------------------------
    # Image Optimization Summary
    # ---------------------------------------
    pivot_sheet = combined_workbook.create_sheet(title="Image Optimization Summary")
    pivot_headers = [
        "Course ID", "Count of Deleted From Course", "Count of Optimized",
        "Sum of Reduced Size", "Sum of Before Size",
        "Sum of After Size"
    ]
    pivot_sheet.append(pivot_headers)

    # Style pivot headers
    for cell in pivot_sheet[1]:
        cell.font = header_font
        cell.fill = header_fill

    summary_data = {}

    for row in combined_sheet.iter_rows(min_row=2, values_only=True):
        course_id = row[0]
        deleted_from_course = row[1]
        reduced_size = row[2]
        before_size = row[5]
        after_size = row[10]

        if course_id not in summary_data:
            summary_data[course_id] = {
                "count_deleted": 0,
                "count_optimized": 0,
                "total_reduced_size": 0,
                "total_before_size": 0,
                "total_after_size": 0
            }

        if deleted_from_course == "Yes":
            summary_data[course_id]["count_deleted"] += 1
        if deleted_from_course == "No":
            summary_data[course_id]["count_optimized"] += 1
        summary_data[course_id]["total_reduced_size"] += (reduced_size or 0)
        summary_data[course_id]["total_before_size"] += (before_size or 0)
        summary_data[course_id]["total_after_size"] += (after_size or 0)

    for course_id, data in summary_data.items():
        pivot_sheet.append([
            course_id, data["count_deleted"], data["count_optimized"],
            utils_img.convert_bytes(data["total_reduced_size"]),
            utils_img.convert_bytes(data["total_before_size"]),
            utils_img.convert_bytes(data["total_after_size"])
        ])

    # Go back and change bytes to KB or MB format for Size columns only for readability.
    for idx, row in enumerate(combined_sheet.iter_rows(min_row=2), start=2):
        for cell in row:
            if combined_sheet.cell(row=1, column=cell.column).value in ["Reduced Size", "Before Size", "After Size"]:
                cell.value = utils_img.convert_bytes(cell.value)

    # Apply alternating row colors to pivot sheet
    for idx, row in enumerate(pivot_sheet.iter_rows(min_row=2), start=2):
        if idx % 2 == 0:
            for cell in row:
                cell.fill = PatternFill(start_color="D3D3D3", end_color="D3D3D3", fill_type="solid")

    pivot_sheet.auto_filter.ref = pivot_sheet.dimensions

    # Expand all columns to fit the content in pivot sheet
    for column in pivot_sheet.columns:
        max_length = 0
        column = list(column)
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(cell.value)
            except:
                pass
        adjusted_width = (max_length + 2)
        pivot_sheet.column_dimensions[column[0].column_letter].width = adjusted_width

    combined_workbook.save(
        os.path.join(
            log_path,
            COMBINED_WORKBOOK_NAME
        )
    )

    # Remove all Excel files after combining into a single Excel file for all courses.
    for excel_file in glob.glob(os.path.join(log_path, f"image_optimization_stats.{APPLICATION_DATE}-*.xlsx")):
        os.remove(excel_file)

def traverse_image_files(course_id, directory_path, course_logger):
    """
    Traverses through all image files and optimizes them. Also, finds and removes unused images.
    """
    OPENEDX_ASSETS_JSON = os.path.join(directory_path, "policies", "assets.json")
    asset_key_strings_to_remove = [] # Keeps track of images that are not used in the course content.
    supported_extensions = ['.png', '.jpeg', '.jpg']

    # Exit early if the `/static` directory does not exist in the course.
    static_dir = os.path.join(directory_path, "static")
    if not os.path.exists(static_dir):
        course_logger.warning(f"The /static directory does not exist in {course_id}.")
        raise FileNotFoundError(f"The /static directory does not exist in {course_id}.")

    # Create a new Excel workbook for the given course.
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Image Optimization Details"
    sheet.append([
        "Course ID", "Deleted From Course", "Reduced Size",
        "Before File Name", "Before Format", "Before Size", "Before Resolution", "Before DPI",
        "After File Name", "After Format", "After Size", "After Resolution", "After DPI"
    ])

    # Limit the walk to the top-level files in the static directory (ignoring subdirectories)
    root, _, files = next(os.walk(static_dir))
    for file in files:
        # Skip hidden files that begin with '.' - macOS
        if file.lower().startswith('.'):
            continue

        if any(file.lower().endswith(ext) for ext in supported_extensions):
            image_path = os.path.join(root, file)
            course_logger.info("--------------------------------------------------------------")
            course_logger.info(f"Found image file ({utils_img.print_image_stats(image_path)}): {image_path}")

            try:
                # Ensure that file use their `/policies/assets.json` key name when searching the
                # course. Example on disk with '/static/iguana-8084900@5257x3505.jpg' including
                # the '@' character is the displayName property in the assets.json file, while
                # the key name replaces the '@' to '_' and the named used within the course
                # content is 'iguana-8084900_5257x3505.jpg' instead.
                file = utils_json.find_parent_key(
                    OPENEDX_ASSETS_JSON,
                    file
                )

                file_displayname_before = utils_json.get_value_from_json(
                    OPENEDX_ASSETS_JSON, file
                ).get('displayname')

                # Get image stats before optimization
                before_stats = utils_img.get_image_stats(image_path)

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
                        course_logger.warning(f"Updated references of {file} to {new_file_name} in assets.json file.")

                    # Get image stats after optimization
                    file_displayname_after = os.path.splitext(file_displayname_before)[0] + ".jpg"
                    after_stats = utils_img.get_image_stats(os.path.join(root, file_displayname_after))

                    # Write stats to Excel
                    sheet.append([
                        course_id, "No", (before_stats.get("Size", 0) - after_stats.get("Size", 0)),
                        file_displayname_before, before_stats.get("Format"), before_stats.get("Size"), before_stats.get("Resolution"), before_stats.get("DPI"),
                        file_displayname_after, after_stats.get("Format"), after_stats.get("Size"), after_stats.get("Resolution"), after_stats.get("DPI")
                    ])
                else:
                    # Remove the unused image from course
                    # Todo: Also need to remove the file configuration in assets.json
                    try:
                        # Write stats to Excel
                        sheet.append([
                            course_id, "Yes", (before_stats.get("Size", 0)),
                            file_displayname_before, before_stats.get("Format"), before_stats.get("Size"), before_stats.get("Resolution"), before_stats.get("DPI"),
                            "", "", "", ""
                        ])
                        
                        os.remove(image_path)
                        course_logger.warning(f"Removed unused image file in course export: {image_path}")
                    except FileNotFoundError:
                        course_logger.warning(f"Image file not found: {image_path}")

                    # Keep track of the unused image Asset key in the course for removal later.
                    asset_key_strings_to_remove.append(
                        utils_json.get_value_from_json(
                            OPENEDX_ASSETS_JSON,
                            file
                        ).get('filename')
                    )

                    # Update the course assets.json file by removing the unused image.
                    utils_json.delete_key_from_json(
                        os.path.join(directory_path, "policies", "assets.json"),
                        file
                    )

            except Exception as error:  # pylint: disable=broad-except
                course_logger.error(f"Error optimizing image {image_path}: {error}")
    
    # Sort the Excel sheet by "Course ID", "Deleted From Course", "Reduced Size"
    data = list(sheet.iter_rows(values_only=True))
    headers = data[0]
    header_indices = {header: index for index, header in enumerate(headers)}
    sorted_data = sorted(data[1:], key=lambda row: (
        row[header_indices["Course ID"]],
        row[header_indices["Deleted From Course"]],
        row[header_indices["Reduced Size"]]
    ))
    
    # Clear the sheet and append sorted data
    sheet.delete_rows(2, sheet.max_row)
    for row in sorted_data:
        sheet.append(row)

    # Save the Excel workbook
    workbook.save(
        os.path.join(
            LOG_PATH,
            f"image_optimization_stats.{APPLICATION_DATE}-{course_id.replace('course-v1:', '')}.xlsx"
        )
    )

    # Remove unused images from the course content in the Open edX platform MongoDB contentstore.
    utils_openedx.delete_course_assets_in_contentstore(course_id, asset_key_strings_to_remove)

def process_tar_file(tar_file, log_path, optimized_directory, tmp_destination):
    """Process a single tar.gz file."""
    app_logger.info(f"Processing tar file: {tar_file}")

    tar_file_name = os.path.splitext(os.path.splitext(os.path.basename(tar_file))[0])[0]
    tar_destination = os.path.join(tmp_destination, tar_file_name)

    # Use a separate logger for file-specific logs
    log_file = os.path.join(log_path, f"{tar_file_name.replace('course.', '')}.log")
    course_logger = utils_logger.setup_logger(log_file, enable_stdout=False)

    course_logger.info(f">>> Optimization courses images for {tar_file_name}")

    utils_tar.extract_tar_gz(tar_file, tar_destination)

    try:
        # Traverse and optimize images in the exported course.
        course_path = os.path.join(tar_destination, "course")
        traverse_image_files(
            tar_file_name.replace('course.', 'course-v1:'), course_path, course_logger
        )

        # Find and replace image references in the exported course content.
        assets_path = os.path.join(course_path, "policies", "assets.json")
        utils_json.find_and_replace_in_json(assets_path, 'image\/png', 'image/jpeg')
        utils_json.find_and_replace_in_json(assets_path, "-png\.jpg", ".jpg")
        utils_json.find_and_replace_in_json(assets_path, "\.png", ".jpg")
        utils_json.replace_json_keys(assets_path, ".png", ".jpg")

        policy_path = utils_json.find_json_file(os.path.join(course_path, "policies"), "policy.json")
        utils_json.find_and_replace_in_json(policy_path, "\.png", ".jpg")
    except FileNotFoundError:
        # Do nothing if no image files are found in the course.
        pass

    # Create a new tar.gz file with the optimized images even if no images were found.
    optimized_file = f"{tar_file_name}-optimized"
    optimized_file_path = optimized_directory
    utils_tar.create_tar_gz(tar_destination, optimized_file_path, optimized_file)
    utils_file.delete_directory(tar_destination)

def chunk_courses_to_optimized(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

def export_courses(course_ids):
    """
    Export courses and backup to S3.
    Returns a list of exported courses to ensure that remaining tasks to optimize courses and import are not called.
    """
    exported_courses = []

    for chunk in chunk_courses_to_optimized(course_ids, CHUNK_SIZE):
        with multiprocessing.Pool(processes=NUM_WORKER_PROCESSES) as pool:
            try:
                pool.starmap(utils_openedx.export_course_from_platform, [(course_id,) for course_id in chunk])
                exported_courses.extend(chunk)
            except (NoCredentialsError, PartialCredentialsError, FileNotFoundError):
                app_logger.error("Could not call export course %s", chunk)

    # Backup SOURCE_DIRECTORY exported courses to S3 as original tar.gz files backup.
    for course_id in exported_courses:
        course_id_filename = course_id.replace('course-v1:', '')
        tar_gz_path = os.path.join(SOURCE_DIRECTORY, f'course.{course_id_filename}.tar.gz')
        s3_key = f'openedx-course-backups/openedx-courses/{course_id_filename}/{APPLICATION_DATE}/course.{course_id_filename}.{APPLICATION_DATE}.{APPLICATION_TIME}.tar.gz'

        try:
            utils_s3.upload_file_to_s3(tar_gz_path, s3_key)
        except (FileNotFoundError, NoCredentialsError, PartialCredentialsError, Exception):
            # Continue to the next course file on S3 upload error.
            continue
    
    return exported_courses

def optimize_courses(course_ids):
    """Optimize images for exported tar gzip Open edX courses."""

    # EXPERIMENTAL:
    # THIS IS COMMENTED OUT BECAUSE WE ARE NOT DOWNLOADING FROM S3
    # WE DID THIS TO RECREATE THE EXCEL STATS FILE
    # -----------------------------------------------------------
    # Download the tar.gz course files from S3 to the SOURCE_DIRECTORY.
    # for course_id in course_ids:
    #     course_id_filename = course_id.replace('course-v1:', '')
    #     s3_key = f'openedx-course-backups/openedx-courses/{course_id_filename}/{APPLICATION_DATE}/course.{course_id_filename}.{APPLICATION_DATE}.{APPLICATION_TIME}.tar.gz'
    #     tar_gz_path = os.path.join(SOURCE_DIRECTORY, f'course.{course_id_filename}.tar.gz')

    #     try:
    #         utils_s3.download_file_from_s3(s3_key, tar_gz_path)
    #     except (FileNotFoundError, NoCredentialsError, PartialCredentialsError, Exception):
    #         # Continue to the next course file on S3 download error.
    #         continue

    # Check to see if any source Open edX tar.gz courses exists and process image optimization.
    tar_files = glob.glob(os.path.join(SOURCE_DIRECTORY, "*.tar.gz"))
    if not tar_files:
        app_logger.info("No .tar.gz files found in source directory.")
        return

    # Process tar.gz course files in chunks to limit resources used at a time.
    for chunk in chunk_courses_to_optimized(tar_files, CHUNK_SIZE):
        with multiprocessing.Pool(processes=NUM_WORKER_PROCESSES) as pool:
            pool.starmap(process_tar_file, [(tar_file, LOG_PATH, OPTIMIZED_DIRECTORY, TMP_DESTINATION) for tar_file in chunk])   

    # Backup OPTIMIZED_DIRECTORY exported courses to S3 as original tar.gz files backup.
    for course_id in course_ids:
        course_id_filename = course_id.replace('course-v1:', '')
        optimized_tar_gz_path = os.path.join(OPTIMIZED_DIRECTORY, f'course.{course_id_filename}-optimized.tar.gz')
        s3_key = f'openedx-course-backups/openedx-courses/{course_id_filename}/{APPLICATION_DATE}/course.{course_id_filename}.{APPLICATION_DATE}.{APPLICATION_TIME}-optimized.tar.gz'

        try:
            utils_s3.upload_file_to_s3(optimized_tar_gz_path, s3_key)
        except (FileNotFoundError, NoCredentialsError, PartialCredentialsError, Exception):
            # Continue to the next course file on S3 upload error.
            continue

        # Remove SOURCE_DIRECTORY tar.gz course file after optimization files have been uploaded.
        src_tar_gz_path = os.path.join(SOURCE_DIRECTORY, f'course.{course_id_filename}.tar.gz')
        try:
            os.remove(src_tar_gz_path)
            app_logger.info(f"Removed source course file: {src_tar_gz_path}")
        except FileNotFoundError: # pylint: disable=broad-except
            app_logger.warning(f"Source course file not found: {src_tar_gz_path}")

def import_courses(course_ids):
    """Import optimized Open edX courses back to the platform."""
    for chunk in chunk_courses_to_optimized(course_ids, CHUNK_SIZE):
        with multiprocessing.Pool(processes=NUM_WORKER_PROCESSES) as pool:
            pool.starmap(utils_openedx.import_course_to_platform, [(course_id,) for course_id in chunk])

def main():
    """
    Main function to process all .tar.gz files from source-courses directory.
    """
    try:
        # Create supporting directories for application logs, optimized course tar.gz output, and
        # temporary modification to existing courses.
        os.makedirs(OPTIMIZED_DIRECTORY, exist_ok=True)
        os.makedirs(TMP_DESTINATION, exist_ok=True)
        
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
                # Exit the application
                sys.exit(0)
            elif command_choice == '1':
                app_logger.info("//////////////////////////////////////////////////////////////")
                app_logger.info(f"Step [{command_choice}] Exporting Open edX courses and backup to S3.")
                app_logger.info("//////////////////////////////////////////////////////////////")
                export_courses(course_ids)
                app_logger.info(f"[{command_choice}] All courses have been exported and backed up to S3.")
            elif command_choice == '2':
                app_logger.info("//////////////////////////////////////////////////////////////")
                app_logger.info(f"Step [{command_choice}] Optimize images for exported tar gzip Open edX courses.")
                app_logger.info("//////////////////////////////////////////////////////////////")

                # EXPERIMENTAL:
                # THIS IS COMMENTED OUT BECAUSE WE ARE NOT DOWNLOADING FROM S3
                # WE DID THIS TO RECREATE THE EXCEL STATS FILE
                # -----------------------------------------------------------
                # Limit the number of courses to optimize at a time to avoid resource exhaustion.
                # for chunk in chunk_courses_to_optimized(course_ids, CHUNK_SIZE):
                #     with multiprocessing.Pool(processes=NUM_WORKER_PROCESSES) as pool:
                #         optimize_courses(chunk)
                
                app_logger.info(f"[{command_choice}] All course images have been optimized")

                # Create a combined Excel file with all image optimization details.
                combine_and_save_image_optimization_excel_summary(LOG_PATH)
            elif command_choice == '3':
                app_logger.info("//////////////////////////////////////////////////////////////")
                app_logger.info(f"Step [{command_choice}] Import optimized Open edX courses back to the platform.")
                app_logger.info("//////////////////////////////////////////////////////////////")
                import_courses(course_ids)
                app_logger.info(f"[{command_choice}] All courses have been imported back to the platform.")
            elif command_choice == '4':
                app_logger.info("//////////////////////////////////////////////////////////////")
                app_logger.info(f"Step [{command_choice}] Exporting Open edX courses and backup to S3, optimizing course, then importing back to the platform.")
                app_logger.info("//////////////////////////////////////////////////////////////")
                
                # Limit the number of courses to optimize at a time to avoid resource exhaustion.
                for chunk in chunk_courses_to_optimized(course_ids, CHUNK_SIZE):
                    with multiprocessing.Pool(processes=NUM_WORKER_PROCESSES) as pool:
                        # Export courses and backup to S3, optimize images for exported tar gzip Open edX courses, and import optimized Open edX courses back to the platform.
                        # Only run the next steps (optimize_courses, import_courses) if the previous step (export_courses) was successful.
                        # This is to ensure we don't optimize and import courses that were not successfully exported.
                        exported_courses = export_courses(chunk)
                        if len(exported_courses) > 0:
                            optimize_courses(exported_courses)
                            import_courses(exported_courses)

                app_logger.info(f"[{command_choice}] All courses have been exported, optimized, and imported back to the platform.")

                # Create a combined Excel file with all image optimization details.
                combine_and_save_image_optimization_excel_summary(LOG_PATH)
            else:
                app_logger.error("Invalid command choice.")

    except OSError as error:
        app_logger.error("Failed to execute main function: %s", error)

    app_logger.info("//////////////////////////////////////////////////////////////")
   
def upload_logs_to_s3():
    """Upload application and course logs for the APPLICATION_DATE to S3 for backup, then delete them locally."""
    try:
        for file in glob.glob(os.path.join(LOG_PATH, "*.log")) + glob.glob(os.path.join(LOG_PATH, "*.xlsx")):
            file_name = os.path.basename(file)
            s3_key = f'openedx-course-backups/logs/{APPLICATION_DATE}.{APPLICATION_TIME}/{file_name}'
            utils_s3.upload_file_to_s3(file, s3_key)
    except (FileNotFoundError, NoCredentialsError, PartialCredentialsError, Exception):
        # Could not upload log files to S3.
        app_logger.error("Could not upload log files to S3.")
    finally:
        # Remove all log files after uploading to S3.
        for file in glob.glob(os.path.join(LOG_PATH, "*.log")) + glob.glob(os.path.join(LOG_PATH, "*.xlsx")):
            os.remove(file)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        # Call upload_logs_to_s3 on KeyboardInterrupt
        app_logger.info("Application interrupted by user.")
        upload_logs_to_s3()
        sys.exit(0)
    except SystemExit:
        # Call upload_logs_to_s3 on SystemExit
        app_logger.info("Application exiting.")
        upload_logs_to_s3()

