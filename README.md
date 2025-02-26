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
The application will provide input options to execute partial or complete course optimization. Make sure to run this on your production server that uses `tutor` configuration as the *export/import* functionality uses this command to perform these operations.
```
Select the command to run:
0. Quit application.
1. Export Open edX courses and backup to S3.
2. Optimize images for exported tar gzip Open edX courses.
3. Import optimized Open edX courses back to the platform.
4. (Run steps 1 - 3) Export, optimize images, and import back to the platform.
Enter the number of the command to run:
``` 

## Add course_ids to run
Update the `process-course-ids.txt` file to include courses from this MySQL command. Course Overviews may include course that were previously deleted from the MongoDB store.

Only courses in this txt file will be run for exporting, optimizing, and importing steps.
```
select distinct id from openedx.course_overviews_courseoverview order by id asc;
```

## Configure Boto3 S3 Configuration
Need to set up the following `settings.py` configuration to connect to an existing S3 bucket. This will be used on options 1 and 2. These key/secret are generated and tied to an existing IAM user account.
```
AWS_ACCESS_KEY_ID = 'SET_ME_PLEASE'
AWS_SECRET_ACCESS_KEY = 'SET_ME_PLEASE'
AWS_S3_USE_SSL = True
S3_BUCKET_NAME = 'SET_ME_PLEASE'
S3_REGION_NAME = 'SET_ME_PLEASE'
```

## Option 1: Export Open edX courses and backup to S3.

Creates Open edX exported course TAR GZIP (tar.gz) files with specific naming convention per course using the built in `tutor` call to the CMS `./manage.py cms export` Django management command. Make sure to perform the rename of tar.gz files in the `courses-sourced` directory prior to running the script. Copy multiple exported course tar.gz files to the `courses-sourced` directory then run the script using this command. 

**This is handled automatically for you when you run `Option 1: Export Open edX courses and backup to S3.` option.**

Ensure that you include the `course_id` Open edX naming convention in the tar.gz file names to ensure that they are named uniquely. This helps the script keep track of log, modification to course content, and final optimized tar.gz file output on a per course basis.

Here are some examples following the (Organization+CourseNumber+CourseRun) format.
- ./courses-sourced
  - course.edX+DemoX+Demo_Course.tar.gz
  - course.Org+CourseNumber+CourseRun.tar.gz

## Option 2: Optimize images for exported tar gzip Open edX courses.

> **CAUTION**
> Make sure that there are TAR GZIP (tar.gz) Open edX course files in the ./courses-sourced directory before running this step.
>
> Even though `Option 1: Export Open edX courses and backup to S3` will backup the original exported copy, this step requires that there is a local copy before running.

Imagick will perform the following convertion for all `/static` (JPEG, PNG) content.

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

## Option 3: Import optimized Open edX courses back to the platform.

> **CAUTION**
> Make sure that there are optimized TAR GZIP (tar.gz) Open edX course files in the ./courses-optimized directory before running this step. This is ideal because otherwise you might be importing a course that has no images optimized.
>
> Even though `Option 2: Optimize images for exported tar gzip Open edX courses` will backup the optimized course copy, this step requires that there is a local copy before running.

This will use the Open edX TAR GZIP (tar.gz) course files located in the `courses-optimized` directory that have already gone through `Step 2: Optimize images for exported tar gzip Open edX courses.`. This option executes the built in `tutor` call to the CMS `./manage.py cms import` Django management command and reload the updated course onto the platform.

Here are some examples following the (Organization+CourseNumber+CourseRun) format. The courses should have `-optimized.tar.gz` extension after having run through the Imagick image optimization step.
- ./courses-optimized
  - course.edX+DemoX+Demo_Course-optimized.tar.gz
  - course.Org+CourseNumber+CourseRun-optimized.tar.gz

## Option 4: (Run steps 1 - 3) Export, optimize images, and import back to the platform.
TBD

## Execute Script To Optimized Course Images
```
# Run the script
python optimize-course-images.py
```

# Directories
The following folders are used while the application is running.
- **/logs:** output each course tracking information for the script.
- **/courses-optimized:** final optimized tar.gz files with `/static` files in JPEG compressed format that can be used when importing into an Open edX platform instance. Files will have `-optimized.tar.gz` at the end (i.e. `course.Org+CourseNumber+CourseRun-optimized.tar.gz`).
- **/courses-sourced:** copy courses that need to be optimized here and make sure to name them according to name each tar.gz file according to the Open edX `course_id` naming convention (i.e. `course.Org+CourseNumber+CourseRun.tar.gz`).
- **/tmp:** temporary output for an extracted course tar.gz that the script is modifying. Contents will be removed after script completes.

Here are the support Python packages that the main optimize-course-images.py uses.
- **/utils:** helper methods to handle files, images, json, s3, and tar content for script.
