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
sudo apt-get install imagemagick
```

## Mac (Brew Installer)
```
brew install imagemagick
```

# Installation
Make sure to install the Python package and its prerequisites before beginning this step because of the Imagick dependency. 

```
# Install Python package and requirements. This package includes a Django management command `delete_course_assets` that will delete assets from the contentstore.
pip install -e .
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
- Keep transparent areas as white instead of black
  - Sets the background color to white, which will be used to fill in transparent areas. | [-background white](https://imagemagick.org/script/command-line-options.php#background)
  - Set any fully-transparent pixel to the background color, while leaving it fully-transparent. This can make some image file formats, such as PNG, smaller as the RGB values of transparent pixels are more uniform, and thus can compress better. | [-alpha background](https://imagemagick.org/script/command-line-options.php#alpha)

### Verifying log output and Excel image optimization tracking.
The application keeps track of it's image optimization process to show before and after image optimizations for JPEG and PNG images. Logs files are use to show details of the optimized sizes for outputted JPEG compressed images. 

An Excel `image_optimization_stats.{YYYYMMDD}.{time}.xlsx` file is created to show before and after image sizes on a details worksheet and a summary worksheet showing overall size reduction per course. We output the `Before Size` and `After Size` columns on the details worksheet in `KB, MB` sizes. To help validate that what the application indicates for image reduction please follow these steps.

#### Create two new columns removing the `KB, MB` strings and convert all values to MB size.
Insert a new column after `Before Resolution` titled `Before Size (MB) Without MB String` with this formula. Here `F2` represents the `Before Resolution` column.
```
=IF(RIGHT(F2,2)="KB", LEFT(F2,LEN(F2)-3)/1024, IF(RIGHT(F2,2)="MB", LEFT(F2,LEN(F2)-3)/1, IF(RIGHT(F2,2)="GB", LEFT(F2,LEN(F2)-3)*1024, 0)))
```

Insert a new column after `After Resolution` titled `After Size (MB) Without MB String`. Here `L2` represents the `After Resolution` column.
```
=IF(RIGHT(L2,2)="KB", LEFT(L2,LEN(L2)-3)/1024, IF(RIGHT(L2,2)="MB", LEFT(L2,LEN(L2)-3)/1, IF(RIGHT(L2,2)="GB", LEFT(L2,LEN(L2)-3)*1024, 0)))
```

#### Validate these MB Excel columns with what's in the courses uploade to S3 as original and -optimized format.
Extract the *.tar.gz files and open each `course/static` directory in a terminal shell. Execute the commands below for original and -optimized courses to see what the total size is and compare this against the two additional columns above.
```
# Before size on disk - check size of images (PNG, JPEG) in the current directory
du -ch ./*.png ./*.jpg | grep total
```

```
# After size on disk - check size of images (JPEG) in the current directory
du -ch ./*.jpg | grep total
```

#### Validate the image resolution changes between the original and -optimized format.
Use the following command to see all JPEG and PNG resolution and sizes in the current directory.
```
**# Before Image Optimization** - Identify the image resolutions and sizes in the current directory for both JPEG and PNG images.
identify *.jpg *.png

Dog-and-Cat.jpg JPEG 640x400 640x400+0+0 8-bit sRGB 34834B 0.000u 0:00.002
L9_buckets.jpg JPEG 670x330 670x330+0+0 8-bit sRGB 33877B 0.000u 0:00.000
ProgressPage.jpg JPEG 1400x540 1400x540+0+0 8-bit sRGB 33124B 0.000u 0:00.000
...
teacher_to_student.png PNG 320x380 320x380+0+0 8-bit sRGB 7801B 0.000u 0:00.000
unavailable.png PNG 1201x395 1201x395+0+0 8-bit sRGB 110580B 0.000u 0:00.000
```

Here is an example for the Iguana (iguana-8084900*) and Butterfly (png-2678397*) changes for the edX Demo course before and after. Notice that the resolution for larger images > 1400 width went down to 1400 width and PNG files were removed.

```
# Before Image Optimization
identify iguana* png-2678397*

iguana-8084900@1280x853.jpg JPEG 1280x853 1280x853+0+0 8-bit sRGB 495826B 0.000u 0:00.000
iguana-8084900@5257x3505.jpg JPEG 5257x3505 5257x3505+0+0 8-bit sRGB 4.28202MiB 0.000u 0:00.000
png-2678397@1280x851.jpg JPEG 1280x851 1280x851+0+0 8-bit sRGB 176769B 0.000u 0:00.000
png-2678397@1280x851.png PNG 1280x851 1280x851+0+0 8-bit sRGB 586769B 0.000u 0:00.000
png-2678397@6016x4000.jpg JPEG 1400x930 1400x930+0+0 8-bit sRGB 176069B 0.000u 0:00.000
png-2678397@6016x4000.png PNG 6016x4000 6016x4000+0+0 8-bit sRGB 9.02263MiB 0.000u 0:00.000

# After Image Optimization
identify iguana* png-2678397*

iguana-8084900@1280x853.jpg JPEG 1280x853 1280x853+0+0 8-bit sRGB 488107B 0.000u 0:00.000
iguana-8084900@5257x3505.jpg JPEG 1400x933 1400x933+0+0 8-bit sRGB 394614B 0.000u 0:00.000
png-2678397@1280x851.jpg JPEG 1280x851 1280x851+0+0 8-bit sRGB 176769B 0.000u 0:00.000
png-2678397@6016x4000.jpg JPEG 1400x930 1400x930+0+0 8-bit sRGB 176069B 0.000u 0:00.000
```

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
Run steps 1 - 3 together. This is to be used as an automated way to handle exporting, image optimization, then importing back into the platform.

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
