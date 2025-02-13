"""
Handlers to work with json files specifically.
"""

import json
import logging
import os
import re

def delete_key_from_json(file_path, key_to_delete):
    """
    Deletes a key-value pair from a JSON file.

    Args:
        file_path (str): The path to the JSON file.
        key_to_delete (str): The key to delete from the JSON data.
    """
    try:
        with open(file_path, 'r') as file:
            data = json.load(file)
    except FileNotFoundError:
        logging.error(f"Error: File not found: {file_path}")
        return
    except json.JSONDecodeError:
        logging.error(f"Error: Invalid JSON format in file: {file_path}")
        return

    if key_to_delete in data:
        del data[key_to_delete]

        with open(file_path, 'w') as file:
            json.dump(data, file, indent=4)
        logging.warning(f"Key '{key_to_delete}' deleted successfully from '{file_path}'.")
    else:
        logging.warning(f"Key '{key_to_delete}' not found in '{file_path}'.")

def find_and_replace_in_json(file_path, search_pattern, replace_with):
    """
    Opens a JSON file, finds and replaces partial values based on a regex pattern, and saves the changes.

    Args:
        file_path (str): The path to the JSON file.
        search_pattern (str): The regular expression pattern to search for.
        replace_with (str): The string to replace the matched patterns with.
    """
    try:
        with open(file_path, 'r') as file:
            data = json.load(file)
    except FileNotFoundError:
        logging.error(f"Error: File not found at path: {file_path}")
        return
    except json.JSONDecodeError:
        logging.error(f"Error: Invalid JSON format in file: {file_path}")
        return

    def replace_recursive(obj):
        if isinstance(obj, dict):
            for key, value in obj.items():
                obj[key] = replace_recursive(value)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                obj[i] = replace_recursive(item)
        elif isinstance(obj, str):
            obj = re.sub(search_pattern, replace_with, obj)
        return obj

    modified_data = replace_recursive(data)

    try:
         with open(file_path, 'w') as file:
            json.dump(modified_data, file, indent=4)
            logging.info(f"Replaced JSON values in {file_path}: '{search_pattern}' → '{replace_with}'")
    except Exception as e:
        logging.error(f"Error writing to file: {e}")

def replace_json_keys(file_path, find_str, replace_str):
    """
    Opens a JSON file and replaces key names that contain a specified string with a new string.
    
    Args:
        file_path (str): The path to the JSON file.
        find_str (str): The substring to find in key names.
        replace_str (str): The substring to replace in key names.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
    except FileNotFoundError:
        logging.error(f"Error: File not found at path: {file_path}")
        return
    except json.JSONDecodeError:
        logging.error(f"Error: Invalid JSON format in file: {file_path}")
        return

    def replace_keys_recursive(obj):
        if isinstance(obj, dict):
            return {k.replace(find_str, replace_str): replace_keys_recursive(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [replace_keys_recursive(item) for item in obj]
        return obj

    modified_data = replace_keys_recursive(data)

    try:
        with open(file_path, 'w', encoding='utf-8') as file:
            json.dump(modified_data, file, indent=4)
        logging.info(f"Replaced JSON keys in {file_path}: '{find_str}' → '{replace_str}'")
    except Exception as e:
        logging.error(f"Error writing to file: {e}")

def find_json_file(root_dir, filename):
    """
    Searches for a JSON file within a directory and its subfolders.

    Args:
        root_dir (str): The root directory to start the search from.
        filename (str): The name of the JSON file to find.

    Returns:
        str: The full path to the JSON file if found, otherwise None.
    """
    for dirpath, dirnames, filenames in os.walk(root_dir):
        for file in filenames:
            if file == filename:
                return os.path.join(dirpath, file)
    return None
