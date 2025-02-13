"""
Handlers to work with images for optimization.
"""

import logging
import os
import subprocess

from wand.image import Image

def get_image_stats(image_path):
    """
    Returns the file size in bytes, KB, or MB, whichever is most appropriate.
    """
    try:
        with Image(filename=image_path) as img:
            file_size_bytes = os.path.getsize(image_path)
            file_size_output = ""

            if file_size_bytes < 1024:
                file_size_output = f"{file_size_bytes} bytes"
            elif file_size_bytes < 1024 * 1024:
                file_size_kb = file_size_bytes / 1024
                file_size_output = f"{file_size_kb:.2f} KB"
            else:
                file_size_mb = file_size_bytes / (1024 * 1024)
                file_size_output = f"{file_size_mb:.2f} MB"
                
            return f"Format: {img.format}, Size: {file_size_output}, Resolution: {img.size}, DPI: {72 if img.resolution[0] == 0 else img.resolution[0]}" # resolution[0]
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

            # Convert all images to JPEG format
            output_path = os.path.splitext(image_path)[0] + ".jpg"
            img.format = "jpeg"
            img.save(filename=output_path)

            # Define JPEG DCT method as float for better quality
            # Apply jpeg:dct-method=float using subprocess
            # Wand Limitation: Since wand.image.Image does not support jpeg:dct-method, we use
            # subprocess.run() to call ImageMagick's convert command.
            subprocess.run([
                "magick", output_path,
                "-define", "jpeg:dct-method=float",
                output_path
            ], check=True)

            logging.info(f"Optimized and converted to ({get_image_stats(output_path)}): {output_path}")

            # Remove the original file if it was not a JPEG
            if not image_path.lower().endswith(('.jpg', '.jpeg')):
                os.remove(image_path)
                logging.info(f"Removed original file: {image_path}")
    except Exception as error:  # pylint: disable=broad-except
        logging.error(f"Error optimizing image: {error}")
