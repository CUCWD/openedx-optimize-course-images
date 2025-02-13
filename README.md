This script will help optimize an exported Open edX course (tar.gz) images files (JPEG, PNG) located within the `/static` directory. It will converting all images to compressed JPEG format and resize image widths greather than the defined Open edX frontend-app-learning content viewing width. Doing so should make the browser page-load time faster, making the platform feel more responsive because image downloads will take less time to download to the users machine. This will reduce the MongoDB file storage costs as these optimized static file images are stored in that database and the overall file size will be reduced.

This script will also find and remove unused images from the course `/static` directory and update `./policies/assets.json` by removing this unused image. 

Multiple courses can be run if separate course tar.gz files exist within the `sources-courses` directory.

# Prerequisites
Install Imagick before using the Wand python package using the Ubuntu/Debian or Mac (Brew Installer) commands below. Here are some additional reference links to help understand Imagick.
- https://imagemagick.org/script/command-line-tools.php 
- https://www.geeksforgeeks.org/python-wand-an-overview/
- https://pypi.org/project/Wand/

## Ubuntu/Debian
```
sudo apt-get install libmagickwand-dev
```

## Mac (Brew Installer)
```
brew install imagemagick
```

# Installation
Make sure to install the prerequisites before beginning this step because of the Imagick dependency. 

```
# Install packages in bulk according to the configuration file.
pip install -r requirements.txt
```

# Running
Make sure to perform the rename of tar.gz files in the `source-courses` directory prior to running the script. Copy multiple exported course tar.gz files to the `source-courses` directory then run the script using this command. 

## Rename Exported Course TAR GZIP (tag.gz) Files With Specific Naming Convention
Ensure that you include the `course_id` Open edX naming convention in the tar.gz file names to ensure that they are named uniquely. This helps the script keep track of log, modification to course content, and final optimized tar.gz file output on a per course basis.

Here are some examples following the (Organization+CourseNumber+CourseRun) format.
- ./source-courses
  - course.edX+DemoX+Demo_Course.tar.gz
  - course.Org+CourseNumber+CourseRun.tar.gz

## Imagick will perform the following convertion for all `/static` (JPEG, PNG) content.
After each Imagick option, there is a link to the command line version for additional information.
- Strip metadata | [--strip](https://imagemagick.org/script/command-line-options.php?#strip)
- Set interlace mode to Plane (for progressive JPEGs) | [-interlace Plane](https://imagemagick.org/script/command-line-options.php?#interlace)
- Set quality to 80% | [--quality 80%](https://imagemagick.org/script/command-line-options.php?#quality)
- Set sampling factor to 4:2:0 (common for JPEG compression) | [-sampling-factor 4:2:0](https://imagemagick.org/script/command-line-options.php?#sampling-factor)
- Set image resolution to 72 DPI | [-density 72](https://imagemagick.org/script/command-line-options.php?#density)
- Set image units to PPI (pixels per inch) | [-units PixelsPerInch](https://imagemagick.org/script/command-line-options.php?#units)
- Resize larger image widths only | [-resize 1400x](https://imagemagick.org/script/command-line-options.php?#resize)
  - *Larger Images (> 1400x width)*
    - Set image width to 1400px to match `frontend-app-learning` content area for future releases of Open edX. There were some images that were coming in at 2280px width which were being scaled down by the browser automatically to fit the content area. Larger images increased the download time for the user making the page-load times increase.
  - *Smaller Images (<= 1400x width)*
    - Need to ensure that drag and drop images stay at 675px width to ensure the target zones continue to function properly.
    - The script does not upscale these images to 1400px width. This is to ensure that the images like drag and drop are preserved to avoid issues with target zones moving.
- Convert all images to JPEG format | [-format jpeg](https://imagemagick.org/script/command-line-options.php?#format)
- Define JPEG DCT method as float for better quality | [-define jpeg:dct-method=float](https://imagemagick.org/script/command-line-options.php?#define)

## Execute Script To Optimized Course Images
```
# Run the script
python optimize-course-images.py
```

# Directories
The following folders are used while the application is running.
- **/logs:** output each course tracking information for the script.
- **/optimized-courses:** final optimized tar.gz files with `/static` files in JPEG compressed format that can be used when importing into an Open edX platform instance. Files will have `-optimized.tar.gz` at the end (i.e. `course.Org+CourseNumber+CourseRun-optimized.tar.gz`).
- **/source-courses:** copy courses that need to be optimized here and make sure to name them according to name each tar.gz file according to the Open edX `course_id` naming convention (i.e. `course.Org+CourseNumber+CourseRun.tar.gz`).
- **/tmp:** temporary output for an extracted course tar.gz that the script is modifying. Contents will be removed after script completes.

Here are the support Python packages that the main optimize-course-images.py uses.
- **/utils:** helper methods to handle files, images, json, and tar content for script.
