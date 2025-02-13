"""
Handlers to work with file and directory traversal, removal, etc.
"""

import logging
import os
import shutil

def clear_destination(destination_path):
    """Recursively removes all files and directories in the given destination path."""
    try:
        for file_name in os.listdir(destination_path):
            file_path = os.path.join(destination_path, file_name)
            if os.path.isdir(file_path):
                shutil.rmtree(file_path)  # Recursively delete directories
            else:
                os.remove(file_path)  # Delete files
        logging.info(f"Cleared all files and directories in {destination_path}")
    except OSError as error:
        logging.error(f"Error clearing destination directory: {error}")

def delete_directory(path):
    """Deletes a directory and its contents.

    Args:
        path: The path to the directory to delete.
    """
    try:
        shutil.rmtree(path)
        logging.info(f"Directory '{path}' deleted successfully.")
    except FileNotFoundError:
        logging.error(f"Error: Directory '{path}' not found.")
    except PermissionError:
        logging.error(f"Error: Permission denied to delete '{path}'.")
    except OSError as e:
        logging.error(f"Error: Could not delete '{path}'. Reason: {e}")
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")

def search_image_in_files(image_name, search_directory):
    """
    Search for an image name within the contents of all files in the given directory and subdirectories,
    excluding the 'assets.json' file.

    :param image_name: The name of the image file to search for (e.g., 'image.jpg').
    :param search_directory: The directory where to start the search.
    :return: A list of file paths where the image name is found within the content.
    """
    matches = []
    
    # Walk through all files and directories within the search_directory
    for root, dirs, files in os.walk(search_directory):
        for file in files:
            # Skip 'assets.json' file
            if file.lower() == 'assets.json':
                continue
            # Skip hidden files that begin with '.' - macOS
            if file.lower().startswith('.'):
                continue
            
            file_path = os.path.join(root, file)
            
            # Skip non-text files (optional)
            if file.lower().endswith(('.txt', '.md', '.html', '.json', '.xml')):  # Add more extensions if needed
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        if image_name.lower() in content.lower():  # Case-insensitive search
                            matches.append(file_path)
                except Exception as e:
                    logging.error(f"Could not read file {file_path}: {e}")
    
    return matches
