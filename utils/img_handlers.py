"""
Handlers to work with images for optimization.
"""

import logging
import os
import subprocess
import shutil

from wand.image import Image

def convert_bytes(num_bytes):
    """Converts bytes to KB, MB."""
    file_size_output = ""

    # Return empty string if num_bytes is None
    # Handles values of no bytes specified (e.g., 0)
    if num_bytes is None:
        return file_size_output

    # Keep track of the sign of num_bytes
    is_negative = num_bytes < 0

    # Make num_bytes an absolute value
    # Handles negative values (e.g., 'Reduced Size: -100400 bytes')
    num_bytes = abs(num_bytes)

    if num_bytes < 1024:
        file_size_output = f"{num_bytes} bytes"
    elif num_bytes < 1024 * 1024:
        file_size_kb = num_bytes / 1024
        file_size_output = f"{file_size_kb:.2f} KB"
    else:
        file_size_mb = num_bytes / (1024 * 1024)
        file_size_output = f"{file_size_mb:.2f} MB"

    # Add back the negative sign if it was originally negative
    if is_negative:
        file_size_output = f"-{file_size_output}"

    return file_size_output

def get_image_stats(image_path):
    """
    Returns a dictionary of image stats including format, size, resolution, and DPI.
    """
    try:
        with Image(filename=image_path) as img:
            # Return the image stats
            return {
                "Format": img.format,
                "Size": os.path.getsize(image_path),
                "Resolution": str(img.size),
                "DPI": 72 if img.resolution[0] == 0 else img.resolution[0]
            }
    except (FileNotFoundError, Exception) as error:  # pylint: disable=broad-except
        return {"error": f"Could not find stats: {error}"}
def print_image_stats(image_path):
    """
    Returns the file size in bytes, KB, or MB, whichever is most appropriate.
    """
    img_stats = get_image_stats(image_path)
    if "error" in img_stats:
        return img_stats["error"]
    
    try:
        # Find the file size in bytes, KB, or MB, whichever is most appropriate
        for key, value in img_stats.items():
            if key == "Size":  # Convert bytes to KB or MB
                img_stats[key] = convert_bytes(value)

        return ", ".join(f"{key}: {value}" for key, value in img_stats.items())
    except (FileNotFoundError, Exception) as error:  # pylint: disable=broad-except
        return f"Could not find stats: {error}"
  
def optimize_image(image_path):
    """
    Optimize the image using specified ImageMagick options.
    Convert all images to JPEG format and remove original non-JPEG images.
    """
    try:
        with Image(filename=image_path) as img:
            # Strip metadata
            img.strip()

            # Set interlace mode to Plane (for progressive JPEGs)
            img.interlace = 'plane'

            # Set quality to 80%
            img.quality = 80

            # Set sampling factor to 4:2:0 (common for JPEG compression)
            img.sampling_factor = (4, 2, 0)

            # Set image resolution to 72 DPI
            # Set image units to PPI (pixels per inch)
            img.resolution = (72, 72)
            img.units = 'pixelsperinch'

            # Resize only if image width > 1400px to new Open edX frontend-app-learning content area dimension.
            if img.width > 1400:
                new_height = int(img.height * (1400 / img.width))
                img.resize(1400, new_height)
                # logging.info(f"Resized {image_path} to width 1400px (maintaining aspect ratio).")
            # else:
                # logging.info(f"Skipping resize for {image_path}, width < 1400px.")

            # Flatten the image to remove transparency and set background color to white
            # For images with transparency (e.g. PNG), the background color will be visible.
            img.background_color = 'white'
            img.alpha_channel = 'background'

            # Convert all images to JPEG format
            output_path = os.path.splitext(image_path)[0] + ".jpg"
            img.format = "jpeg"
            img.save(filename=output_path)

            # Define JPEG DCT method as float for better quality
            # Apply jpeg:dct-method=float using subprocess
            # Wand Limitation: Since wand.image.Image does not support jpeg:dct-method, we use
            # subprocess.run() to call ImageMagick's convert command.
            # Check if 'magick' command is available, otherwise use 'convert'.
            # https://imagemagick.org/script/porting.php - See Command Changes section to use 'magick' command.
            convert_command = "magick" if shutil.which("magick") else "convert"
            subprocess.run([
                convert_command, output_path,
                "-define", "jpeg:dct-method=float",
                output_path
            ], check=True)

            logging.info(f"Optimized and converted to ({print_image_stats(output_path)}): {output_path}")

            # Remove the original file if it was not a JPEG
            if not image_path.lower().endswith(('.jpg', '.jpeg')):
                os.remove(image_path)
                logging.info(f"Removed original file: {image_path}")
    except Exception as error:  # pylint: disable=broad-except
        logging.error(f"Error optimizing image: {error}")
